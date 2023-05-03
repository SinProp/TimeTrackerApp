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

        query = f"SELECT * FROM users WHERE email = %(email)s;"

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
