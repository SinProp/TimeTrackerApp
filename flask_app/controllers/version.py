from flask_app import app
from flask import jsonify
import subprocess
import os

@app.route('/version')
def version():
    """
    Returns git version information for the running application.
    Useful for tracking what version is deployed in production.
    """
    try:
        # Get git commit hash
        git_hash = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        
        # Get branch name
        git_branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        
        # Get commit date
        git_date = subprocess.check_output(
            ['git', 'log', '-1', '--format=%cd', '--date=iso'],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        
        # Get commit message
        git_message = subprocess.check_output(
            ['git', 'log', '-1', '--format=%s'],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        
        return jsonify({
            'version': git_hash,
            'branch': git_branch,
            'commit_date': git_date,
            'commit_message': git_message,
            'full_hash': subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'],
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                stderr=subprocess.DEVNULL
            ).decode('utf-8').strip()
        })
    except Exception as e:
        return jsonify({
            'error': 'Could not retrieve git information',
            'message': str(e)
        }), 500
