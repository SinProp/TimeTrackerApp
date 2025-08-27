#!/usr/bin/env python3
"""Standalone runner for exporting to SharePoint.

Use this in crontab if you prefer cron over in-app scheduler.
"""
from datetime import datetime
from flask_app.utils.export_to_sharepoint import export_database_to_sharepoint


if __name__ == "__main__":
    print(f"[{datetime.now().isoformat()}] Starting export...")
    result = export_database_to_sharepoint()
    print(f"[{datetime.now().isoformat()}] {result}")
