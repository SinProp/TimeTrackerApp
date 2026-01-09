from flask_app.models.job import Job
from flask_app.models.shift import Shift
from datetime import datetime
import logging

# Set up logging for scheduler
logging.basicConfig(level=logging.INFO)
scheduler_logger = logging.getLogger("scheduler")


def auto_end_shifts_at_330pm():
    """
    Automatically end all open shifts at 3:30 PM EST.
    Sets updated_at to 3:30 PM on the same day the shift was created.
    Runs daily at 3:30 PM EST.
    """
    try:
        scheduler_logger.info(f"Starting auto-end shifts at {datetime.now()}")

        result = Shift.auto_end_open_shifts_at_330pm()

        scheduler_logger.info(f"Auto-end shifts completed: {result}")
        return result

    except Exception as e:
        scheduler_logger.error(f"Error in auto-end shifts: {str(e)}")
        return f"Error: {str(e)}"


def automated_job_sync():
    """
    Automated job to sync approved jobs from Dataverse.
    Runs daily at 6 AM EST.

    Optimized to use bulk operations instead of N+1 queries.
    """
    try:
        scheduler_logger.info(f"Starting automated Dataverse sync at {datetime.now()}")

        # Get approved jobs from Dataverse
        approved_jobs = Job.get_approved_jobs_from_dataverse()
        scheduler_logger.info(
            f"Retrieved {len(approved_jobs)} approved jobs from Dataverse"
        )

        if not approved_jobs:
            scheduler_logger.info("No approved jobs to process")
            return "Sync completed. No approved jobs found in Dataverse."

        # OPTIMIZED: Check all IM numbers in one query instead of N queries
        im_numbers = [job["im_number"] for job in approved_jobs]
        existing_im_numbers = Job.get_existing_im_numbers(im_numbers)

        # Filter to only new jobs
        new_jobs = [
            job for job in approved_jobs if job["im_number"] not in existing_im_numbers
        ]

        skipped_count = len(approved_jobs) - len(new_jobs)

        # Log which jobs are being processed
        for job in new_jobs:
            scheduler_logger.info(f"Adding new job with IM number: {job['im_number']}")

        # OPTIMIZED: Insert all new jobs in one query instead of N queries
        added_count = Job.bulk_add_records(new_jobs)

        scheduler_logger.info(
            f"Dataverse sync completed. Added: {added_count}, Skipped: {skipped_count}"
        )
        return f"Sync completed successfully. Added {added_count} jobs, skipped {skipped_count} duplicates."

    except Exception as e:
        scheduler_logger.error(f"Error in automated Dataverse sync: {str(e)}")
        return f"Error: {str(e)}"
