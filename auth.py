"""
Authentication utilities for password-based auth and JWT
"""
from functools import wraps
from datetime import datetime

from flask import jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from werkzeug.security import check_password_hash, generate_password_hash

from models import db, User


class AuthService:
    """Handle authentication operations"""

    @staticmethod
    def generate_tokens(user_id):
        """Generate JWT access and refresh tokens"""
        # Store identity as string for PyJWT/subject compatibility.
        identity = str(user_id)
        access_token = create_access_token(identity=identity)
        refresh_token = create_refresh_token(identity=identity)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer"
        }

    @staticmethod
    def register_user(email, password, phone=None, first_name=None, last_name=None):
        """Create a password-based user account."""
        normalized_email = (email or "").strip().lower()
        raw_password = str(password or "")
        normalized_phone = (phone or "").strip() or None

        if not normalized_email or "@" not in normalized_email:
            return False, "Valid email is required", None
        if len(raw_password) < 6:
            return False, "Password must be at least 6 characters", None

        existing_user = User.query.filter_by(email=normalized_email).first()

        if normalized_phone:
            existing_phone = User.query.filter_by(phone=normalized_phone).first()
            if existing_phone and (not existing_user or existing_phone.id != existing_user.id):
                return False, "This phone number is already linked to another account", None

        if existing_user:
            if existing_user.password_hash:
                return False, "An account with this email already exists", None

            existing_user.password_hash = generate_password_hash(raw_password)
            existing_user.phone = normalized_phone or existing_user.phone
            existing_user.first_name = (first_name or "").strip() or existing_user.first_name
            existing_user.last_name = (last_name or "").strip() or existing_user.last_name
            existing_user.is_verified = True
            existing_user.updated_at = datetime.utcnow()
            db.session.commit()
            return True, "Account upgraded successfully", existing_user

        user = User(
            email=normalized_email,
            password_hash=generate_password_hash(raw_password),
            phone=normalized_phone,
            first_name=(first_name or "").strip() or None,
            last_name=(last_name or "").strip() or None,
            is_verified=True,
        )
        db.session.add(user)
        db.session.commit()
        return True, "Registration successful", user

    @staticmethod
    def authenticate_user(email, password):
        """Validate a password-based login."""
        normalized_email = (email or "").strip().lower()
        raw_password = str(password or "")

        if not normalized_email or not raw_password:
            return False, "Email and password are required", None

        user = User.query.filter_by(email=normalized_email).first()
        if not user or not user.password_hash:
            return False, "Invalid email or password", None
        if not check_password_hash(user.password_hash, raw_password):
            return False, "Invalid email or password", None
        if not user.is_active:
            return False, "User not found or inactive", None
        return True, "Login successful", user


def token_required(f):
    """Decorator to require valid JWT token"""
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        user_id = get_jwt_identity()
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid token identity"}), 401
        user = User.query.get(user_id)
        
        if not user or not user.is_active:
            return jsonify({"error": "User not found or inactive"}), 401
        
        return f(user, *args, **kwargs)
    
    return decorated
