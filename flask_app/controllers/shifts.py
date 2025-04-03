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
        # Assuming validate_shift doesn't need changes for this fix
        # If validation depends on start_time format, it might need adjustment too.
        # For now, redirecting based on original logic.
        # Consider what page is appropriate if validation fails.
        # Maybe redirect back to the form page with an error message.
        flash("Shift validation failed.", "danger") # Example flash message
        # Determine the correct redirect target, e.g., back to the form
        # return redirect('/add/shift/' + request.form.get('job_id', '')) # Example redirect
        # For now, keeping original redirect logic if validation exists
        return redirect('/add/shift/' + request.form.get('job_id', '')) # Adjust if needed

    job_id = request.form['job_id']
    note = request.form.get('note', '')
    user_id = request.form['user_id']

    # Use the start time provided by the user, if available
    start_time_str = request.form.get('start_time')
    if start_time_str:
        try:
            # Handle potential 'Z' for UTC timezone if present
            if start_time_str.endswith('Z'):
                start_time_str = start_time_str[:-1] + '+00:00'
            # Parse the ISO format string (or similar format like YYYY-MM-DDTHH:MM)
            # Using fromisoformat is generally robust for ISO 8601 formats
            start_time_dt = datetime.fromisoformat(start_time_str)
            # Format it to MySQL's expected format
            start_time = start_time_dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            # Handle cases where the date format is incorrect
            flash("Invalid start time format provided.", "danger")
            # Redirect back to the form or an appropriate error page
            return redirect(f'/add/shift/{job_id}')
    else:
        # If start time not provided, use current server time
        start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    shift_data = {
        'job_id': job_id,
        'user_id': user_id,
        'note': note,
        'start_time': start_time # Use the correctly formatted time
    }

    # End any ongoing shift for the user before starting a new one
    Shift.end_current_shift(user_id)

    # Save the shift
    try:
        Shift.save(shift_data)
    except Exception as e:
        # Log the error and inform the user
        print(f"Error saving shift: {e}") # Log the specific DB error
        flash("An error occurred while saving the shift. Please try again.", "danger")
        return redirect(f'/add/shift/{job_id}')

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

        return render_template('shift_report.html', shifts=shifts, user=User.get_by_id(user_data), total_elapsed_time_hms=total_elapsed_time_hms, formatted_elapsed_time=formatted_elapsed_time, start_date=data['start_date'], end_date=data['end_date'])
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

    # Create a data dictionary with the shift ID
    shift_data = {
        "id": shift_id
    }
    
    # Method to end the shift with a specific ID in the Shift model
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
    jobs = Job.get_all()  # Fetch all jobs to populate the dropdown

    return render_template("edit_shift.html", shift=shift, job=job, jobs=jobs, user=User.get_by_id(user_data))


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

    job_id = request.form.get('job_id')
    print(f"Received job_id: {job_id}")  # Debugging statement

    data = {
        "id": id,
        "job_id": job_id,
        "created_at": created_at,
        "updated_at": updated_at,  # Can be None
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
    updated_at = request.form.get('updated_at')
    if updated_at:
        try:
            updated_at = datetime.strptime(updated_at, '%Y-%m-%dT%H:%M')
        except ValueError:
            # Handle the case where the date format is incorrect
            # Redirect back with an error message, or log the error
            return redirect(f'/update/shift/{id}', error='Invalid end date format')

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


@app.route('/batch_assign_shifts', methods=['GET', 'POST'])
def batch_assign_shifts():
    if 'user_id' not in session:
        return redirect('/logout')

    # Check if user is admin
    user_data = {"id": session['user_id']}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != 'ADMINISTRATIVE':
        flash("You don't have permission to access this feature", "danger")
        return redirect('/dashboard')

    if request.method == 'POST':
        # Process the form submission
        user_ids = request.form.getlist('user_ids')
        job_id = request.form['job_id']
        note = request.form.get('note', '')

        # Validate start_time format
        try:
            start_time_str = request.form.get('start_time')
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            # Convert to the format expected by our database
            start_time = start_time.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            flash("Invalid start time format", "danger")
            return redirect('/batch_assign_shifts')

        # Validation
        if not user_ids:
            flash('Please select at least one employee', 'danger')
            return redirect('/batch_assign_shifts')

        if not job_id:
            flash('Please select a job', 'danger')
            return redirect('/batch_assign_shifts')

        # Get job info for the success message
        job_data = {"id": int(job_id)}
        job_info = Job.get_one(job_data)

        # Create shifts for all selected users
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
                # End any ongoing shift for this user
                Shift.end_current_shift(user_id)

                # Create a new shift
                Shift.save(shift_data)
                success_count += 1
            except Exception as e:
                # Log the error
                print(f"Error creating shift for user {user_id}: {str(e)}")
                error_count += 1

        # Prepare success/error message
        if success_count > 0:
            # Instead of redirecting back, render the confirmation page
            if error_count > 0:
                flash(f'Failed to create {error_count} shifts', 'danger')

            # Pass data to the confirmation template
            return render_template('batch_confirmation.html',
                                  success_count=success_count,
                                  job=job_info)
        else:
            flash("No shifts were created", "danger")
            return redirect('/batch_assign_shifts')

    # GET request - show the form
    users = User.get_all()
    jobs = Job.get_all()

    # Add department distribution statistics for UX enhancement
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
            # End the shift by updating updated_at to current time
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
    
    # Get all ongoing shifts
    ongoing_shifts = Shift.get_ongoing()
    
    # Fetch job details for each shift
    for shift in ongoing_shifts:
        job_data = {"id": shift.job_id}
        shift.job = Job.get_one(job_data)
    
    # Get count of shifts started today
    shifts_started_today = Shift.get_started_today()
    
    # Get shifts that ended today
    today = datetime.now().strftime('%Y-%m-%d')
    data = {
        'start_date': today,
        'end_date': today
    }
    completed_shifts = Shift.find_shifts_in_date_range(data)
    
    # Count of completed shifts today
    shifts_ended_today = 0
    if completed_shifts:
        shifts_ended_today = sum(1 for shift in completed_shifts if shift.updated_at and shift.updated_at.date() == datetime.now().date())
    print(f"DEBUG: Shifts ended today count: {shifts_ended_today}") # <-- Add this debug print
    
    # Total active workers
    active_workers = len(ongoing_shifts)
    
    # Department-wise breakdown of active workers
    department_breakdown = {}
    if ongoing_shifts:
        for shift in ongoing_shifts:
            dept = shift.creator.department
            if dept not in department_breakdown:
                department_breakdown[dept] = 0
            department_breakdown[dept] += 1
    
    # Calculate total hours logged today
    total_hours_today = 0
    if completed_shifts:
        for shift in completed_shifts:
            if shift.elapsed_time:
                # Convert elapsed time string to seconds
                try: # Add try-except block for robustness
                    parts = str(shift.elapsed_time).split(':')
                    if len(parts) == 3:
                        hours = int(parts[0])
                        minutes = int(parts[1])
                        # Handle potential float seconds (e.g., '0:00:59.999999')
                        seconds = int(float(parts[2]))
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                        total_hours_today += total_seconds / 3600  # Convert to hours
                    else:
                        print(f"DEBUG: Invalid elapsed_time format for shift {shift.id}: {shift.elapsed_time}")
                except (ValueError, IndexError) as e:
                    print(f"DEBUG: Error processing elapsed_time for shift {shift.id}: {shift.elapsed_time}, Error: {e}")
    
    # Format for display
    hours, remainder = divmod(total_hours_today * 3600, 3600)  # Convert back to seconds for formatting
    minutes, seconds = divmod(remainder, 60)
    formatted_hours = '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))
    print(f"DEBUG: Total hours today (formatted): {formatted_hours}") # <-- Add this debug print
    
    return render_template('todays_activity.html',
                          ongoing_shifts=ongoing_shifts,
                          shifts_started_today=shifts_started_today,
                          shifts_ended_today=shifts_ended_today,
                          active_workers=active_workers,
                          department_breakdown=department_breakdown,
                          total_hours=formatted_hours,
                          user=logged_in_user)
