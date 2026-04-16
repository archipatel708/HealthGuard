"""Authentication utilities for password-based auth and JWT using MongoDB."""

from __future__ import annotations

from datetime import datetime
from functools import wraps
from typing import Optional, Tuple

from flask import jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity, jwt_required
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

from models import User, get_user_by_email, get_user_by_id, save_user


class AuthService:
    """Handle password-based authentication operations."""

    @staticmethod
    def generate_tokens(user_id: str):
        identity = str(user_id)
        access_token = create_access_token(identity=identity)
        refresh_token = create_refresh_token(identity=identity)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
        }

    @staticmethod
    def register_user(
        email: str,
        password: str,
        phone: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[User]]:
        normalized_email = (email or "").strip().lower()
        raw_password = str(password or "")
        normalized_phone = (phone or "").strip() or None

        if not normalized_email or "@" not in normalized_email:
            return False, "Valid email is required", None
        if len(raw_password) < 6:
            return False, "Password must be at least 6 characters", None

        existing_user = get_user_by_email(normalized_email)
        if existing_user:
            if existing_user.password_hash:
                return False, "An account with this email already exists", None

            existing_user.password_hash = generate_password_hash(raw_password)
            existing_user.phone = normalized_phone or existing_user.phone
            existing_user.first_name = (first_name or "").strip() or existing_user.first_name
            existing_user.last_name = (last_name or "").strip() or existing_user.last_name
            existing_user.is_verified = True
            existing_user.updated_at = datetime.utcnow().isoformat()
            try:
                return True, "Account upgraded successfully", save_user(existing_user)
            except DuplicateKeyError:
                return False, "This phone number is already linked to another account", None

        user = User(
            email=normalized_email,
            password_hash=generate_password_hash(raw_password),
            phone=normalized_phone,
            first_name=(first_name or "").strip() or None,
            last_name=(last_name or "").strip() or None,
            is_verified=True,
        )
        try:
            return True, "Registration successful", save_user(user)
        except DuplicateKeyError:
            return False, "Account details already exist", None

    @staticmethod
    def authenticate_user(email: str, password: str) -> Tuple[bool, str, Optional[User]]:
        normalized_email = (email or "").strip().lower()
        raw_password = str(password or "")

        if not normalized_email or not raw_password:
            return False, "Email and password are required", None

        user = get_user_by_email(normalized_email)
        if not user or not user.password_hash:
            return False, "Invalid email or password", None
        if not check_password_hash(user.password_hash, raw_password):
            return False, "Invalid email or password", None
        if not user.is_active:
            return False, "User not found or inactive", None
        return True, "Login successful", user


def token_required(f):
    """Decorator to require a valid JWT token backed by MongoDB."""

    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        user_id = get_jwt_identity()
        user = get_user_by_id(str(user_id))
        if not user or not user.is_active:
            return jsonify({"error": "User not found or inactive"}), 401
        return f(user, *args, **kwargs)

    return decorated
