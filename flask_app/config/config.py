import os
import smartsheet


api_token = os.getenv('SMARTSHEET_API_TOKEN')
ss_client = smartsheet.Smartsheet('SMARTSHEET_API_TOKEN')
