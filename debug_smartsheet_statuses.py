#!/usr/bin/env python3
"""
Debug script to check what submittal statuses exist in the Smartsheet
and verify the filtering logic is working correctly.
"""
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask_app.models.job import Job

def debug_smartsheet_statuses():
    """Debug function to check all submittal statuses in Smartsheet"""
    try:
        print("=== DEBUGGING SMARTSHEET SUBMITTAL STATUSES ===")
        print("Fetching all jobs from Smartsheet (with debug info)...")
        
        # This will now print debug info showing all statuses
        approved_jobs = Job.get_approved_jobs_from_smartsheet()
        
        print(f"\n=== SUMMARY ===")
        print(f"Total jobs with 'Approved' status: {len(approved_jobs)}")
        
        if approved_jobs:
            print("\nApproved jobs found:")
            for job in approved_jobs:
                print(f"  - IM #{job['im_number']}: {job.get('general_contractor', 'Unknown GC')}")
        else:
            print("No approved jobs found.")
            
    except Exception as e:
        print(f"Error debugging smartsheet statuses: {e}")

if __name__ == "__main__":
    debug_smartsheet_statuses()
