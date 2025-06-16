from flask_app import app
from flask_app.controllers import users, jobs, shifts
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask_app.utils.scheduler_tasks import automated_job_sync
import atexit
import pytz

# from dotenv import load_dotenv
# from flask_app.config.config import ss_client
# from flask_app.controllers.webhooks_controller import webhooks_blueprint, setup_webhook


# load_dotenv()

# app.register_blueprint(webhooks_blueprint, url_prefix='/webhook')

# setup_webhook(sheet_id='YOUR_SHEET_ID', callback_url='YOUR_CALLBACK_URL')

# Scheduler setup will be done in the main block to avoid multiple instances

# Assuming 'app' is your Flask app


if __name__ == "__main__":
    # Set up the scheduler
    scheduler = BackgroundScheduler()

    # Define Eastern Time zone
    eastern = pytz.timezone('US/Eastern')

    # Schedule the job to run daily at 6:00 AM EST
    scheduler.add_job(
        func=automated_job_sync,
        trigger=CronTrigger(hour=6, minute=0, timezone=eastern),
        id='daily_smartsheet_sync',
        name='Daily Smartsheet Job Sync',
        replace_existing=True
    )

    # Start the scheduler
    scheduler.start()

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())

    app.run(debug=True)
