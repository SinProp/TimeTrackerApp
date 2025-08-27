from flask_app import app
from flask import render_template, redirect, session, request, flash, url_for
from ..models import user, job, shift
from ..models.user import User
from ..models.job import Job
from flask_bcrypt import Bcrypt
from flask import jsonify
from flask_app.utils.export_to_sharepoint import export_database_to_sharepoint

bcrypt = Bcrypt(app)


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

    # Trigger approved jobs sync on login to keep data current
    try:
        approved_jobs = Job.get_approved_jobs_from_smartsheet()
        print(
            f"Login sync: Retrieved {len(approved_jobs)} approved jobs from Smartsheet")

        added_count = 0
        for job in approved_jobs:
            if not Job.check_im_number_exists({'im_number': job['im_number']}):
                Job.add_new_record(job)
                added_count += 1
                print(f"Login sync: Added IM #{job['im_number']}")

        if added_count > 0:
            print(f"Login sync: Added {added_count} new approved jobs")
        else:
            print("Login sync: No new approved jobs to add")

    except Exception as e:
        print(f"Login sync error: {str(e)}")
        # Don't block login if sync fails

    return redirect('/dashboard')


@app.route("/logout")
def logout():
    session.clear()
    return redirect('/')


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


@app.route('/manage_users')
def manage_users():
    if 'user_id' not in session:
        return redirect('/logout')
    user_data = {
        "id": session['user_id']
    }
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != 'ADMINISTRATIVE':
        return redirect('/dashboard')
    users = User.get_all()
    show_add_form = request.args.get('show_add_form', default=False, type=bool)
    return render_template('manage_users.html', users=users, show_add_form=show_add_form)


@app.route('/create_user_admin', methods=['POST'])
def create_user_admin():
    if 'user_id' not in session:
        return redirect('/logout')
    user_data = {
        'id': session['user_id']
    }
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != 'ADMINISTRATIVE':
        return redirect('/dashboard')

    if not User.validate_registration(request.form):
        return redirect(url_for('manage_users', show_add_form=True))

    pw_hash = bcrypt.generate_password_hash(request.form['password'])
    data = {
        'first_name': request.form['first_name'],
        'last_name': request.form['last_name'],
        'email': request.form['email'],
        'department': request.form['department'],
        'password': pw_hash
    }
    User.create_user(data)
    flash('User created successfully', 'success')
    return redirect('/manage_users')


@app.route('/edit/user/<int:id>')
def edit_user(id):
    if 'user_id' not in session:
        return redirect('/logout')
    user_data = {
        "id": session['user_id']
    }
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != 'ADMINISTRATIVE':
        return redirect('/dashboard')
    user_to_edit = User.get_by_id({"id": id})
    return render_template('edit_user.html', user=user_to_edit)


@app.route('/update/user/<int:id>', methods=['POST'])
def update_user(id):
    if 'user_id' not in session:
        return redirect('/logout')
    user_data = {
        "id": session['user_id']
    }
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != 'ADMINISTRATIVE':
        return redirect('/dashboard')
    data = {
        "id": id,
        "first_name": request.form["first_name"],
        "last_name": request.form["last_name"],
        "email": request.form["email"],
        "department": request.form["department"]
    }
    User.update(data)
    return redirect('/manage_users')


@app.route('/destroy/user/<int:id>', methods=['POST'])
def destroy_user(id):
    if 'user_id' not in session:
        return redirect('/logout')
    user_data = {
        "id": session['user_id']
    }
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != 'ADMINISTRATIVE':
        return redirect('/dashboard')


@app.route('/export/sharepoint/manual')
def manual_sharepoint_export():
    """Manual trigger for SharePoint export (Admin only)."""
    if 'user_id' not in session:
        return redirect('/logout')

    user_data = {"id": session['user_id']}
    current_user = User.get_by_id(user_data)
    if not current_user or current_user.department != 'ADMINISTRATIVE':
        return jsonify({"error": "Unauthorized"}), 403

    result = export_database_to_sharepoint()
    return jsonify({"message": result})

    User.soft_delete({"id": id})
    return redirect('/manage_users')
