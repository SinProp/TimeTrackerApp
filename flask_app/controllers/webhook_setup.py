# controllers/webhook_setup.py

import smartsheet
from flask import jsonify, request


def setup_webhook(app, smartsheet_token, sheet_id, callback_url):
    smartsheet_client = smartsheet.Smartsheet(
        'pp26gxIAvwiWlpO5ri51539uYSOqONhiwV4LI')

    webhook = smartsheet.models.Webhook({
        'name': 'My Webhook',
        'callbackUrl': callback_url,
        'scope': 'sheet',
        'scopeObjectId': sheet_id,
        'events': ['cell.columnValueChange']
    })

    response = smartsheet_client.Webhooks.create_webhook(webhook)

    # Add a route to your Flask app for webhook verification
    @app.route('/webhook-endpoint', methods=['GET'])
    def verify_webhook():
        challenge = request.args.get('smartsheetHookChallenge')
        if challenge:
            return jsonify({'smartsheetHookResponse': challenge})
        else:
            return '', 400

    # Enable the webhook
    smartsheet_client.Webhooks.update_webhook(
        response.result.id, {'enabled': True})

    return app
