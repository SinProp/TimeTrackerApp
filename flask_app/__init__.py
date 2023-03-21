from flask import Flask
# from flask_migrate import Migrate 
# from flask_sqlalchemy import SQLAlchemy



app = Flask(__name__)

app.secret_key = "proper-one is the one"


# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:root@localhost/man_hours'

# def initialize_app(app):
#     app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:root@localhost/man_hours'
#     app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#     db.init_app(app)
#     migrate = Migrate()
#     migrate.init_app(app, db)


# initialize_app(app)