from flask_app.config.mysqlconnection import connectToMySQL
from flask import flash

from ..models import shift, user
from datetime import datetime
from ..dataverse.service import get_approved_jobs

dateFormat = "%m/%d/%Y %I:%M %p"


class Job:
    db_name = "man_hours"

    def __init__(self, db_data):
        self.id = db_data["id"]
        self.im_number = db_data["im_number"]
        self.general_contractor = db_data["general_contractor"]
        self.job_scope = db_data["job_scope"]
        self.estimated_hours = db_data["estimated_hours"]
        self.user = None
        self.user_id = db_data["user_id"]
        self.context = db_data["context"]
        self.created_at = db_data["created_at"]
        self.updated_at = db_data["updated_at"]
        self.status = db_data["status"]
        self.visible_to_production = db_data.get("visible_to_production", True)
        self.source = db_data.get("source", "manual")
        self.shifts = []
        self.shift_users = []  # Add this line

    @classmethod
    def save(cls, data):
        query = "INSERT INTO jobs (im_number, general_contractor, job_scope, estimated_hours, context, user_id) VALUES (%(im_number)s,%(general_contractor)s,%(job_scope)s,%(estimated_hours)s,%(context)s,%(user_id)s);"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def get_all(cls):
        today = datetime.now().strftime("%Y-%m-%d")
        query = """
            SELECT jobs.*,
                shifts.created_at AS shift_start,
                shifts.updated_at AS shift_end,
                shift_users.id AS shift_user_id,
                shift_users.first_name AS shift_user_first_name
            FROM jobs
            LEFT JOIN shifts ON shifts.job_id = jobs.id AND DATE(shifts.created_at) = %s
            LEFT JOIN users AS shift_users ON shifts.user_id = shift_users.id
            ORDER BY jobs.id;
        """
        results = connectToMySQL(cls.db_name).query_db(query, (today,))
        if not results:
            return []

        job_dict = {}
        for row in results:
            if row["id"] not in job_dict:
                # Add default values for new fields if they don't exist in DB yet
                row.setdefault("visible_to_production", True)
                row.setdefault("source", "manual")
                new_job = cls(row)
                new_job.shift_users = []
                job_dict[row["id"]] = new_job

            # If a shift exists, add the user associated with the shift
            if row["shift_user_first_name"]:
                job_dict[row["id"]].shift_users.append(row["shift_user_first_name"])

        return list(job_dict.values())

    @classmethod
    def get_all_jobs(cls):
        query = "SELECT * FROM jobs ORDER BY im_number;"
        results = connectToMySQL(cls.db_name).query_db(query)
        jobs = []
        if results:
            for row in results:
                jobs.append(cls(row))
        return jobs

    @classmethod
    def get_one(cls, data):
        query = "SELECT * FROM jobs WHERE id = %(id)s;"
        results = connectToMySQL(cls.db_name).query_db(query, data)
        if len(results) == 0:
            return False
        return cls(results[0])

    @classmethod
    def update(cls, data):
        query = "UPDATE jobs SET im_number=%(im_number)s, general_contractor=%(general_contractor)s, job_scope=%(job_scope)s, context=%(context)s, estimated_hours=%(estimated_hours)s, status=%(status)s, updated_at = NOW() WHERE id = %(id)s;"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def show_all_jobs(cls):
        query = "SELECT jobs.*, users.first_name, users.last_name, users.email, users.password, users.department, users.created_at as users_created_at, users.updated_at as users_updated_at FROM jobs LEFT JOIN users on users.id = jobs.user_id;"
        results = connectToMySQL(cls.db_name).query_db(query)
        all_jobs = []
        for row in results:
            new_job = cls(row)
            if row["first_name"]:
                user_data = {
                    "id": row["user_id"],
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "email": row["email"],
                    "password": row["password"],
                    "department": row["department"],
                    "created_at": row["users_created_at"],
                    "updated_at": row["users_updated_at"],
                }
                new_job.user = user.User(user_data)
            all_jobs.append(new_job)
        return all_jobs

    @classmethod
    def getJobWithShifts(cls, data):
        from ..models.user import User

        query = """

            SELECT *, TIMEDIFF(shifts.updated_at, shifts.created_at) as elapsed_time
            FROM jobs
            LEFT JOIN shifts
            ON jobs.id = shifts.job_id
            JOIN users
            ON shifts.user_id = users.id
            WHERE jobs.id = %(id)s;"""
        results = connectToMySQL(cls.db_name).query_db(query, data)
        print(f"results: {results}")
        if not results:
            return None
        output = cls(results[0])
        if not results[0]["shifts.id"] == None:
            for row in results:
                # print(row)
                shift_info = {
                    "id": row["shifts.id"],
                    "created_at": row["shifts.created_at"],
                    "updated_at": row["shifts.updated_at"],
                    "elapsed_time": row["elapsed_time"],
                    "job_id": row["job_id"],
                    "user_id": row["user_id"],
                    "note": row["note"],
                }
                user_info = {
                    "id": row["id"],
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "email": row["email"],
                    "password": row["password"],
                    "department": row["department"],
                    "created_at": row["users.created_at"],
                    "updated_at": row["users.updated_at"],
                }

                this_shift = shift.Shift(shift_info)
                this_shift.creator = user.User(user_info)
                output.shifts.append(this_shift)

                print(f"output: {output}")
                print(f"output.shifts: {output.shifts}")
            return output

    # @classmethod
    # def end_current_shift(cls, data):
    #     # Find the current shift for the user
    #     current_shift = Shift.query.filter_by(
    #         user_id=data, end_time=None).first()
    #     if current_shift:
    #         # End the shift by setting the end time to now
    #         current_shift.end_time = datetime.now()
    #         # Save changes to the database
    #         db.session.commit()

    @classmethod
    def get_approved_jobs_from_dataverse(cls):
        """
        Get approved jobs from Dataverse.
        Replaces the old get_approved_jobs_from_smartsheet() method.
        """
        return get_approved_jobs()

    @classmethod
    def check_im_number_exists(cls, data):
        query = "SELECT COUNT(*) AS count FROM jobs WHERE im_number = %(im_number)s;"
        result = connectToMySQL(cls.db_name).query_db(query, data)
        return result[0]["count"] > 0

    @classmethod
    def add_new_record(cls, data):
        # Set default value for estimated_hours if it's not present in data
        data.setdefault("estimated_hours", "0000")
        data.setdefault("user_id", "11")

        if not cls.check_im_number_exists({"im_number": data["im_number"]}):
            query = """INSERT INTO jobs (im_number, general_contractor, job_scope, estimated_hours, user_id) VALUES (%(im_number)s, %(general_contractor)s, %(job_scope)s, %(estimated_hours)s, %(user_id)s);"""
            return connectToMySQL(cls.db_name).query_db(query, data)
        else:
            flash(
                f"IM number {data['im_number']} already exists in the database.",
                "error",
            )
            return False

    @classmethod
    def destroy(cls, data):
        query = "DELETE from jobs where id = %(id)s;"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @staticmethod
    def validate_job(job):
        is_valid = True
        # if len(job['im_number']) < 4:
        #     is_valid = False
        #     flash("IM Numbers must be at least 4 digits","job")
        if len(job["general_contractor"]) < 3:
            is_valid = False
            flash("general_contractor names must be at least 3 characters", "job")
        # if len(band['founding_member']) < 3:
        #     is_valid = False
        #     flash("The name of the Founding Member must be at least 3 characters","band")
        if len(job["job_scope"]) < 5:
            is_valid = False
            flash("The job's scope must be at least 5 characters", "job")
        if len(job["estimated_hours"]) < 2:
            is_valid = False
            flash("The estimated hours must be at least be 2 digits long", "job")
        return is_valid

    # ============ Bulk Operations (Performance Optimization) ============

    @classmethod
    def get_existing_im_numbers(cls, im_numbers):
        """
        Fetch all existing IM numbers from a list in one query.
        Returns a set of IM numbers that already exist in the database.

        This replaces N calls to check_im_number_exists() with 1 query.
        """
        if not im_numbers:
            return set()

        # Build placeholders for IN clause
        placeholders = ",".join(["%s"] * len(im_numbers))
        query = f"SELECT im_number FROM jobs WHERE im_number IN ({placeholders});"
        results = connectToMySQL(cls.db_name).query_db(query, tuple(im_numbers))

        if not results:
            return set()
        return {row["im_number"] for row in results}

    @classmethod
    def bulk_add_records(cls, jobs_data):
        """
        Insert multiple jobs in one query.
        Returns the number of jobs inserted.

        This replaces N calls to add_new_record() with 1 query.

        Args:
            jobs_data: List of dicts with keys: im_number, general_contractor, job_scope,
                       estimated_hours (optional), user_id (optional)
        """
        if not jobs_data:
            return 0

        # Prepare values with defaults
        values = []
        for job in jobs_data:
            values.append(
                (
                    job["im_number"],
                    job["general_contractor"],
                    job["job_scope"],
                    job.get("estimated_hours", "0000"),
                    job.get("user_id", "11"),
                )
            )

        # Build multi-row INSERT
        placeholders = ",".join(["(%s, %s, %s, %s, %s)"] * len(values))
        query = f"""
            INSERT INTO jobs (im_number, general_contractor, job_scope, estimated_hours, user_id)
            VALUES {placeholders};
        """

        # Flatten the values list for the query
        flat_values = [item for sublist in values for item in sublist]

        result = connectToMySQL(cls.db_name).query_db(query, tuple(flat_values))
        return len(jobs_data) if result is not False else 0

    # ============ Office Job Visibility Methods ============

    @classmethod
    def get_all_for_user(cls, department):
        """
        Get all jobs for dashboard.
        All users now see all jobs - jobs auto-activate when someone clocks in.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        # Everyone sees all jobs now - production can search and clock into any job
        query = """
            SELECT jobs.*,
                shifts.created_at AS shift_start,
                shifts.updated_at AS shift_end,
                shift_users.id AS shift_user_id,
                shift_users.first_name AS shift_user_first_name
            FROM jobs
            LEFT JOIN shifts ON shifts.job_id = jobs.id AND DATE(shifts.created_at) = %s
            LEFT JOIN users AS shift_users ON shifts.user_id = shift_users.id
            ORDER BY jobs.id;
        """
        results = connectToMySQL(cls.db_name).query_db(query, (today,))
        if not results:
            return []

        job_dict = {}
        for row in results:
            if row["id"] not in job_dict:
                row.setdefault("visible_to_production", True)
                row.setdefault("source", "manual")
                new_job = cls(row)
                new_job.shift_users = []
                job_dict[row["id"]] = new_job

            if row["shift_user_first_name"]:
                job_dict[row["id"]].shift_users.append(row["shift_user_first_name"])

        return list(job_dict.values())

    @classmethod
    def save_office_job(cls, data):
        """
        Save a new office/pre-production job (hidden from production by default).
        """
        query = """INSERT INTO jobs 
            (im_number, general_contractor, job_scope, estimated_hours, context, user_id, visible_to_production, source) 
            VALUES (%(im_number)s, %(general_contractor)s, %(job_scope)s, %(estimated_hours)s, %(context)s, %(user_id)s, FALSE, 'office');"""
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def make_visible_to_production(cls, job_id):
        """
        Make a job visible to production workers.
        Called when a production user clocks into a hidden job.
        """
        query = "UPDATE jobs SET visible_to_production = TRUE WHERE id = %(id)s;"
        return connectToMySQL(cls.db_name).query_db(query, {"id": job_id})

    @classmethod
    def toggle_visibility(cls, job_id):
        """
        Toggle the visible_to_production status for a job.
        """
        query = "UPDATE jobs SET visible_to_production = NOT visible_to_production WHERE id = %(id)s;"
        return connectToMySQL(cls.db_name).query_db(query, {"id": job_id})

    @classmethod
    def update_from_dataverse(cls, im_number, data):
        """
        Update an existing job with Dataverse data and make it visible.
        Used when Dataverse approves a job that was manually created.
        """
        query = """UPDATE jobs 
            SET general_contractor = %(general_contractor)s, 
                job_scope = %(job_scope)s, 
                visible_to_production = TRUE, 
                source = 'dataverse',
                updated_at = NOW() 
            WHERE im_number = %(im_number)s;"""
        data["im_number"] = im_number
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def get_by_im_number(cls, im_number):
        """
        Get a job by its IM number.
        Returns the job or None if not found.
        """
        query = "SELECT * FROM jobs WHERE im_number = %(im_number)s;"
        results = connectToMySQL(cls.db_name).query_db(query, {"im_number": im_number})
        if not results:
            return None
        row = results[0]
        row.setdefault("visible_to_production", True)
        row.setdefault("source", "manual")
        return cls(row)
