from dotenv import load_dotenv

load_dotenv()  # Must be called before any flask_app imports

from flask_app import app
from flask_app.controllers import users, jobs, shifts, version
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask_app.utils.scheduler_tasks import (
    automated_job_sync,
    auto_clock_out_shifts_at_6pm_weekdays,
)
import atexit
import pytz
import os
import fcntl
import logging

# from flask_app.config.config import ss_client
# from flask_app.controllers.webhooks_controller import webhooks_blueprint, setup_webhook


# load_dotenv()

# app.register_blueprint(webhooks_blueprint, url_prefix='/webhook')

# setup_webhook(sheet_id='YOUR_SHEET_ID', callback_url='YOUR_CALLBACK_URL')

scheduler_logger = logging.getLogger("scheduler")
_scheduler = None
_scheduler_lock_file = None


def _is_truthy(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _should_start_scheduler_in_process():
    if _is_truthy(os.environ.get("FLASK_DEBUG"), default=False):
        return os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    return True


def _shutdown_scheduler():
    global _scheduler, _scheduler_lock_file

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        scheduler_logger.info("Scheduler shut down cleanly")

    _scheduler = None

    if _scheduler_lock_file is not None:
        try:
            fcntl.flock(_scheduler_lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        _scheduler_lock_file.close()
        _scheduler_lock_file = None


def start_scheduler_if_enabled():
    """
    Start APScheduler once per host using a file lock.

    - Enabled by default, can be disabled with ENABLE_SCHEDULER=false
    - Safe under Gunicorn multi-worker: only lock owner starts scheduler
    """
    global _scheduler, _scheduler_lock_file

    if not _is_truthy(os.environ.get("ENABLE_SCHEDULER"), default=True):
        scheduler_logger.info("Scheduler disabled via ENABLE_SCHEDULER")
        return False

    if not _should_start_scheduler_in_process():
        scheduler_logger.info("Skipping scheduler in pre-reloader process")
        return False

    if _scheduler is not None and _scheduler.running:
        return True

    lock_path = os.environ.get("SCHEDULER_LOCK_FILE", "/tmp/island_time_scheduler.lock")
    lock_file = open(lock_path, "a+")

    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        scheduler_logger.info("Scheduler lock already held; not starting in this process")
        lock_file.close()
        return False

    scheduler = BackgroundScheduler()
    eastern = pytz.timezone("US/Eastern")

    scheduler.add_job(
        func=automated_job_sync,
        trigger=CronTrigger(hour=6, minute=0, timezone=eastern),
        id="daily_smartsheet_sync",
        name="Daily Smartsheet Job Sync",
        replace_existing=True,
    )

    scheduler.add_job(
        func=auto_clock_out_shifts_at_6pm_weekdays,
        trigger=CronTrigger(day_of_week="mon-fri", hour=18, minute=0, timezone=eastern),
        id="weekday_auto_clock_out_shifts",
        name="Weekday Auto Clock-Out Shifts at 6:00 PM",
        replace_existing=True,
    )

    scheduler.start()

    _scheduler = scheduler
    _scheduler_lock_file = lock_file
    atexit.register(_shutdown_scheduler)

    scheduler_logger.info("Scheduler started with daily 6AM sync and weekday 6PM auto clock-out")
    return True


if __name__ == "__main__":
    start_scheduler_if_enabled()
    app.run(debug=True)
