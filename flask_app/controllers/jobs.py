from flask import render_template, redirect, session, request, flash, url_for, Blueprint, jsonify
from flask_app import app
from flask_app.models.job import Job
from flask_app.models.user import User
from flask_app.models.shift import Shift
from datetime import datetime

dateFormat = "%m/%d/%Y %I:%M %p"


@app.route('/new/job')
def new_job():
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id": session['user_id']
    }
    return render_template('new_job.html', logged_in_user=User.get_by_id(data))


@app.route('/create/job', methods=['POST'])
def create_job():
    if 'user_id' not in session:
        return redirect('/logout')
    if not Job.validate_job(request.form):
        return redirect('/new/job')
    data = {
        "im_number": request.form["im_number"],
        "general_contractor": request.form["general_contractor"],
        "job_scope": request.form["job_scope"],
        "estimated_hours": request.form["estimated_hours"],
        "context": request.form["context"],
        "user_id": session["user_id"]
    }
    Job.save(data)
    return redirect('/dashboard')


@app.route('/dashboard', endpoint='jobs_dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/logout')
    jobs = Job.get_all()
    return render_template('dashboard.html', jobs=jobs)


@app.route('/show/job/<int:id>')
def get_one(id):
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id": id
    }

    user_data = {
        "id": session['user_id']
    }

    thisJob = Job.getJobWithShifts(data)

    if thisJob is None:
        return redirect(url_for('dashboard', no_shifts=True))

    # Calculate total_elapsed_seconds
    total_elapsed_seconds = 0
    for shift in thisJob.shifts:
        if shift.elapsed_time is not None:
            total_elapsed_seconds += shift.elapsed_time.total_seconds()

    return render_template("view_job.html",
                           thisJob=thisJob,
                           dtf=dateFormat,
                           job=Job.get_one(data),
                           user=User.get_by_id(user_data),
                           total_elapsed_seconds=total_elapsed_seconds)


@app.route('/edit/job/<int:id>')
def edit_job(id):
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id": id
    }
    job = Job.get_one(data)
    user_data = {
        'id': session['user_id']
    }
    logged_user = User.get_by_id(user_data)
    if logged_user.department != 'ADMINISTRATIVE':
        if job.user_id != session['user_id']:
            flash("You can only edit your own jobs.")
            return redirect('/dashboard')
    return render_template('edit_job.html', job=job)


@app.route('/update/job/<int:id>', methods=['POST'])
def update_job(id):
    if 'user_id' not in session:
        return redirect('/logout')
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
        "user_id": session["user_id"]
    }
    Job.update(data)
    return redirect('/dashboard')


@app.route('/api/process-approved-jobs', methods=['POST'])
def process_approved_jobs():
    try:
        # Get approved jobs from Smartsheet
        approved_jobs = Job.get_approved_jobs_from_smartsheet()
        print(f"Retrieved {len(approved_jobs)} Approved jobs from Smartsheet.")

        # Process each approved job
        for job in approved_jobs:
            print(f"Processing job with IM number: {job['im_number']}")
            # Check if the IM number exists
            if not Job.check_im_number_exists({'im_number': job['im_number']}):
                print(
                    f"IM number {job['im_number']} does not exist in the database. Adding new record.")
                # Add a new record
                Job.add_new_record(job)

            else:
                (f"IM number {job['im_number']} already exists in the database. Skipping.")

        print("Finished processing approved jobs.")
        return jsonify({"message": "Approved jobs processed successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/destroy/job/<int:id>')
def destroy_job(id):
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id": id
    }
    Job.destroy(data)
    return redirect('/dashboard')
