"""
Authentication utilities for email/OTP and JWT
"""
import smtplib
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from datetime import datetime, timedelta

from flask import request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from models import db, User, OTP


class AuthService:
    """Handle authentication operations"""
    
    @staticmethod
    def send_otp_email(email, otp_code):
        """Send OTP to user's email"""
        try:
            mail_username = (current_app.config.get("MAIL_USERNAME") or "").strip()
            mail_password = (current_app.config.get("MAIL_PASSWORD") or "").strip()
            # Gmail app passwords are often copied with spaces; strip them for SMTP auth.
            mail_password = mail_password.replace(" ", "")

            if not mail_username or not mail_password:
                return False, "Email service is not configured. Please set MAIL_USERNAME and MAIL_PASSWORD in .env"

            if mail_username == "your-email@gmail.com" or mail_password == "your-app-password":
                return False, "Email service is using placeholder credentials. Update MAIL_USERNAME and MAIL_PASSWORD in .env"

            msg = MIMEMultipart()
            msg["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
            msg["To"] = email
            msg["Subject"] = current_app.config["OTP_EMAIL_SUBJECT"]

            validity_minutes = current_app.config["OTP_VALIDITY_MINUTES"]
            text_body = (
                "Disease Predictor - Email Verification\n\n"
                f"Your one-time password (OTP) is: {otp_code}\n"
                f"This code is valid for {validity_minutes} minutes.\n\n"
                "For your security, do not share this code with anyone.\n"
                "If you did not request this OTP, please ignore this message."
            )

            html_body = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <meta http-equiv="X-UA-Compatible" content="IE=edge">
                <title>Verify Your Email</title>
            </head>
            <body style="margin:0; padding:0; background-color:#f4f7fb; font-family:Arial, Helvetica, sans-serif; color:#1f2937;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f4f7fb; padding:24px 12px;">
                    <tr>
                        <td align="center">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px; background:#ffffff; border:1px solid #e5e7eb; border-radius:12px; overflow:hidden;">
                                <tr>
                                    <td style="background:linear-gradient(135deg, #0f766e 0%, #115e59 100%); padding:20px 24px;">
                                        <p style="margin:0; color:#ffffff; font-size:12px; letter-spacing:1px; text-transform:uppercase; opacity:0.95;">Disease Predictor</p>
                                        <h1 style="margin:8px 0 0 0; color:#ffffff; font-size:22px; line-height:1.3;">Email Verification Code</h1>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding:28px 24px 8px 24px;">
                                        <p style="margin:0 0 14px 0; font-size:15px; line-height:1.6; color:#374151;">Use the one-time password below to continue signing in.</p>
                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:6px 0 18px 0;">
                                            <tr>
                                                <td align="center" style="background:#f8fafc; border:1px dashed #94a3b8; border-radius:10px; padding:16px;">
                                                    <span style="display:inline-block; font-size:34px; line-height:1; letter-spacing:8px; font-weight:700; color:#0f172a;">{otp_code}</span>
                                                </td>
                                            </tr>
                                        </table>
                                        <p style="margin:0 0 10px 0; font-size:14px; color:#475569; line-height:1.6;">This code will expire in <strong>{validity_minutes} minutes</strong>.</p>
                                        <p style="margin:0 0 18px 0; font-size:14px; color:#475569; line-height:1.6;">For security reasons, never share this code with anyone.</p>
                                        <div style="background:#fef3c7; border-left:4px solid #f59e0b; padding:10px 12px; border-radius:6px; margin-bottom:14px;">
                                            <p style="margin:0; font-size:13px; line-height:1.5; color:#92400e;">If you did not request this verification code, you can safely ignore this email.</p>
                                        </div>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding:0 24px 24px 24px;">
                                        <p style="margin:0; padding-top:14px; border-top:1px solid #e5e7eb; font-size:12px; color:#94a3b8; line-height:1.6;">
                                            This is an automated message from Disease Predictor. Please do not reply to this email.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            
            # Send email
            with smtplib.SMTP(
                current_app.config["MAIL_SERVER"],
                current_app.config["MAIL_PORT"],
                timeout=10,
            ) as server:
                if current_app.config["MAIL_USE_TLS"]:
                    server.starttls()
                server.login(mail_username, mail_password)
                server.send_message(msg)
            
            return True, "OTP sent successfully"
        except Exception as e:
            return False, f"Failed to send OTP: {str(e)}"
    
    @staticmethod
    def create_or_get_user(email, phone=None):
        """Create user if doesn't exist or get existing user"""
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, phone=phone)
            db.session.add(user)
            db.session.commit()
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
