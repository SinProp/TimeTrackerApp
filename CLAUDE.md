# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Island Time** — Construction labor tracking system for measuring actual vs estimated labor hours.

- **Stack**: Python 3.9 + Flask + MySQL + APScheduler
- **Integration**: Microsoft Dataverse (Dynamics 365) for job synchronization
- **Production**: AWS EC2 Ubuntu instance (10–12 daily users)

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (http://localhost:5000)
python server.py

# Production SSH access
ssh island-time  # Configured in ~/.ssh/config

# Database backup (production)
mysqldump -u root -p man_hours > ~/backups/$(date +%Y-%m-%d_%H%M)_<context>.sql
```

Required environment variables (see `.env.example`):

```bash
DATAVERSE_BASE_URL, DATAVERSE_TENANT_ID, DATAVERSE_CLIENT_ID, DATAVERSE_CLIENT_SECRET
```

## Architecture

### MVC Structure

```
flask_app/
├── controllers/   # Route handlers (users, jobs, shifts, version)
├── models/        # Database queries + validation (user, job, shift)
├── dataverse/     # Dataverse CRM integration (client.py, service.py)
├── config/        # Config + MySQLConnection abstraction
├── templates/     # Jinja2 HTML templates
└── utils/         # APScheduler tasks
server.py          # Entry point with scheduler setup
```

### Three Core Models

| Model     | Purpose                                         | Key Pattern                                      |
| --------- | ----------------------------------------------- | ------------------------------------------------ |
| **Job**   | Work orders (synced from Dataverse at 6 AM EST) | `get_approved_jobs_from_dataverse()`             |
| **Shift** | Clock in/out records (user → job → timestamps)  | Elapsed time: `TIMEDIFF(updated_at, created_at)` |
| **User**  | Employee accounts with soft-delete              | `WHERE deleted_date IS NULL` required            |

### Data Flow

Dataverse (approved IM jobs) → APScheduler (6 AM sync) → MySQL `man_hours` → Flask controllers → Jinja2 templates

## Critical Patterns

### 1. Soft Deletes (Users)

Users are never hard-deleted. **Always** include `WHERE deleted_date IS NULL`:

```python
query = "SELECT * FROM users WHERE deleted_date IS NULL;"
# Soft delete: UPDATE users SET deleted_date = NOW() WHERE id = %(id)s;
```

### 2. MySQLConnection Pattern (Legacy)

Connection closes after each query. Use `%(key)s` parameterized syntax:

```python
query = "SELECT * FROM jobs WHERE id = %(id)s;"
connectToMySQL('man_hours').query_db(query, {'id': 123})
```

**Known issues**: No connection pooling, no transactions, N+1 queries in loops.

### 3. Session Protection

Every protected route must check session:

```python
if 'user_id' not in session:
    return redirect('/logout')
```

### 4. Admin Role Check

Only `department == 'ADMINISTRATIVE'` users can edit other users' jobs/shifts.

## Dataverse Integration

**Approved jobs filter**: `imi_submittalstatus eq 826130004 and statecode eq 0`

**Field mapping** (Dataverse → MySQL):

- `imi_imnumber` → `im_number` (work order ID)
- `imi_gc` → `general_contractor`
- `imi_scopesummary` → `job_scope` (truncated 255 chars; defaults to "See Work Order")
- `imi_jobid` → `dataverse_id`

**Manual sync**: POST `/api/sync-jobs` (requires ADMINISTRATIVE role)

## Key Files

| File                                  | Responsibility                                 |
| ------------------------------------- | ---------------------------------------------- |
| `flask_app/dataverse/client.py`       | OAuth2 (MSAL) + REST client with token caching |
| `flask_app/dataverse/service.py`      | `get_approved_jobs()`, Dataverse API wrapper   |
| `flask_app/utils/scheduler_tasks.py`  | Daily 6 AM EST sync logic                      |
| `flask_app/config/mysqlconnection.py` | DB abstraction with query logging              |

## Gotchas

1. **Shift timestamps**: `created_at` = punch in, `updated_at` = punch out (confusing naming)
2. **Hardcoded timezone**: EST in `server.py` via `pytz.timezone('US/Eastern')`
3. **Date format**: `"%m/%d/%Y %I:%M %p"` (12-hour AM/PM) for all UI displays
4. **No ORM transactions**: Each query auto-commits independently

## Deprecated Code (Safe to Delete)

- `flask_app/controllers/sheet_id.py`
- `flask_app/controllers/getcolumnids.py`
- `flask_app/controllers/ss_autoadd_jobs.py`
- `flask_app/controllers/webhooks_controller.py`
- `debug_smartsheet_statuses.py`
