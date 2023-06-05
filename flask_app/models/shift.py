from flask_app.config.mysqlconnection import connectToMySQL
from flask import flash
from ..models import user, job


from datetime import datetime, timedelta
dateFormat = "%m/%d/%Y %I:%M %p"


class Shift:
    db_name = 'man_hours'

    def __init__(self, db_data):
        self.id = db_data['id']
        self.job_shifts = []
        self.created_at = db_data['created_at']
        self.updated_at = db_data['updated_at']
        self.job_id = db_data['job_id']
        self.user_id = db_data['user_id']
        self.note = db_data['note']
        self.creator = None
        self.elapsed_time = db_data['elapsed_time']

    @classmethod
    def save(cls, data):
        query = "INSERT INTO shifts (created_at, updated_at, job_id, user_id, note) VALUES (NOW(),NULL,%(job_id)s,%(user_id)s,%(note)s);"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def get_all_shifts(cls, data):
        query = "SELECT * FROM shifts LEFT JOIN jobs on jobs.id = job_id;"
        results = connectToMySQL(cls.db_name).query_db(query)
        all_shifts = []
        for row in results:
            job_data = {
                'id': row['id'],
                'im_number': row['im_number'],
                'general_contractor': row['general_contractor'],
                'job_scope': row['job_scope'],
                'estimated_hours': row['estimated_hours'],
                'user_id': row['user_id'],
                'context': row['context'],
                'created_at': row['jobs.created_at'],
                'updated_at': row['jobs.updated_at'],
                'status': row['status']
            }
            new_shift = cls(row)
            new_shift.job = job.Job(job_data)
            all_shifts.append(new_shift)
        return all_shifts

    @classmethod
    def find_shifts_in_date_range(cls, data):
        query = '''
            SELECT *, TIMEDIFF(shifts.updated_at, shifts.created_at) as elapsed_time
            FROM shifts
            JOIN users
            ON shifts.user_id = users.id
            WHERE shifts.created_at BETWEEN %(start_date)s AND %(end_date)s;
        '''
        results = connectToMySQL(cls.db_name).query_db(query, data)

        if not results:
            return None

        shifts = []
        for row in results:
            shift_info = {
                'id': row['id'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'elapsed_time': row['elapsed_time'],
                'job_id': row['job_id'],
                'user_id': row['user_id'],
                'note': row['note'],
            }
            user_info = {
                'id': row['users.id'],
                'first_name': row['first_name'],
                'last_name': row['last_name'],
                'email': row['email'],
                'password': row['password'],
                'department': row['department'],
                'created_at': row['users.created_at'],
                'updated_at': row['users.updated_at'],
            }

            this_shift = Shift(shift_info)
            this_shift.creator = user.User(user_info)
            shifts.append(this_shift)

        return shifts

    @classmethod
    def get_one_shift(cls, data):
        query = "SELECT *, TIMESTAMPDIFF(HOUR, created_at, updated_at) as elapsed_time FROM shifts WHERE id = %(id)s;"
        results = connectToMySQL(cls.db_name).query_db(query, data)
        if len(results) == 0:
            return False
        return cls(results[0])

    @classmethod
    def update(cls, data):
        query = "UPDATE shifts SET updated_at = NOW() WHERE id = %(id)s;"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def update_time(cls, data):
        query = "UPDATE shifts SET created_at = %(created_at)s, updated_at = %(updated_at)s, note = %(note)s WHERE id = %(id)s;"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def elapsed_time(cls, data):
        query = "SELECT TIMESTAMPDIFF (HOUR, created_at, updated_at) as elapsed_time FROM shifts;"
        return connectToMySQL(cls.db_name).query_db(query, data)

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
            'start': start.strftime('%Y-%m-%d %H:%M:%S'),
            'end': end.strftime('%Y-%m-%d %H:%M:%S'),
        }
        query = "SELECT COUNT(*) as count FROM shifts WHERE created_at BETWEEN %(start)s AND %(end)s;"
        results = connectToMySQL(cls.db_name).query_db(query, data)
        return results[0]['count'] if results else 0

    @staticmethod
    def validate_shift(shift):
        is_valid = True
        return is_valid
