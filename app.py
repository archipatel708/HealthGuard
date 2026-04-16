"""Disease prediction backend with MongoDB persistence and ABHA support."""

from __future__ import annotations

import os
from datetime import datetime
from threading import Lock
from warnings import simplefilter

import joblib
import numpy as np
import pandas as pd
from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt_identity, verify_jwt_in_request
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError
from sklearn.exceptions import InconsistentVersionWarning

from abha import ABHAService
from auth import AuthService, token_required
from config import config
from models import get_mongo_database, save_user
from train import train_and_save_model

load_dotenv()


def create_app(config_name="development"):
    """Application factory function."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config[config_name])
    JWTManager(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    return app


app = create_app(os.getenv("FLASK_ENV", "development"))
simplefilter("default", InconsistentVersionWarning)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
_prediction_assets_lock = Lock()


def _db():
    return get_mongo_database()


def _prediction_collection():
    return _db()["prediction_history"]


def _health_collection():
    return _db()["health_records"]


def _abha_token_collection():
    return _db()["abha_tokens"]


def _serialize_document(doc):
    payload = dict(doc)
    payload["id"] = str(payload.get("_id"))
    payload.pop("_id", None)
    return payload


def _load_model_artifacts():
    """Load persisted model artifacts, retraining if they are incompatible."""
    try:
        classifier = joblib.load(os.path.join(MODEL_DIR, "model.pkl"))
        symptoms = joblib.load(os.path.join(MODEL_DIR, "symptom_list.pkl"))
        severity = joblib.load(os.path.join(MODEL_DIR, "severity_map.pkl"))
        app.logger.info("Loaded persisted ML artifacts successfully.")
        return classifier, symptoms, severity
    except Exception as exc:
        app.logger.warning("Failed to load persisted ML artifacts: %s", exc)
        app.logger.warning("Retraining model artifacts from source CSV files.")
        try:
            classifier, symptoms, severity = train_and_save_model(BASE_DIR, MODEL_DIR)
            app.logger.info("Retrained ML artifacts successfully during startup.")
            return classifier, symptoms, severity
        except Exception as retrain_exc:
            app.logger.exception("Automatic model retraining failed: %s", retrain_exc)
        return None, [], {}


clf = None
all_symptoms = []
severity_map = {}
symptom_index = {}
desc_map = {}
prec_map = {}
_prediction_assets_initialized = False
_prediction_assets_error = None


def _load_reference_data():
    description_df = pd.read_csv(os.path.join(BASE_DIR, "description.csv"))
    description_df.columns = description_df.columns.str.strip()
    description_df["Disease"] = description_df["Disease"].str.strip()
    descriptions = dict(zip(description_df["Disease"], description_df["Description"]))

    precautions_df = pd.read_csv(os.path.join(BASE_DIR, "precautions_df.csv"), index_col=0)
    precautions_df.columns = precautions_df.columns.str.strip()
    precautions_df["Disease"] = precautions_df["Disease"].str.strip()
    precautions = {}
    for _, row in precautions_df.iterrows():
        precs = [
            str(row[column]).strip()
            for column in ["Precaution_1", "Precaution_2", "Precaution_3", "Precaution_4"]
            if pd.notna(row[column]) and str(row[column]).strip() not in ("", "nan")
        ]
        precautions[row["Disease"]] = precs

    return descriptions, precautions


def _ensure_prediction_assets():
    global clf, all_symptoms, severity_map, symptom_index, desc_map, prec_map
    global _prediction_assets_initialized, _prediction_assets_error

    if _prediction_assets_initialized:
        return clf is not None and bool(all_symptoms)

    with _prediction_assets_lock:
        if _prediction_assets_initialized:
            return clf is not None and bool(all_symptoms)

        try:
            classifier, symptoms, severity = _load_model_artifacts()
            descriptions, precautions = _load_reference_data()

            clf = classifier
            all_symptoms = symptoms
            severity_map = severity
            symptom_index = {symptom: index for index, symptom in enumerate(all_symptoms)}
            desc_map = descriptions
            prec_map = precautions
            _prediction_assets_error = None if clf is not None and all_symptoms else "Prediction artifacts unavailable"
        except Exception as exc:
            app.logger.exception("Failed to initialize prediction assets: %s", exc)
            clf = None
            all_symptoms = []
            severity_map = {}
            symptom_index = {}
            desc_map = {}
            prec_map = {}
            _prediction_assets_error = str(exc)
        finally:
            _prediction_assets_initialized = True

    return clf is not None and bool(all_symptoms)


def _safe_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_bp(bp_value):
    if not bp_value:
        return None, None
    text = str(bp_value).strip().replace(" ", "")
    if "/" not in text:
        return None, None
    left, right = text.split("/", 1)
    try:
        return int(left), int(right)
    except ValueError:
        return None, None


def analyze_vitals_impact(health_data):
    if not isinstance(health_data, dict) or not health_data:
        return None

    risk_points = 0
    flags = []

    systolic, diastolic = _parse_bp(health_data.get("blood_pressure"))
    if systolic is not None and diastolic is not None:
        if systolic >= 180 or diastolic >= 120:
            risk_points += 25
            flags.append("Very high blood pressure")
        elif systolic >= 140 or diastolic >= 90:
            risk_points += 12
            flags.append("High blood pressure")
        elif systolic < 90 or diastolic < 60:
            risk_points += 15
            flags.append("Low blood pressure")

    heart_rate = _safe_float(health_data.get("heart_rate"))
    if heart_rate is not None:
        if heart_rate > 120 or heart_rate < 50:
            risk_points += 20
            flags.append("Abnormal heart rate")
        elif heart_rate > 100:
            risk_points += 10
            flags.append("Elevated heart rate")

    temperature = _safe_float(health_data.get("temperature"))
    if temperature is not None:
        if temperature >= 39.5:
            risk_points += 25
            flags.append("High fever")
        elif temperature >= 38.0:
            risk_points += 10
            flags.append("Fever")
        elif temperature < 35.0:
            risk_points += 20
            flags.append("Low body temperature")

    oxygen = _safe_float(health_data.get("oxygen_saturation"))
    if oxygen is not None:
        if oxygen < 90:
            risk_points += 35
            flags.append("Low oxygen saturation")
        elif oxygen < 95:
            risk_points += 20
            flags.append("Borderline oxygen saturation")

    blood_sugar = _safe_float(health_data.get("blood_sugar"))
    if blood_sugar is not None:
        if blood_sugar < 70 or blood_sugar > 250:
            risk_points += 20
            flags.append("Critical blood sugar range")
        elif blood_sugar > 180:
            risk_points += 10
            flags.append("High blood sugar")

    if risk_points >= 35:
        triage_level = "urgent"
    elif risk_points >= 15:
        triage_level = "moderate"
    else:
        triage_level = "low"

    confidence_penalty = min(25.0, round(risk_points * 0.35, 1))
    return {
        "risk_points": risk_points,
        "flags": flags,
        "triage_level": triage_level,
        "confidence_penalty": confidence_penalty,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return "", 204


@app.route("/api/health", methods=["GET"])
def health_check():
    model_ready = clf is not None and bool(all_symptoms)
    model_status = "ready" if model_ready else ("lazy" if not _prediction_assets_initialized else "unavailable")
    db_ready = True
    db_error = None
    try:
        _db().command("ping")
    except Exception as exc:
        db_ready = False
        db_error = str(exc)

    status = "healthy" if model_ready and db_ready else "degraded"
    payload = {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "model_ready": model_ready,
        "model_status": model_status,
        "database_ready": db_ready,
        "symptom_count": len(all_symptoms),
    }
    if _prediction_assets_error:
        payload["model_error"] = _prediction_assets_error
    if db_error:
        payload["database_error"] = db_error
    return jsonify(payload)


@app.route("/api/auth/register", methods=["POST"])
def register_user():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    confirm_password = data.get("confirm_password", "")
    phone = data.get("phone")
    first_name = data.get("first_name")
    last_name = data.get("last_name")

    if password != confirm_password:
        return jsonify({"error": "Passwords do not match"}), 400

    try:
        success, message, user = AuthService.register_user(
            email=email,
            password=password,
            phone=phone,
            first_name=first_name,
            last_name=last_name,
        )
        if not success:
            return jsonify({"error": message}), 400

        tokens = AuthService.generate_tokens(user.id)
        return jsonify({"message": message, "user": user.to_public_dict(), **tokens}), 201
    except DuplicateKeyError:
        return jsonify({"error": "Account details already exist"}), 400
    except Exception as exc:
        return jsonify({"error": f"Registration failed: {str(exc)}"}), 500


@app.route("/api/auth/login", methods=["POST"])
def login_user():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    try:
        success, message, user = AuthService.authenticate_user(email, password)
        if not success:
            return jsonify({"error": message}), 401

        tokens = AuthService.generate_tokens(user.id)
        return jsonify({"message": message, "user": user.to_public_dict(), **tokens}), 200
    except Exception as exc:
        return jsonify({"error": f"Login failed: {str(exc)}"}), 500


@app.route("/api/auth/request-otp", methods=["POST"])
def request_otp():
    return jsonify({"error": "OTP authentication has been removed. Use /api/auth/register or /api/auth/login."}), 410


@app.route("/api/auth/verify-otp", methods=["POST"])
def verify_otp():
    return jsonify({"error": "OTP authentication has been removed. Use /api/auth/login with email and password."}), 410


@app.route("/api/auth/refresh", methods=["POST"])
def refresh_token():
    try:
        verify_jwt_in_request(refresh=True)
        user_id = get_jwt_identity()
        access_token = AuthService.generate_tokens(str(user_id))["access_token"]
        return jsonify({"access_token": access_token}), 200
    except Exception:
        return jsonify({"error": "Token refresh failed"}), 401


@app.route("/api/symptoms", methods=["GET"])
def get_symptoms():
    if not _ensure_prediction_assets():
        return jsonify({"error": "Model symptoms are unavailable right now", "details": _prediction_assets_error}), 503
    display = [symptom.replace("_", " ").title() for symptom in all_symptoms]
    return jsonify([{"value": value, "label": label} for value, label in zip(all_symptoms, display)])


@app.route("/api/predict", methods=["POST"])
@token_required
def predict(user):
    data = request.get_json(force=True, silent=True)
    if not data or "symptoms" not in data:
        abort(400, "Request body must be JSON with a 'symptoms' array.")
    if not _ensure_prediction_assets():
        return jsonify({"error": "Prediction model is unavailable right now. Please try again shortly.", "details": _prediction_assets_error}), 503

    raw_symptoms = data["symptoms"]
    if not isinstance(raw_symptoms, list):
        abort(400, "'symptoms' must be an array.")

    chosen = []
    unknown = []
    for symptom in raw_symptoms:
        clean = str(symptom).strip().lower()
        if clean in symptom_index:
            chosen.append(clean)
        else:
            unknown.append(symptom)

    if not chosen:
        abort(400, "None of the supplied symptoms were recognised.")

    vec = np.zeros((1, len(all_symptoms)), dtype=np.float32)
    for symptom in chosen:
        vec[0, symptom_index[symptom]] = severity_map[symptom]

    disease = clf.predict(vec)[0]
    proba = clf.predict_proba(vec)[0]
    top3_idx = np.argsort(proba)[::-1][:3]
    top3 = [
        {"disease": clf.classes_[index], "probability": round(float(proba[index]) * 100, 1)}
        for index in top3_idx
        if proba[index] > 0
    ]

    base_confidence = round(float(proba[np.argmax(proba)]) * 100, 1)
    health_data = data.get("health_data") if isinstance(data.get("health_data"), dict) else None
    vitals_analysis = analyze_vitals_impact(health_data)
    confidence = base_confidence
    if vitals_analysis:
        confidence = max(20.0, round(base_confidence - vitals_analysis["confidence_penalty"], 1))

    now = datetime.utcnow().isoformat()
    prediction_payload = {
        "user_id": user.id,
        "symptoms": chosen,
        "predicted_disease": disease,
        "confidence_score": confidence,
        "top3_predictions": top3,
        "notes": data.get("notes"),
        "severity_level": data.get("severity_level") or (vitals_analysis["triage_level"] if vitals_analysis else None),
        "created_at": now,
        "updated_at": now,
    }
    prediction_result = _prediction_collection().insert_one(prediction_payload)

    if health_data:
        _health_collection().insert_one(
            {
                "user_id": user.id,
                "prediction_id": str(prediction_result.inserted_id),
                "blood_pressure": health_data.get("blood_pressure"),
                "heart_rate": health_data.get("heart_rate"),
                "temperature": health_data.get("temperature"),
                "oxygen_saturation": health_data.get("oxygen_saturation"),
                "blood_sugar": health_data.get("blood_sugar"),
                "allergies": health_data.get("allergies"),
                "medications": health_data.get("medications"),
                "past_illnesses": health_data.get("past_illnesses"),
                "abha_data": health_data.get("abha_data"),
                "created_at": now,
                "updated_at": now,
            }
        )

    return jsonify(
        {
            "prediction_id": str(prediction_result.inserted_id),
            "disease": disease,
            "description": desc_map.get(disease, "No description available."),
            "precautions": prec_map.get(disease, []),
            "confidence_score": confidence,
            "base_confidence_score": base_confidence,
            "vitals_used": bool(vitals_analysis),
            "vitals_analysis": vitals_analysis,
            "top3": top3,
            "unknown_symptoms": unknown,
            "stored": True,
        }
    ), 200


@app.route("/api/predictions/history", methods=["GET"])
@token_required
def get_prediction_history(user):
    page = max(1, request.args.get("page", 1, type=int))
    per_page = max(1, min(100, request.args.get("limit", 10, type=int)))
    skip = (page - 1) * per_page

    total = _prediction_collection().count_documents({"user_id": user.id})
    docs = (
        _prediction_collection()
        .find({"user_id": user.id})
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(per_page)
    )
    predictions = []
    for doc in docs:
        payload = _serialize_document(doc)
        predictions.append(payload)

    pages = (total + per_page - 1) // per_page if total else 0
    return jsonify(
        {
            "total": total,
            "pages": pages,
            "current_page": page,
            "predictions": predictions,
        }
    ), 200


@app.route("/api/predictions/<prediction_id>", methods=["GET"])
@token_required
def get_prediction_detail(user, prediction_id):
    try:
        object_id = ObjectId(prediction_id)
    except Exception:
        return jsonify({"error": "Prediction not found"}), 404

    prediction = _prediction_collection().find_one({"_id": object_id, "user_id": user.id})
    if not prediction:
        return jsonify({"error": "Prediction not found"}), 404

    health_records = list(_health_collection().find({"prediction_id": prediction_id, "user_id": user.id}))
    return jsonify(
        {
            "prediction": _serialize_document(prediction),
            "health_records": [_serialize_document(record) for record in health_records],
        }
    ), 200


@app.route("/api/user/profile", methods=["GET"])
@token_required
def get_user_profile(user):
    return jsonify(user.to_public_dict()), 200


@app.route("/api/user/profile", methods=["PUT"])
@token_required
def update_user_profile(user):
    data = request.get_json(silent=True) or {}

    try:
        if "first_name" in data:
            first_name = (data.get("first_name") or "").strip()
            user.first_name = first_name or None
        if "last_name" in data:
            last_name = (data.get("last_name") or "").strip()
            user.last_name = last_name or None
        if "age" in data:
            age_value = data.get("age")
            if age_value in (None, ""):
                user.age = None
            else:
                try:
                    parsed_age = int(age_value)
                except (TypeError, ValueError):
                    return jsonify({"error": "Age must be a valid number"}), 400
                if parsed_age < 0 or parsed_age > 130:
                    return jsonify({"error": "Age must be between 0 and 130"}), 400
                user.age = parsed_age
        if "gender" in data:
            gender = (data.get("gender") or "").strip().upper()
            user.gender = gender or None
        if "phone" in data:
            phone = (data.get("phone") or "").strip()
            user.phone = phone or None

        save_user(user)
        return jsonify({"message": "Profile updated successfully", "user": user.to_public_dict()}), 200
    except DuplicateKeyError:
        return jsonify({"error": "Phone number already in use by another account"}), 409
    except Exception as exc:
        return jsonify({"error": f"Failed to update profile: {str(exc)}"}), 500


@app.route("/api/user/health-records", methods=["GET"])
@token_required
def get_health_records(user):
    records = list(_health_collection().find({"user_id": user.id}).sort("created_at", DESCENDING))
    return jsonify({"count": len(records), "records": [_serialize_document(record) for record in records]}), 200


@app.route("/api/user/health-records", methods=["POST"])
@token_required
def add_health_record(user):
    data = request.get_json(silent=True) or {}
    now = datetime.utcnow().isoformat()

    try:
        payload = {
            "user_id": user.id,
            "prediction_id": data.get("prediction_id"),
            "blood_pressure": data.get("blood_pressure"),
            "heart_rate": data.get("heart_rate"),
            "temperature": data.get("temperature"),
            "oxygen_saturation": data.get("oxygen_saturation"),
            "blood_sugar": data.get("blood_sugar"),
            "allergies": data.get("allergies"),
            "medications": data.get("medications"),
            "past_illnesses": data.get("past_illnesses"),
            "abha_data": data.get("abha_data"),
            "created_at": now,
            "updated_at": now,
        }
        result = _health_collection().insert_one(payload)
        payload["id"] = str(result.inserted_id)
        return jsonify({"message": "Health record added successfully", "record": payload}), 201
    except Exception as exc:
        return jsonify({"error": f"Failed to add health record: {str(exc)}"}), 500


@app.route("/api/abha/authorization-url", methods=["GET"])
@token_required
def get_abha_authorization_url(user):
    try:
        state = os.urandom(24).hex()
        auth_url = ABHAService.get_authorization_url(state)
        return jsonify({"authorization_url": auth_url, "state": state}), 200
    except Exception as exc:
        return jsonify({"error": f"Failed to generate authorization URL: {str(exc)}"}), 500


@app.route("/api/abha/operations", methods=["GET"])
@token_required
def get_abha_operations(user):
    return jsonify({"operations": ABHAService.get_operation_catalog(), "count": len(ABHAService.get_operation_catalog())}), 200


@app.route("/api/abha/execute", methods=["POST"])
@token_required
def execute_abha_operation(user):
    data = request.get_json(silent=True) or {}
    operation = data.get("operation")
    payload = data.get("payload") or {}
    provided_auth_token = data.get("auth_token")

    if not operation:
        return jsonify({"error": "operation is required"}), 400

    client_id = (app.config.get("ABHA_CLIENT_ID") or "").strip()
    client_secret = (app.config.get("ABHA_CLIENT_SECRET") or "").strip()
    placeholder_values = {"", "your-abha-client-id", "your-abha-client-secret", "changeme", "replace-me"}
    if client_id in placeholder_values or client_secret in placeholder_values:
        return jsonify({"error": "ABHA credentials are not configured. Set ABHA_CLIENT_ID and ABHA_CLIENT_SECRET in .env"}), 400

    operation_catalog = ABHAService.get_operation_catalog()
    operation_meta = operation_catalog.get(operation)
    if not operation_meta:
        return jsonify({"error": "Unsupported ABHA operation", "operation": operation, "supported_operations": sorted(operation_catalog.keys())}), 400

    effective_auth_token = provided_auth_token
    if operation_meta.get("requires_auth_token") and not effective_auth_token:
        token_doc = _abha_token_collection().find_one({"user_id": user.id})
        if token_doc:
            refresh_ok, refresh_result = ABHAService.refresh_abha_token(user.id)
            if refresh_ok:
                effective_auth_token = refresh_result

    success, result, status_code = ABHAService.execute_operation(operation=operation, payload=payload, auth_token=effective_auth_token)

    if success and operation in {"auth.confirm_aadhaar_otp", "auth.confirm_mobile_otp"}:
        token_value = result.get("token") or result.get("accessToken") or result.get("access_token")
        abha_id = result.get("healthId") or result.get("abhaAddress") or result.get("abhaId")
        if token_value:
            ABHAService.link_abha_account(user.id, token_value, abha_id)

    if success:
        return jsonify({"operation": operation, "endpoint": operation_meta.get("endpoint"), "response": result}), status_code

    return jsonify({"operation": operation, "endpoint": operation_meta.get("endpoint"), "error": result}), status_code or 500


@app.route("/api/abha/callback", methods=["POST"])
@token_required
def abha_callback(user):
    data = request.get_json(silent=True) or {}
    code = data.get("code")
    if not code:
        return jsonify({"error": "Authorization code missing"}), 400

    try:
        success, token_data, status_code = ABHAService.exchange_code_for_token(code)
        if not success:
            return jsonify({"error": token_data}), status_code or 500

        access_token = token_data.get("access_token")
        abha_id = token_data.get("abha_id", "")
        success, message = ABHAService.link_abha_account(user.id, access_token, abha_id)
        if not success:
            return jsonify({"error": message}), 500

        success, message = ABHAService.fetch_and_store_health_records(user.id, access_token)
        return jsonify({"message": "ABHA account linked successfully", "abha_id": abha_id, "health_records_fetched": success}), 200
    except Exception as exc:
        return jsonify({"error": f"ABHA callback failed: {str(exc)}"}), 500


@app.route("/api/abha/health-data", methods=["GET"])
@token_required
def get_abha_health_data(user):
    if not user.abha_id:
        return jsonify({"error": "ABHA account not linked"}), 400

    try:
        success, token = ABHAService.refresh_abha_token(user.id)
        if not success:
            return jsonify({"error": token}), 500

        success, data = ABHAService.get_user_health_data(token)
        if not success:
            return jsonify({"error": data}), 500

        return jsonify({"abha_id": user.abha_id, "health_data": data}), 200
    except Exception as exc:
        return jsonify({"error": f"Failed to fetch ABHA health data: {str(exc)}"}), 500


@app.route("/api/abha/unlink", methods=["POST"])
@token_required
def unlink_abha_account(user):
    try:
        user.abha_id = None
        user.abha_token = None
        user.abha_linked_at = None
        save_user(user)
        _abha_token_collection().delete_many({"user_id": user.id})
        return jsonify({"message": "ABHA account unlinked successfully"}), 200
    except Exception as exc:
        return jsonify({"error": f"Failed to unlink ABHA account: {str(exc)}"}), 500


@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": error.description or "Bad request"}), 400


@app.errorhandler(401)
def unauthorized(error):
    return jsonify({"error": "Unauthorized"}), 401


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    if app.debug:
        return jsonify({"error": f"Internal server error: {str(error)}"}), 500
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    raw_port = os.environ.get("PORT") or os.environ.get("FLASK_PORT") or "5000"
    try:
        port = int(raw_port)
    except ValueError:
        port = 5000
    app.run(debug=os.environ.get("FLASK_ENV") == "development", host=host, port=port)
