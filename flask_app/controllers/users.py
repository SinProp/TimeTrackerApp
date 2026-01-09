from flask_app import app
from flask import render_template, redirect, session, request, flash, url_for
from ..models import user, job, shift
from ..models.user import User
from ..models.job import Job
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt(app)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["POST"])
def register():

    if not user.User.validate_registration(request.form):
        return redirect("/")
    pw_hash = bcrypt.generate_password_hash(request.form["password"])
    print(pw_hash)

    data = {
        "first_name": request.form["first_name"],
        "last_name": request.form["last_name"],
        "email": request.form["email"],
        "department": request.form["department"],
        "password": pw_hash,
    }

    user_id = user.User.create_user(data)

    session["user_id"] = user_id
    return redirect("/dashboard")


@app.route("/login", methods=["POST"])
def login():
    if not user.User.validate_login(request.form):
        return redirect("/")

    data = {"email": request.form["email"]}
    user_with_email = user.User.get_by_email(data)
    if not user_with_email:
        flash("Invalid Email/Password Combination", "error")
        return redirect("/")
    # user bcrypt to validate the password
    if not bcrypt.check_password_hash(
        user_with_email.password, request.form["password"]
    ):
        return redirect("/")

    # populate session with logged in user's id
    session["user_id"] = user_with_email.id
    flash("Congratulations, You logged in!")
    print("SUCCESSFUL LOGIN")

    # Trigger approved jobs sync on login to keep data current
    # OPTIMIZED: Uses bulk operations instead of N+1 queries
    try:
        approved_jobs = Job.get_approved_jobs_from_dataverse()
        print(
            f"Login sync: Retrieved {len(approved_jobs)} approved jobs from Dataverse"
        )

        if approved_jobs:
            # OPTIMIZED: Check all IM numbers in one query instead of N queries
            im_numbers = [job["im_number"] for job in approved_jobs]
            existing_im_numbers = Job.get_existing_im_numbers(im_numbers)

            # Filter to only new jobs
            new_jobs = [
                job
                for job in approved_jobs
                if job["im_number"] not in existing_im_numbers
            ]

            if new_jobs:
                # Log which jobs are being added
                for job in new_jobs:
                    print(f"Login sync: Adding IM #{job['im_number']}")

                # OPTIMIZED: Insert all new jobs in one query instead of N queries
                added_count = Job.bulk_add_records(new_jobs)
                print(
                    f"Login sync: Added {added_count} new approved jobs from Dataverse"
                )
            else:
                print("Login sync: No new approved jobs to add")

    except Exception as e:
        print(f"Login sync error (Dataverse): {str(e)}")
        # Don't block login if sync fails

    return redirect("/dashboard")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/dashboard")
def dashboard():
    no_shifts = request.args.get("no_shifts", default=False, type=bool)
    if "user_id" not in session:
        return redirect("/")
    data = {"id": session["user_id"]}

    started_today = shift.Shift.get_started_today()

    return render_template(
        "dashboard.html",
        jobs=job.Job.get_all(),
        logged_in_user=user.User.get_by_id(data),
        started_today=started_today,
    )


@app.route("/manage_users")
def manage_users():
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        return redirect("/dashboard")
    users = User.get_all()
    show_add_form = request.args.get("show_add_form", default=False, type=bool)
    return render_template(
        "manage_users.html", users=users, show_add_form=show_add_form
    )


@app.route("/create_user_admin", methods=["POST"])
def create_user_admin():
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        return redirect("/dashboard")

    if not User.validate_registration(request.form):
        return redirect(url_for("manage_users", show_add_form=True))

    pw_hash = bcrypt.generate_password_hash(request.form["password"])
    data = {
        "first_name": request.form["first_name"],
        "last_name": request.form["last_name"],
        "email": request.form["email"],
        "department": request.form["department"],
        "password": pw_hash,
    }
    User.create_user(data)
    flash("User created successfully", "success")
    return redirect("/manage_users")


@app.route("/edit/user/<int:id>")
def edit_user(id):
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        return redirect("/dashboard")
    user_to_edit = User.get_by_id({"id": id})
    return render_template("edit_user.html", user=user_to_edit)


@app.route("/update/user/<int:id>", methods=["POST"])
def update_user(id):
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        return redirect("/dashboard")
    data = {
        "id": id,
        "first_name": request.form["first_name"],
        "last_name": request.form["last_name"],
        "email": request.form["email"],
        "department": request.form["department"],
    }
    User.update(data)
    return redirect("/manage_users")


@app.route("/destroy/user/<int:id>", methods=["POST"])
def destroy_user(id):
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        return redirect("/dashboard")
    User.soft_delete({"id": id})
    return redirect("/manage_users")


@app.route("/toggle_roster/<int:id>", methods=["POST"])
def toggle_roster(id):
    """
    Toggle a user's active roster status.
    Only admins can toggle roster status.
    """
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized: Only admins can modify roster status.", "danger")
        return redirect("/dashboard")

    # Get the current user's roster status
    user_to_toggle = User.get_by_id({"id": id})
    if not user_to_toggle:
        flash("User not found.", "danger")
        return redirect("/manage_users")

    # Toggle the roster status
    new_status = not user_to_toggle.on_active_roster
    User.update_roster_status({"id": id, "on_roster": new_status})

    status_text = "added to" if new_status else "removed from"
    flash(f"{user_to_toggle.first_name} {user_to_toggle.last_name} {status_text} active roster.", "success")
    return redirect("/manage_users")
