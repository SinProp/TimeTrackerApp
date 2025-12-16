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
        print("Fetching approved jobs from Dataverse...")
        records = _get_client().list_records(
            ENTITY_SET,
            select=list(SELECT_FIELDS),
            filter_clause=f"imi_submittalstatus eq '{SUBMITTAL_STATUS_APPROVED}' and statecode eq 0",
            orderby="createdon desc",
        )
        print(f"Dataverse returned {len(records)} approved job records.")
    except DataverseClientError as e:
        print(f"Dataverse error fetching approved jobs: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error fetching approved jobs from Dataverse: {e}")
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
        print(f"Job added: IM #{job['im_number']}, GC: {job['general_contractor']}")

    print(f"Total approved jobs from Dataverse: {len(jobs)}")
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
    except Exception as e:
        print(f"Unexpected error fetching all jobs from Dataverse: {e}")
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
