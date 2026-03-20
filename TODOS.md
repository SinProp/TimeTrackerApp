# TODOS

## Holiday Calendar Exclusion

**What:** Add a holiday list (hardcoded or DB-stored) to exclude from workday count in quarterly report utilization.
**Why:** Federal/company holidays inflate possible hours by ~2-3% per quarter, making utilization look slightly lower than reality.
**Pros:** More accurate bonus calculations.
**Cons:** Requires annual maintenance of the holiday list.
**Context:** The 6.5h/day × workdays baseline is already an approximation. Holidays would improve precision but introduce a maintenance burden. Could start with a hardcoded list of ~10 federal holidays and iterate.
**Depends on:** Possible hours feature (quarterly report).
**Added:** 2026-03-20

## Per-Employee Hire/Termination Date Awareness

**What:** Use employee `created_at` (hire) and `deleted_date` (termination) to narrow possible hours window per employee.
**Why:** New hires mid-quarter get credited with possible hours for days they weren't employed, making them look underperforming.
**Pros:** Fair utilization for new/departing employees in their first/last quarter.
**Cons:** Adds complexity to the enrichment logic. Requires joining User date fields.
**Context:** The `users` table already has `created_at` and `deleted_date` fields — the data exists. Narrow each employee's possible hours to `max(start_date, hire_date)` through `min(end_date, termination_date or today)`.
**Depends on:** Possible hours feature (quarterly report).
**Added:** 2026-03-20
