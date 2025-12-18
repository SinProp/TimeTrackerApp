from flask_app import app
from flask import jsonify
import subprocess
import os
from pathlib import Path


def _run_git_command(args, cwd):
    """Run a git command and return stripped stdout or None on failure."""
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        # Intentionally swallow errors; caller will handle missing data
        pass
    return None

@app.route('/version')
def version():
    """
    Returns git version information for the running application.
    Useful for tracking what version is deployed in production.
    """
    repo_root = Path(__file__).resolve().parents[2]

    # Start with environment fallbacks so Docker/production can inject build metadata
    env_version = os.getenv('APP_VERSION') or os.getenv('GIT_COMMIT')
    env_branch = os.getenv('GIT_BRANCH')
    env_date = os.getenv('GIT_COMMIT_DATE')
    env_message = os.getenv('GIT_COMMIT_MESSAGE')

    git_hash = env_version or _run_git_command(['git', 'rev-parse', '--short', 'HEAD'], repo_root)
    git_branch = env_branch or _run_git_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], repo_root)
    git_date = env_date or _run_git_command(['git', 'log', '-1', '--format=%cd', '--date=iso'], repo_root)
    git_message = env_message or _run_git_command(['git', 'log', '-1', '--format=%s'], repo_root)
    full_hash = _run_git_command(['git', 'rev-parse', 'HEAD'], repo_root)

    # Provide safe defaults so the endpoint never 500s
    response = {
        'version': git_hash or 'unknown',
        'branch': git_branch or 'unknown',
        'commit_date': git_date or 'unknown',
        'commit_message': git_message or 'Version unavailable',
        'full_hash': full_hash or git_hash or 'unknown',
        'source': 'env' if env_version else 'git' if git_hash else 'fallback'
    }

    return jsonify(response)
