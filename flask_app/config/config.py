import os

# ===== DATAVERSE CONFIGURATION =====
# These are loaded from environment variables for security
# Set these in your deployment environment (AWS, local .env, etc.)
DATAVERSE_BASE_URL = os.environ.get("DATAVERSE_BASE_URL", "")
DATAVERSE_TENANT_ID = os.environ.get("DATAVERSE_TENANT_ID", "")
DATAVERSE_CLIENT_ID = os.environ.get("DATAVERSE_CLIENT_ID", "")
DATAVERSE_CLIENT_SECRET = os.environ.get("DATAVERSE_CLIENT_SECRET", "")
