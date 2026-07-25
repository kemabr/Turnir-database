from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config
from app.extensions import db, limiter
from app.utils import init_db_data

def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/static', template_folder='templates')
    app.config.from_object(Config)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.config.update(
        SESSION_COOKIE_SECURE=Config.SESSION_COOKIE_SECURE,
        SESSION_COOKIE_HTTPONLY=Config.SESSION_COOKIE_HTTPONLY,
        SESSION_COOKIE_SAMESITE=Config.SESSION_COOKIE_SAMESITE,
        PERMANENT_SESSION_LIFETIME=Config.PERMANENT_SESSION_LIFETIME
    )
    db.init_app(app)
    limiter.init_app(app)
    from app.routes import main, auth, tournament, team, payment, admin, api
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(tournament.bp)
    app.register_blueprint(team.bp)
    app.register_blueprint(payment.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(api.bp)
    with app.app_context():
        db.create_all()
        init_db_data()
    return app
  
