import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from flask_app.utils.export_to_sharepoint import export_database_to_sharepoint


scheduler_logger = logging.getLogger("export_scheduler")
if not scheduler_logger.handlers:
    logging.basicConfig(level=logging.INFO)


def setup_export_scheduler(app):
    """Start a daily job to export to SharePoint at 11:00 PM US/Eastern."""
    scheduler = BackgroundScheduler(timezone=pytz.timezone("US/Eastern"))

    scheduler.add_job(
        func=export_database_to_sharepoint,
        trigger="cron",
        hour=23,
        minute=0,
        id="daily_sharepoint_export",
        name="Daily SharePoint Export",
        replace_existing=True,
    )

    scheduler.start()
    scheduler_logger.info("Daily SharePoint export scheduler started - runs at 11:00 PM EST/EDT")

    # Ensure clean shutdown with Flask app
    import atexit

    atexit.register(lambda: scheduler.shutdown())
    return scheduler
