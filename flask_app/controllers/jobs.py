from flask import render_template, redirect, session, request, flash, url_for, Blueprint, jsonify
import smartsheet
from flask_app import app
from flask_app.models.job import Job
from flask_app.models.user import User
from flask_app.models.shift import Shift
from datetime import datetime
from ..config.config import ss_client

dateFormat = "%m/%d/%Y %I:%M %p"

webhooks_blueprint = Blueprint('webhooks', __name__)


@webhooks_blueprint.route('/webhooks', methods=['POST'])
def smartsheet_webhook():
    data = request.json
    # Replace with actual column ID for 'Job Status'
    job_status_column_id = '4963616297379716'
    sheet_id = '1954899010316164'  # Replace with your sheet ID

    if data['eventType'] == 'updated' and job_status_column_id in data['columnIds']:
        row_id = data['rowId']
        # Retrieve the updated row data
        row = ss_client.Sheets.get_row(sheet_id, row_id)
        job_data = {
            'im_number': get_cell_by_column_name(row, 'IM Number'),
            'job_name_address': get_cell_by_column_name(row, 'Job Name / Address'),
            'general_contractor': get_cell_by_column_name(row, 'G.C.'),
            'job_scope': get_cell_by_column_name(row, 'Scope'),
        }
        job = Job(**job_data)
        job.save_to_db()
        return jsonify({'status': 'success'}), 200
    return jsonify({'status': 'no action'}), 200


def get_cell_by_column_name(row, column_name):
    column_id = get_column_id_by_name(column_name)
    return row.get_column(column_id).value if column_id else None


def get_column_id_by_name(column_name):
    # Logic to retrieve the column ID based on the column name from the sheet
    # You would need to implement caching or a dictionary mapping to avoid excessive API calls
    pass


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


@app.route('/edit/job/<int:id>')
def edit_job(id):
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id": id
    }
    user_data = {
        "id": session['user_id']
    }
    return render_template("edit_job.html",
                           job=Job.get_one(data),
                           user=User.get_by_id(user_data))


@app.route('/update/job/<int:id>', methods=['POST'])
def update_job(id):
    if 'user_id' not in session:
        return redirect('/logout')
    if not Job.validate_job(request.form):
        return redirect(f'/update/job/{{job.id}}')

    # Check if the "status" field is in the form data
    if 'status' in request.form:
        status = 1  # Active
    else:
        status = 0  # Inactive

    data = {
        "im_number": request.form["im_number"],
        "general_contractor": request.form["general_contractor"],
        "job_scope": request.form["job_scope"],
        "estimated_hours": request.form["estimated_hours"],
        "context": request.form["context"],
        "id": request.form['id'],
        "status": 1 if 'status' in request.form else 0
    }
    Job.update(data)
    return redirect('/dashboard')


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

    return render_template("view_job.html",
                           thisJob=thisJob,
                           dtf=dateFormat,
                           job=Job.get_one(data),
                           user=User.get_by_id(user_data))


@app.route('/destroy/job/<int:id>')
def destroy_job(id):
    if 'user_id' not in session:
        return redirect('/logout')
    data = {
        "id": id
    }
    Job.destroy(data)
    return redirect('/dashboard')
