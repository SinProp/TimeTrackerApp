from flask_app import app
from flask import render_template, redirect, session, request, flash, url_for
from ..models import user, job, shift
from ..models.user import User
from flask_bcrypt import Bcrypt
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
bcrypt = Bcrypt(app)


mail = Mail(app)


@app.route('/')
def index():
    return render_template('index.html')


@app.route("/register", methods=["POST"])
def register():

    if not user.User.validate_registration(request.form):
        return redirect('/')
    pw_hash = bcrypt.generate_password_hash(request.form['password'])
    print(pw_hash)

    data = {
        'first_name': request.form['first_name'],
        'last_name': request.form['last_name'],
        'email': request.form['email'],
        'department': request.form['department'],
        'password': pw_hash
    }

    user_id = user.User.create_user(data)

    session['user_id'] = user_id
    return redirect("/dashboard")


@app.route("/login", methods=["POST"])
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


@app.route('/forgot_password', methods=['GET'])
def forgot_password():

    return render_template('forgot_password.html')


@app.route('/forgot_password', methods=['POST'])
def forgot_password_post():
    email = request.form['email']
    user = User.get_by_email({'email': email})
    if user:
        ts = URLSafeTimedSerializer(app.config["SECRET_KEY"])
        token = ts.dumps(email, salt=app.config['SECURITY_PASSWORD_SALT'])

        # Configure your mail settings and then send mail
        msg = Message("Password Reset",
                      sender="tito@islandmillworkinc.com", recipients=[email])
        link = url_for('reset_password', token=token, _external=True)
        msg.body = f'Your link to reset password is {link}'
        mail.send(msg)

        flash('Check your email for a password reset link', 'success')
    else:
        flash('Email address not found', 'error')
    return redirect(url_for('forgot_password'))


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        ts = URLSafeTimedSerializer(app.config["SECRET_KEY"])
        # 24 hours in seconds
        email = ts.loads(
            token, salt=app.config['SECURITY_PASSWORD_SALT'], max_age=86400)
    except:
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        user = User.get_by_email({'email': email})
        pw_hash = bcrypt.generate_password_hash(
            request.form['password']).decode('utf-8')
        # Update user's password
        User.update_password({'id': user.id, 'password': pw_hash})
        flash('Your password has been updated!', 'success')
        return redirect(url_for('index'))

    return render_template('forgot_password.html', token=token)


@app.route("/dashboard")
def dashboard():
    no_shifts = request.args.get('no_shifts', default=False, type=bool)
    if 'user_id' not in session:
        return redirect('/')
    data = {
        'id': session['user_id']
    }

    started_today = shift.Shift.get_started_today()

    return render_template("dashboard.html", jobs=job.Job.get_all(), logged_in_user=user.User.get_by_id(data), started_today=started_today)
