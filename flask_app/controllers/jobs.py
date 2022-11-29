from flask import render_template,redirect,session,request, flash
from flask_app import app
from flask_app.models.job import Job
from flask_app.models.user import User

@app.route('/new/job')
def new_job():
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id":session['user_id']
    }
    return render_template('new_job.html', logged_in_user = User.get_by_id(data))

@app.route('/create/job',methods=['POST'])
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
        "user_id": session["user_id"]
    }
    Job.save(data)
    return redirect('/dashboard',jobs = Job.get_all(), user=User.get_by_id(data) )

@app.route('/edit/job/<int:id>')
def edit_job(id):
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id":id
    }
    user_data = {
        "id":session['user_id']
    }
    return render_template("edit_job.html",edit = Job.get_one(data),user=User.get_by_id(user_data))


@app.route('/update/job',methods=['POST'])
def update_job():
    if 'user_id' not in session:
        return redirect('/logout')
    if not Job.validate_job(request.form):
        return redirect('/new/job')
    data = {
        "im_number": request.form["im_number"],
        "general_contractor": request.form["general_contractor"],
        "job_scope": request.form["job_scope"],
        "estimated_hours": request.form["estimated_hours"],
        "id": request.form['id']
    }
    Job.update(data)
    return redirect('/dashboard')

@app.route('/job/show')
def show_all_jobs():
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id":id
    }
    user_data = {
        "id": session['user_id']
    }
    return render_template("my_jobs.html",jobs = Job.get_all(),user=User.get_by_id(user_data))

@app.route('/destroy/job/<int:id>')
def destroy_job(id):
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id":id
    }
    Job.destroy(data)
    return redirect('/dashboard')