from flask import (
    render_template,
    redirect,
    session,
    request,
    flash,
    url_for,
    Blueprint,
    jsonify,
)
from flask_app import app
from flask_app.models.job import Job
from flask_app.models.user import User
from flask_app.models.shift import Shift
from datetime import datetime

dateFormat = "%m/%d/%Y %I:%M %p"


@app.route("/new/job")
def new_job():
    if "user_id" not in session:
        return redirect("/logout")
    data = {"id": session["user_id"]}
    return render_template("new_job.html", logged_in_user=User.get_by_id(data))


@app.route("/create/job", methods=["POST"])
def create_job():
    if "user_id" not in session:
        return redirect("/logout")
    if not Job.validate_job(request.form):
        return redirect("/new/job")
    data = {
        "im_number": request.form["im_number"],
        "general_contractor": request.form["general_contractor"],
        "job_scope": request.form["job_scope"],
        "estimated_hours": request.form["estimated_hours"],
        "context": request.form["context"],
        "user_id": session["user_id"],
    }
    Job.save(data)
    return redirect("/dashboard")


@app.route("/dashboard", endpoint="jobs_dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    user = User.get_by_id(user_data)
    # Get jobs filtered by user department (admins see all, others see visible only)
    jobs = Job.get_all_for_user(user.department)
    return render_template("dashboard.html", jobs=jobs, logged_in_user=user)


@app.route("/show/job/<int:id>")
def get_one(id):
    if "user_id" not in session:
        return redirect("/logout")
    data = {"id": id}

    user_data = {"id": session["user_id"]}

    thisJob = Job.getJobWithShifts(data)

    if thisJob is None:
        return redirect(url_for("dashboard", no_shifts=True))

    # Calculate total_elapsed_seconds
    total_elapsed_seconds = 0
    for shift in thisJob.shifts:
        if shift.elapsed_time is not None:
            total_elapsed_seconds += shift.elapsed_time.total_seconds()

    return render_template(
        "view_job.html",
        thisJob=thisJob,
        dtf=dateFormat,
        job=Job.get_one(data),
        user=User.get_by_id(user_data),
        total_elapsed_seconds=total_elapsed_seconds,
    )


@app.route("/edit/job/<int:id>")
def edit_job(id):
    if "user_id" not in session:
        return redirect("/logout")
    data = {"id": id}
    job = Job.get_one(data)
    user_data = {"id": session["user_id"]}
    logged_user = User.get_by_id(user_data)
    if logged_user.department != "ADMINISTRATIVE":
        if job.user_id != session["user_id"]:
            flash("You can only edit your own jobs.")
            return redirect("/dashboard")
    return render_template("edit_job.html", job=job)


@app.route("/update/job/<int:id>", methods=["POST"])
def update_job(id):
    if "user_id" not in session:
        return redirect("/logout")
    if not Job.validate_job(request.form):
        return redirect(f"/edit/job/{id}")
    data = {
        "id": id,
        "im_number": request.form["im_number"],
        "general_contractor": request.form["general_contractor"],
        "job_scope": request.form["job_scope"],
        "estimated_hours": request.form["estimated_hours"],
        # Use get() with default value
        "context": request.form.get("context", ""),
        "status": request.form["status"],
        "user_id": session["user_id"],
    }
    Job.update(data)
    return redirect("/dashboard")


@app.route("/api/process-approved-jobs", methods=["POST"])
def process_approved_jobs():
    """
    Process approved jobs from Dataverse.
    OPTIMIZED: Uses bulk operations instead of N+1 queries.
    """
    try:
        # Get approved jobs from Dataverse
        approved_jobs = Job.get_approved_jobs_from_dataverse()
        print(f"Retrieved {len(approved_jobs)} Approved jobs from Dataverse.")

        if not approved_jobs:
            return jsonify({"message": "No approved jobs found in Dataverse."}), 200

        # OPTIMIZED: Check all IM numbers in one query instead of N queries
        im_numbers = [job["im_number"] for job in approved_jobs]
        existing_im_numbers = Job.get_existing_im_numbers(im_numbers)

        # Filter to only new jobs
        new_jobs = [
            job for job in approved_jobs if job["im_number"] not in existing_im_numbers
        ]
        skipped_count = len(approved_jobs) - len(new_jobs)

        # Log which jobs are being processed
        for job in new_jobs:
            print(f"Adding new job with IM number: {job['im_number']}")

        # OPTIMIZED: Insert all new jobs in one query instead of N queries
        added_count = Job.bulk_add_records(new_jobs)

        print("Finished processing approved jobs from Dataverse.")
        return (
            jsonify(
                {
                    "message": f"Dataverse sync complete. Added: {added_count}, Skipped: {skipped_count}"
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sync-jobs", methods=["POST"])
def sync_jobs():
    """
    Manual trigger for syncing approved jobs from Dataverse.
    Requires ADMINISTRATIVE role for security.
    Returns JSON with sync results: added count and skipped count.
    """
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized: not logged in"}), 401

    user_data = {"id": session["user_id"]}
    user = User.get_by_id(user_data)

    # Only admins can manually trigger syncs
    if user.department != "ADMINISTRATIVE":
        return jsonify({"error": "Unauthorized: admin role required"}), 403

    try:
        from flask_app.utils.scheduler_tasks import automated_job_sync

        result = automated_job_sync()
        return jsonify({"message": result, "status": "success"}), 200
    except Exception as e:
        return jsonify({"error": f"Sync failed: {str(e)}", "status": "error"}), 500


@app.route("/destroy/job/<int:id>")
def destroy_job(id):
    if "user_id" not in session:
        return redirect("/logout")
    data = {"id": id}
    Job.destroy(data)
    return redirect("/dashboard")


@app.route("/api/manual-sync-test", methods=["POST"])
def manual_sync_test():
    """Manual trigger for testing the automated sync function"""
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        from flask_app.utils.scheduler_tasks import automated_job_sync

        result = automated_job_sync()
        return jsonify({"message": result}), 200
    except Exception as e:
        return jsonify({"error": f"Manual sync failed: {str(e)}"}), 500


# ============ Office Job Management ============


@app.route("/admin/create_office_job", methods=["GET", "POST"])
def create_office_job():
    """
    Create a new office/pre-production job.
    These jobs are hidden from production workers until they're approved in Dataverse
    or manually made visible.
    """
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized: Only admins can create office jobs.", "danger")
        return redirect("/dashboard")

    if request.method == "POST":
        # Validate the job data
        if not Job.validate_job(request.form):
            return redirect("/admin/create_office_job")

        data = {
            "im_number": request.form["im_number"],
            "general_contractor": request.form["general_contractor"],
            "job_scope": request.form["job_scope"],
            "estimated_hours": request.form.get("estimated_hours", "0000"),
            "context": request.form.get("context", ""),
            "user_id": session["user_id"],
        }

        # Check if IM number already exists
        if Job.check_im_number_exists({"im_number": data["im_number"]}):
            flash(f"IM number {data['im_number']} already exists.", "error")
            return redirect("/admin/create_office_job")

        try:
            Job.save_office_job(data)
            flash(f"Office job {data['im_number']} created successfully! (Hidden from production)", "success")
            return redirect("/dashboard")
        except Exception as e:
            print(f"Error creating office job: {e}")
            flash("An error occurred while creating the office job.", "danger")
            return redirect("/admin/create_office_job")

    return render_template("create_office_job.html", logged_in_user=logged_in_user)


@app.route("/admin/toggle_job_visibility/<int:id>", methods=["POST"])
def toggle_job_visibility(id):
    """
    Toggle the visibility of a job to production workers.
    """
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized: Only admins can toggle job visibility.", "danger")
        return redirect("/dashboard")

    try:
        Job.toggle_visibility(id)
        flash("Job visibility updated successfully.", "success")
    except Exception as e:
        print(f"Error toggling job visibility: {e}")
        flash("An error occurred while updating job visibility.", "danger")

    return redirect("/dashboard")
