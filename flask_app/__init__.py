from flask import Flask

# from flask_app.config.config import ss_client

app = Flask(__name__)

app.secret_key = "proper-one is the one"
app.config['SECURITY_PASSWORD_SALT'] = "ea0e3c5a1587439ac96a3dbafe09ae17"
