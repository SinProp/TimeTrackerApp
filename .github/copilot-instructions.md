# AI Coding Agent Instructions for Island Time

**Project**: Time Tracker Application — Construction labor tracking system  
**Stack**: Python Flask + MySQL + APScheduler | **Status**: Dataverse migration complete  
**Production**: AWS EC2 Ubuntu instance (10–12 daily users)

## Quick Start

```bash
# Local development
pip install -r requirements.txt
export DATAVERSE_BASE_URL="https://your-org.crm.dynamics.com"
export DATAVERSE_TENANT_ID="..." DATAVERSE_CLIENT_ID="..." DATAVERSE_CLIENT_SECRET="..."
python server.py  # http://localhost:5000 with auto-reload

# Production access
ssh island-time  # Configured in ~/.ssh/config (ubuntu@34.207.34.17)
```

## Architecture: Three Core Models

| Model | Purpose | Key Pattern |
|-------|---------|------------|
| **Job** | Work orders (imported from Dataverse daily at 6 AM EST) | `get_approved_jobs_from_dataverse()` method |
| **Shift** | Clock in/out records linking user → job → timestamps | Actual elapsed time calculated from `created_at` and `updated_at` |
| **User** | Employee accounts with soft-delete support | `deleted_date IS NULL` for active records |

**Data Flow**: Dataverse (approved IM jobs) → APScheduler (6 AM sync) → MySQL `man_hours` → Flask controllers → Jinja2 templates

## Critical Patterns

### 1. **Soft Deletes Only**
Users are never hard-deleted. All queries on users must include `WHERE deleted_date IS NULL`:
```python
query = "SELECT * FROM users WHERE deleted_date IS NULL;"
# Soft delete: UPDATE users SET deleted_date = NOW() WHERE id = %(id)s;
```

### 2. **MySQLConnection Pattern** (Legacy)
Parameterized queries close connection after each call. Always use `%(key)s` syntax:
```python
query = "SELECT * FROM jobs WHERE id = %(id)s;"
connectToMySQL('man_hours').query_db(query, {'id': 123})
```

### 3. **Session Protection**
Every route checks for user in session; redirect to `/logout` if missing:
```python
if 'user_id' not in session:
    return redirect('/logout')
```

### 4. **MVC Strict Separation**
- **Models** (`flask_app/models/`): DB queries + validation logic only
- **Controllers** (`flask_app/controllers/`): Flask routes + request handling
- **Templates** (`flask_app/templates/`): HTML rendering only

## Dataverse Integration Details

**Approved jobs filter**: `imi_submittalstatus eq 826130004 and statecode eq 0`

**Field mapping** (Dataverse → MySQL):
| Dataverse | MySQL | Notes |
|-----------|-------|-------|
| `imi_imnumber` | `im_number` | Work order ID |
| `imi_gc` | `general_contractor` | Contractor name |
| `imi_scopesummary` | `job_scope` | Truncated to 255 chars; defaults to "See Work Order" |
| `imi_jobid` | `dataverse_id` | Stored for future write-back |

**Sync logic** (`flask_app/utils/scheduler_tasks.py`):
- Runs automatically at 6 AM EST (configurable in `server.py`)
- Skips IM numbers already in DB (no duplicates)
- Logs to `scheduler_logger` (not `print`)
- Manual trigger: `/new/job` page has "Test Auto Sync" button

## Key Files & Their Responsibilities

| File | Purpose | Key Methods |
|------|---------|------------|
| `server.py` | Flask app + APScheduler setup | `scheduler.add_job()` with `CronTrigger` |
| `flask_app/models/job.py` | Job CRUD + Dataverse sync | `get_approved_jobs_from_dataverse()`, `getJobWithShifts()` |
| `flask_app/models/user.py` | User auth + validation | `EMAIL_REGEX` for validation; `soft_delete()` |
| `flask_app/models/shift.py` | Shift CRUD (clock in/out) | Complex JOINs to fetch user + job info together |
| `flask_app/dataverse/service.py` | Dataverse API wrapper | `get_approved_jobs()`, `get_all_active_jobs()` |
| `flask_app/dataverse/client.py` | OAuth2 + REST client | Singleton token caching; MSAL authentication |
| `flask_app/config/mysqlconnection.py` | DB abstraction | Query logging via `cursor.mogrify()` |

## Code Conventions

| Convention | Example | Usage |
|-----------|---------|-------|
| **Date Format** | `"%m/%d/%Y %I:%M %p"` | All templates & UI displays (12-hour AM/PM) |
| **Flash Messages** | `flash("Success!", "success")` | User feedback in controllers; rendered in templates |
| **Logging** | `print("debug")` / `scheduler_logger.info("sync")` | Console vs. scheduled tasks |
| **Elapsed Time** | `shift.created_at` → `shift.updated_at` | TIMEDIFF in JOIN queries; confusing naming |
| **Validation** | `Job.validate_job(data)` → returns bool | Flash messages for errors inside validators |

## Common Development Tasks

### Adding a Job Field
1. Add column to `jobs` MySQL table
2. Update `Job.__init__()` dict assignment
3. Add to `SELECT` queries in `get_all()`, `get_one()`
4. If from Dataverse: add to `SELECT_FIELDS` tuple in `service.py` + map in `get_approved_jobs()`
5. Update controller form handling + template

### Fixing Dataverse Sync Issues
1. Check `flask_app/dataverse/client.py` OAuth2 token (MSAL setup)
2. Verify `DATAVERSE_*` env vars match Azure app registration
3. Confirm `SUBMITTAL_STATUS_APPROVED = 826130004` is correct in current org
4. Test manually: navigate to `/new/job` → click "Test Auto Sync" → check console

### Modifying Scheduled Task
- Edit trigger in `server.py`: `CronTrigger(hour=6, minute=0, timezone=eastern)`
- Edit logic in `flask_app/utils/scheduler_tasks.py`: `automated_job_sync()`
- Logs go to `scheduler_logger` (configured with `logging.basicConfig()`)

## Production Database Management

**EC2 Instance**: ubuntu@34.207.34.17 (accessible via `ssh island-time`)

**Database Dump Naming Convention**: Always use descriptive, timestamped names to avoid confusion:
- Format: `YYYY-MM-DD_HHmm_<context>.sql`
- Examples:
  - `2025-12-18_1430_pre-migration.sql` — before schema changes
  - `2025-12-18_1500_backup-before-hotfix.sql` — before emergency patch
  - `2025-12-18_1600_production-snapshot.sql` — regular backup
  - `2025-12-18_after-dataverse-sync.sql` — after job sync testing

**Backup Commands**:
```bash
# Local backup of production DB (run from EC2 terminal)
mysqldump -u root -p man_hours > ~/backups/$(date +%Y-%m-%d_%H%M)_pre-<context>.sql

# Restore from backup
mysql -u root -p man_hours < ~/backups/YYYY-MM-DD_HHmm_<context>.sql

# Verify backup integrity before critical operations
mysql -u root -p man_hours < ~/backups/<filename>.sql --dry-run  # Preview
```

**Backup Storage**: Store dumps in `~/backups/` directory on EC2; use `ls -ltr` to view recent backups by timestamp.

## External Dependencies

- **MSAL** (`from msal import ConfidentialClientApplication`): Azure OAuth2 for Dataverse
- **APScheduler**: Background job scheduling (background mode, not daemon)
- **Flask**: Web framework with Jinja2 templating
- **MySQL**: Version 5.7+ (uses `NOW()` function + `TIMEDIFF()`)

## Known Limitations & Gotchas

1. **Connection per Query**: MySQLConnection closes after each call; no pooling. Causes N+1 queries in loops. Migration to SQLAlchemy ORM recommended for high traffic.
2. **No Transactions**: Each query auto-commits. Multi-step operations cannot rollback.
3. **Shift Timestamp Confusion**: `created_at` = punch in, `updated_at` = punch out. Refactor naming if adding new shift logic.
4. **Hardcoded EST**: Scheduler timezone is hardcoded in `server.py`. Change line `eastern = pytz.timezone('US/Eastern')` if needed.
5. **Admin Role**: Only users with `department == 'ADMINISTRATIVE'` can edit other users' jobs. Check in `edit_job()` controller.

## Deprecated Smartsheet Code (TODO: Delete)
- `flask_app/controllers/sheet_id.py`
- `flask_app/controllers/getcolumnids.py`  
- `flask_app/controllers/ss_autoadd_jobs.py`
- `flask_app/controllers/webhooks_controller.py`
- `debug_smartsheet_statuses.py`

## Testing Notes

- Dashboard loads all jobs for the day via LEFT JOIN on shifts (can be slow if many jobs exist)
- Manual sync button on `/new/job` page — useful for testing before deploying
- Admin users can edit/delete shifts; regular users can only view their own
