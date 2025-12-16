"""Dataverse integration module for TimeTrackerApp."""
from .client import DataverseClient, DataverseClientError
from .service import get_approved_jobs, get_all_active_jobs

__all__ = [
    "DataverseClient",
    "DataverseClientError",
    "get_approved_jobs",
    "get_all_active_jobs",
]
