from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from app.extensions import db, limiter
from app.models import User, Tournament
from app.utils import (
    validate_csrf_token, sanitize, validate_phone, login_required,
    get_all_turnirler, get_turnir_data, tournament_to_dict
)
import logging

logger = logging.getLogger(__name__)
bp = Blueprint('tournament', __name__)

@bp.route('/turnir')
def turnir():
    turnirler = get_all_turnirler()
    return render_template('turnir.html', turnirler=turnirler)

@bp.route('/turnir/gosul')
@login_required
def turnir_gosul():
    tournament_id = request.args.get('id', '')
    turnir = None
    if tournament_id and tournament_id.isdigit():
        t = Tournament.query.get(int(tournament_id))
        if t:
            turnir = tournament_to_dict(t)
    if not turnir:
        turnir = {
            'id': 1, 'ad': 'PUBG MOBILE SQUAD', 'senesi': '25 Iýul 2026',
            'wagty': '20:00 (TM)', 'karta': 'Erangel', 'mode': 'squad',
            'gatnasym': 'Squad (4 kişi)', 'tolek': '5 Manat',
            'tolek_usuly': 'TMCell SMS', 'tolekli': 1
        }
    return render_template('turnir_gosul.html', turnir=turnir)

@bp.route('/api/turnir-goşul', methods=['POST'])
@login_required
@limiter.limit("3 per minute")
def api_turnir_gosul():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    pubg_id = sanitize(data.get('pubg_id', ''), 20)
    payment_phone = str(data.get('payment_phone', '')).strip()
    tournament_id = sanitize(data.get('tournament_id', ''), 50)
    turnir_id = data.get('turnir_id')
    if not pubg_id or len(pubg_id) < 8 or not pubg_id.isdigit():
        return jsonify({'success': False, 'message': 'PUBG ID diňe san bolmaly (minimum 8)!'})
    ref = session.get('user_ref', '')
    user = User.query.filter_by(referans_kodu=ref).first()
    if not user:
        return jsonify({'success': False, 'message': 'Giriş ediň!'})
    if not turnir_id:
        first_t = Tournament.query.order_by(Tournament.id.asc()).first()
        turnir_id = first_t.id if first_t else 1
    else:
        turnir_id = int(turnir_id)
    turnir = Tournament.query.get(turnir_id)
    if not turnir:
        return jsonify({'success': False, 'message': 'Turnir tapylmady!'})
    is_tolekli = turnir.tolekli == 1
    if is_tolekli:
        valid, phone_clean = validate_phone(payment_phone)
        if not valid:
            return jsonify({'success': False, 'message': 'Telefon belgisi nadogry!'})
    else:
        phone_clean = payment_phone if payment_phone else ''
    now = datetime.now()
    if not is_tolekli:
        user.pubg_id = pubg_id
        user.payment_phone = phone_clean
        user.tournament_id = tournament_id
        user.turnir_id = turnir_id
        user.odeme_durumu = 1
        user.admin_onay = 1
        user.onay_tarihi = now
        db.session.commit()
        logger.info(f"Turnir goşul (tolegsiz): {ref} -> turnir_id: {turnir_id}")
        return jsonify({'success': True, 'message': 'Turnira üstünlikli goşuldyňyz!', 'turnir_id': turnir_id, 'auto_approved': True})
    user.pubg_id = pubg_id
    user.payment_phone = phone_clean
    user.tournament_id = tournament_id
    user.turnir_id = turnir_id
    db.session.commit()
    logger.info(f"Turnir goşul (tolekli): {ref} -> turnir_id: {turnir_id}")
    return jsonify({'success': True, 'message': 'Turnira goşuldyňyz! Indi töleg ediň.', 'turnir_id': turnir_id})

@bp.route('/api/turnir-detay/<int:turnir_id>')
def api_turnir_detay(turnir_id):
    turnir = Tournament.query.get(turnir_id)
    if not turnir:
        return jsonify({'success': False, 'message': 'Turnir tapylmady!'})
    return jsonify({'success': True, 'turnir': tournament_to_dict(turnir)})
