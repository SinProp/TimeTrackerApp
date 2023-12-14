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
    job_data = {
        "id": id
    }

    return render_template('new_shift.html', job=Job.get_one(job_data), logged_in_user=User.get_by_id(data))


@app.route('/create/shift', methods=['POST'])
def create_shift():
    if 'user_id' not in session:
        return redirect('/logout')
    if not Shift.validate_shift(request.form):
        return redirect('/add/shift')

    job_id = request.form['job_id']
    # Get the value of the 'note' field from the form
    note = request.form.get('note', '')

    shift_data = request.form.copy()  # Make a copy of the form data
    # Assign the 'note' value to the 'note' key in the form data
    shift_data['note'] = note

    # End any ongoing shift for the user before starting a new one
    user_id = session['user_id']
    Shift.end_current_shift(user_id)

    Shift.save(shift_data)  # Save the modified form data with the 'note' value

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
        return redirect(f'/update/shift/{{shift.id}}')
    data = {

        "id": request.form['id'],
        "job_id": request.form['job_id'],
        # "note": request.form['note']
    }
    Shift.update(data)

    job_id = request.form['job_id']
    print(f"Job ID: {job_id}")

    return redirect(f'/show/job/{job_id}')


@app.route('/update/time/<int:id>', methods=['POST'])
def update_time(id):
    if 'user_id' not in session:
        return redirect('/logout')

    created_at = request.form.get('created_at')
    updated_at = request.form.get('updated_at')

    try:
        created_at = datetime.strptime(created_at, '%Y-%m-%dT%H:%M')
        updated_at = datetime.strptime(updated_at, '%Y-%m-%dT%H:%M')

        created_at_mysql_format = created_at.strftime('%Y-%m-%d %H:%M')
        updated_at_mysql_format = updated_at.strftime('%Y-%m-%d %H:%M')
    except ValueError as e:
        # Handle the case where the datetime input is not valid
        # You can return an error message or redirect to an error page
        print(f"Exception: {e}")
        print(
            f"Invalid input value: created_at: {created_at}, updated_at: {updated_at}")
        return redirect(f'/edit/shift/{id}')

    if not Shift.validate_shift(request.form):
        return redirect(f'/update/time/{id}')
    data = {
        "id": request.form['id'],
        "note": request.form['note'],
        "created_at": created_at_mysql_format,
        "updated_at": updated_at_mysql_format
    }
    Shift.update_time(data)
    return redirect('/dashboard')


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
