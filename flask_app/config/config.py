import os
import smartsheet


api_token = os.getenv('SMARTSHEET_API_TOKEN')
ss_client = smartsheet.Smartsheet('SMARTSHEET_API_TOKEN')

app.config['MAIL_SERVER'] = 'gator4253.hostgator.com'  # The mail server
app.config['MAIL_PORT'] = 993  # The mail port, 587 for TLS
app.config['MAIL_USE_TLS'] = True  # Enable TLS
app.config['MAIL_USE_SSL'] = True  # Disable SSL
app.config['MAIL_USERNAME'] = 'tito@islandmillworkinc.com'  # Your email
app.config['MAIL_PASSWORD'] = 'Island$4157'  # Your email password
# Default sender
app.config['MAIL_DEFAULT_SENDER'] = 'tito@islandmillworkinc.com'
