from flask_app import app
from flask_app.controllers import users, jobs, shifts
# from dotenv import load_dotenv
# from flask_app.config.config import ss_client
# from flask_app.controllers.webhooks_controller import webhooks_blueprint, setup_webhook


# load_dotenv()

# app.register_blueprint(webhooks_blueprint, url_prefix='/webhook')

# setup_webhook(sheet_id='YOUR_SHEET_ID', callback_url='YOUR_CALLBACK_URL')


if __name__ == "__main__":
    app.run(debug=True)
