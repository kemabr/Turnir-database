from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from sqlalchemy import or_
from app.extensions import db, limiter
from app.models import User, Team, TeamMember, Tournament, Setting
from app.utils import (
    validate_csrf_token, sanitize, admin_required,
    get_stats, get_turnir_data, get_bayraklar, get_all_turnirler,
    set_ayar, send_telegram_message, check_password,
    user_to_dict, team_to_dict, tournament_to_dict, export_csv
)
import logging

logger = logging.getLogger(__name__)
bp = Blueprint('admin', __name__)

@bp.route('/admin')
def admin_login():
    return render_template('admin_login.html')

@bp.route('/api/admin-login', methods=['POST'])
@limiter.limit("5 per minute")
def api_admin_login():
    data = request.get_json() or {}
    sifre = data.get('sifre', '')
    if not sifre or len(sifre) < 6:
        logger.warning(f"Nadogry login (gysga parol): {request.remote_addr}")
        return jsonify({'success': False, 'message': 'Parol 6 harpdan uly bolmaly!'})
    if not check_password(sifre):
        logger.warning(f"Nadogry login: {request.remote_addr}")
        return jsonify({'success': False, 'message': 'Parol nädogry!'})
    session['admin_logged_in'] = True
    session.permanent = True
    logger.info(f"Admin login: {request.remote_addr}")
    return jsonify({'success': True, 'message': 'Giriş üstünlikli!'})

@bp.route('/admin/logout', methods=['GET', 'POST'])
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.admin_login'))

@bp.route('/admin/panel')
@admin_required
def admin_panel():
    page_k = request.args.get('page_k', 1, type=int)
    page_t = request.args.get('page_t', 1, type=int)
    page_tr = request.args.get('page_tr', 1, type=int)
    q = request.args.get('q', '')
    turnir_filter = request.args.get('turnir_filter', '')
    per_page = 20

    k_query = User.query
    if q:
        k_query = k_query.filter(or_(
            User.ad.ilike(f'%{q}%'),
            User.telefon.ilike(f'%{q}%'),
            User.referans_kodu.ilike(f'%{q}%')
        ))
    if turnir_filter and turnir_filter.isdigit():
        k_query = k_query.filter(User.turnir_id == int(turnir_filter))
    k_pagination = k_query.order_by(User.kayit_tarihi.desc()).paginate(
        page=page_k, per_page=per_page, error_out=False)
    katilimcilar = [user_to_dict(u) for u in k_pagination.items]

    t_pagination = Team.query.order_by(Team.id.desc()).paginate(
        page=page_t, per_page=per_page, error_out=False)
    takimlar = [team_to_dict(t) for t in t_pagination.items]

    tr_pagination = Tournament.query.order_by(Tournament.created_at.desc()).paginate(
        page=page_tr, per_page=per_page, error_out=False)
    turnirler_list = [tournament_to_dict(t) for t in tr_pagination.items]
    for t in turnirler_list:
        stats = get_stats(t['id'])
        t['onaylanan'] = stats['onaylanan']
        t['galan'] = stats['galan']

    all_turnirler = Tournament.query.order_by(Tournament.created_at.desc()).all()
    all_turnirler_dict = [tournament_to_dict(t) for t in all_turnirler]

    return render_template('admin_panel.html',
        stats=get_stats(),
        katilimcilar=katilimcilar,
        katilimcilar_page=page_k,
        katilimcilar_pages=k_pagination.pages,
        katilimcilar_total=k_pagination.total,
        takimlar=takimlar,
        takimlar_page=page_t,
        takimlar_pages=t_pagination.pages,
        takimlar_total=t_pagination.total,
        turnir=get_turnir_data(),
        bayraklar=get_bayraklar(),
        turnirler=turnirler_list,
        turnirler_page=page_tr,
        turnirler_pages=tr_pagination.pages,
        turnirler_total=tr_pagination.total,
        all_turnirler=all_turnirler_dict,
        q=q,
        turnir_filter=turnir_filter)

@bp.route('/api/admin-export/<type_name>')
@admin_required
def admin_export(type_name):
    return export_csv(type_name)

@bp.route('/api/admin-turnir-ekle', methods=['POST'])
@admin_required
def api_admin_turnir_ekle():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    ad = sanitize(data.get('ad', ''), 100)
    senesi = sanitize(data.get('senesi', ''), 50)
    wagty = sanitize(data.get('wagty', ''), 50)
    karta = sanitize(data.get('karta', ''), 50)
    mode = sanitize(data.get('mode', 'squad'), 20)
    gatnasym = sanitize(data.get('gatnasym', ''), 100)
    tolek = sanitize(data.get('tolek', ''), 50)
    tolek_usuly = sanitize(data.get('tolek_usuly', ''), 100)
    yer_sany = int(data.get('yer_sany', 100))
    bayrak_1 = sanitize(data.get('bayrak_1', '300 Manat|+ 🏆 Kubok'), 100)
    bayrak_2 = sanitize(data.get('bayrak_2', '150 Manat'), 100)
    bayrak_3 = sanitize(data.get('bayrak_3', '50 Manat'), 100)
    bayrak_jemi = sanitize(data.get('bayrak_jemi', '500 M'), 100)
    status = sanitize(data.get('status', 'upcoming'), 20)
    tolekli = 1 if data.get('tolekli', True) else 0
    if not all([ad, senesi, wagty, karta]):
        return jsonify({'success': False, 'message': 'Ad, sene, wagt we karta hökmany!'})
    now = datetime.now()
    t = Tournament(ad=ad, senesi=senesi, wagty=wagty, karta=karta, mode=mode,
        gatnasym=gatnasym, tolek=tolek, tolek_usuly=tolek_usuly,
        yer_sany=yer_sany, bayrak_1=bayrak_1, bayrak_2=bayrak_2,
        bayrak_3=bayrak_3, bayrak_jemi=bayrak_jemi, status=status,
        tolekli=tolekli, created_at=now)
    db.session.add(t)
    db.session.commit()
    logger.info(f"Täze turnir goşuldy: {ad} (tolekli={tolekli})")
    return jsonify({'success': True, 'message': 'Turnir üstünlikli goşuldy!'})

@bp.route('/api/admin-turnir-guncelle', methods=['POST'])
@admin_required
def api_admin_turnir_guncelle():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    turnir_id = data.get('turnir_id')
    if not turnir_id:
        return jsonify({'success': False, 'message': 'Turnir ID hökmany!'})
    turnir = Tournament.query.get(turnir_id)
    if not turnir:
        return jsonify({'success': False, 'message': 'Turnir tapylmady!'})
    fields_map = {
        'ad': 'ad', 'senesi': 'senesi', 'wagty': 'wagty', 'karta': 'karta',
        'mode': 'mode', 'gatnasym': 'gatnasym', 'tolek': 'tolek',
        'tolek_usuly': 'tolek_usuly', 'bayrak_1': 'bayrak_1',
        'bayrak_2': 'bayrak_2', 'bayrak_3': 'bayrak_3', 'bayrak_jemi': 'bayrak_jemi',
        'status': 'status'
    }
    for key, attr in fields_map.items():
        if key in data:
            setattr(turnir, attr, sanitize(data[key], 200))
    if 'yer_sany' in data:
        turnir.yer_sany = int(data['yer_sany'])
    if 'tolekli' in data:
        turnir.tolekli = 1 if data['tolekli'] else 0
    db.session.commit()
    logger.info(f"Turnir üýtgedildi: ID {turnir_id}")
    return jsonify({'success': True, 'message': 'Turnir üstünlikli üýtgedildi!'})

@bp.route('/api/admin-turnir-sil', methods=['POST'])
@admin_required
def api_admin_turnir_sil():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    turnir_id = data.get('turnir_id')
    if not turnir_id:
        return jsonify({'success': False, 'message': 'Turnir ID hökmany!'})
    User.query.filter_by(turnir_id=turnir_id).update({'turnir_id': None})
    Tournament.query.filter_by(id=turnir_id).delete()
    db.session.commit()
    logger.info(f"Turnir pozuldy: ID {turnir_id}")
    return jsonify({'success': True, 'message': 'Turnir üstünlikli pozuldy!'})

@bp.route('/api/admin-ayarlari-kaydet', methods=['POST'])
@admin_required
def api_admin_ayarlari_kaydet():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    for key, value in data.items():
        if key != 'csrf_token' and value is not None:
            set_ayar(key, str(value))
    logger.info("Ayarlar üýtgedildi")
    return jsonify({'success': True, 'message': 'Ayarlar üstünlikli saklandy!'})

@bp.route('/api/admin-onayla', methods=['POST'])
@admin_required
def api_admin_onayla():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    ref = data.get('referans_kodu', '')
    user = User.query.filter_by(referans_kodu=ref).first()
    if not user:
        return jsonify({'success': False, 'message': 'Katylyjy tapylmady!'})
    if not user.turnir_id:
        return jsonify({'success': False, 'message': 'Katylyjy entek turnira goşulmadyk!'})
    now = datetime.now()
    user.admin_onay = 1
    user.onay_tarihi = now
    db.session.commit()
    msg = f"✅ <b>TASSYKLANDY!</b>\n\n👤 {user.ad}\n🔑 {ref}\n📅 {now.strftime('%Y-%m-%d %H:%M:%S')}"
    send_telegram_message(msg)
    logger.info(f"Onay: {ref}")
    return jsonify({'success': True, 'message': 'Katylyjy tassyklandy!'})

@bp.route('/api/admin-reddet', methods=['POST'])
@admin_required
def api_admin_reddet():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    ref = data.get('referans_kodu', '')
    user = User.query.filter_by(referans_kodu=ref).first()
    if not user:
        return jsonify({'success': False, 'message': 'Katylyjy tapylmady!'})
    user.admin_onay = 2
    db.session.commit()
    msg = f"❌ <b>RET EDILDI!</b>\n\n👤 {user.ad}\n🔑 {ref}"
    send_telegram_message(msg)
    logger.info(f"Red: {ref}")
    return jsonify({'success': True, 'message': 'Katylyjy ret edildi!'})

@bp.route('/api/admin-poz', methods=['POST'])
@admin_required
def api_admin_poz():
    data = request.get_json() or {}
    if not validate_csrf_token(data.get('csrf_token', '')):
        return jsonify({'success': False, 'message': 'CSRF token nadogry!'})
    ref = data.get('referans_kodu', '')
    user = User.query.filter_by(referans_kodu=ref).first()
    if not user:
        return jsonify({'success': False, 'message': 'Katylyjy tapylmady!'})
    memberships = TeamMember.query.filter_by(user_id=user.id).all()
    for m in memberships:
        team = m.team
        if m.role == 'leader':
            TeamMember.query.filter_by(team_id=team.id).delete()
            db.session.delete(team)
        else:
            db.session.delete(m)
    user.takim_lideri = 0
    db.session.delete(user)
    db.session.commit()
    logger.info(f"Pozuldy: {ref}")
    return jsonify({'success': True, 'message': 'Katylyjy pozuldy!'})
