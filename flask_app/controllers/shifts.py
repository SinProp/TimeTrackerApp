from flask import render_template,redirect,session,request, flash
from flask_app import app
from flask_app.models.job import Job
from flask_app.models.user import User
from flask_app.models.shift import Shift

@app.route('/add/shift')
def new_shift():
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id":session['user_id']
    }
    return render_template('new_shift.html', logged_in_user = User.get_by_id(data))

@app.route('/create/shift',methods=['POST'])
def create_shift():
    if 'user_id' not in session:
        return redirect('/logout')
    if not Job.validate_job(request.form):
        return redirect('/add/shift')
    data = {
        "shift start": request.form["shift_start"],
        "shift_end": request.form["shift_end"],
        "user_id": session["user_id"]
    }
    Shift.save(data)
    return redirect('/dashboard')

@app.route('/edit/shift/<int:id>')
def edit_shift(id):
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id":id
    }
    user_data = {
        "id":session['user_id']
    }
    return render_template("edit_shift.html",job = Job.get_one(data),user=User.get_by_id(user_data))


@app.route('/update/shift',methods=['POST'])
def update_shift():
    if 'user_id' not in session:
        return redirect('/logout')
    if not Job.validate_job(request.form):
        return redirect(f'/update/shift/{{shift.id}}')
    data = {
        "shift start": request.form["shift_start"],
        "shift_end": request.form["shift_end"],
        "id": request.form['id']
    }
    Shift.update(data)
    return redirect('/dashboard')

@app.route('/shift/show')
def show_all_shifts():
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id":id
    }
    user_data = {
        "id": session['user_id']
    }
    return render_template("see_shifts.html",shifts = Shift.get_all(),user=User.get_by_id(user_data))

@app.route('/destroy/shift/<int:id>')
def destroy_shift(id):
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id":id
    }
    Shift.destroy(data)
    return redirect('/dashboard')