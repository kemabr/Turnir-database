from flask import Blueprint, render_template, request, session, jsonify
from app.models import User
from app.utils import get_stats, get_turnir_data, get_bayraklar

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    user_turnir_id = None
    if session.get('user_logged_in') and session.get('user_ref'):
        user = User.query.filter_by(referans_kodu=session['user_ref']).first()
        if user and user.turnir_id:
            user_turnir_id = user.turnir_id
    return render_template('index.html',
        stats=get_stats(user_turnir_id),
        turnir=get_turnir_data(user_turnir_id),
        bayraklar=get_bayraklar(user_turnir_id),
        user_turnir_id=user_turnir_id)

@bp.route('/magazyn')
def magazyn():
    return render_template('magazyn.html')

@bp.route('/menyu')
def menyu():
    return render_template('menyu.html')

@bp.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Sahypa tapylmady'}), 404
    return render_template('404.html'), 404

@bp.errorhandler(500)
def server_error(e):
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f'500: {e}', exc_info=True)
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Serwer ýalňyşlygy'}), 500
    return render_template('500.html'), 500

@bp.errorhandler(429)
def rate_limit(e):
    return jsonify({'success': False, 'message': 'Gaty köp synanyşyk!'}), 429
