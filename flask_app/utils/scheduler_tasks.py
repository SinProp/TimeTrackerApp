from flask_app.models.job import Job
from datetime import datetime
import logging

# Set up logging for scheduler
logging.basicConfig(level=logging.INFO)
scheduler_logger = logging.getLogger('scheduler')

def automated_job_sync():
    """
    Automated job to sync approved jobs from Smartsheet
    Runs daily at 6 AM EST
    """
    try:
        scheduler_logger.info(f"Starting automated Smartsheet sync at {datetime.now()}")
        
        # Get approved jobs from Smartsheet
        approved_jobs = Job.get_approved_jobs_from_smartsheet()
        scheduler_logger.info(f"Retrieved {len(approved_jobs)} approved jobs from Smartsheet")

        # Process each approved job
        added_count = 0
        skipped_count = 0
        
        for job in approved_jobs:
            scheduler_logger.info(f"Processing job with IM number: {job['im_number']}")
            
            # Check if the IM number exists
            if not Job.check_im_number_exists({'im_number': job['im_number']}):
                scheduler_logger.info(f"IM number {job['im_number']} does not exist. Adding new record.")
                Job.add_new_record(job)
                added_count += 1
            else:
                scheduler_logger.info(f"IM number {job['im_number']} already exists. Skipping.")
                skipped_count += 1

        scheduler_logger.info(f"Automated sync completed. Added: {added_count}, Skipped: {skipped_count}")
        return f"Sync completed successfully. Added {added_count} jobs, skipped {skipped_count} duplicates."
        
    except Exception as e:
        scheduler_logger.error(f"Error in automated job sync: {str(e)}")
        return f"Error: {str(e)}"
