# AI Coding Agent Instructions for Island Time

**Project**: Time Tracker Application - Labor tracking system for construction/maintenance work  
**Stack**: Python Flask + MySQL + APScheduler  
**Current Status**: Smartsheet → Dataverse migration in progress

## Architecture Overview

Island Time is an MVC Flask application that tracks actual labor vs. estimated labor. Three core models:

- **Jobs**: Work orders (imported from Dataverse, synced daily at 6 AM EST via APScheduler)
- **Shifts**: Clock in/out records linking users to jobs with timestamps
- **Users**: Employee accounts with bcrypt-hashed passwords, soft-delete support

**Data Flow**: Dataverse (approved jobs) → MySQL (`man_hours` DB) → Flask controllers → Jinja2 templates

## Critical Architecture Decisions

1. **Soft Deletes Only**: Users use `deleted_date` column, never hard-deleted. Pattern: `WHERE deleted_date IS NULL`
2. **MVC Strict Separation**: Models only do DB/auth logic; controllers route; templates render
3. **Scheduled Sync Model**: Jobs sync automatically daily; manual sync via `/api/process-approved-jobs` endpoint
4. **Legacy MySQLConnection Pattern**: Uses pooled cursors with `mogrify()` for safe parameterization; closes connection after each query (not ideal but established pattern)

## Key Files & Responsibilities

| File | Purpose | Critical Notes |
|------|---------|-----------------|
| `server.py` | Flask app entry + APScheduler setup | Runs daily sync; timezone is EST |
| `flask_app/models/job.py` | Job logic + Dataverse client init | `get_approved_jobs_from_dataverse()` replaces old Smartsheet method |
| `flask_app/models/shift.py` | Shift CRUD (clock in/out) | JOIN query complexity to get user + job info |
| `flask_app/models/user.py` | User CRUD + validation + login | EMAIL_REGEX pattern for validation |
| `flask_app/config/mysqlconnection.py` | DB abstraction layer | Connection closes after query; autocommit enabled |
| `flask_app/dataverse/service.py` | Dataverse API wrapper | Token caching; filters for `imi_submittalstatus eq 826130004` (Approved) |
| `flask_app/utils/scheduler_tasks.py` | `automated_job_sync()` function | Logs to scheduler logger; runs at 6 AM EST |

## Dataverse Migration Status

**Current**: Transitioning from Smartsheet to Dataverse.

**What's Done**:
- Dataverse client + service modules created
- Job model updated to call `get_approved_jobs_from_dataverse()`
- Config.py updated with Dataverse env vars
- Scheduler updated to use Dataverse sync

**Field Mapping**:
```
Dataverse imi_jobs table → MySQL jobs table:
├── imi_imnumber       → im_number
├── imi_gc             → general_contractor
├── imi_scopesummary   → job_scope (truncated to 255 chars)
├── imi_submittalstatus ≡ 826130004 (Approved filter)
└── imi_jobid          → stored for future write-back
```

**Smartsheet Code**: DEPRECATED. Files to delete when Dataverse fully live:
- `flask_app/controllers/sheet_id.py`
- `flask_app/controllers/getcolumnids.py`
- `flask_app/controllers/ss_autoadd_jobs.py`
- `flask_app/controllers/webhooks_controller.py`
- `debug_smartsheet_statuses.py`

## Developer Workflows

### Local Setup
```bash
pip install -r requirements.txt
export DATAVERSE_BASE_URL="https://your-org.crm.dynamics.com"
export DATAVERSE_TENANT_ID="..."
export DATAVERSE_CLIENT_ID="..."
export DATAVERSE_CLIENT_SECRET="..."
python server.py  # Runs on http://localhost:5000 with debug=True
```

### Testing Job Sync Locally
1. Navigate to `/new/job` page
2. Click "Test Auto Sync" button (calls `automated_job_sync()` manually)
3. Check console logs for sync details

### Accessing Production EC2 Server
The production Ubuntu EC2 instance can be accessed via SSH shortcut:
```bash
ssh island-time  # Connects to ubuntu@34.207.34.17 using ~/.ssh/island-time-ec2.pem
```
SSH config location: `~/.ssh/config`

### Database Queries
All queries use parameterized `mogrify()` pattern:
```python
query = "SELECT * FROM users WHERE email = %(email)s;"
result = connectToMySQL('man_hours').query_db(query, {'email': 'user@example.com'})
```

## Project-Specific Conventions

1. **Date Format**: `"%m/%d/%Y %I:%M %p"` (12-hour with AM/PM) — used across templates
2. **Flash Messages**: Use `flash()` for user feedback in controllers; templates render with `get_flashed_messages()`
3. **Session Check**: Every route checks `if 'user_id' not in session: return redirect('/logout')`
4. **Logging**: `print()` for debug; `scheduler_logger.info()` for scheduled tasks
5. **Database Schema**: Timestamps use MySQL `NOW()` function; soft deletes check `deleted_date IS NULL`

## Common Tasks

### Adding a New Job Field
1. Add column to MySQL `jobs` table
2. Update `Job.__init__()` to assign from `db_data` dict
3. Add to `get_all()` and `get_by_id()` SELECT queries
4. If from Dataverse: map in `flask_app/dataverse/service.py`'s `get_approved_jobs()`
5. Update controller methods to pass in form data

### Modifying Sync Logic
- Approved jobs filter: `imi_submittalstatus eq 826130004` (in `flask_app/dataverse/service.py`)
- Sync runs at `6 AM EST` (in `server.py`, APScheduler CronTrigger)
- Manual endpoints: `/api/process-approved-jobs`, login trigger in `flask_app/controllers/users.py`

### Debugging Failed Queries
Check `flask_app/config/mysqlconnection.py`:
- Logs printed query via `cursor.mogrify()` 
- All exceptions caught and logged
- Connection closes after query (if debugging hanging requests, check query completion)

## External Dependencies

- **MSAL**: Azure authentication for Dataverse API (`from msal import ConfidentialClientApplication`)
- **APScheduler**: Background job scheduling (already in requirements.txt)
- **Dataverse Web API**: Accessed via REST + OAuth2 tokens (see `flask_app/dataverse/client.py`)
- **MySQL**: Version 5.7+ required for `NOW()` function

## Known Limitations

1. **Single DB Connection Pattern**: MySQLConnection closes after each query (not pooled). For high-concurrency apps, consider replacing with SQLAlchemy ORM.
2. **No Transaction Support**: Each query commits immediately; no rollback on multi-step operations.
3. **Hardcoded Timezone**: EST timezone in APScheduler; change in `server.py` if needed.
4. **Shift Timestamps**: `created_at` = punch in, `updated_at` = punch out (confusing naming; consider refactoring).

## Testing Notes

- Dashboard loads all jobs for the day via LEFT JOIN on shifts (can be slow if many jobs exist)
- Manual sync button on `/new/job` page — useful for testing before deploying
- Admin users can edit/delete shifts; regular users can only view their own
