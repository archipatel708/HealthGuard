"""Configuration for the Disease Prediction Backend."""

import os
from datetime import timedelta


def _get_bool_env(name, default=False):
    """Parse common boolean env representations."""
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Base configuration."""

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    MODEL_DIR = os.path.join(BASE_DIR, "model")

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.environ.get("FLASK_ENV") == "development"

    MONGODB_URI = os.environ.get("MONGODB_URI", "")
    MONGODB_DB = os.environ.get("MONGODB_DB", "healthguard")

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-key-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=90)

    ABHA_API_URL = os.environ.get("ABHA_API_URL", "https://healthiddev.ndhm.gov.in")
    ABHA_CLIENT_ID = os.environ.get("ABHA_CLIENT_ID", "")
    ABHA_CLIENT_SECRET = os.environ.get("ABHA_CLIENT_SECRET", "")
    ABHA_CM_ID = os.environ.get("ABHA_CM_ID", "")
    ABHA_REDIRECT_URI = os.environ.get("ABHA_REDIRECT_URI", "http://localhost:5000/api/abha/callback")

    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = _get_bool_env("MAIL_USE_TLS", True)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "your-email@gmail.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "your-app-password")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@healthguard.com")


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    TESTING = True
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
