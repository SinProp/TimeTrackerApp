from flask_app.config.mysqlconnection import connectToMySQL
from flask import flash
from ..models import user

class Job:
    db_name = 'man_hours'

    def __init__(self,db_data):
        self.id = db_data['id']
        self.im_number = db_data['im_number']
        self.general_contractor = db_data['general_contractor']
        self.job_scope = db_data['job_scope']
        self.estimated_hours = db_data['estimated_hours']
        self.user = None
        self.user_id = db_data['user_id']
        self.created_at = db_data['created_at']
        self.updated_at = db_data['updated_at']

    @classmethod
    def save(cls,data):
        query = "INSERT INTO jobs (im_number, general_contractor, job_scope, estimated_hours, user_id) VALUES (%(im_number)s,%(general_contractor)s,%(job_scope)s,%(estimated_hours)s,%(user_id)s);"
        return connectToMySQL(cls.db_name).query_db(query, data)

    @classmethod
    def get_all(cls):
        query = "SELECT * FROM jobs LEFT JOIN users on users.id = user_id;"
        results =  connectToMySQL(cls.db_name).query_db(query)
        all_jobs = []
        for row in results:
            user_data ={
                'id': row['id'],
                'first_name': row['first_name'],
                'last_name': row['last_name'],
                'email': row['email'],
                'password': row['password'],
                'user_id': row['user_id'],
                'created_at': row['users.created_at'],
                'updated_at': row['users.updated_at'],
            }
            new_job = cls(row)
            new_job.user = user.User(user_data)
            all_jobs.append(new_job)
        return all_jobs
    
    @classmethod
    def get_one(cls,data):
        query = "SELECT * FROM jobs WHERE id = %(id)s;"
        results = connectToMySQL(cls.db_name).query_db(query,data)
        if len(results) == 0:
            return False
        return cls( results[0] )

    @classmethod
    def update(cls, data):
        query = "UPDATE jobs SET general_contractor=%(general_contractor)s, job_scope=%(job_scope)s, estimated_hours=%(estimated_hours)s, updated_at = NOW() WHERE id = %(id)s;"
        return connectToMySQL(cls.db_name).query_db(query,data)

    @classmethod
    def show_all_jobs(cls):
        query = "SELECT * FROM jobs LEFT JOIN users on users.id = user_id;"
        results = connectToMySQL(cls.db_name).query_db(query)
        all_jobs = []
        for row in results:
            user_data = {
                'id': row['id'],
                'first_name': row['first_name'],
                'last_name': row['last_name'],
                'email': row['email'],
                'password': row['password'],
                'id': session['user_id'],
                'created_at': row['users.created_at'],
                'updated_at': row['users.updated_at'],
            }
            new_job = cls(row)
            new_job.user = user.User(user_data)
            all_jobs.append(new_job)
        return all_jobs

    @classmethod
    def destroy(cls, data):
        query = "DELETE from jobs where id = %(id)s;"
        return connectToMySQL(cls.db_name).query_db(query,data)

    @staticmethod
    def validate_job(job):
        is_valid = True
        # if len(job['im_number']) < 4:
        #     is_valid = False
        #     flash("IM Numbers must be at least 4 digits","job")
        if len(job['general_contractor']) < 3:
            is_valid = False
            flash("GC names must be at least 3 characters","job")
        # if len(band['founding_member']) < 3:
        #     is_valid = False
        #     flash("The name of the Founding Member must be at least 3 characters","band")
        if len(job['job_scope']) < 5:
            is_valid = False
            flash("The job's scope must be at least 5 characters","job")
        if len(job['estimated_hours']) < 2:
            is_valid = False
            flash("The estimated hours must be at least be 2 digits long","job")
        return is_valid
