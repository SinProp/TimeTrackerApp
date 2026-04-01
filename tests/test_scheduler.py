"""Tests for APScheduler registration."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server


class FakeScheduler:
    def __init__(self):
        self.jobs = []
        self.running = False

    def add_job(self, **kwargs):
        self.jobs.append(kwargs)

    def start(self):
        self.running = True

    def shutdown(self, wait=False):
        self.running = False


def test_start_scheduler_registers_single_weekday_shift_job(monkeypatch, tmp_path):
    fake_scheduler = FakeScheduler()
    lock_path = tmp_path / "scheduler.lock"

    monkeypatch.setattr(server, "BackgroundScheduler", lambda: fake_scheduler)
    monkeypatch.setattr(server, "_should_start_scheduler_in_process", lambda: True)
    monkeypatch.setattr(server.fcntl, "flock", lambda *args, **kwargs: None)
    monkeypatch.setattr(server.atexit, "register", lambda *args, **kwargs: None)
    monkeypatch.setenv("SCHEDULER_LOCK_FILE", str(lock_path))
    monkeypatch.delenv("ENABLE_SCHEDULER", raising=False)

    server._scheduler = None
    server._scheduler_lock_file = None

    try:
        assert server.start_scheduler_if_enabled() is True
    finally:
        server._shutdown_scheduler()

    assert len(fake_scheduler.jobs) == 2

    daily_sync_job = next(job for job in fake_scheduler.jobs if job["id"] == "daily_smartsheet_sync")
    shift_job = next(job for job in fake_scheduler.jobs if job["id"] == "weekday_shift_remediation")

    assert daily_sync_job["name"] == "Daily Smartsheet Job Sync"
    assert shift_job["name"] == "Weekday Shift Remediation at 6:00 PM"
    assert shift_job["func"] is server.run_weekday_shift_remediation
    assert "day_of_week='mon-fri'" in str(shift_job["trigger"])
    assert "hour='18'" in str(shift_job["trigger"])
    assert "minute='0'" in str(shift_job["trigger"])
