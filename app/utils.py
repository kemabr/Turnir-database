import os
import random
import string
import secrets
import re
import logging
import hashlib
import csv
import io
from datetime import datetime
from functools import wraps
from html import escape as html_escape

import requests
from flask import session, jsonify, render_template, request, Response
from sqlalchemy import inspect

from app.extensions import db
from app.models import User, Team, TeamMember, Tournament, Setting
from app.config import Config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def model_to_dict(model):
    if not model:
        return None
    return {c.key: getattr(model, c.key) for c in inspect(model).mapper.column_attrs}

def user_to_dict(user):
    if not user:
        return None
    data = model_to_dict(user)
    membership = TeamMember.query.filter_by(user_id=user.id).first()
    if membership:
        data['takim_kodu'] = membership.team.takim_kodu
        data['takim_adi'] = membership.team.takim_adi
    else:
        data['takim_kodu'] = None
        data['takim_adi'] = None
    if user.turnir_id:
        t = Tournament.query.get(user.turnir_id)
        data['turnir_ady'] = t.ad if t else ''
    else:
        data['turnir_ady'] = ''
    return data

def team_to_dict(team):
    if not team:
        return None
    data = model_to_dict(team)
    leader = User.query.filter_by(referans_kodu=team.lider_referans).first()
    data['lider_ady'] = leader.ad if leader else ''
    members = TeamMember.query.filter_by(team_id=team.id).all()
    non_leaders = [m for m in members if m.role != 'leader']
    for i in range(1, 4):
        if i <= len(non_leaders):
            data[f'uye{i}_referans'] = non_leaders[i-1].user.referans_kodu
        else:
            data[f'uye{i}_referans'] = None
    return data

def tournament_to_dict(t):
    if not t:
        return None
    return model_to_dict(t)

def get_ayar(key, default=''):
    row = Setting.query.get(key)
    return row.value if row else default

def set_ayar(key, value):
    s = Setting.query.get(key)
    if s:
        s.value = str(value)
    else:
        s = Setting(key=key, value=str(value))
        db.session.add(s)
    db.session.commit()

def generate_ref_code():
    while True:
        code = 'PUBG-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not User.query.filter_by(referans_kodu=code).first():
            return code

def generate_csrf_token():
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['csrf_token'] = token
    return token

def validate_csrf_token(token):
    return token and token == session.get('csrf_token')

def send_telegram_message(message):
    url = f"{Config.CLOUDFLARE_WORKER_URL}/send-message"
    if not Config.CLOUDFLARE_WORKER_URL:
        logger.warning("CLOUDFLARE_WORKER_URL bosh!")
        return False
    try:
        response = requests.post(url, json={'message': message}, timeout=15)
        return response.status_code == 200
    except requests.RequestException as e:
        logger.error(f"Telegram error: {e}")
        return False

def get_stats(turnir_id=None):
    if turnir_id:
        toplam = User.query.filter_by(turnir_id=turnir_id).count()
        odeme_yapan = User.query.filter_by(turnir_id=turnir_id, odeme_durumu=1).count()
        onaylanan = User.query.filter_by(turnir_id=turnir_id, admin_onay=1).count()
        t = Tournament.query.get(turnir_id)
        yer_sany = t.yer_sany if t else 100
    else:
        toplam = User.query.count()
        odeme_yapan = User.query.filter_by(odeme_durumu=1).count()
        onaylanan = User.query.filter_by(admin_onay=1).count()
        yer_sany = int(get_ayar('turnir_yer_sany', '100'))
    return {
        'toplam': toplam,
        'odeme_yapan': odeme_yapan,
        'onaylanan': onaylanan,
        'yer_sany': yer_sany,
        'galan': max(0, yer_sany - onaylanan)
    }

def get_turnir_data(turnir_id=None):
    if turnir_id:
        row = Tournament.query.get(turnir_id)
        if row:
            return tournament_to_dict(row)
    return {
        'id': None,
        'ad': 'PUBG MOBILE SQUAD',
        'senesi': get_ayar('turnir_senesi'),
        'wagty': get_ayar('turnir_wagty'),
        'karta': get_ayar('turnir_karta'),
        'gatnasym': get_ayar('turnir_gatnasym'),
        'tolek': get_ayar('turnir_tolek'),
        'tolek_usuly': get_ayar('turnir_tolek_usuly'),
        'mode': 'squad',
        'tolekli': 1
    }

def get_bayraklar(turnir_id=None):
    if turnir_id:
        row = Tournament.query.get(turnir_id)
        if row:
            b1 = row.bayrak_1.split('|')
            b2 = row.bayrak_2.split('|')
            b3 = row.bayrak_3.split('|')
            return {
                'bir': {'mukdar': b1[0], 'bonus': b1[1] if len(b1) > 1 else ''},
                'iki': {'mukdar': b2[0], 'bonus': b2[1] if len(b2) > 1 else ''},
                'uc': {'mukdar': b3[0], 'bonus': b3[1] if len(b3) > 1 else ''},
                'jemi': row.bayrak_jemi
            }
    b1 = get_ayar('bayrak_1').split('|')
    b2 = get_ayar('bayrak_2').split('|')
    b3 = get_ayar('bayrak_3').split('|')
    return {
        'bir': {'mukdar': b1[0], 'bonus': b1[1] if len(b1) > 1 else ''},
        'iki': {'mukdar': b2[0], 'bonus': b2[1] if len(b2) > 1 else ''},
        'uc': {'mukdar': b3[0], 'bonus': b3[1] if len(b3) > 1 else ''},
        'jemi': get_ayar('bayrak_jemi')
    }

def get_all_turnirler(status=None, mode=None):
    query = Tournament.query
    if status:
        query = query.filter_by(status=status)
    if mode:
        query = query.filter_by(mode=mode)
    rows = query.order_by(Tournament.created_at.desc()).all()
    turnirler = []
    for row in rows:
        stats = get_stats(row.id)
        turnirler.append({
            'id': row.id, 'ad': row.ad, 'senesi': row.senesi, 'wagty': row.wagty,
            'karta': row.karta, 'mode': row.mode, 'gatnasym': row.gatnasym,
            'tolek': row.tolek, 'tolek_usuly': row.tolek_usuly, 'yer_sany': row.yer_sany,
            'bayrak_jemi': row.bayrak_jemi, 'status': row.status, 'tolekli': row.tolekli,
            'onaylanan': stats['onaylanan'], 'galan': stats['galan']
        })
    return turnirler

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            from flask import redirect, url_for
            return redirect(url_for('main.admin_login'))
        return f(*args, **kwargs)
    return decorated

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_logged_in'):
            from flask import redirect, url_for
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def validate_phone(phone):
    if not phone:
        return False, None
    cleaned = re.sub(r'[\s\-\+\(\)]', '', phone)
    if not cleaned.isdigit():
        return False, None
    if len(cleaned) == 8:
        return True, cleaned
    if len(cleaned) == 11 and cleaned.startswith('993'):
        return True, cleaned[3:]
    return False, None

def sanitize(text, max_len=100):
    if not text:
        return ''
    return html_escape(str(text).strip())[:max_len]

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def check_password(password):
    return password == Config.ADMIN_SIFRE_HASH

def export_csv(type_name):
    output = io.StringIO()
    writer = csv.writer(output)
    if type_name == 'katilimcilar':
        writer.writerow(['ID', 'Referans Kodu', 'Ad', 'Telefon', 'PUBG ID', 'Turnir', 'Toleg', 'Onay', 'Kayit Tarihi'])
        users = User.query.order_by(User.kayit_tarihi.desc()).all()
        for u in users:
            turnir_adi = ''
            if u.turnir_id:
                t = Tournament.query.get(u.turnir_id)
                if t:
                    turnir_adi = t.ad
            writer.writerow([
                u.id, u.referans_kodu, u.ad, u.telefon,
                u.pubg_id or '', turnir_adi,
                'Evet' if u.odeme_durumu else 'Hayir',
                {0: 'Garasyl yar', 1: 'Tassyklandy', 2: 'Ret edildi'}.get(u.admin_onay, ''),
                u.kayit_tarihi.strftime('%Y-%m-%d %H:%M:%S') if u.kayit_tarihi else ''
            ])
    elif type_name == 'takimlar':
        writer.writerow(['ID', 'Takim Kodu', 'Takim Adi', 'Lider', 'Agza Sany', 'Durum'])
        teams = Team.query.order_by(Team.id.desc()).all()
        for t in teams:
            leader = User.query.filter_by(referans_kodu=t.lider_referans).first()
            count = TeamMember.query.filter_by(team_id=t.id).count()
            writer.writerow([
                t.id, t.takim_kodu, t.takim_adi or '',
                leader.ad if leader else '', count, t.durum
            ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={type_name}.csv'}
    )

def init_db_data():
    defaults = {
        'turnir_senesi': '25 Iýul 2026', 'turnir_wagty': '20:00 (TM)',
        'turnir_karta': 'Erangel', 'turnir_gatnasym': 'Squad (4 kişi)',
        'turnir_tolek': '5 Manat', 'turnir_tolek_usuly': 'TMCell SMS',
        'turnir_yer_sany': '100', 'bayrak_1': '300 Manat|+ 🏆 Kubok',
        'bayrak_2': '150 Manat', 'bayrak_3': '50 Manat', 'bayrak_jemi': '500 M'
    }
    for key, value in defaults.items():
        if not Setting.query.get(key):
            db.session.add(Setting(key=key, value=value))
    if not Tournament.query.first():
        now = datetime.now()
        db.session.add(Tournament(
            ad='PUBG MOBILE SQUAD', senesi='25 Iýul 2026', wagty='20:00 (TM)',
            karta='Erangel', mode='squad', gatnasym='Squad (4 kişi)',
            tolek='5 Manat', tolek_usuly='TMCell SMS', yer_sany=100,
            status='upcoming', tolekli=1, created_at=now
        ))
    db.session.commit()
