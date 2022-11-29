from flask_app import app
from flask import render_template, redirect, session, request, flash
from ..models import user, job 
from flask_bcrypt import Bcrypt
bcrypt = Bcrypt(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/register", methods = ["POST"])
def register():

    if not user.User.validate_registration(request.form):
        return redirect('/')
    pw_hash = bcrypt.generate_password_hash(request.form['password'])
    print(pw_hash)

    data = {
        'first_name': request.form['first_name'],
        'last_name': request.form['last_name'],
        'email': request.form['email'],
        'password': pw_hash
    }

    user_id = user.User.create_user(data)

    session['user_id'] = user_id
    return redirect("/dashboard")

@app.route("/login", methods = ["POST"])
def login():
    if not user.User.validate_login(request.form):
        return redirect('/')

    data = {
        'email': request.form['email']
    }
    user_with_email = user.User.get_by_email(data)
    if not user_with_email:
        flash('Invalid Email/Password Combination', 'error')
        return redirect('/')
    # user bcrypt to validate the password 
    if not bcrypt.check_password_hash(user_with_email.password, request.form['password']):
        return redirect('/')

    # populate session with logged in user's id
    session['user_id'] = user_with_email.id
    flash('Congratulations, You logged in!')
    print("SUCCESSFUL LOGIN")
    return redirect('/dashboard')

@app.route("/logout")
def logout():
    session.clear()
    return redirect('/')

@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect('/')
    data = {
        'id' : session['user_id']
    }
    return render_template("dashboard.html", jobs = job.Job.get_all(), logged_in_user = user.User.get_by_id(data))