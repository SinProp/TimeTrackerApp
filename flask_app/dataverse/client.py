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
        """Get or refresh the access token with caching."""
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
        """Build request headers with authentication."""
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
        
        # Enhanced error logging
        if response.status_code != 200:
            print(f"Dataverse API Error {response.status_code}: {response.text}")
        
        response.raise_for_status()
        data = response.json()
        return data.get("value", [])
