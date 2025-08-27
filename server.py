from flask_app import app
from flask_app.controllers import users, jobs, shifts
from flask_app.utils.daily_export_scheduler import setup_export_scheduler
from dotenv import load_dotenv

# from dotenv import load_dotenv
# from flask_app.config.config import ss_client
# from flask_app.controllers.webhooks_controller import webhooks_blueprint, setup_webhook


# load_dotenv()

# app.register_blueprint(webhooks_blueprint, url_prefix='/webhook')

# setup_webhook(sheet_id='YOUR_SHEET_ID', callback_url='YOUR_CALLBACK_URL')

# Scheduler setup will be done in the main block to avoid multiple instances

# Assuming 'app' is your Flask app


if __name__ == "__main__":
    # Load environment variables from .env (for local dev/testing)
    load_dotenv()
    # Start daily export scheduler (runs inside app process)
    setup_export_scheduler(app)
    app.run(debug=True)
