import re
import random
import string
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from app.extensions import db, limiter
from app.models import User, Team, TeamMember
from app.utils import validate_csrf_token, sanitize, login_required, send_telegram_message, user_to_dict
import logging

logger = logging.getLogger(__name__)
bp = Blueprint('team', __name__)

@bp.route('/takim')
@login_required
def takim():
    ref_code = session.get('user_ref')
    if not ref_code:
        return redirect(url_for('auth.login'))
    user = User.query.filter_by(referans_kodu=ref_code).first()
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))
    return render_template('takim.html', katilimci=user_to_dict(user))

@bp.route('/api/takim-olustur', methods=['POST'])
@login_required
@limiter.limit("3 per minute")
def api_takim_olustur():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    lider_ref = session.get('user_ref', '')
    if not lider_ref:
        return jsonify({'success': False, 'message': 'Giriş ediň!'})
    takim_adi = sanitize(data.get('takim_adi', ''), 50)
    if len(takim_adi) < 2 or len(takim_adi) > 50:
        return jsonify({'success': False, 'message': 'Topar ady 2-50 harp aralygynda bolmaly!'})
    user = User.query.filter_by(referans_kodu=lider_ref).first()
    if not user:
        return jsonify({'success': False, 'message': 'Katylyjy tapylmady!'})
    if user.memberships.first():
        return jsonify({'success': False, 'message': 'Siz eýýäm topar bolduňyz!'})
    kod = 'TEAM-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    team = Team(takim_kodu=kod, takim_adi=takim_adi, lider_referans=lider_ref)
    db.session.add(team)
    db.session.flush()
    user.takim_lideri = 1
    tm = TeamMember(team_id=team.id, user_id=user.id, role='leader')
    db.session.add(tm)
    db.session.commit()
    logger.info(f"Topar: {kod} - {takim_adi}")
    return jsonify({'success': True, 'takim_kodu': kod, 'message': 'Topar üstünlikli döredildi!'})

@bp.route('/api/takima-katil', methods=['POST'])
@login_required
@limiter.limit("3 per minute")
def api_takima_katil():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    uye_ref = session.get('user_ref', '')
    if not uye_ref:
        return jsonify({'success': False, 'message': 'Giriş ediň!'})
    takim_kodu = str(data.get('takim_kodu', '')).strip().upper()
    if not re.match(r'^TEAM-[A-Z0-9]{5}$', takim_kodu):
        return jsonify({'success': False, 'message': 'Topar kody nädogry format!'})
    user = User.query.filter_by(referans_kodu=uye_ref).first()
    if not user:
        return jsonify({'success': False, 'message': 'Katylyjy tapylmady!'})
    if user.memberships.first():
        return jsonify({'success': False, 'message': 'Siz eýýäm topar bolduňyz!'})
    team = Team.query.filter_by(takim_kodu=takim_kodu).first()
    if not team:
        return jsonify({'success': False, 'message': 'Topar kody nädogry!'})
    count = TeamMember.query.filter_by(team_id=team.id).count()
    if count >= 4:
        return jsonify({'success': False, 'message': 'Bu topar doly (4 kişi)!'})
    tm = TeamMember(team_id=team.id, user_id=user.id, role='member')
    db.session.add(tm)
    db.session.commit()
    msg = f"👥 <b>TOPARA TÄZE AGZA!</b>\n\nTopar: {team.takim_adi or 'Topar'}\nKod: {takim_kodu}\n👤 {user.ad}"
    send_telegram_message(msg)
    logger.info(f"Katil: {takim_kodu} - {user.ad}")
    return jsonify({'success': True, 'message': f'Topara goşuldyňyz! ({count+1}/4)'})
