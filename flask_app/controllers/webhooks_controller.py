import smartsheet
import os
from flask import Blueprint, jsonify, request

# Initialize Smartsheet client outside of the function to avoid re-creation for every call
SMARTSHEET_API_TOKEN = os.getenv('SMARTSHEET_API_TOKEN')
smartsheet_client = smartsheet.Smartsheet(SMARTSHEET_API_TOKEN)

# Create a Blueprint for your webhook
webhook_blueprint = Blueprint('webhook_blueprint', __name__)


@webhook_blueprint.route('/webhook-endpoint', methods=['GET', 'POST'])
def webhook_endpoint():
    if request.method == 'GET':
        # Verification request from Smartsheet
        challenge = request.args.get('smartsheetHookChallenge')
        if challenge:
            return jsonify({'smartsheetHookResponse': challenge})
        return '', 400
    elif request.method == 'POST':
        # Here you'll handle the incoming webhook data
        # Make sure to implement verification and security checks
        webhook_data = request.json
        # Process the webhook data
        return '', 200


def setup_webhook(sheet_id, callback_url):
    # Create a new webhook
    webhook = smartsheet.models.Webhook({
        'name': 'My Webhook',
        'callbackUrl': 'https://87ae-2001-579-2470-90-48e6-721c-4a62-588d.ngrok-free.app/webhook-endpoint',
        'scope': 'sheet',
        'scopeObjectId': 1954899010316164,
        # Adjust the events to your needs
        'events': ['cell.columnValueChange.{4963616297379716}']
    })

    # Error handling for creating the webhook
    try:
        response = smartsheet_client.Webhooks.create_webhook(webhook)
        webhook_id = response.result.id
        # Enable the webhook
        smartsheet_client.Webhooks.update_webhook(
            webhook_id, {'enabled': True})
    except smartsheet.exceptions.SmartsheetError as e:
        print(f"Error creating webhook: {e}")


# Call this function from your main application context with appropriate arguments
# setup_webhook(sheet_id='YOUR_SHEET_ID', callback_url='YOUR_CALLBACK_URL')
