import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret")
    MONGO_URI = os.environ.get("MONGO_URI") or os.environ.get(
        "MONGODB_URI", "mongodb://localhost:27017/disease_prediction"
    )
    MONGO_DBNAME = os.environ.get("MONGO_DBNAME") or os.environ.get("MONGODB_DB", "disease_prediction")
    OPENROUTER_API_URL = os.environ.get(
        "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
    )
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    OPENROUTER_API_KEY_FALLBACK = os.environ.get("OPENROUTER_API_KEY_FALLBACK", "")
    OPENROUTER_API_KEY_TERTIARY = os.environ.get("OPENROUTER_API_KEY_TERTIARY", "")
    OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "qwen/qwen3-next-80b-a3b-instruct:free")
    OPENROUTER_MODEL_FALLBACK = os.environ.get("OPENROUTER_MODEL_FALLBACK", "openai/gpt-oss-120b:free")
    OPENROUTER_MODEL_TERTIARY = os.environ.get("OPENROUTER_MODEL_TERTIARY", "")
    JWT_COOKIE_NAME = "dp_session"
    JWT_EXPIRES_HOURS = 24
    SESSION_COOKIE_SAMESITE = "Lax"
