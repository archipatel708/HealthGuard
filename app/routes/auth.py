from flask import Blueprint, jsonify, request

from app.extensions import bcrypt
from app.models.user_model import create_user, get_user_by_email
from app.services.auth_service import (
    clear_auth_cookie,
    current_user_from_cookie,
    generate_token,
    set_auth_cookie,
)

auth_bp = Blueprint("auth", __name__)


def _public_user(user_doc: dict) -> dict:
    return {
        "id": str(user_doc["_id"]),
        "name": user_doc.get("name", ""),
        "email": user_doc.get("email", ""),
        "phone": user_doc.get("phone", ""),
        "gender": user_doc.get("gender", "unspecified"),
        "abha_records_count": len(user_doc.get("abha_records", [])),
    }


def _verify_password(user_doc: dict, password: str) -> bool:
    stored_hash = user_doc.get("password_hash", "")
    if not stored_hash:
        return False
    try:
        return bcrypt.check_password_hash(stored_hash, password)
    except (ValueError, TypeError):
        # Handles legacy/invalid hash formats without crashing login endpoint.
        return False


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name", "").strip()
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")

    if not name or not email or not password:
        return jsonify({"error": "name, email, and password are required"}), 400

    if get_user_by_email(email):
        return jsonify({"error": "Email already exists"}), 409

    password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user_doc = create_user(name=name, email=email, password_hash=password_hash)
    token = generate_token(str(user_doc["_id"]))
    response = jsonify({"user": _public_user(user_doc), "message": "registered"})
    return set_auth_cookie(response, token), 201


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")

    user_doc = get_user_by_email(email)
    if not user_doc or not _verify_password(user_doc, password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = generate_token(str(user_doc["_id"]))
    response = jsonify({"user": _public_user(user_doc), "message": "logged_in"})
    return set_auth_cookie(response, token), 200


@auth_bp.post("/logout")
def logout():
    response = jsonify({"message": "logged_out"})
    return clear_auth_cookie(response), 200


@auth_bp.get("/me")
def me():
    user_doc = current_user_from_cookie()
    if not user_doc:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"user": _public_user(user_doc)}), 200
