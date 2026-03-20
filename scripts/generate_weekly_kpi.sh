#!/usr/bin/env zsh

set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "Missing prerequisite: gh" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Missing prerequisite: python3" >&2
  exit 1
fi

python3 - "$@" <<'PY'
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo


OUTPUT_FILE = os.path.expanduser(sys.argv[2]) if len(sys.argv) > 2 else None
TIMEZONE = ZoneInfo(os.environ.get("TZ") or "America/New_York")
REPOS = [
    ("Island Time", ["Island-Time", "TimeTrackerApp"]),
    ("Island Estimator", ["Island-Estimator", "island-estimator"]),
    ("Island Platform", ["Island-Platform"]),
    ("Value Chain Manifest", ["Value-Chain-Manifest"]),
    ("Manifest App", ["Manifest-App", "Manifest"]),
]
HEATMAP_SCALE = ".:-=+*#%@"


def ascii_clean(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.replace("\n", " ").split())


def short_text(value: str, limit: int) -> str:
    cleaned = ascii_clean(value)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def gh_command(args):
    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "GitHub CLI command failed")
    return result.stdout


def detect_default_owner() -> str:
    fallback = "IslandMillwork"
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return fallback
    url = result.stdout.strip()
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/[^/]+(?:\.git)?$", url)
    if not match:
        return fallback
    return match.group("owner") or fallback


def parse_json_stream(raw_text: str):
    text = raw_text.strip()
    if not text:
        return []
    decoder = json.JSONDecoder()
    values = []
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        value, next_index = decoder.raw_decode(text, index)
        values.append(value)
        index = next_index
    return values


def fetch_commits(owner: str, repo_slug: str, since_iso: str, until_iso: str):
    endpoint = (
        f"repos/{owner}/{repo_slug}/commits"
        f"?since={quote(since_iso, safe='')}"
        f"&until={quote(until_iso, safe='')}"
        f"&per_page=100"
    )
    raw = gh_command(["gh", "api", "--paginate", endpoint])
    pages = parse_json_stream(raw)
    commits = []
    for page in pages:
        if isinstance(page, list):
            commits.extend(page)
    return commits


def fetch_merged_prs(owner: str, repo_slug: str, start_date: str, end_date: str):
    query = f"merged:{start_date}..{end_date}"
    raw = gh_command(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            f"{owner}/{repo_slug}",
            "--state",
            "merged",
            "--search",
            query,
            "--limit",
            "100",
            "--json",
            "number,title,mergedAt,author",
        ]
    )
    return json.loads(raw)


def classify_commit(message: str) -> str:
    subject = ascii_clean(message).lower()
    prefixes = [
        ("feat", ("feat", "feature", "add", "create", "implement")),
        ("fix", ("fix", "bug", "patch", "repair", "resolve")),
        ("refactor", ("refactor", "cleanup", "simplify", "rework")),
        ("docs", ("docs", "doc", "readme")),
        ("test", ("test", "spec", "assert")),
        ("chore", ("chore", "ci", "build", "deps", "bump", "workflow")),
        ("data", ("schema", "sql", "db", "migration", "migrate", "seed")),
        ("perf", ("perf", "optimize", "speed", "cache")),
    ]
    for label, options in prefixes:
        if subject.startswith(tuple(f"{option}:" for option in options)) or subject.startswith(options):
            return label
    return "other"


def format_bar(count: int, max_count: int, width: int = 28) -> str:
    if max_count <= 0:
        return ""
    filled = max(1, round((count / max_count) * width)) if count > 0 else 0
    return "#" * filled


def heat_char(count: int, max_count: int) -> str:
    if count <= 0 or max_count <= 0:
        return "."
    index = round((count / max_count) * (len(HEATMAP_SCALE) - 1))
    index = max(1, min(index, len(HEATMAP_SCALE) - 1))
    return HEATMAP_SCALE[index]


def boxed_header(lines):
    inner_width = max(len(line) for line in lines) + 2
    border = "+" + ("-" * inner_width) + "+"
    output = [border]
    for line in lines:
        output.append("| " + line.ljust(inner_width - 2) + " |")
    output.append(border)
    return output


today = datetime.now(TIMEZONE).date()
this_week_monday = today - timedelta(days=today.weekday())
last_week_monday = this_week_monday - timedelta(days=7)
last_week_friday = last_week_monday + timedelta(days=4)
range_start = datetime.combine(last_week_monday, time(0, 0, 0), TIMEZONE)
range_end = datetime.combine(last_week_friday, time(23, 59, 59), TIMEZONE)
range_start_iso = range_start.isoformat()
range_end_iso = range_end.isoformat()
range_start_date = last_week_monday.isoformat()
range_end_date = last_week_friday.isoformat()
weekday_dates = [last_week_monday + timedelta(days=offset) for offset in range(5)]
OWNER = sys.argv[1] if len(sys.argv) > 1 else detect_default_owner()


repo_reports = []
missing_repos = []

for repo_name, candidate_slugs in REPOS:
    report = {
        "name": repo_name,
        "slug": None,
        "candidates": candidate_slugs,
        "error": None,
        "commits": [],
        "prs": [],
        "count_by_day": defaultdict(int),
        "type_counts": Counter(),
    }
    last_error = None
    for repo_slug in candidate_slugs:
        try:
            commits = fetch_commits(OWNER, repo_slug, range_start_iso, range_end_iso)
            merged_prs = fetch_merged_prs(OWNER, repo_slug, range_start_date, range_end_date)
            count_by_day = defaultdict(int)
            type_counts = Counter()
            commit_items = []
            pr_items = []
            for commit in commits:
                committed_at = commit.get("commit", {}).get("committer", {}).get("date")
                if not committed_at:
                    continue
                commit_dt = datetime.fromisoformat(committed_at.replace("Z", "+00:00")).astimezone(TIMEZONE)
                subject = commit.get("commit", {}).get("message", "").splitlines()[0]
                commit_type = classify_commit(subject)
                item = {
                    "date": commit_dt.date().isoformat(),
                    "datetime": commit_dt,
                    "message": ascii_clean(subject),
                    "type": commit_type,
                }
                commit_items.append(item)
                count_by_day[commit_dt.date().isoformat()] += 1
                type_counts[commit_type] += 1

            for pr in merged_prs:
                merged_at = pr.get("mergedAt")
                pr_dt = None
                if merged_at:
                    pr_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00")).astimezone(TIMEZONE)
                author = (pr.get("author") or {}).get("login") or "unknown"
                pr_items.append(
                    {
                        "number": pr.get("number"),
                        "title": ascii_clean(pr.get("title", "")),
                        "merged_date": pr_dt.date().isoformat() if pr_dt else "unknown",
                        "author": ascii_clean(author),
                    }
                )

            report["slug"] = repo_slug
            report["commits"] = commit_items
            report["prs"] = pr_items
            report["count_by_day"] = count_by_day
            report["type_counts"] = type_counts
            last_error = None
            break
        except RuntimeError as error:
            last_error = ascii_clean(str(error))

    if last_error and not report["slug"]:
        report["error"] = last_error
        missing_repos.append((repo_name, "/".join(candidate_slugs), report["error"]))
    report["commits"].sort(key=lambda item: item["datetime"])
    report["prs"].sort(key=lambda item: (item["merged_date"], item["number"]))
    repo_reports.append(report)


total_commits = sum(len(report["commits"]) for report in repo_reports)
total_prs = sum(len(report["prs"]) for report in repo_reports)
accessible_reports = [report for report in repo_reports if not report["error"]]
active_reports = [report for report in accessible_reports if report["commits"]]
max_repo_commits = max((len(report["commits"]) for report in accessible_reports), default=0)
max_day_commits = max(
    (report["count_by_day"].get(day.isoformat(), 0) for report in accessible_reports for day in weekday_dates),
    default=0,
)
all_type_counts = Counter()
for report in repo_reports:
    all_type_counts.update(report["type_counts"])

day_totals = []
for day in weekday_dates:
    count = sum(report["count_by_day"].get(day.isoformat(), 0) for report in accessible_reports)
    day_totals.append((day, count))

busiest_repo = max(accessible_reports, key=lambda report: len(report["commits"]), default=None)
busiest_day = max(day_totals, key=lambda item: item[1], default=None)
zero_activity = [report["name"] for report in accessible_reports if not report["commits"]]
top_type = all_type_counts.most_common(1)[0] if all_type_counts else ("none", 0)
avg_commits_per_active_repo = (total_commits / len(active_reports)) if active_reports else 0.0

header_lines = boxed_header(
    [
        "ISLAND MILLWORK WEEKLY KPI REPORT",
        f"Window: {range_start_date} 00:00 through {range_end_date} 23:59 ({TIMEZONE.key})",
        f"Owner: {OWNER}",
    ]
)

lines = []
lines.extend(header_lines)
lines.append("")
lines.append("Scope")
lines.append("-----")
lines.append(
    f"Repos: {len(REPOS)} total | Accessible: {len(accessible_reports)} | Missing/Inaccessible: {len(missing_repos)}"
)
resolved_overrides = [
    f"{report['name']}={report['slug']}"
    for report in accessible_reports
    if report["slug"] and report["slug"] != report["candidates"][0]
]
if resolved_overrides:
    lines.append("Resolved slugs: " + ", ".join(resolved_overrides))
lines.append("")
lines.append("Commit Counts")
lines.append("-------------")
for report in repo_reports:
    if report["error"]:
        lines.append(f"{report['name']:<22} missing  {short_text(report['error'], 72)}")
        continue
    count = len(report["commits"])
    share = f"{(count / total_commits * 100):5.1f}%" if total_commits else "  0.0%"
    lines.append(
        f"{report['name']:<22} {count:>3}  {share}  {format_bar(count, max_repo_commits)}"
    )
lines.append(f"{'TOTAL':<22} {total_commits:>3}  {'100.0%' if total_commits else '0.0%':>6}")
lines.append("")
lines.append("Commit Details")
lines.append("--------------")
for report in repo_reports:
    lines.append(f"[{report['name']}]")
    if report["error"]:
        lines.append(f"  unavailable: {short_text(report['error'], 84)}")
    elif not report["commits"]:
        lines.append("  no commits in range")
    else:
        lines.append("  Date        Type      Message")
        for commit in report["commits"]:
            lines.append(
                f"  {commit['date']}  {commit['type']:<8}  {short_text(commit['message'], 64)}"
            )
    lines.append("")

lines.append("Merged PRs")
lines.append("----------")
for report in repo_reports:
    lines.append(f"[{report['name']}]")
    if report["error"]:
        lines.append(f"  unavailable: {short_text(report['error'], 84)}")
    elif not report["prs"]:
        lines.append("  no merged PRs in range")
    else:
        for pr in report["prs"]:
            lines.append(
                f"  #{pr['number']:<5} {pr['merged_date']}  {short_text(pr['title'], 52):<52}  by {pr['author']}"
            )
    lines.append("")

lines.append("Mon-Fri Activity Heatmap")
lines.append("-----------------------")
lines.append("Repo                    Mon Tue Wed Thu Fri | Total")
for report in repo_reports:
    if report["error"]:
        lines.append(f"{report['name']:<22}  n/a n/a n/a n/a n/a |  n/a")
        continue
    chars = []
    total = 0
    for day in weekday_dates:
        count = report["count_by_day"].get(day.isoformat(), 0)
        total += count
        chars.append(heat_char(count, max_day_commits))
    lines.append(f"{report['name']:<22}  {'   '.join(chars)} | {total:>4}")
lines.append(
    "All Repos                "
    + "   ".join(heat_char(count, max_day_commits) for _, count in day_totals)
    + f" | {total_commits:>4}"
)
lines.append("Legend: . none, : low, higher symbols mean more commits relative to the busiest day.")
lines.append("")

lines.append("KPI Highlights")
lines.append("--------------")
lines.append(f"Total commits: {total_commits}")
lines.append(f"Total merged PRs: {total_prs}")
if busiest_repo:
    share = (len(busiest_repo["commits"]) / total_commits * 100) if total_commits else 0.0
    lines.append(f"Busiest repo: {busiest_repo['name']} ({len(busiest_repo['commits'])} commits, {share:.1f}% of total)")
else:
    lines.append("Busiest repo: none")
if busiest_day:
    if busiest_day[1] > 0:
        lines.append(f"Busiest day: {busiest_day[0]:%a %Y-%m-%d} ({busiest_day[1]} commits)")
    else:
        lines.append("Busiest day: none")
else:
    lines.append("Busiest day: none")
lines.append(f"Most common commit type: {top_type[0]} ({top_type[1]})")
lines.append(f"Average commits per active repo: {avg_commits_per_active_repo:.2f}")
lines.append(
    "Zero-activity repos: " + (", ".join(zero_activity) if zero_activity else "none")
)
if missing_repos:
    lines.append(
        "Missing/inaccessible repos: "
        + ", ".join(f"{name} ({slug})" for name, slug, _ in missing_repos)
    )
else:
    lines.append("Missing/inaccessible repos: none")

report_text = "\n".join(lines).rstrip() + "\n"

if OUTPUT_FILE:
    out_dir = os.path.dirname(OUTPUT_FILE)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="ascii", errors="ignore") as handle:
        handle.write(report_text)

sys.stdout.write(report_text)
PY
