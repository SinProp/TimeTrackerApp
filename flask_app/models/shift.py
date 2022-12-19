from flask_app.config.mysqlconnection import connectToMySQL
from flask import flash
from ..models import user
from ..models import job

class Shift:
    db_name = 'man_hours'

    def __init__(self,db_data):
        self.id = db_data['id']
        self.job_shifts = []
        self.created_at = db_data['created_at']
        self.updated_at = db_data['updated_at']
        self.job_id = db_data['job_id']
        self.user_id = db_data['user_id']
        

    @classmethod
    def save(cls,data):
        query = "INSERT INTO shifts (created_at, updated_at, job_id, user_id) VALUES (NOW(),NULL,%(job_id)s,%(user_id)s);"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def get_all_shifts(cls, data):
        query = "SELECT * FROM shifts LEFT JOIN jobs on jobs.id = job_id;"
        results =  connectToMySQL(cls.db_name).query_db(query)
        all_shifts = []
        for row in results:
            job_data ={
                'id': row['id'],
                'im_number': row['im_number'],
                'general_contractor': row['general_contractor'],
                'job_scope': row['job_scope'],
                'estimated_hours': row['estimated_hours'],
                'user_id': row['user_id'],
                'created_at': row['jobs.created_at'],
                'updated_at': row['jobs.updated_at'],
            }
            new_shift = cls(row)
            new_shift.job = job.Job(job_data)
            all_shifts.append(new_shift)
        return all_shifts
    
    @classmethod
    def get_one_shift(cls,data):
        query = "SELECT * FROM shifts WHERE id = %(id)s;"
        results = connectToMySQL(cls.db_name).query_db(query,data)
        if len(results) == 0:
            return False
        return cls( results[0] )

    @classmethod
    def update(cls, data):
        query = "UPDATE shifts SET updated_at = NOW() WHERE id = %(id)s;"
        return connectToMySQL(cls.db_name).query_db(query,data)

    # @classmethod
    # def show_all_jobs(cls):
    #     query = "SELECT * FROM jobs LEFT JOIN users on users.id = user_id;"
    #     results = connectToMySQL(cls.db_name).query_db(query)
    #     all_jobs = []
    #     for row in results:
    #         user_data = {
    #             'id': row['id'],
    #             'first_name': row['first_name'],
    #             'last_name': row['last_name'],
    #             'email': row['email'],
    #             'password': row['password'],
    #             'id': session['user_id'],
    #             'created_at': row['users.created_at'],
    #             'updated_at': row['users.updated_at'],
    #         }
    #         new_job = cls(row)
    #         new_job.user = user.User(user_data)
    #         all_jobs.append(new_job)
    #     return all_jobs

    # @classmethod
    # def destroy(cls, data):
    #     query = "DELETE from jobs where id = %(id)s;"
    #     return connectToMySQL(cls.db_name).query_db(query,data)

    @staticmethod
    def validate_shift(shift):
        is_valid = True
        return is_valid
