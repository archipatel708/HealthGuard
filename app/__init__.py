from flask import Flask

from app.config import Config
from app.extensions import bcrypt, mongo
from app.routes.auth import auth_bp
from app.routes.health import health_bp
from app.routes.predict import predict_bp
from app.routes.profile import profile_bp
from app.routes.ui import ui_bp


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    bcrypt.init_app(app)
    mongo.init_app(app)

    app.register_blueprint(ui_bp)
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(predict_bp, url_prefix="/api")
    return app
