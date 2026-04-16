from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, jsonify, request

from app.models.user_model import get_user_by_id


def generate_token(user_id: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(hours=current_app.config["JWT_EXPIRES_HOURS"])
    payload = {"sub": user_id, "exp": expires}
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def decode_token(token: str):
    return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])


def set_auth_cookie(response, token: str):
    secure_flag = request.is_secure
    response.set_cookie(
        current_app.config["JWT_COOKIE_NAME"],
        token,
        httponly=True,
        secure=secure_flag,
        samesite=current_app.config["SESSION_COOKIE_SAMESITE"],
        max_age=current_app.config["JWT_EXPIRES_HOURS"] * 3600,
    )
    return response


def clear_auth_cookie(response):
    response.delete_cookie(current_app.config["JWT_COOKIE_NAME"])
    return response


def current_user_from_cookie():
    token = request.cookies.get(current_app.config["JWT_COOKIE_NAME"])
    if not token:
        return None
    try:
        payload = decode_token(token)
        return get_user_by_id(payload["sub"])
    except jwt.PyJWTError:
        return None


def login_required(view_fn):
    @wraps(view_fn)
    def wrapper(*args, **kwargs):
        user = current_user_from_cookie()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        return view_fn(user, *args, **kwargs)

    return wrapper
