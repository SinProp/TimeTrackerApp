# TimeTrackerApp → Dataverse Migration Plan

## Executive Summary

This document outlines the steps to migrate the **TimeTrackerApp** (AWS-deployed Flask labor tracking app) from **Smartsheet** to **Microsoft Dataverse** as the job data source. The app will continue using MySQL for local shift/user data but will sync job information from Dataverse. **This is a complete replacement** — Smartsheet will be fully removed from the stack.

---

## Current Architecture Analysis

### TimeTrackerApp Tech Stack
| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend | Flask (Python) | API & web server |
| Database | MySQL (`man_hours` DB) | Users, jobs, shifts |
| Job Sync | Smartsheet API | Imports "Approved" jobs |
| Scheduler | APScheduler | Daily 6 AM EST sync |
| Hosting | AWS | Production deployment |

### Current Data Models
```
jobs table:
├── id (PK)
├── im_number        ← Smartsheet: IM_NUMBER_COLUMN_ID
├── general_contractor ← Smartsheet: GC_COLUMN_ID
├── job_scope        ← Smartsheet: SCOPE_COLUMN_ID
├── estimated_hours
├── user_id
├── context
├── status
├── created_at / updated_at

shifts table:
├── id (PK)
├── job_id (FK → jobs)
├── user_id (FK → users)
├── created_at (punch in)
├── updated_at (punch out)
├── note

users table:
├── id (PK)
├── first_name, last_name, email
├── department
├── password (bcrypt)
├── deleted_date
```

### Current Smartsheet Integration Points

| File | Function | Purpose |
|------|----------|---------|
| `flask_app/config/config.py` | `SMARTSHEET_API_KEY`, `SHEET_ID`, column IDs | Configuration |
| `flask_app/models/job.py` | `get_approved_jobs_from_smartsheet()` | Fetch approved jobs |
| `flask_app/models/job.py` | `check_im_number_exists()`, `add_new_record()` | Insert new jobs |
| `flask_app/utils/scheduler_tasks.py` | `automated_job_sync()` | Daily sync job |
| `flask_app/controllers/jobs.py` | `/api/process-approved-jobs` | Manual sync endpoint |
| `flask_app/controllers/users.py` | Login sync trigger | Sync on user login |
| `server.py` | APScheduler setup | Scheduled sync |

---

## Migration Steps for Your Agent

### Phase 1: Create Dataverse Client Module

**Create new file: `flask_app/dataverse/client.py`**

```python
"""Dataverse client for TimeTrackerApp - mirrors Island-Platform pattern."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
import os
import requests
from msal import ConfidentialClientApplication


class DataverseClientError(RuntimeError):
    """Raised when Dataverse operations fail."""


class DataverseClient:
    """Thin wrapper around the Dataverse Web API with token caching."""

    def __init__(
        self,
        base_url: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = None,
        *,
        api_version: str = "v9.2",
        timeout_seconds: int = 30,
    ) -> None:
        if not base_url:
            raise DataverseClientError("DATAVERSE_BASE_URL is required")
        if not tenant_id:
            raise DataverseClientError("DATAVERSE_TENANT_ID is required")
        if not client_id:
            raise DataverseClientError("DATAVERSE_CLIENT_ID is required")
        if not client_secret:
            raise DataverseClientError("DATAVERSE_CLIENT_SECRET is required")

        self._resource_url = base_url.rstrip("/")
        self._api_url = f"{self._resource_url}/api/data/{api_version.strip('/')}"
        self._authority = f"https://login.microsoftonline.com/{tenant_id}"
        self._scope = scope or f"{self._resource_url}/.default"
        self._timeout = timeout_seconds

        self._client = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=self._authority,
        )
        self._cached_token: Optional[str] = None
        self._token_expires_at: float = 0

    def _access_token(self) -> str:
        now = time.time()
        if self._cached_token and now < self._token_expires_at - 60:
            return self._cached_token

        token_result = self._client.acquire_token_for_client(scopes=[self._scope])
        if "access_token" not in token_result:
            raise DataverseClientError(
                f"Failed to acquire Dataverse token: {token_result.get('error_description', 'Unknown error')}"
            )

        self._cached_token = token_result["access_token"]
        expires_in = token_result.get("expires_in", 0)
        self._token_expires_at = now + max(int(expires_in), 60)
        return self._cached_token

    def _headers(self, *, include_annotations: bool = True) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
        }
        if include_annotations:
            headers["Prefer"] = 'odata.maxpagesize=5000, odata.include-annotations="OData.Community.Display.V1.FormattedValue"'
        return headers

    def list_records(
        self,
        entity_set: str,
        *,
        select: Optional[List[str]] = None,
        orderby: Optional[str] = None,
        filter_clause: Optional[str] = None,
        top: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch records from Dataverse entity set."""
        url = f"{self._api_url}/{entity_set}"
        params = {}
        
        if select:
            params["$select"] = ",".join(select)
        if orderby:
            params["$orderby"] = orderby
        if filter_clause:
            params["$filter"] = filter_clause
        if top:
            params["$top"] = str(top)

        response = requests.get(
            url, headers=self._headers(), params=params, timeout=self._timeout
        )
        response.raise_for_status()
        data = response.json()
        return data.get("value", [])
```

---

### Phase 2: Create Dataverse Service Module

**Create new file: `flask_app/dataverse/service.py`**

```python
"""Dataverse service for TimeTrackerApp - job sync functionality."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .client import DataverseClient, DataverseClientError

# Entity and field mappings
ENTITY_SET = "imi_jobs"

SELECT_FIELDS = (
    "imi_jobid",
    "imi_imnumber",
    "imi_jobnameaddress",
    "imi_gc",
    "imi_scopesummary",
    "imi_submittalstatus",
    "imi_productionphase",
    "createdon",
)

# Submittal Status OptionSet values
SUBMITTAL_STATUS_APPROVED = 826130004  # "Approved" status in Dataverse

SUBMITTAL_STATUS_LABELS = {
    826130000: "Needed",
    826130001: "Ready to Submit",
    826130002: "AWT Approval",
    826130003: "Update with Field #'s",
    826130004: "Approved",
    826130005: "N/A",
}

_client: Optional[DataverseClient] = None


def _get_client() -> DataverseClient:
    """Get or create Dataverse client singleton."""
    global _client
    if _client is None:
        _client = DataverseClient(
            base_url=os.environ.get("DATAVERSE_BASE_URL", ""),
            tenant_id=os.environ.get("DATAVERSE_TENANT_ID", ""),
            client_id=os.environ.get("DATAVERSE_CLIENT_ID", ""),
            client_secret=os.environ.get("DATAVERSE_CLIENT_SECRET", ""),
        )
    return _client


def get_approved_jobs() -> List[Dict[str, Any]]:
    """
    Fetch all approved jobs from Dataverse.
    
    Equivalent to the old Smartsheet `get_approved_jobs_from_smartsheet()` method.
    Returns jobs where imi_submittalstatus = 826130004 (Approved).
    """
    try:
        records = _get_client().list_records(
            ENTITY_SET,
            select=list(SELECT_FIELDS),
            filter_clause=f"imi_submittalstatus eq {SUBMITTAL_STATUS_APPROVED} and statecode eq 0",
            orderby="createdon desc",
        )
    except DataverseClientError as e:
        print(f"Dataverse error fetching approved jobs: {e}")
        return []

    jobs: List[Dict[str, Any]] = []
    for record in records:
        im_number = record.get("imi_imnumber")
        if not im_number:
            continue
        
        # Transform to match existing TimeTrackerApp job schema
        job = {
            "im_number": str(im_number),
            "general_contractor": record.get("imi_gc") or "Unknown",
            "job_scope": _truncate_scope(record.get("imi_scopesummary")),
            "dataverse_id": record.get("imi_jobid"),  # Store for future reference
        }
        jobs.append(job)
    
    return jobs


def get_all_active_jobs() -> List[Dict[str, Any]]:
    """
    Fetch ALL active jobs from Dataverse (not just approved).
    
    Useful for job lookups and dropdown population.
    """
    try:
        records = _get_client().list_records(
            ENTITY_SET,
            select=list(SELECT_FIELDS),
            filter_clause="statecode eq 0",  # Active jobs only
            orderby="imi_imnumber desc",
        )
    except DataverseClientError as e:
        print(f"Dataverse error fetching all jobs: {e}")
        return []

    jobs: List[Dict[str, Any]] = []
    for record in records:
        im_number = record.get("imi_imnumber")
        if not im_number:
            continue
        
        job = {
            "im_number": str(im_number),
            "general_contractor": record.get("imi_gc") or "Unknown",
            "job_scope": _truncate_scope(record.get("imi_scopesummary")),
            "submittal_status": record.get("imi_submittalstatus"),
            "submittal_status_label": SUBMITTAL_STATUS_LABELS.get(
                record.get("imi_submittalstatus"), "Unknown"
            ),
            "dataverse_id": record.get("imi_jobid"),
        }
        jobs.append(job)
    
    return jobs


def _truncate_scope(scope: Optional[str], max_length: int = 255) -> str:
    """Truncate job scope to fit database field."""
    if not scope:
        return "See Work Order"
    if len(scope) > max_length:
        return "See Work Order"
    return scope
```

---

### Phase 3: Update Configuration

**Replace `flask_app/config/config.py` completely:**

```python
import os

# ===== DATAVERSE CONFIGURATION =====
DATAVERSE_BASE_URL = os.environ.get("DATAVERSE_BASE_URL", "")
DATAVERSE_TENANT_ID = os.environ.get("DATAVERSE_TENANT_ID", "")
DATAVERSE_CLIENT_ID = os.environ.get("DATAVERSE_CLIENT_ID", "")
DATAVERSE_CLIENT_SECRET = os.environ.get("DATAVERSE_CLIENT_SECRET", "")

# Remove all Smartsheet configuration
# Smartsheet is fully deprecated
```

---

### Phase 4: Update Job Model

**Modify `flask_app/models/job.py`:**

```python
from flask_app.config.mysqlconnection import connectToMySQL
from flask import flash
from ..models import shift, user
from datetime import datetime
from ..config.config import USE_DATAVERSE

# Conditional import based on feature flag
if USE_DATAVERSE:
    from ..dataverse.service import get_approved_jobs, get_all_active_jobs
else:
    import smartsheet
    from ..config.config import (
       dataverse.service import get_approved_jobs, get_all_active_jobs

dateFormat = "%m/%d/%Y %I:%M %p"


class Job:
    db_name = 'man_hours'

    def __init__(self, db_data):
        self.id = db_data['id']
        self.im_number = db_data['im_number']
        self.general_contractor = db_data['general_contractor']
        self.job_scope = db_data['job_scope']
        self.estimated_hours = db_data['estimated_hours']
        self.user = None
        self.user_id = db_data['user_id']
        self.context = db_data['context']
        self.created_at = db_data['created_at']
        self.updated_at = db_data['updated_at']
        self.status = db_data['status']
        self.shifts = []
        self.shift_users = []

    @classmethod
    def get_approved_jobs_from_dataverse(cls):
        """
        Get approved jobs from Dataverse.
        Replaces the old get_approved_jobs_from_smartsheet() method.
        """
        return get_approved_jobs()

    # ... rest of existing methods unchanged ...
    
    # REMOVE the following methods entirely:
    # - get_approved_jobs_from_smartsheet()
    # - smartsheet_client initialization
    # - Any Smartsheet imports
```python
import logging
from datetime import datetime
from flask_app.models.job import Job
from flask_app.config.config import USE_DATAVERSE

scheduler_logger = logging.getLogger('scheduler')
scheduler_logger.setLevel(logging.INFO)


def automated_job_sync():
    """
    Automated job sync from configured data source.
    Runs daily at 6 AM EST.
    """
    source = "Dataverse" if USE_DATAVERSE else "Smartsheet"
    
    try:
        scheduler_logger.info(f"Starting automated {source} sync at {datetime.now()}")
        
        # Use unified method that respects feature flag
        approved_jobs = Job.get_approved_jobs_from_source()

scheduler_logger = logging.getLogger('scheduler')
scheduler_logger.setLevel(logging.INFO)


def automated_job_sync():
    """
    Automated job sync from Dataverse.
    Runs daily at 6 AM EST.
    """
    try:
        scheduler_logger.info(f"Starting automated Dataverse sync at {datetime.now()}")
        
        # Get approved jobs from Dataverse
        approved_jobs = Job.get_approved_jobs_from_dataverse()
        scheduler_logger.info(f"Retrieved {len(approved_jobs)} approved jobs from Dataverse")

        added_count = 0
        skipped_count = 0
        
        for job in approved_jobs:
            scheduler_logger.info(f"Processing job with IM number: {job['im_number']}")
            
            if not Job.check_im_number_exists({'im_number': job['im_number']}):
                scheduler_logger.info(f"IM number {job['im_number']} does not exist. Adding new record.")
                Job.add_new_record(job)
                added_count += 1
            else:
                scheduler_logger.info(f"IM number {job['im_number']} already exists. Skipping.")
                skipped_count += 1

        scheduler_logger.info(
            f"Dataverse sync completed: {added_count} added, {skipped_count} skipped"
        )

    except Exception as e:
        scheduler_logger.error(f"Error during Dataverse

    # Trigger approved jobs sync on login using configured source
    try:
        from ..config.config import USE_DATAVERSE
        source = "Dataverse" if USE_DATAVERSE else "Smartsheet"
        
        approved_jobs = Job.get_approved_jobs_from_source()
        print(f"Login sync: Retrieved {len(approved_jobs)} approved jobs from {source}")

        added_count = 0
        for job in approved_jobs:
            if not Job.check_im_number_exists({'im_number': job['im_number']}):
                Job.add_new_record(job)
                added_count += 1

        if added_count > 0:
            print(f"Login sync: Added {added_count} new jobs")
            
    except Exception as e:
        print(f"Warning: Could not sync jobs during login: {e}")

    return redirect("/dashboard")
```from Dataverse on login
    try:
        approved_jobs = Job.get_approved_jobs_from_dataverse()
        print(f"Login sync: Retrieved {len(approved_jobs)} approved jobs from Dataverse")

        added_count = 0
        for job in approved_jobs:
            if not Job.check_im_number_exists({'im_number': job['im_number']}):
                Job.add_new_record(job)
                added_count += 1

        if added_count > 0:
            print(f"Login sync: Added {added_count} new jobs from Dataverse")
            
    except Exception as e:
        print(f"Warning: Could not sync jobs from Dataverse
### Phase 8: AWS Environment Variables

**Add these environment variables to your AWS deployment:**

```bash
# Dataverse Configuration (use same creds as Island-Platform)
DATAVERSE_BASE_URL=https://your-org.crm.dynamics.com
DATAVERSE_TENANT_ID=your-tenant-id
DATAVERSE_CLIENT_ID=your-client-id
DATAVERSE_CLIENT_SECRET=your-client-secret

# Modify `requirements.txt`:**

```
# Dataverse integration (NEW)
msal>=1.24.0
requests>=2.28.0

# REMOVE this line:
# smartsheet-python-sdk>=2.177.1  # DEPRECATED - Remove completelyrse Field | Type |
|---------------------|-------------------|-----------------|------|
| `im_number` | IM_NUMBER_COLUMN_ID | `imi_imnumber` | String |
| `general_contractor` | GC_COLUMN_ID | `imi_gc` | String |
| `job_scope` | SCOPE_COLUMN_ID | `imi_scopesummary` | String (255 max) |
| `submittal_status` | SUBMITTAL_STATUS_COLUMN_ID | `imi_submittalstatus` | OptionSet |
| - | - | `imi_productionphase` | OptionSet (bonus) |
Replace AWS environment variables:**

```bash
# Dataverse Configuration (use same creds as Island-Platform)
DATAVERSE_BASE_URL=https://your-org.crm.dynamics.com
DATAVERSE_TENANT_ID=your-tenant-id
DATAVERSE_CLIENT_ID=your-client-id
DATAVERSE_CLIENT_SECRET=your-client-secret

# REMOVE these (deprecated):
# SMARTSHEET_API_KEY
# SMARTSHEET_SHEET_ID
---

## Testing Checklist

- [ ] Create `flask_app/dataverse/__init__.py`
- [ ] Create `flask_app/dataverse/client.py`
- [ ] Create `flask_app/dataverse/service.py`
- [ ] Update `flask_app/config/config.py` with Dataverse vars
- [ ] Add `USE_DATAVERSE` feature flag
- [ ] Update `flask_app/models/job.py` with `get_approved_jobs_from_source()`
- [ ] Update `flask_app/utils/scheduler_tasks.py`
- [ ] Update `flask_app/controllers/users.py` login sync
- [ ] Update `requirements.txt` with `msal`
- [ ] Test locally with `USE_DATAVERSE=true`
- [ ] Test rollback with `USE_DATAVERSE=false`
- [ ] Deploy to AWS with new env vars
- [ ] Verify daily sync runs correctly
- [ ] Remove Smartsheet UI links from templates (optional)

---

## Rollback Plan

1. Set `USE_DATAVERSE=false` in AWS environment
2. Restart the application
3. App reverts to Smartsheet sync automatically

---

## Future Enhancements
Replace `flask_app/config/config.py` (remove all Smartsheet config)
- [ ] Update `flask_app/models/job.py` - rename method to `get_approved_jobs_from_dataverse()`
- [ ] Remove `get_approved_jobs_from_smartsheet()` method entirely
- [ ] Update `flask_app/utils/scheduler_tasks.py`
- [ ] Update `flask_app/controllers/users.py` login sync
- [ ] Update `flask_app/controllers/jobs.py` API endpoints
- [ ] Remove `smartsheet-python-sdk` from `requirements.txt`
- [ ] Add `msal` to `requirements.txt`
- [ ] Remove all Smartsheet imports from codebase
- [ ] Test locally with Dataverse credentials
- [ ] Deploy to AWS with new env vars (remove old Smartsheet vars)
- [ ] Verify daily sync runs correctly
- [ ] Remove Smartsheet UI links from templates
- [ ] Delete unused Smartsheet files: `sheet_id.py`, `getcolumnids.py`, `ss_autoadd_jobs.py`, `webhooks_controller.py`
| MODIFY | `flask_app/controllers/jobs.py` |
| MODIFY | `requirements.txt` |
| MODIFY | AWS Environment Variables |

---

*Generated for Island-Platform Dataverse integration pattern transfer to TimeTrackerApp*
Phase 9: Remove Smartsheet Code & Files

**Delete these files completely:**

```bash
# Smartsheet-specific files to delete
flask_app/controllers/sheet_id.py
flask_app/controllers/getcolumnids.py
flask_app/controllers/ss_autoadd_jobs.py
flask_app/controllers/webhooks_controller.py
debug_smartsheet_statuses.py
AUTOMATED_SYNC_GUIDE.md  # Old Smartsheet sync documentation
```

**Remove Smartsheet UI links from templates:**

Search and replace in all `.html` files:
- Remove links to `https://app.smartsheet.com/sheets/...`
- Remove "View SmartSheet" buttons
- Update help text that references Smartsheet

---

## Future Enhancements

1. **Write-back to Dataverse**: When shifts are tracked, update `imi_actualhours` in Dataverse
2. **Bi-directional sync**: Listen for Dataverse changes via webhooks
3. **Job status updates**: Update `imi_productionphase` based on labor completion
4. **Unified auth**: Use same Dataverse credentials for SharePoint folder links

---

## Files to Create/Modify/Delete Summary

| Action | File Path |
|--------|-----------|
| CREATE | `flask_app/dataverse/__init__.py` |
| CREATE | `flask_app/dataverse/client.py` |
| CREATE | `flask_app/dataverse/service.py` |
| MODIFY | `flask_app/config/config.py` (remove all Smartsheet) |
| MODIFY | `flask_app/models/job.py` (replace method, remove imports) |
| MODIFY | `flask_app/utils/scheduler_tasks.py` |
| MODIFY | `flask_app/controllers/users.py` |
| MODIFY | `flask_app/controllers/jobs.py` |
| MODIFY | `requirements.txt` (remove smartsheet-python-sdk) |
| MODIFY | AWS Environment Variables (remove Smartsheet vars) |
| DELETE | `flask_app/controllers/sheet_id.py` |
| DELETE | `flask_app/controllers/getcolumnids.py` |
| DELETE | `flask_app/controllers/ss_autoadd_jobs.py` |
| DELETE | `flask_app/controllers/webhooks_controller.py` |
| DELETE | `debug_smartsheet_statuses.py` |
| DELETE | `AUTOMATED_SYNC_GUIDE.md` |
| MODIFY | All `.html` templates (remove Smartsheet links) |

---

*Generated for Island-Platform Dataverse integration pattern transfer to TimeTrackerApp - Full Smartsheet Deprecation