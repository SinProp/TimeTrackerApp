# Automated Smartsheet Job Sync - Implementation Guide

## Current Implementation: APScheduler (ACTIVE)

✅ **Status**: Implemented and running
📅 **Schedule**: Daily at 6:00 AM EST
🔧 **Location**: Runs within your Flask application

### How it works:
- The scheduler runs as a background process within your Flask app
- Automatically syncs approved jobs from Smartsheet every day at 6 AM EST
- Logs all activities for monitoring and debugging
- Includes a manual test button on the "New Job" page

### Testing:
1. Go to `/new/job` page
2. Click "Test Auto Sync" button to test the automated function manually
3. Check the console logs for detailed output

---

## Alternative Options (Not Implemented)

### Option 2: Windows Task Scheduler
- **Pros**: Independent of Flask app, reliable
- **Cons**: Requires creating separate Python script
- **Setup**: Would need to create a standalone script that calls your sync function

### Option 3: Cron Job (Linux/Mac) or Scheduled Tasks
- **Pros**: System-level reliability
- **Cons**: Platform-specific, more complex setup
- **Setup**: Would require deploying to a Linux server with cron

### Option 4: Cloud Solutions (AWS Lambda, Azure Functions)
- **Pros**: Highly reliable, serverless
- **Cons**: More complex, requires cloud setup and additional costs
- **Setup**: Would need to extract sync logic to cloud function

---

## Monitoring and Troubleshooting

### Log Files:
- Scheduler logs appear in your Flask console
- Look for messages starting with "INFO:scheduler:"

### Manual Testing:
Use the "Test Auto Sync" button to verify the sync function works correctly.

### Common Issues:
1. **Timezone**: Ensure your server timezone is correct for EST scheduling
2. **Smartsheet API Limits**: Monitor for API rate limiting
3. **Database Connection**: Ensure MySQL connection remains stable

---

## Production Deployment Recommendations

For production environments, consider:

1. **Use a proper WSGI server** (Gunicorn, uWSGI) instead of Flask's development server
2. **Set up log rotation** to prevent log files from growing too large
3. **Monitor the scheduler** with health checks
4. **Consider Option 2 or 4** for critical production environments where 100% uptime is required

---

## Files Modified:

1. `server.py` - Added scheduler initialization
2. `flask_app/utils/scheduler_tasks.py` - Created sync function
3. `flask_app/controllers/jobs.py` - Added manual test endpoint
4. `flask_app/templates/new_job.html` - Added test button
5. `requirements.txt` - Added APScheduler and pytz dependencies
