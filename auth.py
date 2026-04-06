"""
Authentication utilities for email/OTP and JWT
"""
import os
import base64
import secrets
import traceback
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from functools import wraps
from datetime import datetime, timedelta

from flask import request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from models import db, User, OTP, IntegrityError


class AuthService:
    """Handle authentication operations"""
    

def get_gmail_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ.get("GMAIL_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GMAIL_CLIENT_ID"),
        client_secret=os.environ.get("GMAIL_CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
    service = build("gmail", "v1", credentials=creds)
    return service
    
    @staticmethod
    def send_otp_email(email, otp_code):
        """Send OTP to user's email via Gmail API (OAuth2)"""
        try:
            sender = os.environ.get("GMAIL_SENDER") or current_app.config.get("MAIL_USERNAME")

            message = MIMEText(
                f"Your HealthGuard one-time password is: {otp_code}\n\nThis code expires in 10 minutes.",
                "plain"
            )
            message["to"] = email
            message["from"] = sender
            message["subject"] = current_app.config.get("OTP_EMAIL_SUBJECT", "Your OTP Code - HealthGuard")

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            service = get_gmail_service()
            service.users().messages().send(
                userId="me",
                body={"raw": raw}
            ).execute()

            current_app.logger.info(f"[GMAIL API] OTP email sent to {email}")
            return True, "OTP sent successfully"

        except Exception as e:
            current_app.logger.error("GMAIL API FAILURE")
            current_app.logger.error(str(e))
            current_app.logger.error(traceback.format_exc())
            return False, str(e)
    
    @staticmethod
    def create_or_get_user(email, phone=None):
        """Create user if doesn't exist or get existing user"""
        normalized_email = (email or "").strip().lower()
        user = User.query.filter_by(email=normalized_email).first()
        if not user:
            payload = {"email": email}
            clean_phone = (phone or "").strip()
            if clean_phone:
                payload["phone"] = clean_phone
            payload["email"] = normalized_email

            try:
                user = User(**payload)
                db.session.add(user)
                db.session.commit()
            except IntegrityError:
                # Another request may have created this email between read and insert.
                existing = User.query.filter_by(email=normalized_email).first()
                if existing:
                    return existing
                raise
        return user
    
    @staticmethod
    def generate_otp(email):
        """Generate and store OTP for email"""
        # Delete previous unverified OTPs
        OTP.query.filter_by(email=email, is_used=False).delete()
        
        # Create new OTP
        otp = OTP.create_otp(email, current_app.config["OTP_VALIDITY_MINUTES"])
        db.session.add(otp)
        db.session.commit()
        
        # Send OTP via email
        success, message = AuthService.send_otp_email(email, otp.otp_code)
        
        return otp, success, message
    
    @staticmethod
    def verify_otp(email, otp_code):
        """Verify OTP and mark as used"""
        otp = OTP.query.filter_by(email=email, is_used=False).order_by(OTP.created_at.desc()).first()
        
        if not otp:
            return False, "OTP not found or expired"
        
        if otp.is_expired():
            return False, "OTP has expired"
        
        if otp.attempts >= current_app.config["OTP_MAX_ATTEMPTS"]:
            return False, "Too many failed attempts. Request a new OTP"
        
        if otp.otp_code != otp_code:
            otp.attempts += 1
            db.session.commit()
            return False, "Invalid OTP"
        
        # Mark OTP as used
        otp.is_used = True
        otp.verified_at = datetime.utcnow()
        db.session.commit()
        
        return True, "OTP verified successfully"
    
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
