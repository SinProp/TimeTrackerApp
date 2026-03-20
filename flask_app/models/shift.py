from flask_app.config.mysqlconnection import connectToMySQL
from flask import flash
from ..models import user, job
from collections import defaultdict


from datetime import datetime, timedelta, date

dateFormat = "%m/%d/%Y %I:%M %p"

HOURS_PER_WORKDAY = 6.5


def format_seconds_as_hms(total_seconds):
    """Convert a number of seconds to HH:MM:SS string."""
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))


def count_workdays(start_date, end_date):
    """
    Count weekdays (Mon-Fri) between start_date and end_date (inclusive).
    Caps end_date at today to avoid counting future days.

    Args:
        start_date: date object
        end_date: date object

    Returns:
        tuple: (workdays: int, capped_end: date)
    """
    today = date.today()
    capped_end = min(end_date, today)
    if capped_end < start_date:
        return (0, capped_end)
    count = 0
    current = start_date
    while current <= capped_end:
        if current.weekday() < 5:  # Mon=0 .. Fri=4
            count += 1
        current += timedelta(days=1)
    return (count, capped_end)


def enrich_with_possible_hours(employee_data, workdays):
    """
    Add possible_seconds, possible_hours_formatted, and utilization_pct
    to each employee dict in place.

    Args:
        employee_data: list of dicts from group_shifts_by_employee()
        workdays: int — number of workdays in the range
    """
    possible_seconds = workdays * HOURS_PER_WORKDAY * 3600
    possible_formatted = format_seconds_as_hms(possible_seconds)
    for emp in employee_data:
        emp["possible_seconds"] = possible_seconds
        emp["possible_hours_formatted"] = possible_formatted
        if possible_seconds > 0:
            emp["utilization_pct"] = round(
                emp["total_seconds"] / possible_seconds * 100, 1
            )
        else:
            emp["utilization_pct"] = None


class Shift:
    db_name = "man_hours"

    def __init__(self, db_data):
        self.id = db_data["id"]
        self.job_shifts = []
        self.created_at = db_data["created_at"]
        self.updated_at = db_data["updated_at"]
        self.job_id = db_data["job_id"]
        self.user_id = db_data["user_id"]
        self.note = db_data["note"]
        self.creator = None
        self.elapsed_time = db_data.get("elapsed_time")

    @classmethod
    def save(cls, data):
        query = "INSERT INTO shifts (created_at, updated_at, job_id, user_id, note) VALUES (%(start_time)s, NULL, %(job_id)s, %(user_id)s, %(note)s);"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def get_all_shifts(cls, data):
        query = "SELECT * FROM shifts LEFT JOIN jobs on jobs.id = job_id;"
        results = connectToMySQL(cls.db_name).query_db(query)
        all_shifts = []
        for row in results:
            job_data = {
                "id": row["id"],
                "im_number": row["im_number"],
                "general_contractor": row["general_contractor"],
                "job_scope": row["job_scope"],
                "estimated_hours": row["estimated_hours"],
                "user_id": row["user_id"],
                "context": row["context"],
                "created_at": row["jobs.created_at"],
                "updated_at": row["jobs.updated_at"],
                "status": row["status"],
            }
            new_shift = cls(row)
            new_shift.job = job.Job(job_data)
            all_shifts.append(new_shift)
        return all_shifts

    @classmethod
    def find_shifts_in_date_range(cls, data, employee_id=None):
        """
        Find completed shifts in a date range. Filters on updated_at (punch-out time).
        NOTE: This reports shifts by when they ENDED, not when they started.
        For same-day construction shifts this is equivalent; cross-day shifts
        are attributed to the day/quarter they ended.

        Args:
            data: dict with start_date, end_date (YYYY-MM-DD strings)
            employee_id: optional — filter to a single employee's shifts
        """
        # Ensure start_date and end_date cover the entire day
        start_date_str = data["start_date"] + " 00:00:00"
        end_date_str = data["end_date"] + " 23:59:59"

        query = """
            SELECT
                shifts.*,
                users.id as creator_id, users.first_name, users.last_name, users.email, users.password as creator_password,
                users.department, users.created_at as creator_created_at, users.updated_at as creator_updated_at,
                jobs.id as job_id_alias, jobs.im_number, jobs.general_contractor, jobs.job_scope, jobs.estimated_hours,
                jobs.user_id as job_user_id, jobs.context, jobs.created_at as job_created_at, jobs.updated_at as job_updated_at,
                jobs.status,
                TIMEDIFF(shifts.updated_at, shifts.created_at) as elapsed_time
            FROM shifts
            JOIN users ON shifts.user_id = users.id
            LEFT JOIN jobs ON shifts.job_id = jobs.id
            WHERE shifts.updated_at BETWEEN %(start_date)s AND %(end_date)s
            AND shifts.updated_at IS NOT NULL"""

        query_data = {"start_date": start_date_str, "end_date": end_date_str}

        if employee_id:
            query += "\n            AND shifts.user_id = %(employee_id)s"
            query_data["employee_id"] = employee_id

        query += ";"

        results = connectToMySQL(cls.db_name).query_db(query, query_data)

        if not results:
            return []

        shifts = []
        for row in results:
            this_shift = cls(row)

            user_data = {
                "id": row["creator_id"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "email": row["email"],
                "password": row["creator_password"],
                "department": row["department"],
                "created_at": row["creator_created_at"],
                "updated_at": row["creator_updated_at"],
            }
            this_shift.creator = user.User(user_data)

            if row.get("im_number") is not None:
                job_data = {
                    "id": row["job_id_alias"],
                    "im_number": row["im_number"],
                    "general_contractor": row["general_contractor"],
                    "job_scope": row["job_scope"],
                    "estimated_hours": row["estimated_hours"],
                    "user_id": row["job_user_id"],
                    "context": row["context"],
                    "created_at": row["job_created_at"],
                    "updated_at": row["job_updated_at"],
                    "status": row["status"],
                }
                this_shift.job = job.Job(job_data)
            else:
                this_shift.job = None

            shifts.append(this_shift)

        return shifts

    # ============ Quarterly Report Aggregation ============
    #
    #  shifts[] ──▶ group_shifts_by_employee() ──▶ { user_id: { user, shifts, total } }
    #                       │
    #                       ▼
    #             group_by_department() ──▶ { dept: [ employee_data ] }
    #

    @staticmethod
    def group_shifts_by_employee(shifts):
        """
        Group a flat list of shifts by employee, calculating per-employee totals.

        Args:
            shifts: list of Shift objects (from find_shifts_in_date_range)

        Returns:
            List of dicts sorted by total_hours descending:
            [{ 'user': User, 'shifts': [Shift], 'total_seconds': float,
               'total_hours_formatted': str, 'shift_count': int }]
        """
        grouped = defaultdict(
            lambda: {
                "user": None,
                "shift_count": 0,
                "total_seconds": 0,
            }
        )

        for shift in shifts:
            if not shift.creator:
                continue  # skip orphaned shifts (user deleted or LEFT JOIN miss)
            uid = shift.creator.id
            if grouped[uid]["user"] is None:
                grouped[uid]["user"] = shift.creator
            grouped[uid]["shift_count"] += 1
            if shift.elapsed_time:
                try:
                    grouped[uid]["total_seconds"] += shift.elapsed_time.total_seconds()
                except AttributeError:
                    parts = str(shift.elapsed_time).split(":")
                    if len(parts) == 3:
                        h, m, s = int(parts[0]), int(parts[1]), int(float(parts[2]))
                        grouped[uid]["total_seconds"] += h * 3600 + m * 60 + s

        result = []
        for uid, data in grouped.items():
            data["total_hours_formatted"] = format_seconds_as_hms(data["total_seconds"])
            result.append(data)

        # Default sort: total hours descending
        result.sort(key=lambda x: x["total_seconds"], reverse=True)
        return result

    @staticmethod
    def group_by_department(employee_data_list):
        """
        Group per-employee data by department with subtotals.

        Args:
            employee_data_list: list from group_shifts_by_employee()

        Returns:
            List of dicts, each representing a department:
            [{ 'department': str, 'employees': [...], 'total_seconds': float,
               'total_hours_formatted': str, 'shift_count': int }]
        """
        dept_map = defaultdict(
            lambda: {
                "employees": [],
                "total_seconds": 0,
                "shift_count": 0,
                "possible_seconds": 0,
            }
        )

        for emp in employee_data_list:
            dept = emp["user"].department or "UNKNOWN"
            dept_map[dept]["employees"].append(emp)
            dept_map[dept]["total_seconds"] += emp["total_seconds"]
            dept_map[dept]["shift_count"] += emp["shift_count"]
            dept_map[dept]["possible_seconds"] += emp.get("possible_seconds", 0)

        result = []
        for dept_name, data in dept_map.items():
            data["department"] = dept_name
            data["total_hours_formatted"] = format_seconds_as_hms(data["total_seconds"])
            if data["possible_seconds"] > 0:
                data["possible_hours_formatted"] = format_seconds_as_hms(
                    data["possible_seconds"]
                )
                data["utilization_pct"] = round(
                    data["total_seconds"] / data["possible_seconds"] * 100, 1
                )
            else:
                data["possible_hours_formatted"] = None
                data["utilization_pct"] = None
            # Ensure employees sorted by hours descending within each department
            data["employees"].sort(key=lambda x: x["total_seconds"], reverse=True)
            result.append(data)

        # Sort departments alphabetically
        result.sort(key=lambda x: x["department"])
        return result

    @classmethod
    def get_one_shift(cls, data):
        query = "SELECT *, TIMESTAMPDIFF(HOUR, created_at, updated_at) as elapsed_time FROM shifts WHERE id = %(id)s;"
        results = connectToMySQL(cls.db_name).query_db(query, data)
        if len(results) == 0:
            return False
        return cls(results[0])

    @classmethod
    def get_ongoing(cls):
        """
        Get all ongoing shifts (not yet clocked out) started today.
        OPTIMIZED: Now includes job data via JOIN to avoid N+1 queries in controllers.
        """
        query = """
        SELECT shifts.*,
            users.id as user_id, users.first_name, users.last_name, users.email,
            users.password, users.department, users.created_at as users_created_at,
            users.updated_at as users_updated_at,
            jobs.id as job_id_alias, jobs.im_number, jobs.general_contractor, jobs.job_scope,
            jobs.estimated_hours, jobs.user_id as job_user_id, jobs.context,
            jobs.created_at as job_created_at, jobs.updated_at as job_updated_at, jobs.status,
            TIMEDIFF(IFNULL(shifts.updated_at, NOW()), shifts.created_at) as elapsed_time
        FROM shifts
        JOIN users ON shifts.user_id = users.id
        LEFT JOIN jobs ON shifts.job_id = jobs.id
        WHERE shifts.updated_at IS NULL
        AND DATE(shifts.created_at) = CURDATE();  -- Filter for shifts started today
        """
        results = connectToMySQL(cls.db_name).query_db(query)
        ongoing_shifts = []
        for row in results:
            shift_info = {
                "id": row["id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "elapsed_time": row["elapsed_time"],
                "job_id": row["job_id"],
                "user_id": row["user_id"],
                "note": row["note"],
            }
            user_info = {
                "id": row["user_id"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "email": row["email"],
                "password": row["password"],
                "department": row["department"],
                "created_at": row["users_created_at"],
                "updated_at": row["users_updated_at"],
            }
            this_shift = cls(shift_info)
            this_shift.creator = user.User(user_info)

            # OPTIMIZED: Include job data from JOIN instead of separate query
            if row.get("im_number") is not None:
                job_info = {
                    "id": row["job_id_alias"],
                    "im_number": row["im_number"],
                    "general_contractor": row["general_contractor"],
                    "job_scope": row["job_scope"],
                    "estimated_hours": row["estimated_hours"],
                    "user_id": row["job_user_id"],
                    "context": row["context"],
                    "created_at": row["job_created_at"],
                    "updated_at": row["job_updated_at"],
                    "status": row["status"],
                }
                this_shift.job = job.Job(job_info)
            else:
                this_shift.job = None

            ongoing_shifts.append(this_shift)

        return ongoing_shifts

    @classmethod
    def update(cls, data):
        query = "UPDATE shifts SET updated_at = NOW() WHERE id = %(id)s AND updated_at IS NULL;"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def update_time(cls, data):
        query_parts = []
        query_data = {"id": data["id"]}

        if "note" in data:
            query_parts.append("note = %(note)s")
            query_data["note"] = data["note"]

        if "job_id" in data and data["job_id"]:
            query_parts.append("job_id = %(job_id)s")
            query_data["job_id"] = data["job_id"]

        if "created_at" in data and data["created_at"]:
            query_parts.append("created_at = %(created_at)s")
            query_data["created_at"] = data["created_at"]

        if "updated_at" in data:
            if data["updated_at"]:
                query_parts.append("updated_at = %(updated_at)s")
                query_data["updated_at"] = data["updated_at"]
            else:
                query_parts.append("updated_at = NULL")

        if not query_parts:
            return  # Nothing to update

        query = f"UPDATE shifts SET {', '.join(query_parts)} WHERE id = %(id)s;"

        print(f"Executing update query: {query} with data: {query_data}")
        return connectToMySQL(cls.db_name).query_db(query, query_data)

    @classmethod
    def elapsed_time(cls, data):
        query = "SELECT TIMESTAMPDIFF (HOUR, created_at, updated_at) as elapsed_time FROM shifts;"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def end_current_shift(cls, user_id):
        now = datetime.now()
        start_of_day = datetime(now.year, now.month, now.day)

        query = """
        UPDATE shifts
        SET updated_at = %(now)s
        WHERE user_id = %(user_id)s AND created_at >= %(start_of_day)s AND updated_at IS NULL;
        """
        data = {
            "user_id": user_id,
            "now": now.strftime("%Y-%m-%d %H:%M:%S"),
            "start_of_day": start_of_day.strftime("%Y-%m-%d %H:%M:%S"),
        }
        connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def destroy(cls, data):
        print(f"Executing delete query for shift with id: {data['id']}")
        query = "DELETE from shifts where id = %(id)s;"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def get_started_today(cls):
        now = datetime.now()
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
        data = {
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end.strftime("%Y-%m-%d %H:%M:%S"),
        }
        query = "SELECT COUNT(*) as count FROM shifts WHERE created_at BETWEEN %(start)s AND %(end)s;"
        results = connectToMySQL(cls.db_name).query_db(query, data)
        return results[0]["count"] if results else 0

    @staticmethod
    def validate_shift(shift):
        is_valid = True
        return is_valid

    # ============ Bulk Operations (Performance Optimization) ============

    @classmethod
    def bulk_end_current_shifts(cls, user_ids):
        """
        End all ongoing shifts for multiple users in one query.
        This replaces N calls to end_current_shift() with 1 query.

        Args:
            user_ids: List of user IDs whose current shifts should be ended
        """
        if not user_ids:
            return

        now = datetime.now()
        start_of_day = datetime(now.year, now.month, now.day)

        # Build placeholders for IN clause
        placeholders = ",".join(["%s"] * len(user_ids))
        query = f"""
            UPDATE shifts
            SET updated_at = %s
            WHERE user_id IN ({placeholders})
            AND created_at >= %s
            AND updated_at IS NULL;
        """

        # Build params: now, user_ids..., start_of_day
        params = (
            [now.strftime("%Y-%m-%d %H:%M:%S")]
            + list(user_ids)
            + [start_of_day.strftime("%Y-%m-%d %H:%M:%S")]
        )

        connectToMySQL(cls.db_name).query_db(query, tuple(params))

    @classmethod
    def bulk_save(cls, shifts_data):
        """
        Insert multiple shifts in one query.
        Returns the number of shifts inserted.

        This replaces N calls to save() with 1 query.

        Args:
            shifts_data: List of dicts with keys: start_time, job_id, user_id, note
        """
        if not shifts_data:
            return 0

        # Prepare values
        values = []
        for shift in shifts_data:
            values.append(
                (
                    shift["start_time"],
                    None,  # updated_at is NULL for new shifts
                    shift["job_id"],
                    shift["user_id"],
                    shift.get("note", ""),
                )
            )

        # Build multi-row INSERT
        placeholders = ",".join(["(%s, %s, %s, %s, %s)"] * len(values))
        query = f"""
            INSERT INTO shifts (created_at, updated_at, job_id, user_id, note)
            VALUES {placeholders};
        """

        # Flatten the values list for the query
        flat_values = [item for sublist in values for item in sublist]

        result = connectToMySQL(cls.db_name).query_db(query, tuple(flat_values))
        return len(shifts_data) if result is not False else 0

    # ============ Auto-End Shifts at 3:30 PM ============

    @classmethod
    def auto_clock_out_open_shifts_created_today(cls):
        """
        End all open shifts created today using a 3:30 PM baseline.

        Used by weekday 6:00 PM automation. At 6:00 PM, open shifts are closed as:
        - If shift started before 3:30 PM: set updated_at to 3:30 PM same date
        - If shift started at/after 3:30 PM: set updated_at to created_at

        This avoids negative durations while preserving the business rule that
        missing clock-outs map to 3:30 PM baseline when possible.

        Safe/idempotent because it only affects rows where updated_at IS NULL.

        Returns:
            Number of shifts clocked out.
        """
        count_query = """
            SELECT COUNT(*) as count FROM shifts
            WHERE updated_at IS NULL
            AND DATE(created_at) = CURDATE();
        """
        count_result = connectToMySQL(cls.db_name).query_db(count_query)
        count = count_result[0]["count"] if count_result else 0

        if count > 0:
            query = """
                UPDATE shifts
                SET updated_at = CASE
                    WHEN TIME(created_at) < '15:30:00'
                    THEN DATE_FORMAT(created_at, '%%Y-%%m-%%d 15:30:00')
                    ELSE created_at
                END
                WHERE updated_at IS NULL
                AND DATE(created_at) = CURDATE();
            """
            connectToMySQL(cls.db_name).query_db(query)

        return count

    @classmethod
    def auto_end_open_shifts_at_330pm(cls):
        """
        End all open shifts by setting updated_at to 3:30 PM on the same day they were created.
        This runs daily at 3:30 PM EST to auto-clock-out workers.

        IMPORTANT: Only ends shifts that started BEFORE 3:30 PM to avoid negative durations.
        Shifts that started after 3:30 PM are left open for manual handling.

        Returns a summary of how many shifts were ended.
        """
        # Count how many shifts will be ended BEFORE updating
        # Only count shifts that started BEFORE 3:30 PM to avoid negative durations
        count_query = """
            SELECT COUNT(*) as count FROM shifts
            WHERE updated_at IS NULL
            AND DATE(created_at) = CURDATE()
            AND TIME(created_at) < '15:30:00';
        """
        count_result = connectToMySQL(cls.db_name).query_db(count_query)
        count = count_result[0]["count"] if count_result else 0

        if count > 0:
            # Set updated_at to 3:30 PM on the day the shift was created
            # Only for shifts that started BEFORE 3:30 PM
            query = """
                UPDATE shifts
                SET updated_at = DATE_FORMAT(created_at, '%%Y-%%m-%%d 15:30:00')
                WHERE updated_at IS NULL
                AND DATE(created_at) = CURDATE()
                AND TIME(created_at) < '15:30:00';
            """
            connectToMySQL(cls.db_name).query_db(query)

        return f"Ended {count} open shifts at 3:30 PM"

    # ============ Stale Shift Remediation ============

    @classmethod
    def get_stale_shifts(cls, hours_threshold=12):
        """
        Find shifts that are 'stale' - open shifts that started more than X hours ago.
        These are shifts that were never clocked out.

        Args:
            hours_threshold: Number of hours after which an open shift is considered stale (default 12)

        Returns:
            List of Shift objects with creator and job data
        """
        query = """
            SELECT shifts.*,
                users.id as user_id, users.first_name, users.last_name, users.email,
                users.password, users.department, users.created_at as users_created_at,
                users.updated_at as users_updated_at,
                jobs.id as job_id_alias, jobs.im_number, jobs.general_contractor, jobs.job_scope,
                jobs.estimated_hours, jobs.user_id as job_user_id, jobs.context,
                jobs.created_at as job_created_at, jobs.updated_at as job_updated_at, jobs.status,
                TIMESTAMPDIFF(HOUR, shifts.created_at, NOW()) as hours_open
            FROM shifts
            JOIN users ON shifts.user_id = users.id
            LEFT JOIN jobs ON shifts.job_id = jobs.id
            WHERE shifts.updated_at IS NULL
            AND TIMESTAMPDIFF(HOUR, shifts.created_at, NOW()) >= %(hours_threshold)s
            ORDER BY shifts.created_at ASC;
        """
        results = connectToMySQL(cls.db_name).query_db(
            query, {"hours_threshold": hours_threshold}
        )

        if not results:
            return []

        stale_shifts = []
        for row in results:
            shift_info = {
                "id": row["id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "elapsed_time": None,
                "job_id": row["job_id"],
                "user_id": row["user_id"],
                "note": row["note"],
            }
            user_info = {
                "id": row["user_id"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "email": row["email"],
                "password": row["password"],
                "department": row["department"],
                "created_at": row["users_created_at"],
                "updated_at": row["users_updated_at"],
            }
            this_shift = cls(shift_info)
            this_shift.creator = user.User(user_info)
            this_shift.hours_open = row["hours_open"]

            if row.get("im_number") is not None:
                job_info = {
                    "id": row["job_id_alias"],
                    "im_number": row["im_number"],
                    "general_contractor": row["general_contractor"],
                    "job_scope": row["job_scope"],
                    "estimated_hours": row["estimated_hours"],
                    "user_id": row["job_user_id"],
                    "context": row["context"],
                    "created_at": row["job_created_at"],
                    "updated_at": row["job_updated_at"],
                    "status": row["status"],
                }
                this_shift.job = job.Job(job_info)
            else:
                this_shift.job = None

            stale_shifts.append(this_shift)

        return stale_shifts

    @classmethod
    def fix_stale_shift(cls, shift_id):
        """
        Fix a single stale shift by setting its updated_at appropriately.

        - If shift started BEFORE 3:30 PM: end at 3:30 PM same day
        - If shift started AT or AFTER 3:30 PM: end at start time (0 duration)

        This avoids negative durations when shifts started after 3:30 PM.

        Args:
            shift_id: The ID of the shift to fix

        Returns:
            True if successful, False otherwise
        """
        query = """
            UPDATE shifts
            SET updated_at = CASE
                WHEN TIME(created_at) < '15:30:00'
                THEN DATE_FORMAT(created_at, '%%Y-%%m-%%d 15:30:00')
                ELSE created_at
            END
            WHERE id = %(shift_id)s AND updated_at IS NULL;
        """
        result = connectToMySQL(cls.db_name).query_db(query, {"shift_id": shift_id})
        return result is not False

    @classmethod
    def fix_all_stale_shifts(cls, hours_threshold=12):
        """
        Fix all stale shifts by setting their updated_at appropriately.

        - If shift started BEFORE 3:30 PM: end at 3:30 PM same day
        - If shift started AT or AFTER 3:30 PM: end at start time (0 duration)

        This avoids negative durations when shifts started after 3:30 PM.

        Args:
            hours_threshold: Number of hours after which an open shift is considered stale

        Returns:
            Number of shifts fixed
        """
        # Count how many shifts will be fixed BEFORE updating
        # (ROW_COUNT() doesn't work across separate connections)
        count_query = """
            SELECT COUNT(*) as count FROM shifts
            WHERE updated_at IS NULL
            AND TIMESTAMPDIFF(HOUR, created_at, NOW()) >= %(hours_threshold)s;
        """
        count_result = connectToMySQL(cls.db_name).query_db(
            count_query, {"hours_threshold": hours_threshold}
        )
        count = count_result[0]["count"] if count_result else 0

        if count > 0:
            query = """
                UPDATE shifts
                SET updated_at = CASE
                    WHEN TIME(created_at) < '15:30:00'
                    THEN DATE_FORMAT(created_at, '%%Y-%%m-%%d 15:30:00')
                    ELSE created_at
                END
                WHERE updated_at IS NULL
                AND TIMESTAMPDIFF(HOUR, created_at, NOW()) >= %(hours_threshold)s;
            """
            connectToMySQL(cls.db_name).query_db(
                query, {"hours_threshold": hours_threshold}
            )

        return count

    @classmethod
    def count_stale_shifts(cls, hours_threshold=12):
        """
        Count open stale shifts older than the configured threshold.
        """
        count_query = """
            SELECT COUNT(*) as count FROM shifts
            WHERE updated_at IS NULL
            AND TIMESTAMPDIFF(HOUR, created_at, NOW()) >= %(hours_threshold)s;
        """
        count_result = connectToMySQL(cls.db_name).query_db(
            count_query, {"hours_threshold": hours_threshold}
        )
        return count_result[0]["count"] if count_result else 0

    @classmethod
    def fix_stale_shifts_batch(cls, batch_size=10, hours_threshold=12):
        """
        Fix stale shifts in controlled batches, oldest first.

        Args:
            batch_size: Max number of stale shifts to fix in this run
            hours_threshold: Number of hours after which an open shift is stale

        Returns:
            Number of shifts fixed
        """
        batch_size = int(batch_size)
        if batch_size <= 0:
            return 0

        stale_count = cls.count_stale_shifts(hours_threshold=hours_threshold)
        target_count = min(batch_size, stale_count)

        if target_count > 0:
            query = f"""
                UPDATE shifts
                SET updated_at = CASE
                    WHEN TIME(created_at) < '15:30:00'
                    THEN DATE_FORMAT(created_at, '%%Y-%%m-%%d 15:30:00')
                    ELSE created_at
                END
                WHERE updated_at IS NULL
                AND TIMESTAMPDIFF(HOUR, created_at, NOW()) >= %(hours_threshold)s
                ORDER BY created_at ASC
                LIMIT {int(target_count)};  -- int() cast guards copy-paste reuse
            """
            connectToMySQL(cls.db_name).query_db(
                query, {"hours_threshold": hours_threshold}
            )

        return target_count

    @classmethod
    def fix_negative_duration_shifts(cls):
        """
        Fix shifts where updated_at < created_at (resulting in negative durations).

        This corrects corrupted data from the old auto-end logic that set end times
        to 3:30 PM even for shifts that started after 3:30 PM.

        For these shifts, sets updated_at = created_at (0 duration).

        Returns:
            Number of shifts fixed
        """
        # Count corrupted shifts
        count_query = """
            SELECT COUNT(*) as count FROM shifts
            WHERE updated_at IS NOT NULL
            AND updated_at < created_at;
        """
        count_result = connectToMySQL(cls.db_name).query_db(count_query)
        count = count_result[0]["count"] if count_result else 0

        if count > 0:
            # Fix by setting end time to start time (0 duration)
            query = """
                UPDATE shifts
                SET updated_at = created_at
                WHERE updated_at IS NOT NULL
                AND updated_at < created_at;
            """
            connectToMySQL(cls.db_name).query_db(query)

        return count
