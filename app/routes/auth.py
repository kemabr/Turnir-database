from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from app.extensions import db, limiter
from app.models import User, Tournament
from app.utils import (
    generate_ref_code, generate_csrf_token, validate_csrf_token,
    validate_phone, sanitize, hash_password, login_required,
    send_telegram_message, user_to_dict
)
import logging

logger = logging.getLogger(__name__)
bp = Blueprint('auth', __name__)

@bp.route('/kayit')
def kayit():
    return render_template('kayit.html')

@bp.route('/login')
def login():
    return render_template('login.html')

@bp.route('/api/kayit-ol', methods=['POST'])
@limiter.limit("3 per minute")
def api_kayit_ol():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    ad = sanitize(data.get('ad', ''), 100)
    telefon = str(data.get('telefon', '')).strip()
    parol = data.get('parol', '')
    parol_tekrar = data.get('parol_tekrar', '')
    if not all([ad, telefon, parol]):
        return jsonify({'success': False, 'message': 'Ahli maglumatlary dolduryň!'})
    if len(parol) < 6:
        return jsonify({'success': False, 'message': 'Parol 6 harpdan uly bolmaly!'})
    if parol != parol_tekrar:
        return jsonify({'success': False, 'message': 'Parollar deň däl!'})
    valid, telefon_clean = validate_phone(telefon)
    if not valid:
        return jsonify({'success': False, 'message': 'Telefon belgisi nadogry!'})
    if len(ad) < 2:
        return jsonify({'success': False, 'message': 'Ad 2 harpdan uly bolmaly!'})
    existing = User.query.filter_by(telefon=telefon_clean).first()
    if existing:
        return jsonify({'success': False, 'message': 'Bu telefon belgisi bilen eýýäm hasap açylypdyr!'})
    ref = generate_ref_code()
    parol_hash = hash_password(parol)
    now = datetime.now()
    user = User(referans_kodu=ref, ad=ad, telefon=telefon_clean, parol_hash=parol_hash, kayit_tarihi=now)
    db.session.add(user)
    db.session.commit()
    msg = f"🎮 <b>TÄZE KATYLYJY!</b>\n\n👤 {ad}\n📞 {telefon_clean}\n🔑 {ref}"
    send_telegram_message(msg)
    logger.info(f"Kayit: {ref} - {ad}")
    session['user_logged_in'] = True
    session['user_ref'] = ref
    session['user_telefon'] = telefon_clean
    session.permanent = True
    return jsonify({'success': True, 'referans_kodu': ref, 'message': 'Ustunlikli!'})

@bp.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")
def api_login():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    telefon = str(data.get('telefon', '')).strip()
    parol = data.get('parol', '')
    if not all([telefon, parol]):
        return jsonify({'success': False, 'message': 'Telefon we parol girizin!'})
    valid, telefon_clean = validate_phone(telefon)
    if not valid:
        return jsonify({'success': False, 'message': 'Telefon belgisi nadogry!'})
    parol_hash = hash_password(parol)
    kat = User.query.filter_by(telefon=telefon_clean, parol_hash=parol_hash).first()
    if not kat:
        return jsonify({'success': False, 'message': 'Telefon belgisi ýa-da parol nädogry!'})
    session['user_logged_in'] = True
    session['user_ref'] = kat.referans_kodu
    session['user_telefon'] = telefon_clean
    session.permanent = True
    logger.info(f"Login: {kat.referans_kodu} - {kat.ad}")
    return jsonify({'success': True, 'referans_kodu': kat.referans_kodu, 'message': 'Giriş üstünlikli!'})

@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('user_logged_in', None)
    session.pop('user_ref', None)
    session.pop('user_telefon', None)
    return redirect(url_for('main.index'))

@bp.route('/profil')
@login_required
def profil():
    ref_code = session.get('user_ref')
    if not ref_code:
        return redirect(url_for('auth.login'))
    user = User.query.filter_by(referans_kodu=ref_code).first()
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))
    kat = user_to_dict(user)
    user_turnir = None
    if user.turnir_id:
        row = Tournament.query.get(user.turnir_id)
        if row:
            user_turnir = {'id': row.id, 'ad': row.ad, 'senesi': row.senesi, 'wagty': row.wagty, 'karta': row.karta, 'tolekli': row.tolekli}
    arkadaslar = []
    if kat.get('takim_kodu'):
        membership = user.memberships[0] if user.memberships else None
        if membership:
            friends = db.session.query(User).join(TeamMember).filter(
                TeamMember.team_id == membership.team_id, User.id != user.id).all()
            arkadaslar = [{'ad': f.ad, 'referans_kodu': f.referans_kodu, 'admin_onay': f.admin_onay} for f in friends]
    return render_template('profil.html',
        katilimci=kat, takim_arkadaslari=arkadaslar, user_turnir=user_turnir)

@bp.route('/api/katilimci/me')
@login_required
def api_katilimci_me():
    ref = session.get('user_ref')
    if not ref:
        return jsonify({'success': False, 'message': 'Giris edilmedi'}), 401
    user = User.query.filter_by(referans_kodu=ref).first()
    if not user:
        session.clear()
        return jsonify({'success': False, 'message': 'Katylyjy tapylmady'}), 404
    result = user_to_dict(user)
    if user.turnir_id:
        t = Tournament.query.get(user.turnir_id)
        if t:
            result['turnir_ady'] = t.ad
            result['turnir_senesi'] = t.senesi
            result['turnir_wagty'] = t.wagty
    return jsonify({'success': True, 'katilimci': result})

@bp.route('/api/katilimci/<ref_code>')
@login_required
def api_katilimci(ref_code):
    user = User.query.filter_by(referans_kodu=ref_code).first()
    if not user:
        return jsonify({'success': False})
    return jsonify({'success': True, 'katilimci': user_to_dict(user)})
