from flask import (
    render_template,
    redirect,
    session,
    request,
    flash,
    url_for,
    jsonify,
    Response,
)
from flask_app import app
from flask_app.models.job import Job
from flask_app.models.user import User
from flask_app.models.shift import (
    Shift,
    format_seconds_as_hms,
    count_workdays,
    enrich_with_possible_hours,
    HOURS_PER_WORKDAY,
)
from datetime import datetime, timedelta, timezone
import csv
import io

dateFormat = "%m/%d/%Y %I:%M %p"


def normalize_employee_id(val):
    """Normalize employee_id from request: return int or None."""
    if val in (None, "", "all"):
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def parse_date_range(req):
    """
    Extract and validate start_date/end_date from a Flask request (GET or POST).

    Returns:
        (start_date, end_date) as date objects on success
        (None, None) and flashes error on failure
    """
    if req.method == "POST":
        start_str = req.form.get("start_date")
        end_str = req.form.get("end_date")
    else:
        start_str = req.args.get("start_date")
        end_str = req.args.get("end_date")

    if not start_str or not end_str:
        return None, None

    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
        return None, None

    if end_date < start_date:
        flash("End date must be after start date.", "danger")
        return None, None

    return start_date, end_date


def get_quarter_dates(quarter, year=None):
    """
    Get start and end dates for a calendar year quarter.

    Args:
        quarter: 1-4
        year: defaults to current year

    Returns:
        (start_date, end_date) as date objects
    """
    if year is None:
        year = datetime.now().year

    quarters = {
        1: (datetime(year, 1, 1).date(), datetime(year, 3, 31).date()),
        2: (datetime(year, 4, 1).date(), datetime(year, 6, 30).date()),
        3: (datetime(year, 7, 1).date(), datetime(year, 9, 30).date()),
        4: (datetime(year, 10, 1).date(), datetime(year, 12, 31).date()),
    }
    return quarters.get(quarter, (None, None))


@app.route("/add/shift/<int:id>")
def new_shift(id):
    if "user_id" not in session:
        return redirect("/logout")
    data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(data)

    # Check if the logged-in user is an admin
    if logged_in_user.department == "ADMINISTRATIVE":
        users = User.get_all()  # Get all users if the user is an admin
    else:
        users = None  # Set users to None if not an admin

    job_data = {"id": id}

    return render_template(
        "new_shift.html",
        job=Job.get_one(job_data),
        logged_in_user=User.get_by_id(data),
        users=users,
    )


@app.route("/create/shift", methods=["POST"])
def create_shift():
    if "user_id" not in session:
        return redirect("/logout")

    if not Shift.validate_shift(request.form):
        flash("Shift validation failed.", "danger")
        return redirect("/add/shift/" + request.form.get("job_id", ""))

    job_id = request.form["job_id"]
    note = request.form.get("note", "")

    if "user_id" in request.form and request.form["user_id"] != str(session["user_id"]):
        logged_in_user_data = {"id": session["user_id"]}
        logged_in_user = User.get_by_id(logged_in_user_data)
        if logged_in_user.department == "ADMINISTRATIVE":
            user_id = request.form["user_id"]
        else:
            flash("Unauthorized action: Cannot start shift for another user.", "danger")
            user_id = session["user_id"]
    else:
        user_id = session["user_id"]

    # Check if this is a hidden job and make it visible if production user clocks in
    job_data = {"id": job_id}
    job = Job.get_one(job_data)
    if job and not job.visible_to_production:
        # Get the user who is clocking in
        clocking_user = User.get_by_id({"id": user_id})
        if clocking_user and clocking_user.department != "ADMINISTRATIVE":
            # Production user clocking into hidden job - make it visible
            Job.make_visible_to_production(job_id)
            print(f"Job {job.im_number} made visible to production after clock-in")

    start_time_str = request.form.get("start_time")
    if start_time_str:
        try:
            if start_time_str.endswith("Z"):
                start_time_str = start_time_str.replace("Z", "+00:00")
            start_time_dt_aware = datetime.fromisoformat(start_time_str)
            start_time = start_time_dt_aware.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            flash("Invalid start time format received from form.", "danger")
            return redirect(f"/add/shift/{job_id}")
    else:
        start_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    shift_data = {
        "job_id": job_id,
        "user_id": user_id,
        "note": note,
        "start_time": start_time,
    }

    Shift.end_current_shift(user_id)

    try:
        Shift.save(shift_data)
    except Exception as e:
        print(f"Error saving shift: {e}")
        flash("An error occurred while saving the shift. Please try again.", "danger")
        return redirect(f"/add/shift/{job_id}")

    return redirect(f"/show/job/{job_id}")


def render_shift_report(start_date, end_date, employee_id=None):
    user_data = {"id": session["user_id"]}
    data = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
    }

    shifts = Shift.find_shifts_in_date_range(data, employee_id=employee_id)
    all_jobs = Job.get_all_jobs()

    total_elapsed_time = timedelta()
    for shift in shifts:
        if shift.elapsed_time:
            total_elapsed_time += shift.elapsed_time

    total_elapsed_time_hms = format_seconds_as_hms(total_elapsed_time.total_seconds())

    # Build back-link to quarterly report if coming from drill-down
    back_to_quarterly = None
    if employee_id:
        back_to_quarterly = url_for(
            "quarterly_report",
            start_date=data["start_date"],
            end_date=data["end_date"],
        )

    return render_template(
        "shift_report.html",
        shifts=shifts,
        user=User.get_by_id(user_data),
        total_elapsed_time_hms=total_elapsed_time_hms,
        start_date=data["start_date"],
        end_date=data["end_date"],
        all_jobs=all_jobs,
        employee_id=employee_id,
        back_to_quarterly=back_to_quarterly,
    )


@app.route("/shift_report", methods=["GET", "POST"])
def shift_report():
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")

    start_date, end_date = parse_date_range(request)
    employee_id = normalize_employee_id(
        request.args.get("employee_id") or request.form.get("employee_id")
    )

    if start_date and end_date:
        return render_shift_report(start_date, end_date, employee_id=employee_id)
    else:
        return render_template("shift_report.html", user=logged_in_user)


@app.route("/shift_report/last_week")
def shift_report_last_week():
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=7)
    return render_shift_report(start_date, end_date)


@app.route("/shift_report/last_two_weeks")
def shift_report_last_two_weeks():
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=14)
    return render_shift_report(start_date, end_date)


@app.route("/shift_report/last_month")
def shift_report_last_month():
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")
    today = datetime.utcnow().date()
    first_day_current = today.replace(day=1)
    end_date = first_day_current - timedelta(days=1)
    start_date = end_date.replace(day=1)
    return render_shift_report(start_date, end_date)


@app.route("/shift_report/current_month")
def shift_report_current_month():
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")
    today = datetime.utcnow().date()
    start_date = today.replace(day=1)
    end_date = today
    return render_shift_report(start_date, end_date)


# ============ Quarterly Report ============
#
#  /quarterly_report (GET/POST) ── admin only
#      │
#      ├─ Quarter preset (Q1-Q4) OR custom date range
#      ├─ Optional employee_id filter
#      ├─ Query: find_shifts_in_date_range → group_by_employee → group_by_department
#      │
#      ▼
#  quarterly_report.html ──[View →]──▶ /shift_report?employee_id=X
#  /quarterly_report/csv ──▶ CSV download


@app.route("/quarterly_report", methods=["GET", "POST"])
def quarterly_report():
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")

    all_users = User.get_all()
    current_year = datetime.now().year

    start_date, end_date = parse_date_range(request)
    employee_id = normalize_employee_id(
        request.args.get("employee_id") or request.form.get("employee_id")
    )

    if start_date and end_date:
        data = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        }

        shifts = Shift.find_shifts_in_date_range(data, employee_id=employee_id)
        employee_data = Shift.group_shifts_by_employee(shifts)

        # Enrich with possible hours + utilization %
        workdays, capped_end = count_workdays(start_date, end_date)
        enrich_with_possible_hours(employee_data, workdays)

        department_data = Shift.group_by_department(employee_data)

        # Calculate grand totals
        total_seconds = sum(e["total_seconds"] for e in employee_data)
        total_shifts = sum(e["shift_count"] for e in employee_data)
        total_hours_formatted = format_seconds_as_hms(total_seconds)

        # Possible hours grand totals (per-employee baseline)
        possible_seconds = workdays * HOURS_PER_WORKDAY * 3600
        total_possible_formatted = format_seconds_as_hms(possible_seconds)
        overall_utilization = None
        if possible_seconds > 0 and employee_data:
            avg_seconds = total_seconds / len(employee_data)
            overall_utilization = round(avg_seconds / possible_seconds * 100, 1)

        # Did we cap the end date at today?
        end_was_capped = capped_end < end_date

        # Get filtered employee name for header
        filtered_employee_name = None
        if employee_id and employee_data:
            filtered_employee_name = f"{employee_data[0]['user'].first_name} {employee_data[0]['user'].last_name}"

        return render_template(
            "quarterly_report.html",
            user=logged_in_user,
            department_data=department_data,
            total_hours=total_hours_formatted,
            total_shifts=total_shifts,
            total_employees=len(employee_data),
            start_date=data["start_date"],
            end_date=data["end_date"],
            all_users=all_users,
            current_year=current_year,
            employee_id=employee_id,
            filtered_employee_name=filtered_employee_name,
            total_possible_hours=total_possible_formatted,
            workdays=workdays,
            overall_utilization=overall_utilization,
            end_was_capped=end_was_capped,
            capped_end=capped_end.strftime("%m/%d/%Y") if end_was_capped else None,
        )

    return render_template(
        "quarterly_report.html",
        user=logged_in_user,
        all_users=all_users,
        current_year=current_year,
    )


@app.route("/quarterly_report/q/<int:quarter>")
def quarterly_report_preset(quarter):
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")
    if quarter < 1 or quarter > 4:
        flash("Invalid quarter.", "danger")
        return redirect("/quarterly_report")
    start_date, end_date = get_quarter_dates(quarter)
    return redirect(
        url_for(
            "quarterly_report",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
    )


@app.route("/quarterly_report/csv")
def quarterly_report_csv():
    """Download quarterly report as CSV (utf-8-sig BOM for Excel compatibility)."""
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")

    start_date, end_date = parse_date_range(request)
    employee_id = normalize_employee_id(request.args.get("employee_id"))

    if not start_date or not end_date:
        flash("Date range required for CSV export.", "danger")
        return redirect("/quarterly_report")

    data = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
    }
    shifts = Shift.find_shifts_in_date_range(data, employee_id=employee_id)
    employee_data = Shift.group_shifts_by_employee(shifts)

    # Enrich with possible hours for CSV
    workdays, _ = count_workdays(start_date, end_date)
    enrich_with_possible_hours(employee_data, workdays)

    # Sanitize cell values to prevent CSV/Excel formula injection.
    # Values starting with =, +, -, @ are interpreted as formulas by Excel.
    def sanitize_csv_cell(val):
        s = str(val)
        if s and s[0] in ("=", "+", "-", "@"):
            return "'" + s
        return s

    # Build CSV — explicitly exclude password, only include relevant fields
    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM for Excel
    writer = csv.writer(output)
    writer.writerow(
        [
            "Employee",
            "Department",
            "Total Shifts",
            "Total Hours",
            "Possible Hours",
            "Utilization %",
        ]
    )

    for emp in employee_data:
        util_display = (
            f"{emp['utilization_pct']}%"
            if emp["utilization_pct"] is not None
            else "N/A"
        )
        possible_display = emp.get("possible_hours_formatted", "N/A") or "N/A"
        writer.writerow(
            [
                sanitize_csv_cell(f"{emp['user'].first_name} {emp['user'].last_name}"),
                sanitize_csv_cell(emp["user"].department),
                emp["shift_count"],
                emp["total_hours_formatted"],
                possible_display,
                util_display,
            ]
        )

    csv_content = output.getvalue()
    output.close()

    filename = f"quarterly_report_{data['start_date']}_to_{data['end_date']}.csv"
    return Response(
        csv_content,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/punch_out/<int:shift_id>", methods=["POST"])
def punch_out(shift_id):
    if "user_id" not in session:
        return redirect("/login")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != "ADMINISTRATIVE":
        return redirect("/dashboard", error="Unauthorized access")

    shift_data = {"id": shift_id}

    Shift.update(shift_data)
    return redirect("/dashboard")


@app.route("/end_of_day")
def end_of_day():
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}

    logged_in_user = User.get_by_id(user_data)

    ongoing_shifts = Shift.get_ongoing()
    return render_template(
        "eod_punch.html", ongoing_shifts=ongoing_shifts, logged_in_user=logged_in_user
    )


@app.route("/edit/shift/<int:id>")
def edit_shift(id):
    if "user_id" not in session:
        return redirect("/logout")
    data = {"id": id}
    user_data = {"id": session["user_id"]}

    shift = Shift.get_one_shift(data)

    job_data = {"id": shift.job_id}

    job = Job.get_one(job_data)
    jobs = Job.get_all()

    return render_template(
        "edit_shift.html",
        shift=shift,
        job=job,
        jobs=jobs,
        user=User.get_by_id(user_data),
    )


@app.route("/update/shift/<int:id>", methods=["POST"])
def update_shift(id):
    if "user_id" not in session:
        return redirect("/logout")

    if not Shift.validate_shift(request.form):
        # TODO: This redirect should be improved to handle validation errors from the shift report modal
        return redirect(f"/edit/shift/{id}")

    job_id = request.form.get("job_id")
    created_at_str = request.form.get("created_at")
    if created_at_str:
        try:
            created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Invalid start date format.", "danger")
            # TODO: Redirect back to the source page
            return redirect(f"/edit/shift/{id}")
    else:
        created_at = None

    updated_at_str = request.form.get("updated_at")
    if updated_at_str:
        try:
            updated_at = datetime.strptime(updated_at_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Invalid end date format.", "danger")
            # TODO: Redirect back to the source page
            return redirect(f"/edit/shift/{id}")
    else:
        updated_at = None

    data = {
        "id": id,
        "job_id": job_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "note": request.form["note"],
    }

    Shift.update_time(data)

    if request.form.get("source_page") == "shift_report":
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        employee_id = request.form.get("employee_id")
        params = {"start_date": start_date, "end_date": end_date}
        if employee_id:
            params["employee_id"] = employee_id
        return redirect(url_for("shift_report", **params))

    return redirect(f"/show/job/{job_id}")


@app.route("/update/punchout/<int:id>", methods=["POST"])
def update_time(id):
    print("Form data received:", request.form)
    if "user_id" not in session:
        return redirect("/logout")

    if not Shift.validate_shift(request.form):
        return redirect(f"/update/shift/{id}")

    created_at = request.form.get("created_at")
    if created_at:
        try:
            created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M")
        except ValueError:
            return redirect(f"/update/shift/{id}", error="Invalid start date format")

    updated_at = request.form.get("updated_at")
    if updated_at:
        try:
            updated_at = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M")
        except ValueError:
            return redirect(f"/update/shift/{id}", error="Invalid end date format")

    data = {
        "id": id,
        "job_id": request.form.get("job_id"),
        "created_at": created_at,
        "updated_at": updated_at,
    }

    Shift.update(data)

    job_id = request.form.get("job_id")
    return redirect(f"/show/job/{job_id}")


@app.route("/admin/assign_shift", methods=["GET", "POST"])
def assign_shift():
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")

    if request.method == "POST":
        if not Shift.validate_shift(request.form):
            users = User.get_all()
            jobs = Job.get_all()
            return render_template(
                "assign_shift.html",
                users=users,
                jobs=jobs,
                logged_in_user=logged_in_user,
            )

        user_id = request.form.get("user_id")
        job_id = request.form.get("job_id")
        note = request.form.get("note", "")
        start_time_str = request.form.get("start_time")

        if not user_id or not job_id or not start_time_str:
            flash("User, Job, and Start Time are required.", "danger")
            users = User.get_all()
            jobs = Job.get_all()
            return render_template(
                "assign_shift.html",
                users=users,
                jobs=jobs,
                logged_in_user=logged_in_user,
            )

        try:
            start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
            start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            flash("Invalid start time format. Please use YYYY-MM-DDTHH:MM.", "danger")
            users = User.get_all()
            jobs = Job.get_all()
            return render_template(
                "assign_shift.html",
                users=users,
                jobs=jobs,
                logged_in_user=logged_in_user,
            )

        shift_data = {
            "user_id": user_id,
            "job_id": job_id,
            "note": note,
            "start_time": start_time,
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
            return render_template(
                "assign_shift.html",
                users=users,
                jobs=jobs,
                logged_in_user=logged_in_user,
            )

        return redirect("/dashboard")
    else:
        users = User.get_all()
        jobs = Job.get_all()
        return render_template(
            "assign_shift.html", users=users, jobs=jobs, logged_in_user=logged_in_user
        )


@app.route("/shift/show")
def show_all_shifts():
    if "user_id" not in session:
        return redirect("/logout")
    data = {"id": id}
    user_data = {"id": session["user_id"]}
    return render_template(
        "see_shifts.html", shifts=Shift.get_all(), user=User.get_by_id(user_data)
    )


@app.route("/user/shifts/<int:id>")
def show_user_shifts(id):
    if "user_id" not in session:
        return redirect("/logout")
    data = {"id": id}

    user_data = {"id": session["user_id"]}

    return render_template(
        "viewUserShifts.html",
        thisShift=User.getUserWithShifts(data),
        dtf=dateFormat,
        user=User.get_by_id(user_data),
    )


@app.route("/manage_shifts")
def manage_shifts():
    if "user_id" not in session:
        return redirect("/logout")

    return render_template("manage_shifts.html")


@app.route("/destroy/shift/<int:id>", methods=["POST"])
def destroy_shift(id):
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")

    data = {"id": id}
    Shift.destroy(data)
    return redirect("/dashboard")


@app.route("/batch_assign_shifts", methods=["GET", "POST"])
def batch_assign_shifts():
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        flash("You don't have permission to access this feature", "danger")
        return redirect("/dashboard")

    if request.method == "POST":
        user_ids = request.form.getlist("user_ids")
        job_id = request.form["job_id"]
        note = request.form.get("note", "")

        try:
            start_time_str = request.form.get("start_time")
            start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
            start_time = start_time.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            flash("Invalid start time format", "danger")
            return redirect("/batch_assign_shifts")

        if not user_ids:
            flash("Please select at least one employee", "danger")
            return redirect("/batch_assign_shifts")

        if not job_id:
            flash("Please select a job", "danger")
            return redirect("/batch_assign_shifts")

        job_data = {"id": int(job_id)}
        job_info = Job.get_one(job_data)

        try:
            # OPTIMIZED: End all current shifts in one query instead of N queries
            Shift.bulk_end_current_shifts(user_ids)

            # OPTIMIZED: Build all shift data and insert in one query instead of N queries
            shifts_data = [
                {
                    "job_id": job_id,
                    "user_id": user_id,
                    "note": note,
                    "start_time": start_time,
                }
                for user_id in user_ids
            ]
            success_count = Shift.bulk_save(shifts_data)

            return render_template(
                "batch_confirmation.html", success_count=success_count, job=job_info
            )
        except Exception as e:
            print(f"Error in batch shift assignment: {str(e)}")
            flash("An error occurred while assigning shifts", "danger")
            return redirect("/batch_assign_shifts")

    users = User.get_all()
    jobs = Job.get_all()

    department_counts = {}
    for user in users:
        if user.department not in department_counts:
            department_counts[user.department] = 0
        department_counts[user.department] += 1

    return render_template(
        "batch_assign_shifts.html",
        users=users,
        jobs=jobs,
        logged_in_user=logged_in_user,
        department_counts=department_counts,
    )


@app.route("/batch_punch_out", methods=["POST"])
def batch_punch_out():
    if "user_id" not in session:
        return redirect("/logout")
    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)
    if logged_in_user.department != "ADMINISTRATIVE":
        flash("You don't have permission to access this feature", "danger")
        return redirect("/dashboard")
    shift_ids = request.form.getlist("shift_ids")
    success_count = 0
    for shift_id in shift_ids:
        try:
            Shift.update({"id": shift_id})
            success_count += 1
        except Exception as e:
            print(f"Error punching out shift {shift_id}: {str(e)}")
    flash(f"Successfully punched out {success_count} shifts", "success")
    return redirect("/end_of_day")


@app.route("/todays_activity")
def todays_activity():
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}

    logged_in_user = User.get_by_id(user_data)

    # Get all jobs for the edit modal dropdown
    all_jobs = Job.get_all()

    # OPTIMIZED: get_ongoing() now includes job data via JOIN, no need for N+1 loop
    ongoing_shifts = Shift.get_ongoing()

    # Get list of user IDs with ongoing shifts for missing workers calculation
    ongoing_user_ids = (
        [shift.creator.id for shift in ongoing_shifts] if ongoing_shifts else []
    )

    # Get missing workers (on roster but not clocked in)
    missing_workers = User.get_missing_workers_today(ongoing_user_ids)

    shifts_started_today = Shift.get_started_today()

    today = datetime.now().strftime("%Y-%m-%d")
    data = {"start_date": today, "end_date": today}
    completed_shifts = Shift.find_shifts_in_date_range(data)

    shifts_ended_today = 0
    if completed_shifts:
        shifts_ended_today = sum(
            1
            for shift in completed_shifts
            if shift.updated_at and shift.updated_at.date() == datetime.now().date()
        )
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
                    parts = str(shift.elapsed_time).split(":")
                    if len(parts) == 3:
                        hours = int(parts[0])
                        minutes = int(parts[1])
                        seconds = int(float(parts[2]))
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                        total_hours_today += total_seconds / 3600
                    else:
                        print(
                            f"DEBUG: Invalid elapsed_time format for shift {shift.id}: {shift.elapsed_time}"
                        )
                except (ValueError, IndexError) as e:
                    print(
                        f"DEBUG: Error processing elapsed_time for shift {shift.id}: {shift.elapsed_time}, Error: {e}"
                    )

    hours, remainder = divmod(total_hours_today * 3600, 3600)
    minutes, seconds = divmod(remainder, 60)
    formatted_hours = "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))
    print(f"DEBUG: Total hours today (formatted): {formatted_hours}")

    return render_template(
        "todays_activity.html",
        ongoing_shifts=ongoing_shifts,
        shifts_started_today=shifts_started_today,
        shifts_ended_today=shifts_ended_today,
        active_workers=active_workers,
        department_breakdown=department_breakdown,
        total_hours=formatted_hours,
        all_jobs=all_jobs,
        user=logged_in_user,
        missing_workers=missing_workers,
    )


@app.route("/update/active-shift/<int:id>", methods=["POST"])
def update_active_shift(id):
    """Quick update route for active shifts from today's activity page"""
    if "user_id" not in session:
        return redirect("/logout")

    if not Shift.validate_shift(request.form):
        flash("Invalid shift data provided.", "danger")
        return redirect("/todays_activity")

    # Get the shift to verify it's active
    shift_data = {"id": id}
    shift = Shift.get_one_shift(shift_data)

    # Only allow editing of active shifts (those without updated_at)
    if shift.updated_at is not None:
        flash("Cannot edit completed shifts from this page.", "warning")
        return redirect("/todays_activity")

    created_at = request.form.get("created_at")
    if created_at and created_at.strip():
        created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M")
    else:
        created_at = shift.created_at

    job_id = request.form.get("job_id")
    note = request.form.get("note", "")

    update_data = {
        "id": id,
        "job_id": job_id,
        "created_at": created_at,
        "updated_at": None,  # Keep it active
        "note": note,
    }

    try:
        Shift.update_time(update_data)
        flash("Active shift updated successfully!", "success")
    except Exception as e:
        print(f"Error updating active shift: {e}")
        flash("An error occurred while updating the shift.", "danger")

    return redirect("/todays_activity")


# ============ Stale Shift Remediation ============


@app.route("/admin/stale_shifts")
def stale_shifts():
    """
    Admin page to view and fix stale shifts (open shifts > 12 hours).
    """
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")

    # Get stale shifts (default threshold: 12 hours)
    stale_shifts_list = Shift.get_stale_shifts(hours_threshold=12)

    recommended_batch_sizes = [5, 25]

    return render_template(
        "stale_shifts.html",
        stale_shifts=stale_shifts_list,
        logged_in_user=logged_in_user,
        shift_count=len(stale_shifts_list),
        recommended_batch_sizes=recommended_batch_sizes,
    )


@app.route("/admin/fix_stale_shift/<int:shift_id>", methods=["POST"])
def fix_stale_shift(shift_id):
    """
    Fix a single stale shift by setting its end time to 3:30 PM on the day it started.
    """
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")

    try:
        Shift.fix_stale_shift(shift_id)
        flash("Shift fixed successfully! End time set to 3:30 PM.", "success")
    except Exception as e:
        print(f"Error fixing stale shift {shift_id}: {e}")
        flash("An error occurred while fixing the shift.", "danger")

    return redirect("/admin/stale_shifts")


@app.route("/admin/fix_all_stale_shifts", methods=["POST"])
def fix_all_stale_shifts():
    """
    Fix all stale shifts by setting their end times to 3:30 PM on the day they started.
    """
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")

    try:
        # Require explicit typed confirmation for all "Fix All" runs.
        # Server-side enforcement — browser confirm() dialogs are bypassable via curl.
        bulk_confirmation = (request.form.get("bulk_confirmation") or "").strip()
        if bulk_confirmation != "FIX ALL":
            flash(
                "Bulk run blocked. Type FIX ALL exactly to confirm full remediation.",
                "danger",
            )
            return redirect("/admin/stale_shifts")

        fixed_count = Shift.fix_all_stale_shifts(hours_threshold=12)
        flash(f"Successfully fixed {fixed_count} stale shifts!", "success")
    except Exception as e:
        print(f"Error fixing all stale shifts: {e}")
        flash("An error occurred while fixing stale shifts.", "danger")

    return redirect("/admin/stale_shifts")


@app.route("/admin/fix_stale_shifts_batch", methods=["POST"])
def fix_stale_shifts_batch():
    """
    Fix stale shifts in a controlled batch to allow safer progressive remediation.
    """
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")

    batch_size_raw = request.form.get("batch_size", "10")
    try:
        batch_size = int(batch_size_raw)
    except (TypeError, ValueError):
        flash("Batch size must be a whole number.", "danger")
        return redirect("/admin/stale_shifts")

    if batch_size < 1 or batch_size > 250:
        flash("Batch size must be between 1 and 250.", "danger")
        return redirect("/admin/stale_shifts")

    try:
        fixed_count = Shift.fix_stale_shifts_batch(
            batch_size=batch_size, hours_threshold=12
        )
        if fixed_count > 0:
            flash(
                f"Pilot batch complete: fixed {fixed_count} stale shift(s) (oldest first).",
                "success",
            )
        else:
            flash("No stale shifts were fixed. There may be none remaining.", "warning")
    except Exception as e:
        print(f"Error fixing stale shifts batch: {e}")
        flash("An error occurred while fixing the stale shift batch.", "danger")

    return redirect("/admin/stale_shifts")


@app.route("/admin/fix_negative_durations", methods=["POST"])
def fix_negative_durations():
    """
    Fix all shifts with negative durations (where end time < start time).
    This corrects corrupted data from the old auto-end logic.
    """
    if "user_id" not in session:
        return redirect("/logout")

    user_data = {"id": session["user_id"]}
    logged_in_user = User.get_by_id(user_data)

    if logged_in_user.department != "ADMINISTRATIVE":
        flash("Unauthorized access.", "danger")
        return redirect("/dashboard")

    try:
        fixed_count = Shift.fix_negative_duration_shifts()
        if fixed_count > 0:
            flash(
                f"Successfully fixed {fixed_count} shifts with negative durations!",
                "success",
            )
        else:
            flash("No shifts with negative durations found.", "info")
    except Exception as e:
        print(f"Error fixing negative duration shifts: {e}")
        flash("An error occurred while fixing shifts.", "danger")

    return redirect("/admin/stale_shifts")


# ============ Worker Dismissal API ============


@app.route("/api/dismiss-worker", methods=["POST"])
def dismiss_worker():
    """
    API endpoint to dismiss a worker from the 'Yet to Clock In' list for today.
    Stores dismissal server-side so it's visible to all users.
    """
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json()
    if not data or "user_id" not in data:
        return jsonify({"success": False, "error": "Missing user_id"}), 400

    worker_id = data["user_id"]
    dismissed_by = session["user_id"]

    try:
        User.dismiss_worker_today(worker_id, dismissed_by)
        return jsonify({"success": True, "message": "Worker dismissed for today"})
    except Exception as e:
        print(f"Error dismissing worker {worker_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/undismiss-worker", methods=["POST"])
def undismiss_worker():
    """
    API endpoint to restore a worker to the 'Yet to Clock In' list.
    """
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json()
    if not data or "user_id" not in data:
        return jsonify({"success": False, "error": "Missing user_id"}), 400

    worker_id = data["user_id"]

    try:
        User.undismiss_worker_today(worker_id)
        return jsonify({"success": True, "message": "Worker restored to list"})
    except Exception as e:
        print(f"Error undismissing worker {worker_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dismissed-workers", methods=["GET"])
def get_dismissed_workers():
    """
    API endpoint to get list of dismissed worker IDs for today.
    """
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        dismissed_ids = User.get_dismissed_worker_ids_today()
        return jsonify({"success": True, "dismissed_ids": dismissed_ids})
    except Exception as e:
        print(f"Error getting dismissed workers: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
