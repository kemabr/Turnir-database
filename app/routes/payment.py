from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from app.extensions import db, limiter
from app.models import User, Tournament
from app.utils import validate_csrf_token, login_required, send_telegram_message, user_to_dict
import logging

logger = logging.getLogger(__name__)
bp = Blueprint('payment', __name__)

@bp.route('/odeme')
@login_required
def odeme():
    ref_code = session.get('user_ref')
    if not ref_code:
        return redirect(url_for('auth.login'))
    user = User.query.filter_by(referans_kodu=ref_code).first()
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))
    turnir_tolek = '5 Manat'
    turnir_tolek_usuly = 'TMCell SMS'
    if user.turnir_id:
        turnir = Tournament.query.get(user.turnir_id)
        if turnir:
            turnir_tolek = turnir.tolek
            turnir_tolek_usuly = turnir.tolek_usuly
    return render_template('odeme.html',
        katilimci=user_to_dict(user), turnir_tolek=turnir_tolek, turnir_tolek_usuly=turnir_tolek_usuly)

@bp.route('/api/odeme-yapildi', methods=['POST'])
@limiter.limit("5 per minute")
@login_required
def api_odeme_yapildi():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    ref = session.get('user_ref', '')
    if not ref:
        return jsonify({'success': False, 'message': 'Giriş ediň!'})
    user = User.query.filter_by(referans_kodu=ref).first()
    if not user:
        return jsonify({'success': False, 'message': 'Katylyjy tapylmady!'})
    now = datetime.now()
    user.odeme_durumu = 1
    user.odeme_tarihi = now
    db.session.commit()
    msg = f"💰 <b>TÖLEG!</b>\n\n👤 {user.ad}\n🔑 {ref}\n📅 {now.strftime('%Y-%m-%d %H:%M:%S')}"
    send_telegram_message(msg)
    logger.info(f"Odeme: {ref}")
    return jsonify({'success': True, 'message': 'Töleg bildirimi ugradyldy!'})
