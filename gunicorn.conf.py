"""
Gunicorn configuration for Island Time.

Uses post_fork hook to start APScheduler AFTER worker processes are forked,
avoiding the thread-death-on-fork issue where scheduler threads started in
the master process don't survive into workers.
"""

import sys
import os

# Ensure the app directory is on Python's path so `import server` works
# when gunicorn is invoked from outside the working directory.
sys.path.insert(0, os.path.dirname(__file__))


def post_fork(server, worker):
    """Start the scheduler in exactly one worker process (via file lock)."""
    from server import start_scheduler_if_enabled

    started = start_scheduler_if_enabled()
    if started:
        server.log.info(f"Scheduler started in worker {worker.pid}")
