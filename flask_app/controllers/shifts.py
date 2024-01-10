from flask import render_template, redirect, session, request, flash
from flask_app import app
from flask_app.models.job import Job
from flask_app.models.user import User
from flask_app.models.shift import Shift
from datetime import datetime, timedelta
dateFormat = "%m/%d/%Y %I:%M %p"


@app.route('/add/shift/<int:id>')
def new_shift(id):
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id": session['user_id']

    }
    logged_in_user = User.get_by_id(data)

    # Check if the logged-in user is an admin
    if logged_in_user.department == 'ADMINISTRATIVE':
        users = User.get_all()  # Get all users if the user is an admin
    else:
        users = None  # Set users to None if not an admin

    job_data = {
        "id": id
    }

    return render_template('new_shift.html', job=Job.get_one(job_data), logged_in_user=User.get_by_id(data), users=users)


@app.route('/create/shift', methods=['POST'])
def create_shift():
    if 'user_id' not in session:
        return redirect('/logout')

    if not Shift.validate_shift(request.form):
        return redirect('/add/shift')

    job_id = request.form['job_id']
    note = request.form.get('note', '')

    # Get the current server time as the start time
    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    shift_data = {
        'job_id': job_id,
        'user_id': request.form['user_id'],
        'note': note,
        'start_time': start_time  # Current time as start time
    }

    # End any ongoing shift for the user before starting a new one
    Shift.end_current_shift(shift_data['user_id'])

    # Save the shift with the start time provided by the user
    Shift.save(shift_data)

    return redirect(f'/show/job/{job_id}')


@app.route('/shift_report', methods=['GET', 'POST'])
def shift_report():
    user_data = {
        "id": session['user_id']
    }

    # Get the number of shifts started today
    today_shifts_count = Shift.get_started_today()

    if request.method == 'POST':
        data = {
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date']
        }

        shifts = Shift.find_shifts_in_date_range(data)

        dateFormat = "%m/%d/%Y %I:%M %p"
        total_elapsed_time = timedelta()  # Initialize a timedelta object

        for shift in shifts:
            if shift.elapsed_time:
                total_elapsed_time += shift.elapsed_time

        # format the total elapsed time
        hours, remainder = divmod(total_elapsed_time.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        total_elapsed_time_hms = '{:02}:{:02}:{:02}'.format(
            int(hours), int(minutes), int(seconds))

        formatted_elapsed_time = '{:02}:{:02}:{:02}'.format(
            int(hours), int(minutes), int(seconds))
        print(formatted_elapsed_time)

        return render_template('shift_report.html', shifts=shifts, user=User.get_by_id(user_data), total_elapsed_time_hms=total_elapsed_time_hms, formatted_elapsed_time=total_elapsed_time, start_date=data['start_date'], end_date=data['end_date'])
    else:
        return render_template('shift_report.html', user=User.get_by_id(user_data))


@app.route('/punch_out/<int:shift_id>', methods=['POST'])
def punch_out(shift_id):
    if 'user_id' not in session:
        # Redirect to login page if no user is logged in
        return redirect('/login')

    # Fetch user details from the database
    user_data = {"id": session['user_id']}
    logged_in_user = User.get_by_id(user_data)

    # Check if the user's department is ADMINISTRATIVE
    if logged_in_user.department != 'ADMINISTRATIVE':
        # Redirect with an error message if the user is not admin
        return redirect('/dashboard', error='Unauthorized access')

    # Method to end the shift with a specific ID in the Shift model
    Shift.update(shift_id)
    return redirect('/dashboard')


@app.route('/end_of_day')
def end_of_day():
    if 'user_id' not in session:
        return redirect('/logout')

    user_data = {
        "id": session['user_id']
    }

    logged_in_user = User.get_by_id(user_data)

    # Method to fetch ongoing shifts from the Shift model
    ongoing_shifts = Shift.get_ongoing()
    return render_template('eod_punch.html', ongoing_shifts=ongoing_shifts, logged_in_user=logged_in_user)


@app.route('/edit/shift/<int:id>')
def edit_shift(id):
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id": id

    }
    user_data = {
        "id": session['user_id']
    }

    shift = Shift.get_one_shift(data)

    job_data = {
        "id": shift.job_id  # assuming Shift model has a job_id field

    }

    job = Job.get_one(job_data)  # fetch the job associated with this shift

    return render_template("edit_shift.html", shift=shift, job=job, user=User.get_by_id(user_data))


@app.route('/update/shift/<int:id>', methods=['POST'])
def update_shift(id):
    if 'user_id' not in session:
        return redirect('/logout')

    if not Shift.validate_shift(request.form):
        return redirect(f'/update/shift/{id}')

    created_at = request.form.get('created_at')
    updated_at = request.form.get('updated_at')

    # Parse the datetime if not None and not empty
    if created_at and created_at.strip():
        created_at = datetime.strptime(created_at, '%Y-%m-%dT%H:%M')
    if updated_at and updated_at.strip():
        updated_at = datetime.strptime(updated_at, '%Y-%m-%dT%H:%M')
    else:
        updated_at = None  # Allow updated_at to be None

    data = {
        "id": id,
        "job_id": request.form['job_id'],
        "created_at": created_at,
        "updated_at": updated_at,  # Can be None
        "note": request.form['note']
    }

    Shift.update_time(data)

    job_id = request.form['job_id']
    return redirect(f'/show/job/{job_id}')


@app.route('/update/punchout/<int:id>', methods=['POST'])
def update_time(id):
    print("Form data received:", request.form)
    if 'user_id' not in session:
        return redirect('/logout')

    if not Shift.validate_shift(request.form):
        return redirect(f'/update/shift/{id}')

    # Retrieve the start time (created_at) from the form
    created_at = request.form.get('created_at')
    if created_at:
        try:
            created_at = datetime.strptime(created_at, '%Y-%m-%dT%H:%M')
        except ValueError:
            # Handle the case where the date format is incorrect
            # Redirect back with an error message, or log the error
            return redirect(f'/update/shift/{id}', error='Invalid start date format')

    # Check if updated_at is provided and parse it
    updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Prepare data for updating the shift
    data = {
        "id": id,
        "job_id": request.form.get('job_id'),
        "created_at": created_at,
        "updated_at": updated_at,
        # Include other fields as necessary
    }

    # Update the shift in the database
    Shift.update(data)

    # Redirect to the job's page after updating
    job_id = request.form.get('job_id')
    return redirect(f'/show/job/{job_id}')


@app.route('/admin/assign_shift', methods=['GET', 'POST'])
def assign_shift():
    if 'user_id' not in session:
        return redirect('/logout')
    if request.method == 'POST':
        # Validation for the form
        if not Shift.validate_shift(request.form):
            return redirect('/admin/assign_shift')
        Shift.save(request.form)  # Save the form data to the Shift model
        return redirect('/dashboard')
    else:
        users = User.get_all()  # Get all users
        jobs = Job.get_all()  # Get all jobs
        return render_template('assign_shift.html', users=users, jobs=jobs)


@app.route('/shift/show')
def show_all_shifts():
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id": id
    }
    user_data = {
        "id": session['user_id']
    }
    return render_template("see_shifts.html", shifts=Shift.get_all(), user=User.get_by_id(user_data))


@app.route('/user/shifts/<int:id>')
def show_user_shifts(id):
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id": id
    }

    user_data = {
        "id": session['user_id']
    }

    return render_template("viewUserShifts.html",
                           thisShift=User.getUserWithShifts(data),
                           dtf=dateFormat,
                           user=User.get_by_id(user_data))


@app.route('/manage_shifts')
def manage_shifts():
    if 'user_id' not in session:
        # or redirect to a different page if user is not admin
        return redirect('/logout')

    return render_template('manage_shifts.html')


@app.route('/destroy/shift/<int:id>', methods=['POST'])
def destroy_shift(id):
    if 'user_id' not in session:
        return redirect('/logout')
    print(f"Deleting shift with id: {id}")

    data = {
        "id": id
    }
    Shift.destroy(data)
    return redirect('/dashboard')
