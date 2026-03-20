from server import app, start_scheduler_if_enabled

application = app

# NOTE: Do NOT call start_scheduler_if_enabled() here.
# Under gunicorn, this runs in the master process before forking,
# and the scheduler thread dies on fork. Instead, gunicorn.conf.py
# uses post_fork to start the scheduler inside a worker process.
#
# For non-gunicorn usage (e.g. `python wsgi.py`), __main__ handles it.
if __name__ == "__main__":
    start_scheduler_if_enabled()
    application.run()
