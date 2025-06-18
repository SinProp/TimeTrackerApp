from flask import render_template, redirect, session, request, flash
from flask_app import app
from flask_app.models.job import Job
from flask_app.models.user import User
from flask_app.models.shift import Shift
from datetime import datetime, timedelta, timezone
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
    if (logged_in_user.department == 'ADMINISTRATIVE'):
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
        flash("Shift validation failed.", "danger")
        return redirect('/add/shift/' + request.form.get('job_id', ''))

    job_id = request.form['job_id']
    note = request.form.get('note', '')

    if 'user_id' in request.form and request.form['user_id'] != str(session['user_id']):
        logged_in_user_data = {"id": session['user_id']}
        logged_in_user = User.get_by_id(logged_in_user_data)
        if logged_in_user.department == 'ADMINISTRATIVE':
            user_id = request.form['user_id']
        else:
            flash("Unauthorized action: Cannot start shift for another user.", "danger")
            user_id = session['user_id']
    else:
        user_id = session['user_id']

    start_time_str = request.form.get('start_time')
    if start_time_str:
        try:
            if start_time_str.endswith('Z'):
                start_time_str = start_time_str.replace('Z', '+00:00')
            start_time_dt_aware = datetime.fromisoformat(start_time_str)
            start_time = start_time_dt_aware.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            flash("Invalid start time format received from form.", "danger")
            return redirect(f'/add/shift/{job_id}')
    else:
        start_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    shift_data = {
        'job_id': job_id,
        'user_id': user_id,
        'note': note,
        'start_time': start_time
    }

    Shift.end_current_shift(user_id)

    try:
        Shift.save(shift_data)
    except Exception as e:
        print(f"Error saving shift: {e}")
        flash("An error occurred while saving the shift. Please try again.", "danger")
        return redirect(f'/add/shift/{job_id}')

    return redirect(f'/show/job/{job_id}')


def render_shift_report(start_date, end_date):
    user_data = {"id": session['user_id']}
    data = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d')
    }

    shifts = Shift.find_shifts_in_date_range(data)

    total_elapsed_time = timedelta()
    for shift in shifts:
        if shift.elapsed_time:
            total_elapsed_time += shift.elapsed_time

    hours, remainder = divmod(total_elapsed_time.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    total_elapsed_time_hms = '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))

    formatted_elapsed_time = total_elapsed_time_hms

    return render_template('shift_report.html',
                           shifts=shifts,
                           user=User.get_by_id(user_data),
                           total_elapsed_time_hms=total_elapsed_time_hms,
                           formatted_elapsed_time=formatted_elapsed_time,
                           start_date=data['start_date'],
                           end_date=data['end_date'])


@app.route('/shift_report', methods=['GET', 'POST'])
def shift_report():
    user_data = {"id": session['user_id']}

    if request.method == 'POST':
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        return render_shift_report(start_date, end_date)
    else:
        return render_template('shift_report.html', user=User.get_by_id(user_data))


@app.route('/shift_report/last_week')
def shift_report_last_week():
    if 'user_id' not in session:
        return redirect('/logout')
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=7)
    return render_shift_report(start_date, end_date)


@app.route('/shift_report/last_two_weeks')
def shift_report_last_two_weeks():
    if 'user_id' not in session:
        return redirect('/logout')
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=14)
    return render_shift_report(start_date, end_date)


@app.route('/shift_report/last_month')
def shift_report_last_month():
    if 'user_id' not in session:
        return redirect('/logout')
    today = datetime.utcnow().date()
    first_day_current = today.replace(day=1)
    end_date = first_day_current - timedelta(days=1)
    start_date = end_date.replace(day=1)
    return render_shift_report(start_date, end_date)


@app.route('/shift_report/current_month')
def shift_report_current_month():
    if 'user_id' not in session:
        return redirect('/logout')
    today = datetime.utcnow().date()
    start_date = today.replace(day=1)
    end_date = today
    return render_shift_report(start_date, end_date)


@app.route('/punch_out/<int:shift_id>', methods=['POST'])
def punch_out(shift_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_data = {"id": session['user_id']}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != 'ADMINISTRATIVE':
        return redirect('/dashboard', error='Unauthorized access')

    shift_data = {
        "id": shift_id
    }

    Shift.update(shift_data)
    return redirect('/dashboard')


@app.route('/end_of_day')
def end_of_day():
    if 'user_id' not in session:
        return redirect('/logout')

    user_data = {
        "id": session['user_id']
    }

    logged_in_user = User.get_by_id(user_data)

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
        "id": shift.job_id

    }

    job = Job.get_one(job_data)
    jobs = Job.get_all()

    return render_template("edit_shift.html", shift=shift, job=job, jobs=jobs, user=User.get_by_id(user_data))


@app.route('/update/shift/<int:id>', methods=['POST'])
def update_shift(id):
    if 'user_id' not in session:
        return redirect('/logout')

    if not Shift.validate_shift(request.form):
        return redirect(f'/update/shift/{id}')

    created_at = request.form.get('created_at')
    updated_at = request.form.get('updated_at')

    if created_at and created_at.strip():
        created_at = datetime.strptime(created_at, '%Y-%m-%dT%H:%M')
    if updated_at and updated_at.strip():
        updated_at = datetime.strptime(updated_at, '%Y-%m-%dT%H:%M')
    else:
        updated_at = None

    job_id = request.form.get('job_id')
    print(f"Received job_id: {job_id}")

    data = {
        "id": id,
        "job_id": job_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "note": request.form['note']
    }

    Shift.update_time(data)

    return redirect(f'/show/job/{job_id}')


@app.route('/update/punchout/<int:id>', methods=['POST'])
def update_time(id):
    print("Form data received:", request.form)
    if 'user_id' not in session:
        return redirect('/logout')

    if not Shift.validate_shift(request.form):
        return redirect(f'/update/shift/{id}')

    created_at = request.form.get('created_at')
    if created_at:
        try:
            created_at = datetime.strptime(created_at, '%Y-%m-%dT%H:%M')
        except ValueError:
            return redirect(f'/update/shift/{id}', error='Invalid start date format')

    updated_at = request.form.get('updated_at')
    if updated_at:
        try:
            updated_at = datetime.strptime(updated_at, '%Y-%m-%dT%H:%M')
        except ValueError:
            return redirect(f'/update/shift/{id}', error='Invalid end date format')

    data = {
        "id": id,
        "job_id": request.form.get('job_id'),
        "created_at": created_at,
        "updated_at": updated_at,
    }

    Shift.update(data)

    job_id = request.form.get('job_id')
    return redirect(f'/show/job/{job_id}')


@app.route('/admin/assign_shift', methods=['GET', 'POST'])
def assign_shift():
    if 'user_id' not in session:
        return redirect('/logout')

    user_data = {"id": session['user_id']}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != 'ADMINISTRATIVE':
        flash("Unauthorized access.", "danger")
        return redirect('/dashboard')

    if request.method == 'POST':
        if not Shift.validate_shift(request.form):
            users = User.get_all()
            jobs = Job.get_all()
            return render_template('assign_shift.html', users=users, jobs=jobs, logged_in_user=logged_in_user)

        user_id = request.form.get('user_id')
        job_id = request.form.get('job_id')
        note = request.form.get('note', '')
        start_time_str = request.form.get('start_time')

        if not user_id or not job_id or not start_time_str:
            flash("User, Job, and Start Time are required.", "danger")
            users = User.get_all()
            jobs = Job.get_all()
            return render_template('assign_shift.html', users=users, jobs=jobs, logged_in_user=logged_in_user)

        try:
            start_time_dt = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            start_time = start_time_dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            flash("Invalid start time format. Please use YYYY-MM-DDTHH:MM.", "danger")
            users = User.get_all()
            jobs = Job.get_all()
            return render_template('assign_shift.html', users=users, jobs=jobs, logged_in_user=logged_in_user)

        shift_data = {
            'user_id': user_id,
            'job_id': job_id,
            'note': note,
            'start_time': start_time
        }

        Shift.end_current_shift(user_id)

        try:
            Shift.save(shift_data)
            flash("Shift assigned successfully.", "success")
        except Exception as e:
            print(f"Error saving assigned shift: {e}")
            flash("An error occurred while assigning the shift.", "danger")
            users = User.get_all()
            jobs = Job.get_all()
            return render_template('assign_shift.html', users=users, jobs=jobs, logged_in_user=logged_in_user)

        return redirect('/dashboard')
    else:
        users = User.get_all()
        jobs = Job.get_all()
        return render_template('assign_shift.html', users=users, jobs=jobs, logged_in_user=logged_in_user)


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


@app.route('/batch_assign_shifts', methods=['GET', 'POST'])
def batch_assign_shifts():
    if 'user_id' not in session:
        return redirect('/logout')

    user_data = {"id": session['user_id']}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != 'ADMINISTRATIVE':
        flash("You don't have permission to access this feature", "danger")
        return redirect('/dashboard')

    if request.method == 'POST':
        user_ids = request.form.getlist('user_ids')
        job_id = request.form['job_id']
        note = request.form.get('note', '')

        try:
            start_time_str = request.form.get('start_time')
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            start_time = start_time.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            flash("Invalid start time format", "danger")
            return redirect('/batch_assign_shifts')

        if not user_ids:
            flash('Please select at least one employee', 'danger')
            return redirect('/batch_assign_shifts')

        if not job_id:
            flash('Please select a job', 'danger')
            return redirect('/batch_assign_shifts')

        job_data = {"id": int(job_id)}
        job_info = Job.get_one(job_data)

        success_count = 0
        error_count = 0

        for user_id in user_ids:
            shift_data = {
                'job_id': job_id,
                'user_id': user_id,
                'note': note,
                'start_time': start_time
            }

            try:
                Shift.end_current_shift(user_id)
                Shift.save(shift_data)
                success_count += 1
            except Exception as e:
                print(f"Error creating shift for user {user_id}: {str(e)}")
                error_count += 1

        if success_count > 0:
            if error_count > 0:
                flash(f'Failed to create {error_count} shifts', 'danger')

            return render_template('batch_confirmation.html',
                                   success_count=success_count,
                                   job=job_info)
        else:
            flash("No shifts were created", "danger")
            return redirect('/batch_assign_shifts')

    users = User.get_all()
    jobs = Job.get_all()

    department_counts = {}
    for user in users:
        if user.department not in department_counts:
            department_counts[user.department] = 0
        department_counts[user.department] += 1

    return render_template('batch_assign_shifts.html',
                           users=users,
                           jobs=jobs,
                           logged_in_user=logged_in_user,
                           department_counts=department_counts)


@app.route('/batch_punch_out', methods=['POST'])
def batch_punch_out():
    if 'user_id' not in session:
        return redirect('/logout')
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != 'ADMINISTRATIVE':
        flash("You don't have permission to access this feature", "danger")
        return redirect('/dashboard')
    shift_ids = request.form.getlist("shift_ids")
    success_count = 0
    for shift_id in shift_ids:
        try:
            Shift.update({"id": shift_id})
            success_count += 1
        except Exception as e:
            print(f"Error punching out shift {shift_id}: {str(e)}")
    flash(f"Successfully punched out {success_count} shifts", "success")
    return redirect('/end_of_day')


@app.route('/todays_activity')
def todays_activity():
    if 'user_id' not in session:
        return redirect('/logout')

    user_data = {
        "id": session['user_id']
    }

    logged_in_user = User.get_by_id(user_data)
    
    # Get all jobs for the edit modal dropdown
    all_jobs = Job.get_all()

    ongoing_shifts = Shift.get_ongoing()

    for shift in ongoing_shifts:
        job_data = {"id": shift.job_id}
        shift.job = Job.get_one(job_data)

    shifts_started_today = Shift.get_started_today()

    today = datetime.now().strftime('%Y-%m-%d')
    data = {
        'start_date': today,
        'end_date': today
    }
    completed_shifts = Shift.find_shifts_in_date_range(data)

    shifts_ended_today = 0
    if completed_shifts:
        shifts_ended_today = sum(
            1 for shift in completed_shifts if shift.updated_at and shift.updated_at.date() == datetime.now().date())
    print(f"DEBUG: Shifts ended today count: {shifts_ended_today}")

    active_workers = len(ongoing_shifts)

    department_breakdown = {}
    if ongoing_shifts:
        for shift in ongoing_shifts:
            dept = shift.creator.department
            if dept not in department_breakdown:
                department_breakdown[dept] = 0
            department_breakdown[dept] += 1

    total_hours_today = 0
    if completed_shifts:
        for shift in completed_shifts:
            if shift.elapsed_time:
                try:
                    parts = str(shift.elapsed_time).split(':')
                    if len(parts) == 3:
                        hours = int(parts[0])
                        minutes = int(parts[1])
                        seconds = int(float(parts[2]))
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                        total_hours_today += total_seconds / 3600
                    else:
                        print(
                            f"DEBUG: Invalid elapsed_time format for shift {shift.id}: {shift.elapsed_time}")
                except (ValueError, IndexError) as e:
                    print(
                        f"DEBUG: Error processing elapsed_time for shift {shift.id}: {shift.elapsed_time}, Error: {e}")

    hours, remainder = divmod(total_hours_today * 3600, 3600)
    minutes, seconds = divmod(remainder, 60)
    formatted_hours = '{:02}:{:02}:{:02}'.format(
        int(hours), int(minutes), int(seconds))
    print(f"DEBUG: Total hours today (formatted): {formatted_hours}")

    return render_template('todays_activity.html',
                           ongoing_shifts=ongoing_shifts,
                           shifts_started_today=shifts_started_today,
                           shifts_ended_today=shifts_ended_today,
                           active_workers=active_workers,
                           department_breakdown=department_breakdown,
                           total_hours=formatted_hours,
                           all_jobs=all_jobs,
                           user=logged_in_user)


@app.route('/update/active-shift/<int:id>', methods=['POST'])
def update_active_shift(id):
    """Quick update route for active shifts from today's activity page"""
    if 'user_id' not in session:
        return redirect('/logout')

    if not Shift.validate_shift(request.form):
        flash("Invalid shift data provided.", "danger")
        return redirect('/todays_activity')

    # Get the shift to verify it's active
    shift_data = {"id": id}
    shift = Shift.get_one_shift(shift_data)
    
    # Only allow editing of active shifts (those without updated_at)
    if shift.updated_at is not None:
        flash("Cannot edit completed shifts from this page.", "warning")
        return redirect('/todays_activity')

    created_at = request.form.get('created_at')
    if created_at and created_at.strip():
        created_at = datetime.strptime(created_at, '%Y-%m-%dT%H:%M')
    else:
        created_at = shift.created_at

    job_id = request.form.get('job_id')
    note = request.form.get('note', '')

    update_data = {
        "id": id,
        "job_id": job_id,
        "created_at": created_at,
        "updated_at": None,  # Keep it active
        "note": note
    }

    try:
        Shift.update_time(update_data)
        flash("Active shift updated successfully!", "success")
    except Exception as e:
        print(f"Error updating active shift: {e}")
        flash("An error occurred while updating the shift.", "danger")

    return redirect('/todays_activity')
