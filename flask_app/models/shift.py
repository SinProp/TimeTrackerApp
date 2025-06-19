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
        self.elapsed_time = db_data.get('elapsed_time')

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
        # Ensure start_date and end_date cover the entire day
        start_date_str = data['start_date'] + " 00:00:00"
        end_date_str = data['end_date'] + " 23:59:59"

        query = '''
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
            AND shifts.updated_at IS NOT NULL;
        '''

        query_data = {
            'start_date': start_date_str,
            'end_date': end_date_str
        }

        results = connectToMySQL(cls.db_name).query_db(query, query_data)

        if not results:
            return []

        shifts = []
        for row in results:
            this_shift = cls(row)

            user_data = {
                'id': row['creator_id'],
                'first_name': row['first_name'],
                'last_name': row['last_name'],
                'email': row['email'],
                'password': row['creator_password'],
                'department': row['department'],
                'created_at': row['creator_created_at'],
                'updated_at': row['creator_updated_at'],
            }
            this_shift.creator = user.User(user_data)

            if row.get('im_number') is not None:
                job_data = {
                    'id': row['job_id_alias'],
                    'im_number': row['im_number'],
                    'general_contractor': row['general_contractor'],
                    'job_scope': row['job_scope'],
                    'estimated_hours': row['estimated_hours'],
                    'user_id': row['job_user_id'],
                    'context': row['context'],
                    'created_at': row['job_created_at'],
                    'updated_at': row['job_updated_at'],
                    'status': row['status']
                }
                this_shift.job = job.Job(job_data)
            else:
                this_shift.job = None

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
    def get_ongoing(cls):
        query = '''
        SELECT shifts.*, users.id as user_id, users.first_name, users.last_name, users.email, 
        users.password, users.department, users.created_at as users_created_at, 
        users.updated_at as users_updated_at,
        TIMEDIFF(IFNULL(shifts.updated_at, NOW()), shifts.created_at) as elapsed_time
        FROM shifts
        JOIN users ON shifts.user_id = users.id
        WHERE shifts.updated_at IS NULL
        AND DATE(shifts.created_at) = CURDATE();  -- Filter for shifts started today
        '''
        results = connectToMySQL(cls.db_name).query_db(query)
        ongoing_shifts = []
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
                'id': row['user_id'],
                'first_name': row['first_name'],
                'last_name': row['last_name'],
                'email': row['email'],
                'password': row['password'],
                'department': row['department'],
                'created_at': row['users_created_at'],
                'updated_at': row['users_updated_at'],
            }
            this_shift = cls(shift_info)
            this_shift.creator = user.User(user_info)
            ongoing_shifts.append(this_shift)

        return ongoing_shifts

    @classmethod
    def update(cls, data):
        query = "UPDATE shifts SET updated_at = NOW() WHERE id = %(id)s;"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def update_time(cls, data):
        query_parts = []
        query_data = {'id': data['id']}

        if 'note' in data:
            query_parts.append("note = %(note)s")
            query_data['note'] = data['note']

        if 'job_id' in data and data['job_id']:
            query_parts.append("job_id = %(job_id)s")
            query_data['job_id'] = data['job_id']

        if 'created_at' in data and data['created_at']:
            query_parts.append("created_at = %(created_at)s")
            query_data['created_at'] = data['created_at']

        if 'updated_at' in data:
            if data['updated_at']:
                query_parts.append("updated_at = %(updated_at)s")
                query_data['updated_at'] = data['updated_at']
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

        query = '''
        UPDATE shifts
        SET updated_at = %(now)s
        WHERE user_id = %(user_id)s AND created_at >= %(start_of_day)s AND updated_at IS NULL;
        '''
        data = {
            'user_id': user_id,
            'now': now.strftime('%Y-%m-%d %H:%M:%S'),
            'start_of_day': start_of_day.strftime('%Y-%m-%d %H:%M:%S')
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
