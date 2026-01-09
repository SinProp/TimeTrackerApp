from ..config.mysqlconnection import connectToMySQL
from flask import flash
import re
from ..models import shift


EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9.+_-]+@[a-zA-Z0-9._-]+\.[a-zA-Z]+$')


class User:
    db = 'man_hours'

    def __init__(self, data):
        self.id = data['id']
        self.first_name = data['first_name']
        self.last_name = data['last_name']
        self.email = data['email']
        self.department = data['department']
        self.password = data['password']
        self.created_at = data['created_at']
        self.updated_at = data['updated_at']
        self.deleted_date = data['deleted_date'] if 'deleted_date' in data else None
        self.on_active_roster = data.get('on_active_roster', True)
        self.shifts = []

        # class methods go below

    @classmethod
    def create_user(cls, data):
        query = "INSERT INTO users (first_name, last_name, email, department, password) VALUES (%(first_name)s, %(last_name)s, %(email)s, %(department)s,  %(password)s);"

        return connectToMySQL(cls.db).query_db(query, data)

    @staticmethod
    def validate_registration(data):
        is_valid = True
        # special_characters = [':, "#', '!']

        if len(data['first_name']) == 0:
            is_valid = False
            flash('First Name is required', 'error')
        if len(data['last_name']) == 0:
            is_valid = False
            flash("Last Name is required", "error")
        if len(data['password']) < 8:
            is_valid = False
            flash("Length of password must be at least 8 characters", "error")
        if data['password'] != data.get('confirm_password', None):
            is_valid = False
            flash("Passwords do not match", "error")
        if not EMAIL_REGEX.match(data['email']):
            flash("Invalid email address!")
            is_valid = False

        query = "SELECT * FROM users WHERE email = %(email)s;"

        results = connectToMySQL(User.db).query_db(query, data)
        if len(results) >= 1:
            is_valid = False
            flash("That email is already taken", "error")

        return is_valid

    @classmethod
    def get_by_email(cls, data):
        query = "SELECT * FROM users WHERE email = %(email)s;"
        results = connectToMySQL(cls.db).query_db(query, data)
        # gives back a list with one dictionary

        if len(results) == 0:
            return False
        return cls(results[0])
        # return an instance of the first dictionary

    @classmethod
    def get_by_id(cls, data):
        query = "SELECT * FROM users WHERE id = %(id)s;"
        results = connectToMySQL(cls.db).query_db(query, data)
        # gives back a list with one dictionary

        if len(results) == 0:
            return False
        return cls(results[0])
        # return an instance of the first dictionary

    @classmethod
    def get_all(cls):
        query = "SELECT * FROM users WHERE deleted_date IS NULL;"
        results = connectToMySQL(cls.db).query_db(query)
        all_users = []
        for row in results:
            user_data = {
                'id': row['id'],
                'first_name': row['first_name'],
                'last_name': row['last_name'],
                'department': row['department'],
                'email': row['email'],
                'password': row['password'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'on_active_roster': row.get('on_active_roster', True),
            }
            new_user = cls(user_data)
            all_users.append(new_user)
        return all_users

    @classmethod
    def getUserWithShifts(cls, data):
        query = '''
            SELECT * 
            FROM users
            LEFT JOIN shifts
            ON users.id = shifts.user_id
            WHERE users.id = %(id)s;'''
        results = connectToMySQL(cls.db).query_db(query, data)
        print(f"results: {results}")
        output = cls(results[0])
        if not results[0]['shifts.id'] == None:
            for row in results:
                # print(row)
                shift_info = {
                    'id': row['shifts.id'],
                    'created_at': row['shifts.created_at'],
                    'updated_at': row['shifts.updated_at'],
                    'job_id': row['job_id'],
                    'user_id': row['user_id']
                }
                user_info = {
                    'id': row['id'],
                    'first_name': row['first_name'],
                    'last_name': row['last_name'],
                    'email': row['email'],
                    'department': row['department'],
                    'password': row['password'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }

                this_shift = shift.Shift(shift_info)
                this_shift.creator = (user_info)
                output.shifts.append(this_shift)

                print(f"output: {output}")
                print(f"output.shifts: {output.shifts}")
            return output

    @staticmethod
    def validate_login(data):
        is_valid = True
        if len(data['email']) == 0:
            is_valid = False
            flash('An email is required', 'error')
        if len(data['password']) == 0:
            is_valid = False
            flash('A password is required', 'error')
        return is_valid

    @classmethod
    def update(cls, data):
        query = """
        UPDATE users 
        SET first_name = %(first_name)s, 
            last_name = %(last_name)s, 
            email = %(email)s, 
            department = %(department)s 
        WHERE id = %(id)s;
        """
        return connectToMySQL(cls.db).query_db(query, data)

    @classmethod
    def soft_delete(cls, data):
        query = "UPDATE users SET deleted_date = NOW() WHERE id = %(id)s;"
        return connectToMySQL(cls.db).query_db(query, data)

    @classmethod
    def destroy(cls, data):
        query = "DELETE FROM users WHERE id = %(id)s;"
        return connectToMySQL(cls.db).query_db(query, data)

    @classmethod
    def get_missing_workers_today(cls, ongoing_user_ids):
        """
        Get users on active roster who haven't clocked in today.
        Args:
            ongoing_user_ids: list of user IDs with ongoing shifts
        Returns:
            List of User objects for workers expected but not signed in
        """
        query = "SELECT * FROM users WHERE deleted_date IS NULL AND on_active_roster = TRUE;"
        results = connectToMySQL(cls.db).query_db(query)
        missing_workers = []
        for row in results:
            if row['id'] not in ongoing_user_ids:
                user_data = {
                    'id': row['id'],
                    'first_name': row['first_name'],
                    'last_name': row['last_name'],
                    'department': row['department'],
                    'email': row['email'],
                    'password': row['password'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'on_active_roster': row.get('on_active_roster', True),
                }
                missing_workers.append(cls(user_data))
        return missing_workers

    @classmethod
    def update_roster_status(cls, data):
        """
        Toggle the on_active_roster status for a user.
        Args:
            data: dict with 'id' and 'on_roster' (boolean)
        """
        query = "UPDATE users SET on_active_roster = %(on_roster)s WHERE id = %(id)s;"
        return connectToMySQL(cls.db).query_db(query, data)
