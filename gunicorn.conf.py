"""
Gunicorn configuration for Island Time.

Uses post_fork hook to start APScheduler AFTER worker processes are forked,
avoiding the thread-death-on-fork issue where scheduler threads started in
the master process don't survive into workers.
"""


def post_fork(server, worker):
    """Start the scheduler in exactly one worker process (via file lock)."""
    from server import start_scheduler_if_enabled

    started = start_scheduler_if_enabled()
    if started:
        server.log.info(f"Scheduler started in worker {worker.pid}")
