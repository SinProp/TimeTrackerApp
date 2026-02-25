from flask_app.models.job import Job
from flask_app.models.shift import Shift
from datetime import datetime
import logging

# Set up logging for scheduler
logging.basicConfig(level=logging.INFO)
scheduler_logger = logging.getLogger("scheduler")


def auto_clock_out_shifts_at_6pm_weekdays():
    """
    Automatically clock out open shifts at 6:00 PM EST on weekdays.
    Only affects open shifts created today.
    """
    try:
        scheduler_logger.info(
            f"Starting weekday 6:00 PM auto clock-out at {datetime.now()}"
        )

        closed_count = Shift.auto_clock_out_open_shifts_created_today()

        scheduler_logger.info(
            f"Weekday 6:00 PM auto clock-out completed. Closed {closed_count} shifts."
        )
        return f"Closed {closed_count} open shifts at 6:00 PM"

    except Exception as e:
        scheduler_logger.error(f"Error in weekday 6:00 PM auto clock-out: {str(e)}")
        return f"Error: {str(e)}"


def automated_job_sync():
    """
    Automated job to sync approved jobs from Dataverse.
    Runs daily at 6 AM EST.

    Optimized to use bulk operations instead of N+1 queries.
    
    Smart sync behavior:
    - If job exists (by IM number): Update it and make visible to production
    - If job is new: Insert it with visible_to_production=TRUE
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

        # Separate into new jobs and existing jobs to update
        new_jobs = []
        updated_count = 0
        
        for job in approved_jobs:
            if job["im_number"] in existing_im_numbers:
                # Update existing job and make it visible
                try:
                    Job.update_from_dataverse(job["im_number"], {
                        "general_contractor": job["general_contractor"],
                        "job_scope": job["job_scope"],
                    })
                    updated_count += 1
                    scheduler_logger.info(f"Updated existing job IM #{job['im_number']} from Dataverse")
                except Exception as e:
                    scheduler_logger.error(f"Error updating job {job['im_number']}: {e}")
            else:
                # New job - will be bulk inserted
                new_jobs.append(job)

        # Log which new jobs are being processed
        for job in new_jobs:
            scheduler_logger.info(f"Adding new job with IM number: {job['im_number']}")

        # OPTIMIZED: Insert all new jobs in one query instead of N queries
        added_count = Job.bulk_add_records(new_jobs) if new_jobs else 0

        scheduler_logger.info(
            f"Dataverse sync completed. Added: {added_count}, Updated: {updated_count}"
        )
        return f"Sync completed successfully. Added {added_count} jobs, updated {updated_count} existing jobs."

    except Exception as e:
        scheduler_logger.error(f"Error in automated Dataverse sync: {str(e)}")
        return f"Error: {str(e)}"
