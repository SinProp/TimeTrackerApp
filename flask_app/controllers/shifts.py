from flask import render_template, redirect, session, request, flash
from flask_app import app
from flask_app.models.job import Job
from flask_app.models.user import User
from flask_app.models.shift import Shift
from datetime import datetime
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
    Shift.save(request.form)
    return redirect(f'/show/job/{job_id}')


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
    return render_template("edit_shift.html", shift=Shift.get_one_shift(data), user=User.get_by_id(user_data))


@app.route('/update/shift/<int:id>', methods=['POST'])
def update_shift(id):
    if 'user_id' not in session:
        return redirect('/logout')
    if not Shift.validate_shift(request.form):
        return redirect(f'/update/shift/{{shift.id}}')
    data = {

        "id": request.form['id'],
        "job_id": request.form['job_id'],
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
        "created_at": created_at_mysql_format,
        "updated_at": updated_at_mysql_format
    }
    Shift.update_time(data)
    return redirect('/dashboard')


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
