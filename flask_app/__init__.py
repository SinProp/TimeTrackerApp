from flask import Flask

from flask_app.config.config import ss_client

app = Flask(__name__)

app.secret_key = "proper-one is the one"
