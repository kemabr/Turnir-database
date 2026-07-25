from datetime import datetime
from app.extensions import db

class User(db.Model):
    __tablename__ = 'katilimcilar'
    id = db.Column(db.Integer, primary_key=True)
    referans_kodu = db.Column(db.String(20), unique=True, nullable=False)
    ad = db.Column(db.String(100), nullable=False)
    telefon = db.Column(db.String(20), unique=True, nullable=False)
    parol_hash = db.Column(db.String(64), nullable=False)
    pubg_id = db.Column(db.String(20))
    payment_phone = db.Column(db.String(20))
    tournament_id = db.Column(db.String(50))
    turnir_id = db.Column(db.Integer, db.ForeignKey('turnirler.id'))
    ulasim = db.Column(db.String(100))
    takim_lideri = db.Column(db.Integer, default=0)
    odeme_durumu = db.Column(db.Integer, default=0)
    admin_onay = db.Column(db.Integer, default=0)
    kayit_tarihi = db.Column(db.DateTime, default=datetime.now)
    odeme_tarihi = db.Column(db.DateTime)
    onay_tarihi = db.Column(db.DateTime)
    turnir = db.relationship('Tournament', backref='katilimcilar_list')
    memberships = db.relationship('TeamMember', back_populates='user', cascade='all, delete-orphan')

class Team(db.Model):
    __tablename__ = 'takimlar'
    id = db.Column(db.Integer, primary_key=True)
    takim_kodu = db.Column(db.String(20), unique=True, nullable=False)
    takim_adi = db.Column(db.String(50))
    lider_referans = db.Column(db.String(20), nullable=False)
    durum = db.Column(db.Integer, default=0)
    members = db.relationship('TeamMember', back_populates='team', cascade='all, delete-orphan', lazy='dynamic')

class TeamMember(db.Model):
    __tablename__ = 'team_members'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('takimlar.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('katilimcilar.id'), nullable=False)
    role = db.Column(db.String(20), default='member')
    joined_at = db.Column(db.DateTime, default=datetime.now)
    team = db.relationship('Team', back_populates='members')
    user = db.relationship('User', back_populates='memberships')

class Tournament(db.Model):
    __tablename__ = 'turnirler'
    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(100), nullable=False)
    senesi = db.Column(db.String(50), nullable=False)
    wagty = db.Column(db.String(50), nullable=False)
    karta = db.Column(db.String(50), nullable=False)
    mode = db.Column(db.String(20), default='squad')
    gatnasym = db.Column(db.String(100), nullable=False)
    tolek = db.Column(db.String(50), nullable=False)
    tolek_usuly = db.Column(db.String(100), nullable=False)
    yer_sany = db.Column(db.Integer, default=100)
    bayrak_1 = db.Column(db.String(100), default='300 Manat|+ 🏆 Kubok')
    bayrak_2 = db.Column(db.String(100), default='150 Manat')
    bayrak_3 = db.Column(db.String(100), default='50 Manat')
    bayrak_jemi = db.Column(db.String(100), default='500 M')
    status = db.Column(db.String(20), default='upcoming')
    tolekli = db.Column(db.Integer, default=1)
    durum = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Setting(db.Model):
    __tablename__ = 'ayarlar'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(500), nullable=False)
