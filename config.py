"""
Configuration for the Disease Prediction Backend
"""
import os
from datetime import timedelta


def _get_bool_env(name, default=False):
    """Parse common boolean env representations."""
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

class Config:
    """Base configuration"""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    MODEL_DIR = os.path.join(BASE_DIR, "model")
    
    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.environ.get("FLASK_ENV") == "development"
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", 
        f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-key-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=90)
    
    # Email Configuration (Gmail SMTP)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = _get_bool_env("MAIL_USE_TLS", True)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "your-email@gmail.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "your-app-password")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@healthguard.com")
    
    # OTP Configuration
    OTP_VALIDITY_MINUTES = 5
    OTP_MAX_ATTEMPTS = 3
    OTP_EMAIL_SUBJECT = "Your Disease Predictor OTP"
    
    # ABHA API Configuration
    ABHA_API_URL = os.environ.get("ABHA_API_URL", "https://healthiddev.ndhm.gov.in")
    ABHA_CLIENT_ID = os.environ.get("ABHA_CLIENT_ID", "")
    ABHA_CLIENT_SECRET = os.environ.get("ABHA_CLIENT_SECRET", "")
    ABHA_CM_ID = os.environ.get("ABHA_CM_ID", "")
    ABHA_REDIRECT_URI = os.environ.get("ABHA_REDIRECT_URI", "http://localhost:5000/api/abha/callback")

    # LLM Review Layer (OpenRouter)
    ENABLE_LLM_REVIEW = _get_bool_env("ENABLE_LLM_REVIEW", False)
    LLM_FORCE_ALL_CASES = _get_bool_env("LLM_FORCE_ALL_CASES", False)
    LLM_STRICT_FORCE_MODE = _get_bool_env("LLM_STRICT_FORCE_MODE", False)
    LLM_FORCE_BELOW_CONFIDENCE = float(os.environ.get("LLM_FORCE_BELOW_CONFIDENCE", 25.0))
    LLM_WEAK_SUPPORT_THRESHOLD = float(os.environ.get("LLM_WEAK_SUPPORT_THRESHOLD", 35.0))
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    OPENROUTER_API_KEY_FALLBACK = os.environ.get("OPENROUTER_API_KEY_FALLBACK", "")
    OPENROUTER_API_KEY_TERTIARY = os.environ.get("OPENROUTER_API_KEY_TERTIARY", "")
    OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "qwen/qwen3-next-80b-a3b-instruct:free")
    OPENROUTER_MODEL_FALLBACK = os.environ.get("OPENROUTER_MODEL_FALLBACK", "openai/gpt-oss-120b:free")
    OPENROUTER_MODEL_TERTIARY = os.environ.get("OPENROUTER_MODEL_TERTIARY", "qwen/qwen3.6-plus:free")
    OPENROUTER_API_URL = os.environ.get("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
    OPENROUTER_TIMEOUT_SECONDS = int(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", 20))
    OPENROUTER_RATE_LIMIT_COOLDOWN_SECONDS = int(os.environ.get("OPENROUTER_RATE_LIMIT_COOLDOWN_SECONDS", 120))
    OPENROUTER_BILLING_COOLDOWN_SECONDS = int(os.environ.get("OPENROUTER_BILLING_COOLDOWN_SECONDS", 900))
    OPENROUTER_SITE_URL = os.environ.get("OPENROUTER_SITE_URL", "")
    OPENROUTER_SITE_NAME = os.environ.get("OPENROUTER_SITE_NAME", "HealthGuard")
    # Backward-compatible aliases
    OPENROUTER_APP_URL = os.environ.get("OPENROUTER_APP_URL", "")
    OPENROUTER_APP_NAME = os.environ.get("OPENROUTER_APP_NAME", "HealthGuard")
    
    # CORS
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
    
class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)

config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
