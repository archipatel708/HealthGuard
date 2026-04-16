"""
Database Models for Disease Prediction Backend
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import inspect, text
import secrets

db = SQLAlchemy()


class User(db.Model):
    """User model for storing user account information"""
    __tablename__ = "users"
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    
    # ABHA Integration
    abha_id = db.Column(db.String(255), unique=True, nullable=True)
    abha_token = db.Column(db.Text, nullable=True)
    abha_linked_at = db.Column(db.DateTime, nullable=True)
    
    # Account Status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    otps = db.relationship("OTP", backref="user", lazy=True, cascade="all, delete-orphan")
    predictions = db.relationship("PredictionHistory", backref="user", lazy=True, cascade="all, delete-orphan")
    health_records = db.relationship("HealthRecord", backref="user", lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "phone": self.phone,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "age": self.age,
            "gender": self.gender,
            "abha_id": self.abha_id,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def ensure_schema():
    """Apply lightweight schema fixes for existing deployments."""
    inspector = inspect(db.engine)
    if not inspector.has_table("users"):
        return

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "password_hash" not in user_columns:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))


class OTP(db.Model):
    """OTP model for email-based authentication"""
    __tablename__ = "otps"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    otp_code = db.Column(db.String(6), nullable=False)
    
    # OTP Status
    is_used = db.Column(db.Boolean, default=False)
    attempts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    verified_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f"<OTP {self.email}>"
    
    def is_valid(self):
        """Check if OTP is still valid"""
        return (
            not self.is_used
            and self.attempts < 3
            and datetime.utcnow() < self.expires_at
        )
    
    def is_expired(self):
        """Check if OTP has expired"""
        return datetime.utcnow() > self.expires_at
    
    @staticmethod
    def create_otp(email, validity_minutes=5):
        """Create a new OTP for given email"""
        otp_code = ''.join(secrets.choice('0123456789') for _ in range(6))
        expires_at = datetime.utcnow() + timedelta(minutes=validity_minutes)
        
        otp = OTP(
            email=email,
            otp_code=otp_code,
            expires_at=expires_at
        )
        return otp


class PredictionHistory(db.Model):
    """Store user's prediction history"""
    __tablename__ = "prediction_history"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    
    # Symptoms and Results
    symptoms = db.Column(db.JSON, nullable=False)  # List of symptoms
    predicted_disease = db.Column(db.String(255), nullable=False)
    confidence_score = db.Column(db.Float)
    top3_predictions = db.Column(db.JSON)  # Store top 3 predictions with probabilities
    
    # Additional Info
    notes = db.Column(db.Text)
    severity_level = db.Column(db.String(50))  # mild, moderate, severe
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<PredictionHistory {self.id} - {self.predicted_disease}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "symptoms": self.symptoms,
            "predicted_disease": self.predicted_disease,
            "confidence_score": self.confidence_score,
            "top3_predictions": self.top3_predictions,
            "notes": self.notes,
            "severity_level": self.severity_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class HealthRecord(db.Model):
    """Store detailed health records linked to predictions"""
    __tablename__ = "health_records"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey("prediction_history.id"), nullable=True)
    
    # Health Information
    blood_pressure = db.Column(db.String(50))  # systolic/diastolic
    heart_rate = db.Column(db.Integer)  # bpm
    temperature = db.Column(db.Float)  # celsius
    oxygen_saturation = db.Column(db.Float)  # percentage
    blood_sugar = db.Column(db.Float)  # mg/dL
    
    # Medical History
    allergies = db.Column(db.JSON)
    medications = db.Column(db.JSON)
    past_illnesses = db.Column(db.JSON)
    
    # ABHA Data (if linked)
    abha_data = db.Column(db.JSON)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<HealthRecord {self.id}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "blood_pressure": self.blood_pressure,
            "heart_rate": self.heart_rate,
            "temperature": self.temperature,
            "oxygen_saturation": self.oxygen_saturation,
            "blood_sugar": self.blood_sugar,
            "allergies": self.allergies,
            "medications": self.medications,
            "past_illnesses": self.past_illnesses,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ABHAToken(db.Model):
    """Store ABHA authentication tokens and session info"""
    __tablename__ = "abha_tokens"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    token_type = db.Column(db.String(50), default="Bearer")
    
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def is_expired(self):
        """Check if ABHA token has expired"""
        return datetime.utcnow() > self.expires_at if self.expires_at else False
    
    def __repr__(self):
        return f"<ABHAToken {self.user_id}>"
