from flask import Blueprint, jsonify
from app.utils import generate_csrf_token

bp = Blueprint('api', __name__)

@bp.route('/api/csrf-token')
def api_csrf_token():
    return jsonify({'success': True, 'csrf_token': generate_csrf_token()})
