"""
Enhanced Flask backend with Email+OTP Authentication, Data Persistence, and ABHA API Support
"""

import os
import json
import re
import random
import subprocess
import sys
import numpy as np
import pandas as pd
import joblib
import sklearn
from datetime import datetime, timedelta, timezone
import secrets
import requests
from dotenv import load_dotenv

from flask import Flask, jsonify, render_template, request, abort, url_for, current_app
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from sqlalchemy.exc import IntegrityError

from config import config
from models import db, User, OTP, PredictionHistory, HealthRecord, ABHAToken
from auth import AuthService, token_required
from abha import ABHAService

# Load environment variables from .env before creating app/config.
# override=True avoids stale shell/session variables silently disabling features.
load_dotenv(override=True)

# ── Initialize Flask App ──────────────────────────────────────────────────────
def create_app(config_name="development"):
    """Application factory function"""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    JWTManager(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    
    with app.app_context():
        db.create_all()
    
    return app


app = create_app(os.getenv("FLASK_ENV", "development"))

# ── Load ML Model Artefacts ───────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")

_model_runtime_info = {
    "loaded": False,
    "load_error": None,
    "auto_retrained": False,
    "retrain_error": None,
}


def _model_artifact_paths():
    return {
        "model": os.path.join(MODEL_DIR, "model.pkl"),
        "symptom_list": os.path.join(MODEL_DIR, "symptom_list.pkl"),
        "severity_map": os.path.join(MODEL_DIR, "severity_map.pkl"),
    }


def _load_model_artifacts():
    paths = _model_artifact_paths()
    loaded_clf = joblib.load(paths["model"])
    loaded_symptoms = joblib.load(paths["symptom_list"])
    loaded_severity = joblib.load(paths["severity_map"])
    loaded_index = {s: i for i, s in enumerate(loaded_symptoms)}
    return loaded_clf, loaded_symptoms, loaded_severity, loaded_index


def _retrain_model_artifacts():
    train_script = os.path.join(BASE_DIR, "train.py")
    if not os.path.exists(train_script):
        raise RuntimeError("train.py not found; cannot auto-retrain model artifacts")

    result = subprocess.run(
        [sys.executable, train_script],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        stderr_tail = (result.stderr or "").strip()[-1000:]
        stdout_tail = (result.stdout or "").strip()[-1000:]
        raise RuntimeError(
            "Auto-retrain failed. "
            f"Exit code={result.returncode}. "
            f"stderr={stderr_tail or 'empty'}. stdout={stdout_tail or 'empty'}"
        )


def _initialize_model_artifacts():
    global clf, all_symptoms, severity_map, symptom_index

    try:
        clf, all_symptoms, severity_map, symptom_index = _load_model_artifacts()
        _model_runtime_info["loaded"] = True
        _model_runtime_info["load_error"] = None
        return
    except Exception as exc:
        _model_runtime_info["loaded"] = False
        _model_runtime_info["load_error"] = str(exc)
        app.logger.warning("Model artifact load failed; attempting auto-retrain: %s", exc)

    try:
        _retrain_model_artifacts()
        clf, all_symptoms, severity_map, symptom_index = _load_model_artifacts()
        _model_runtime_info["loaded"] = True
        _model_runtime_info["auto_retrained"] = True
        _model_runtime_info["retrain_error"] = None
        app.logger.info("Model artifacts auto-retrained and loaded successfully")
    except Exception as exc:
        _model_runtime_info["loaded"] = False
        _model_runtime_info["retrain_error"] = str(exc)
        app.logger.exception("Model initialization failed after auto-retrain attempt")
        raise RuntimeError(
            "Model artifacts could not be loaded. "
            "This is often caused by numpy/scikit-learn/joblib version mismatch. "
            "Pin compatible versions and retrain model artifacts in the deployment environment. "
            f"Details: {exc}"
        )


_initialize_model_artifacts()

# ── Load reference datasets ───────────────────────────────────────────────────
description_df = pd.read_csv(os.path.join(BASE_DIR, "description.csv"))
description_df.columns = description_df.columns.str.strip()
description_df["Disease"] = description_df["Disease"].str.strip()
desc_map = dict(zip(description_df["Disease"], description_df["Description"]))

precautions_df = pd.read_csv(os.path.join(BASE_DIR, "precautions_df.csv"), index_col=0)
precautions_df.columns = precautions_df.columns.str.strip()
precautions_df["Disease"] = precautions_df["Disease"].str.strip()
prec_map = {}
for _, row in precautions_df.iterrows():
    precs = [str(row[c]).strip() for c in ["Precaution_1", "Precaution_2", "Precaution_3", "Precaution_4"]
             if pd.notna(row[c]) and str(row[c]).strip() not in ("", "nan")]
    prec_map[row["Disease"]] = precs


_openrouter_cooldown_until = None

GENDER_ALIASES = {
    "m": "M",
    "male": "M",
    "man": "M",
    "f": "F",
    "female": "F",
    "woman": "F",
    "o": "O",
    "other": "O",
    "non-binary": "O",
    "nonbinary": "O",
}

FEMALE_ONLY_SYMPTOMS = {
    "abnormal_menstruation",
    "missed_periods",
    "heavy_menstrual_bleeding",
    "spotting_between_periods",
    "vaginal_discharge",
}

MALE_ONLY_SYMPTOMS = {
    "testicular_pain",
    "erectile_dysfunction",
}

FEMALE_DISEASE_KEYWORDS = [
    "menstrual",
    "endometriosis",
    "pcos",
    "ovar",
    "uter",
    "vagin",
]

MALE_DISEASE_KEYWORDS = [
    "prostate",
    "prostatitis",
    "testicular",
    "erectile",
    "varicocele",
]

# Layperson phrase fallback map for symptom narrative parsing.
COMMON_SYMPTOM_PHRASE_MAP = {
    "fever": ["high_fever", "mild_fever"],
    "temperature": ["high_fever", "mild_fever"],
    "cold": ["runny_nose", "congestion"],
    "runny nose": ["runny_nose"],
    "blocked nose": ["congestion"],
    "stuffy nose": ["congestion"],
    "sneezing": ["continuous_sneezing"],
    "cough": ["cough", "dry_cough"],
    "dry cough": ["dry_cough"],
    "breathlessness": ["shortness_of_breath", "breathlessness"],
    "shortness of breath": ["shortness_of_breath"],
    "wheezing": ["wheezing"],
    "chest tightness": ["chest_tightness"],
    "chest pain": ["chest_pain"],
    "throat pain": ["throat_irritation"],
    "sore throat": ["throat_irritation"],
    "headache": ["headache"],
    "migraine": ["headache", "light_sensitivity", "visual_disturbances"],
    "nausea": ["nausea"],
    "vomit": ["vomiting"],
    "vomiting": ["vomiting"],
    "dizzy": ["dizziness"],
    "dizziness": ["dizziness"],
    "tired": ["fatigue"],
    "fatigue": ["fatigue"],
    "weakness": ["general_weakness"],
    "body pain": ["muscle_pain"],
    "muscle pain": ["muscle_pain"],
    "joint pain": ["joint_pain"],
    "shoulder pain": ["joint_pain", "muscle_pain"],
    "back pain": ["back_pain"],
    "neck pain": ["neck_pain"],
    "knee pain": ["knee_pain"],
    "abdominal pain": ["abdominal_pain", "stomach_pain"],
    "stomach pain": ["stomach_pain"],
    "acidity": ["acidity", "heartburn", "acid_reflux"],
    "heartburn": ["heartburn", "acid_reflux"],
    "burning urination": ["burning_micturition", "painful_urination"],
    "frequent urination": ["frequent_urination", "polyuria"],
    "period pain": ["abnormal_menstruation", "cramps"],
    "menstrual": ["abnormal_menstruation", "heavy_menstrual_bleeding"],
}

DUMMY_ABHA_ISSUE_CATALOG = [
    {
        "condition": "Type 2 Diabetes",
        "details": "Diagnosed previously; periodic high sugar episodes",
        "category": "metabolic",
    },
    {
        "condition": "Shoulder Injury After Accident",
        "details": "Old trauma-related shoulder pain with intermittent flare-ups",
        "category": "musculoskeletal",
    },
    {
        "condition": "Forearm Fracture (Healed)",
        "details": "Past fracture with occasional pain during overuse",
        "category": "musculoskeletal",
    },
    {
        "condition": "Asthma History",
        "details": "Episodic breathing discomfort triggered by allergens",
        "category": "respiratory",
    },
    {
        "condition": "Hypertension",
        "details": "Known blood pressure variability requiring monitoring",
        "category": "cardiometabolic",
    },
    {
        "condition": "Migraine History",
        "details": "Recurrent migraine with sensitivity to light",
        "category": "neurological",
    },
    {
        "condition": "Lumbar Strain After Fall",
        "details": "Previous lower back injury with recurrent pain",
        "category": "musculoskeletal",
    },
    {
        "condition": "Kidney Stone Episode",
        "details": "Past renal colic episode; advised hydration",
        "category": "renal",
    },
]


def _safe_float(value):
    """Best-effort numeric parsing for optional vitals fields."""
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_bp(bp_value):
    """Parse blood pressure string formats like '120/80'."""
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
    """Generate a simple risk score from vitals and map it to triage guidance."""
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

    # Penalize confidence up to 25 points when vitals indicate higher instability.
    confidence_penalty = min(25.0, round(risk_points * 0.35, 1))

    return {
        "risk_points": risk_points,
        "flags": flags,
        "triage_level": triage_level,
        "confidence_penalty": confidence_penalty,
    }


def _extract_first_json_object(text):
    """Extract first JSON object from model text output."""
    if not text:
        return None

    raw = str(text).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = raw[start:end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _openrouter_is_in_cooldown():
    """Return whether OpenRouter calls are temporarily paused after hard failures."""
    global _openrouter_cooldown_until
    if _openrouter_cooldown_until is None:
        return False
    if datetime.now(timezone.utc) >= _openrouter_cooldown_until:
        _openrouter_cooldown_until = None
        return False
    return True


def _set_openrouter_cooldown(seconds):
    """Pause OpenRouter calls for a bounded cooldown period."""
    global _openrouter_cooldown_until
    safe_seconds = max(5, min(int(seconds), 3600))
    _openrouter_cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=safe_seconds)


def _generate_dummy_abha_past_illnesses_for_user(user_id):
    """Generate synthetic ABHA-like past illness entries for demo mode."""
    sample_count = random.randint(2, 4)
    sampled = random.sample(DUMMY_ABHA_ISSUE_CATALOG, k=sample_count)

    issues = []
    this_year = datetime.utcnow().year
    for item in sampled:
        years_ago = random.randint(1, 8)
        issues.append(
            {
                "condition": item["condition"],
                "details": item["details"],
                "category": item["category"],
                "event_year": this_year - years_ago,
                "source": "abha_dummy",
            }
        )
    return issues


def get_user_latest_past_illnesses(user_id):
    """Return most recent non-empty past illnesses from stored health records."""
    records = HealthRecord.query.filter_by(user_id=user_id).order_by(HealthRecord.created_at.desc()).all()
    for record in records:
        if isinstance(record.past_illnesses, list) and record.past_illnesses:
            return record.past_illnesses
    return []


def analyze_medical_history_impact(chosen_symptoms, past_illnesses):
    """Derive lightweight recurrence context from past medical issues."""
    if not chosen_symptoms or not past_illnesses:
        return {
            "used": False,
            "confidence_penalty": 0.0,
            "flags": [],
        }

    chosen = set(chosen_symptoms)
    text_blob = " ".join(
        f"{item.get('condition', '')} {item.get('details', '')}".lower()
        for item in past_illnesses
        if isinstance(item, dict)
    )

    flags = []
    penalty = 0.0

    musculoskeletal_symptoms = {
        "joint_pain",
        "muscle_pain",
        "back_pain",
        "neck_pain",
        "knee_pain",
        "hip_joint_pain",
        "movement_stiffness",
        "painful_walking",
    }
    if any(sym in chosen for sym in musculoskeletal_symptoms) and any(
        marker in text_blob for marker in {"injury", "fracture", "accident", "strain", "fall", "trauma"}
    ):
        flags.append("Past injury/fracture may explain recurrent musculoskeletal pain")
        penalty += 4.0

    diabetic_markers = {"polyuria", "irregular_sugar_level", "excessive_hunger", "fatigue", "weight_loss"}
    if any(sym in chosen for sym in diabetic_markers) and "diabetes" in text_blob:
        flags.append("Past diabetes history may influence current metabolic symptoms")
        penalty += 3.0

    respiratory_markers = {"shortness_of_breath", "wheezing", "dry_cough", "chest_tightness", "rapid_breathing"}
    if any(sym in chosen for sym in respiratory_markers) and "asthma" in text_blob:
        flags.append("Past asthma history may indicate recurrence/exacerbation")
        penalty += 3.0

    return {
        "used": bool(flags),
        "confidence_penalty": min(8.0, round(penalty, 1)),
        "flags": flags,
    }


def canonicalize_gender(value):
    """Normalize user-supplied gender values into M/F/O buckets."""
    if value is None:
        return None
    key = str(value).strip().lower()
    return GENDER_ALIASES.get(key)


def validate_gender_symptom_compatibility(patient_gender, chosen_symptoms):
    """Reject symptom patterns that are physiologically incompatible with profile gender."""
    if patient_gender not in {"M", "F"}:
        return {"ok": True, "conflicting": []}

    chosen = set(chosen_symptoms or [])
    if patient_gender == "M":
        conflicting = sorted(s for s in chosen if s in FEMALE_ONLY_SYMPTOMS)
    else:
        conflicting = sorted(s for s in chosen if s in MALE_ONLY_SYMPTOMS)

    return {
        "ok": len(conflicting) == 0,
        "conflicting": conflicting,
    }


def is_disease_gender_compatible(patient_gender, disease_name):
    """Check whether a disease name is incompatible with the patient's profile gender."""
    if patient_gender not in {"M", "F"} or not disease_name:
        return True

    text = str(disease_name).strip().lower()
    if patient_gender == "M":
        return not any(marker in text for marker in FEMALE_DISEASE_KEYWORDS)
    return not any(marker in text for marker in MALE_DISEASE_KEYWORDS)


def _direct_symptom_match_from_text(symptom_text):
    """Fast deterministic phrase matching against known symptom names."""
    normalized = re.sub(r"[^a-z0-9\s]", " ", str(symptom_text or "").lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    padded = f" {normalized} "

    matches = set()
    for symptom in all_symptoms:
        as_phrase = symptom.replace("_", " ")
        if f" {as_phrase} " in padded:
            matches.add(symptom)
    return sorted(matches)


def _keyword_symptom_match_from_text(symptom_text):
    """Fallback mapping from common plain-language phrases to known model symptoms."""
    normalized = re.sub(r"[^a-z0-9\s]", " ", str(symptom_text or "").lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    matches = set()
    for phrase, mapped in COMMON_SYMPTOM_PHRASE_MAP.items():
        if phrase in normalized:
            for symptom in mapped:
                if symptom in symptom_index:
                    matches.add(symptom)
    return sorted(matches)


def interpret_symptoms_from_text(symptom_text, patient_gender=None):
    """Convert free-text symptom narration to known model symptom tokens."""
    text = str(symptom_text or "").strip()
    if not text:
        return {
            "symptoms": [],
            "llm_used": False,
            "source": "none",
            "reason": "No symptom text provided",
        }

    direct_matches = _direct_symptom_match_from_text(text)
    keyword_matches = _keyword_symptom_match_from_text(text)

    api_keys = []
    primary_key = (current_app.config.get("OPENROUTER_API_KEY") or "").strip()
    fallback_key = (current_app.config.get("OPENROUTER_API_KEY_FALLBACK") or "").strip()
    tertiary_key = (current_app.config.get("OPENROUTER_API_KEY_TERTIARY") or "").strip()
    for key in [primary_key, fallback_key, tertiary_key]:
        if key and key not in api_keys:
            api_keys.append(key)

    model_name = (current_app.config.get("OPENROUTER_MODEL") or "").strip()
    if not api_keys or not model_name or _openrouter_is_in_cooldown():
        merged = []
        seen = set()
        for symptom in direct_matches + keyword_matches:
            if symptom in symptom_index and symptom not in seen:
                merged.append(symptom)
                seen.add(symptom)

        compatible = validate_gender_symptom_compatibility(patient_gender, merged)
        filtered = [s for s in merged if s not in compatible.get("conflicting", [])]
        return {
            "symptoms": filtered,
            "llm_used": False,
            "source": "direct+keyword_match",
            "reason": "LLM unavailable or paused; used deterministic parsing",
        }

    selection_gender = "male" if patient_gender == "M" else "female" if patient_gender == "F" else "other"
    prompt = (
        "Extract symptoms from this patient narrative and map them ONLY to the provided allowed_symptoms list. "
        "Return JSON only: {\"symptoms\": [\"symptom_name\", ...]}. "
        "Keep it conservative: include only explicitly present symptoms and avoid speculation. "
        "Respect profile gender and avoid incompatible sex-specific symptoms.\n\n"
        f"patient_gender: {selection_gender}\n"
        f"allowed_symptoms: {json.dumps(all_symptoms, ensure_ascii=True)}\n"
        f"narrative: {text}"
    )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You map symptom text to an allowed symptom vocabulary."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }

    headers = {"Content-Type": "application/json"}
    site_url = (
        (current_app.config.get("OPENROUTER_SITE_URL") or "").strip()
        or (current_app.config.get("OPENROUTER_APP_URL") or "").strip()
    )
    site_name = (
        (current_app.config.get("OPENROUTER_SITE_NAME") or "").strip()
        or (current_app.config.get("OPENROUTER_APP_NAME") or "").strip()
    )
    if site_url:
        headers["HTTP-Referer"] = site_url
    if site_name:
        headers["X-OpenRouter-Title"] = site_name

    llm_candidates = []
    try:
        for key in api_keys:
            headers["Authorization"] = f"Bearer {key}"
            resp = requests.post(
                url=current_app.config.get("OPENROUTER_API_URL"),
                headers=headers,
                data=json.dumps(payload),
                timeout=current_app.config.get("OPENROUTER_TIMEOUT_SECONDS", 20),
            )
            resp.raise_for_status()
            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            parsed = _extract_first_json_object(content)
            if isinstance(parsed, dict) and isinstance(parsed.get("symptoms"), list):
                for symptom in parsed.get("symptoms", []):
                    clean = str(symptom).strip().lower()
                    if clean in symptom_index:
                        llm_candidates.append(clean)
                if llm_candidates:
                    break
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in (429, 402):
            cooldown = current_app.config.get("OPENROUTER_RATE_LIMIT_COOLDOWN_SECONDS", 120)
            if status_code == 402:
                cooldown = current_app.config.get("OPENROUTER_BILLING_COOLDOWN_SECONDS", 900)
            _set_openrouter_cooldown(cooldown)
    except Exception:
        pass

    combined = []
    seen = set()
    for symptom in llm_candidates + direct_matches + keyword_matches:
        if symptom in symptom_index and symptom not in seen:
            combined.append(symptom)
            seen.add(symptom)

    compatibility = validate_gender_symptom_compatibility(patient_gender, combined)
    filtered = [s for s in combined if s not in compatibility.get("conflicting", [])]

    return {
        "symptoms": filtered,
        "llm_used": bool(llm_candidates),
        "source": "llm+direct+keyword" if llm_candidates else "direct+keyword_match",
        "reason": "Symptoms interpreted from narrative text",
    }


def apply_prediction_guardrails(chosen_symptoms, current_disease, current_confidence, top3):
    """Apply deterministic fallback corrections for clearly implausible mappings."""
    chosen = set(chosen_symptoms or [])
    if not chosen:
        return {
            "applied": False,
            "disease": current_disease,
            "confidence": current_confidence,
            "reason": "no_symptoms",
        }

    # Guardrail 1: isolated/common nasal-respiratory symptom patterns should not map to unrelated diseases.
    respiratory_markers = {
        "runny_nose",
        "continuous_sneezing",
        "congestion",
        "throat_irritation",
        "cough",
        "dry_cough",
        "chest_tightness",
        "shortness_of_breath",
        "breathlessness",
        "patches_in_throat",
    }
    severe_red_flags = {
        "high_fever",
        "blood_in_sputum",
        "chest_pain",
        "difficulty_breathing",
        "rapid_breathing",
    }
    implausible_for_isolated_nasal = {
        "Fungal infection",
        "Urinary tract infection",
        "Dimorphic hemmorhoids(piles)",
        "Acne",
        "Arthritis",
        "Hypertension",
        "AIDS",
        "Diabetes",
        "Hypothyroidism",
        "Hyperthyroidism",
        "Varicose veins",
    }

    if "runny_nose" in chosen:
        respiratory_count = sum(1 for s in chosen if s in respiratory_markers)
        has_red_flags = any(s in chosen for s in severe_red_flags)

        if current_disease in implausible_for_isolated_nasal and respiratory_count >= 1 and not has_red_flags:
            fallback_disease = "Common Cold"
            if "continuous_sneezing" in chosen and "cough" not in chosen and "dry_cough" not in chosen:
                fallback_disease = "Allergy"

            # Keep confidence conservative on heuristic overrides.
            fallback_confidence = min(float(current_confidence), 45.0)

            # If fallback already exists in top3, anchor confidence to that probability when available.
            for item in top3 or []:
                if item.get("disease") == fallback_disease:
                    try:
                        fallback_confidence = max(25.0, min(55.0, float(item.get("probability", fallback_confidence))))
                    except (TypeError, ValueError):
                        pass
                    break

            return {
                "applied": True,
                "disease": fallback_disease,
                "confidence": round(float(fallback_confidence), 1),
                "reason": "nasal_pattern_implausible_mapping_corrected",
            }

    return {
        "applied": False,
        "disease": current_disease,
        "confidence": current_confidence,
        "reason": "no_guardrail_trigger",
    }


def llm_review_prediction(symptoms, top3, base_prediction, base_confidence, vitals_analysis=None, patient_gender=None, medical_history=None):
    """Optionally review ML prediction with OpenRouter and return an adjusted suggestion."""
    if not current_app.config.get("ENABLE_LLM_REVIEW", False):
        return {
            "enabled": False,
            "used": False,
            "reason": "LLM review disabled (ENABLE_LLM_REVIEW is false at runtime)",
        }

    api_keys = []
    primary_key = (current_app.config.get("OPENROUTER_API_KEY") or "").strip()
    fallback_key = (current_app.config.get("OPENROUTER_API_KEY_FALLBACK") or "").strip()
    tertiary_key = (current_app.config.get("OPENROUTER_API_KEY_TERTIARY") or "").strip()
    # Prediction review should hit tertiary credentials first.
    for k in [tertiary_key, primary_key, fallback_key]:
        if k and k not in api_keys:
            api_keys.append(k)

    if not api_keys:
        return {
            "enabled": True,
            "used": False,
            "reason": "OPENROUTER_API_KEY missing (and no fallback/tertiary key configured)",
        }

    if _openrouter_is_in_cooldown():
        return {
            "enabled": True,
            "used": False,
            "reason": "OpenRouter temporarily paused after recent API limit/billing error",
        }

    candidate_diseases = [item.get("disease") for item in top3 if item.get("disease")]
    if base_prediction and base_prediction not in candidate_diseases:
        candidate_diseases.insert(0, base_prediction)

    if not candidate_diseases:
        return {
            "enabled": True,
            "used": False,
            "reason": "No candidate diseases available",
        }

    top_support = 0.0
    try:
        top_support = max(float(item.get("probability", 0.0)) for item in (top3 or []))
    except (TypeError, ValueError):
        top_support = float(base_confidence or 0.0)

    weak_support_threshold = float(current_app.config.get("LLM_WEAK_SUPPORT_THRESHOLD", 35.0))
    weak_support_mode = top_support < weak_support_threshold

    known_disease_catalog = [str(c) for c in clf.classes_]
    selection_pool = known_disease_catalog if weak_support_mode else candidate_diseases
    selection_pool = [d for d in selection_pool if is_disease_gender_compatible(patient_gender, d)]

    if not selection_pool:
        return {
            "enabled": True,
            "used": False,
            "reason": "No gender-compatible candidate diseases available",
        }

    prompt_payload = {
        "symptoms": symptoms,
        "medical_history": medical_history or [],
        "ml_prediction": {
            "disease": base_prediction,
            "confidence": base_confidence,
            "top3": top3,
        },
        "vitals_analysis": vitals_analysis,
        "weak_support_mode": weak_support_mode,
        "weak_support_threshold": weak_support_threshold,
        "top_support": top_support,
        "top3_candidates": candidate_diseases,
        "allowed_diseases": selection_pool,
    }

    system_prompt = (
        "You are a conservative clinical triage sanity-checker for a symptom-based prediction app. "
        "You are NOT diagnosing disease; you are validating whether the ML output is plausible. "
        "Prioritize common, symptom-consistent conditions over rare/unlikely classes unless strong evidence exists. "
        "Never invent diseases and never use knowledge outside the provided candidates. "
        "If weak_support_mode=false: choose ONLY from top3_candidates. "
        "If weak_support_mode=true: you may choose from allowed_diseases (full known disease catalog) based on symptoms. "
        "Decision policy: "
        "1) If top ML choice is plausible, keep it (override=false). "
        "2) Override when current choice is clearly inconsistent with symptom pattern or weak_support_mode=true. "
        "3) If symptom evidence is weak/ambiguous, lower confidence and set caution_level appropriately. "
        "4) Keep rationale concise and evidence-based from given symptoms/vitals only. "
        "Output must be ONLY a JSON object with EXACT keys: "
        "selected_disease, adjusted_confidence, override, rationale, caution_level. "
        "Types: selected_disease=string from allowed_diseases, adjusted_confidence=number 1-100, "
        "override=boolean, rationale=string <= 220 chars, caution_level in [low,moderate,high]."
    )

    user_prompt = (
        "Task: review ML prediction and return a safer final screening output.\n"
        "Important examples of bad mapping: isolated mild symptoms (like runny nose) should not map to unlikely fungal/systemic diagnoses unless strongly justified.\n"
        "Past medical history may explain recurrent symptoms; consider recurrence context before overriding.\n"
        "If symptoms suggest common respiratory illness, prefer a common respiratory candidate from allowed_diseases.\n"
        "If none strongly fits, keep the best candidate but reduce confidence and raise caution_level.\n\n"
        "Return JSON only. No markdown, no explanation outside JSON.\n\n"
        f"INPUT_JSON:\n{json.dumps(prompt_payload, ensure_ascii=True)}"
    )

    base_headers = {
        "Content-Type": "application/json",
    }

    site_url = (
        (current_app.config.get("OPENROUTER_SITE_URL") or "").strip()
        or (current_app.config.get("OPENROUTER_APP_URL") or "").strip()
    )
    site_name = (
        (current_app.config.get("OPENROUTER_SITE_NAME") or "").strip()
        or (current_app.config.get("OPENROUTER_APP_NAME") or "").strip()
    )
    if site_url:
        base_headers["HTTP-Referer"] = site_url
    if site_name:
        base_headers["X-OpenRouter-Title"] = site_name

    models = []
    primary_model = (current_app.config.get("OPENROUTER_MODEL") or "").strip()
    fallback_model = (current_app.config.get("OPENROUTER_MODEL_FALLBACK") or "").strip()
    tertiary_model = (current_app.config.get("OPENROUTER_MODEL_TERTIARY") or "").strip()

    def _add_model_candidates(model_name):
        if not model_name:
            return
        if model_name not in models:
            models.append(model_name)
        # Some providers expose the same model without the ':free' suffix.
        if model_name.endswith(":free"):
            alt = model_name[:-5]
            if alt and alt not in models:
                models.append(alt)

    _add_model_candidates(tertiary_model)
    _add_model_candidates(primary_model)
    _add_model_candidates(fallback_model)

    if not models:
        return {
            "enabled": True,
            "used": False,
            "reason": "OPENROUTER_MODEL missing",
        }

    base_payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }

    last_http_exc = None
    last_http_context = None
    try:
        data = None
        used_model = None
        for model_idx, model_name in enumerate(models):
            payload = dict(base_payload)
            payload["model"] = model_name

            for key_idx, key in enumerate(api_keys):
                headers = dict(base_headers)
                headers["Authorization"] = f"Bearer {key}"

                try:
                    response = requests.post(
                        url=current_app.config.get("OPENROUTER_API_URL"),
                        headers=headers,
                        data=json.dumps(payload),
                        timeout=current_app.config.get("OPENROUTER_TIMEOUT_SECONDS", 20),
                    )
                    response.raise_for_status()
                    data = response.json()
                    used_model = model_name
                    break
                except requests.exceptions.HTTPError as exc:
                    last_http_exc = exc
                    status_code = exc.response.status_code if exc.response is not None else None
                    body_preview = ""
                    if exc.response is not None and exc.response.text:
                        body_preview = exc.response.text[:280].replace("\n", " ")
                    last_http_context = {
                        "model": model_name,
                        "key_index": key_idx + 1,
                        "status": status_code,
                        "body_preview": body_preview,
                    }

                    # Try next key/model automatically on common auth/quota/rate failures.
                    has_next_key = key_idx < len(api_keys) - 1
                    has_next_model = model_idx < len(models) - 1
                    if status_code in (401, 402, 403, 429):
                        if has_next_key or has_next_model:
                            current_app.logger.warning(
                                "OpenRouter model '%s' key #%s failed with %s; trying next option",
                                model_name,
                                key_idx + 1,
                                status_code,
                            )
                            continue

                    # For other failures, still try remaining options if available.
                    if has_next_key or has_next_model:
                        current_app.logger.warning(
                            "OpenRouter model '%s' key #%s request failed; trying next option: %s",
                            model_name,
                            key_idx + 1,
                            exc,
                        )
                        continue

                    raise

            if data is not None:
                break

        if data is None and last_http_exc is not None:
            if last_http_context:
                current_app.logger.warning(
                    "OpenRouter final failure model='%s' key#%s status=%s body=%s",
                    last_http_context.get("model"),
                    last_http_context.get("key_index"),
                    last_http_context.get("status"),
                    last_http_context.get("body_preview"),
                )
            raise last_http_exc

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        reviewed = _extract_first_json_object(content)
        if not isinstance(reviewed, dict):
            return {
                "enabled": True,
                "used": False,
                "reason": "LLM returned non-JSON content",
            }

        selected_disease = str(reviewed.get("selected_disease", "")).strip()
        if selected_disease not in selection_pool:
            selected_disease = base_prediction

        try:
            adjusted_confidence = float(reviewed.get("adjusted_confidence", base_confidence))
        except (TypeError, ValueError):
            adjusted_confidence = float(base_confidence)
        adjusted_confidence = max(1.0, min(100.0, round(adjusted_confidence, 1)))

        caution_level = str(reviewed.get("caution_level", "moderate")).strip().lower()
        if caution_level not in {"low", "moderate", "high"}:
            caution_level = "moderate"

        should_override = bool(reviewed.get("override", False)) and selected_disease != base_prediction

        return {
            "enabled": True,
            "used": True,
            "model": used_model or current_app.config.get("OPENROUTER_MODEL"),
            "selected_disease": selected_disease,
            "adjusted_confidence": adjusted_confidence,
            "override": should_override,
            "rationale": str(reviewed.get("rationale", "")).strip()[:240],
            "caution_level": caution_level,
            "weak_support_mode": weak_support_mode,
            "selection_scope": "catalog" if weak_support_mode else "top3",
        }
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in (429, 402):
            retry_after = 0
            if exc.response is not None:
                retry_after_header = (exc.response.headers.get("Retry-After") or "").strip()
                try:
                    retry_after = int(retry_after_header)
                except (TypeError, ValueError):
                    retry_after = 0

            if status_code == 429:
                fallback = current_app.config.get("OPENROUTER_RATE_LIMIT_COOLDOWN_SECONDS", 120)
                reason = "OpenRouter rate limit reached (429)"
            else:
                fallback = current_app.config.get("OPENROUTER_BILLING_COOLDOWN_SECONDS", 900)
                reason = "OpenRouter billing/spend limit reached (402)"

            _set_openrouter_cooldown(retry_after or fallback)
            current_app.logger.warning("LLM review skipped: %s", reason)
            return {
                "enabled": True,
                "used": False,
                "reason": reason,
            }

        current_app.logger.warning("LLM review failed with HTTP error: %s", exc)
        return {
            "enabled": True,
            "used": False,
            "reason": f"LLM request failed: {str(exc)}",
        }
    except Exception as exc:
        current_app.logger.warning("LLM review failed: %s", exc)
        return {
            "enabled": True,
            "used": False,
            "reason": f"LLM request failed: {str(exc)}",
        }


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                     PUBLIC ROUTES (No Authentication)                      ║
# ╚════════════════════════════════════════════════════════════════════════════╝

@app.route("/")
def index():
    """Serve the frontend"""
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    """Silence browser favicon 404s when no icon file is configured."""
    return "", 204


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})


@app.route("/api/model/runtime-info", methods=["GET"])
def model_runtime_info():
    """Expose non-sensitive model runtime diagnostics for deployment debugging."""
    return jsonify(
        {
            "model_loaded": _model_runtime_info.get("loaded", False),
            "auto_retrained": _model_runtime_info.get("auto_retrained", False),
            "load_error": _model_runtime_info.get("load_error"),
            "retrain_error": _model_runtime_info.get("retrain_error"),
            "versions": {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "scikit_learn": sklearn.__version__,
                "joblib": joblib.__version__,
            },
        }
    )


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                    AUTHENTICATION ROUTES                                   ║
# ╚════════════════════════════════════════════════════════════════════════════╝

@app.route("/api/auth/request-otp", methods=["POST"])
def request_otp():
    """
    Request OTP for email-based login/signup
    
    Body: {"email": "user@example.com"}
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    
    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400
    
    try:
        # Create or get user
        user = AuthService.create_or_get_user(email)
        
        # Generate OTP
        otp, success, message = AuthService.generate_otp(email)
        
        if not success:
            return jsonify({"error": message}), 500
        
        return jsonify({
            "message": "OTP sent successfully",
            "email": email,
            "validity_minutes": app.config["OTP_VALIDITY_MINUTES"],
            "user_id": user.id
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to request OTP: {str(e)}"}), 500


@app.route("/api/auth/verify-otp", methods=["POST"])
def verify_otp():
    """
    Verify OTP and generate JWT tokens
    
    Body: {"email": "user@example.com", "otp": "123456"}
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    otp_code = data.get("otp", "").strip()
    
    if not email or not otp_code or len(otp_code) != 6:
        return jsonify({"error": "Valid email and 6-digit OTP required"}), 400
    
    try:
        # Verify OTP
        is_valid, message = AuthService.verify_otp(email, otp_code)
        if not is_valid:
            return jsonify({"error": message}), 401
        
        # Get or create user
        user = User.query.filter_by(email=email).first()
        if not user:
            user = AuthService.create_or_get_user(email)
        
        # Mark user as verified
        user.is_verified = True
        db.session.commit()
        
        # Generate JWT tokens
        tokens = AuthService.generate_tokens(user.id)
        
        return jsonify({
            "message": "Login successful",
            "user": user.to_dict(),
            **tokens
        }), 200
    except Exception as e:
        return jsonify({"error": f"OTP verification failed: {str(e)}"}), 500


@app.route("/api/auth/refresh", methods=["POST"])
def refresh_token():
    """Refresh JWT access token using refresh token"""
    from flask_jwt_extended import verify_jwt_in_request
    
    try:
        verify_jwt_in_request(refresh=True)
        from flask_jwt_extended import get_jwt_identity
        user_id = get_jwt_identity()
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid token identity"}), 401
        
        access_token = AuthService.generate_tokens(user_id)["access_token"]
        
        return jsonify({"access_token": access_token}), 200
    except Exception as e:
        return jsonify({"error": "Token refresh failed"}), 401


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                    PREDICTION ROUTES (Authenticated)                       ║
# ╚════════════════════════════════════════════════════════════════════════════╝

@app.route("/api/symptoms", methods=["GET"])
def get_symptoms():
    """Return the full list of symptoms (display-friendly labels)"""
    display = [s.replace("_", " ").title() for s in all_symptoms]
    return jsonify([{"value": s, "label": d} for s, d in zip(all_symptoms, display)])


@app.route("/api/predict", methods=["POST"])
@token_required
def predict(user):
    """
    Predict disease based on symptoms and store in history
    
    Body: {
        "symptoms": ["cough", "fever"],
        "notes": "optional notes",
        "health_data": {optional health vitals}
    }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        abort(400, "Request body must be valid JSON.")

    prediction_gender = canonicalize_gender(data.get("prediction_gender"))
    patient_gender = prediction_gender or canonicalize_gender(user.gender)
    if patient_gender not in {"M", "F"}:
        return jsonify({
            "error": "Gender selection is mandatory before prediction. Provide prediction_gender as Male/Female or update profile.",
            "required_action": "update_profile_gender"
        }), 400

    # Sync runtime-selected gender to profile for consistent future predictions.
    if prediction_gender in {"M", "F"} and canonicalize_gender(user.gender) != prediction_gender:
        user.gender = prediction_gender

    raw_symptoms = data.get("symptoms")
    symptom_text = str(data.get("symptom_text", "")).strip()
    interpreted = {
        "symptoms": [],
        "llm_used": False,
        "source": "none",
        "reason": "No symptom text provided",
    }

    if raw_symptoms is None and not symptom_text:
        abort(400, "Provide either a 'symptoms' array or a non-empty 'symptom_text' field.")

    if raw_symptoms is not None and not isinstance(raw_symptoms, list):
        abort(400, "'symptoms' must be an array when provided.")

    # Sanitise input: keep only known symptoms
    chosen = []
    unknown = []

    if isinstance(raw_symptoms, list):
        for s in raw_symptoms:
            clean = str(s).strip().lower()
            if clean in symptom_index:
                chosen.append(clean)
            else:
                unknown.append(s)

    if symptom_text:
        interpreted = interpret_symptoms_from_text(symptom_text, patient_gender=patient_gender)
        for sym in interpreted.get("symptoms", []):
            if sym in symptom_index and sym not in chosen:
                chosen.append(sym)

    if not chosen:
        return jsonify({
            "error": "Could not map the symptom description to known symptoms. Try a clearer phrase like fever, cough, chest pain, shoulder pain, or headache.",
            "interpreted_symptoms": interpreted,
            "unknown_symptoms": unknown,
        }), 422

    compatibility = validate_gender_symptom_compatibility(patient_gender, chosen)
    if not compatibility.get("ok"):
        return jsonify({
            "error": "Some symptoms are incompatible with your selected gender profile. Please update profile gender or symptom text.",
            "incompatible_symptoms": compatibility.get("conflicting", []),
            "gender": patient_gender,
        }), 400

    # Build feature vector
    vec = np.zeros((1, len(all_symptoms)), dtype=np.float32)
    for s in chosen:
        vec[0, symptom_index[s]] = severity_map[s]

    # Get predictions from symptom model
    disease = clf.predict(vec)[0]
    proba = clf.predict_proba(vec)[0]
    top3_idx = np.argsort(proba)[::-1][:3]
    top3 = [
        {"disease": clf.classes_[i], "probability": round(float(proba[i]) * 100, 1)}
        for i in top3_idx
        if proba[i] > 0
    ]

    compatible_top3 = [
        item for item in top3
        if is_disease_gender_compatible(patient_gender, item.get("disease"))
    ]
    if not compatible_top3:
        return jsonify({
            "error": "No gender-compatible disease candidates found for the supplied symptoms.",
            "gender": patient_gender,
            "suggestion": "Please review your symptom description and profile details.",
        }), 422

    top3 = compatible_top3

    if not is_disease_gender_compatible(patient_gender, disease):
        disease = top3[0]["disease"]

    base_confidence = next(
        (item["probability"] for item in top3 if item.get("disease") == disease),
        round(float(proba[np.argmax(proba)]) * 100, 1),
    )

    health_data = data.get("health_data") if isinstance(data.get("health_data"), dict) else None
    vitals_analysis = analyze_vitals_impact(health_data)
    past_illnesses = get_user_latest_past_illnesses(user.id)
    history_analysis = analyze_medical_history_impact(chosen, past_illnesses)

    confidence = base_confidence
    if vitals_analysis:
        confidence = max(20.0, round(base_confidence - vitals_analysis["confidence_penalty"], 1))
    if history_analysis.get("used"):
        confidence = max(18.0, round(confidence - history_analysis.get("confidence_penalty", 0.0), 1))
    
    force_llm_threshold = float(current_app.config.get("LLM_FORCE_BELOW_CONFIDENCE", 25.0))
    force_llm_mode = confidence < force_llm_threshold
    force_llm_all_cases = bool(current_app.config.get("LLM_FORCE_ALL_CASES", False))
    strict_force_mode = bool(current_app.config.get("LLM_STRICT_FORCE_MODE", False))

    llm_review = llm_review_prediction(
        symptoms=chosen,
        top3=top3,
        base_prediction=disease,
        base_confidence=confidence,
        vitals_analysis=vitals_analysis,
        patient_gender=patient_gender,
        medical_history=past_illnesses,
    )

    # Strict mode: when always-force is enabled, require LLM for every prediction.
    # Otherwise, require LLM only for low-confidence predictions.
    requires_llm = force_llm_all_cases or (strict_force_mode and force_llm_mode)
    if requires_llm and not llm_review.get("used"):
        return jsonify({
            "error": "Prediction requires LLM review, but LLM review is currently unavailable.",
            "confidence_score": confidence,
            "force_llm_threshold": force_llm_threshold,
            "force_llm_all_cases": force_llm_all_cases,
            "strict_force_mode": strict_force_mode,
            "ai_review": llm_review,
            "required_action": "configure_or_enable_llm",
        }), 503

    final_disease = disease
    final_confidence = confidence
    if llm_review.get("used") and (force_llm_all_cases or force_llm_mode):
        final_disease = llm_review.get("selected_disease") or disease
        final_confidence = llm_review.get("adjusted_confidence", confidence)
    elif llm_review.get("used") and llm_review.get("override"):
        final_disease = llm_review.get("selected_disease") or disease
        final_confidence = llm_review.get("adjusted_confidence", confidence)
    elif llm_review.get("used"):
        final_confidence = llm_review.get("adjusted_confidence", confidence)

    llm_unavailable_below_threshold = (force_llm_all_cases or force_llm_mode) and not llm_review.get("used")

    guardrail_result = {
        "applied": False,
        "reason": "skipped_because_llm_used",
    }
    if not llm_review.get("used"):
        guardrail_result = apply_prediction_guardrails(
            chosen_symptoms=chosen,
            current_disease=final_disease,
            current_confidence=final_confidence,
            top3=top3,
        )
        if guardrail_result.get("applied"):
            final_disease = guardrail_result.get("disease", final_disease)
            final_confidence = guardrail_result.get("confidence", final_confidence)

    # Store prediction in database
    prediction = PredictionHistory(
        user_id=user.id,
        symptoms=chosen,
        predicted_disease=final_disease,
        confidence_score=final_confidence,
        top3_predictions=top3,
        notes=data.get("notes"),
        severity_level=data.get("severity_level") or (vitals_analysis["triage_level"] if vitals_analysis else None)
    )
    
    # Store health data if provided
    if health_data:
        health_record = HealthRecord(
            user_id=user.id,
            prediction_id=None,
            blood_pressure=health_data.get("blood_pressure"),
            heart_rate=health_data.get("heart_rate"),
            temperature=health_data.get("temperature"),
            oxygen_saturation=health_data.get("oxygen_saturation"),
            blood_sugar=health_data.get("blood_sugar"),
            allergies=health_data.get("allergies"),
            medications=health_data.get("medications")
        )
        db.session.add(health_record)
    
    db.session.add(prediction)
    db.session.commit()

    return jsonify({
        "prediction_id": prediction.id,
        "disease": final_disease,
        "description": desc_map.get(final_disease, "No description available."),
        "precautions": prec_map.get(final_disease, []),
        "confidence_score": final_confidence,
        "base_confidence_score": base_confidence,
        "ml_prediction": {
            "disease": disease,
            "confidence_score": confidence,
        },
        "prediction_strategy": {
            "force_llm_all_cases": force_llm_all_cases,
            "force_llm_mode": force_llm_mode,
            "force_llm_threshold": force_llm_threshold,
            "strict_force_mode": strict_force_mode,
        },
        "ai_review": llm_review,
        "llm_unavailable_below_threshold": llm_unavailable_below_threshold,
        "guardrail": guardrail_result,
        "vitals_used": bool(vitals_analysis),
        "vitals_analysis": vitals_analysis,
        "past_medical_history": past_illnesses,
        "history_analysis": history_analysis,
        "top3": top3,
        "patient_gender": patient_gender,
        "interpreted_symptoms": interpreted,
        "symptoms_used": chosen,
        "unknown_symptoms": unknown,
        "stored": True
    }), 200


@app.route("/api/predictions/history", methods=["GET"])
@token_required
def get_prediction_history(user):
    """Get user's prediction history with pagination"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("limit", 10, type=int)
    
    paginated = PredictionHistory.query.filter_by(user_id=user.id).order_by(
        PredictionHistory.created_at.desc()
    ).paginate(page=page, per_page=per_page)
    
    return jsonify({
        "total": paginated.total,
        "pages": paginated.pages,
        "current_page": page,
        "predictions": [p.to_dict() for p in paginated.items]
    }), 200


@app.route("/api/predictions/<int:prediction_id>", methods=["GET"])
@token_required
def get_prediction_detail(user, prediction_id):
    """Get detailed prediction with associated health data"""
    prediction = PredictionHistory.query.filter_by(
        id=prediction_id, user_id=user.id
    ).first()
    
    if not prediction:
        return jsonify({"error": "Prediction not found"}), 404
    
    # Get associated health records
    health_records = HealthRecord.query.filter_by(
        prediction_id=prediction_id
    ).all()
    
    return jsonify({
        "prediction": prediction.to_dict(),
        "health_records": [h.to_dict() for h in health_records]
    }), 200


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                    USER PROFILE ROUTES (Authenticated)                     ║
# ╚════════════════════════════════════════════════════════════════════════════╝

@app.route("/api/user/profile", methods=["GET"])
@token_required
def get_user_profile(user):
    """Get current user's profile"""
    return jsonify(user.to_dict()), 200


@app.route("/api/user/profile", methods=["PUT"])
@token_required
def update_user_profile(user):
    """Update user profile information"""
    data = request.get_json(silent=True) or {}
    
    try:
        # Update allowed fields
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
            # Empty phone should be stored as NULL to avoid unique constraint conflicts.
            phone = (data.get("phone") or "").strip()
            user.phone = phone or None
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            "message": "Profile updated successfully",
            "user": user.to_dict()
        }), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Phone number already in use by another account"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to update profile: {str(e)}"}), 500


@app.route("/api/user/health-records", methods=["GET"])
@token_required
def get_health_records(user):
    """Get user's health records"""
    records = HealthRecord.query.filter_by(user_id=user.id).order_by(
        HealthRecord.created_at.desc()
    ).all()
    
    return jsonify({
        "count": len(records),
        "records": [r.to_dict() for r in records]
    }), 200


@app.route("/api/user/health-records", methods=["POST"])
@token_required
def add_health_record(user):
    """Add a new health record"""
    data = request.get_json(silent=True) or {}
    
    try:
        health_record = HealthRecord(
            user_id=user.id,
            blood_pressure=data.get("blood_pressure"),
            heart_rate=data.get("heart_rate"),
            temperature=data.get("temperature"),
            oxygen_saturation=data.get("oxygen_saturation"),
            blood_sugar=data.get("blood_sugar"),
            allergies=data.get("allergies"),
            medications=data.get("medications"),
            past_illnesses=data.get("past_illnesses")
        )
        
        db.session.add(health_record)
        db.session.commit()
        
        return jsonify({
            "message": "Health record added successfully",
            "record": health_record.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to add health record: {str(e)}"}), 500


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                    ABHA INTEGRATION ROUTES                                 ║
# ╚════════════════════════════════════════════════════════════════════════════╝

@app.route("/api/abha/authorization-url", methods=["GET"])
@token_required
def get_abha_authorization_url(user):
    """Generate ABHA OAuth authorization URL"""
    try:
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        auth_url = ABHAService.get_authorization_url(state)
        
        return jsonify({
            "authorization_url": auth_url,
            "state": state
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to generate authorization URL: {str(e)}"}), 500


@app.route("/api/abha/operations", methods=["GET"])
@token_required
def get_abha_operations(user):
    """Return supported ABHA operations mapped to official ABDM endpoints."""
    return jsonify({
        "operations": ABHAService.get_operation_catalog(),
        "count": len(ABHAService.get_operation_catalog())
    }), 200


@app.route("/api/abha/execute", methods=["POST"])
@token_required
def execute_abha_operation(user):
    """
    Execute one whitelisted ABHA operation.

    Body:
    {
      "operation": "auth.init",
      "payload": {...},
      "auth_token": "optional-abha-token"
    }
    """
    data = request.get_json(silent=True) or {}
    operation = data.get("operation")
    payload = data.get("payload") or {}
    provided_auth_token = data.get("auth_token")

    if not operation:
        return jsonify({"error": "operation is required"}), 400

    client_id = (app.config.get("ABHA_CLIENT_ID") or "").strip()
    client_secret = (app.config.get("ABHA_CLIENT_SECRET") or "").strip()
    placeholder_values = {
        "",
        "your-abha-client-id",
        "your-abha-client-secret",
        "changeme",
        "replace-me",
    }
    if client_id in placeholder_values or client_secret in placeholder_values:
        return jsonify({
            "error": "ABHA credentials are not configured. Set ABHA_CLIENT_ID and ABHA_CLIENT_SECRET in .env"
        }), 400

    operation_catalog = ABHAService.get_operation_catalog()
    operation_meta = operation_catalog.get(operation)
    if not operation_meta:
        return jsonify({
            "error": "Unsupported ABHA operation",
            "operation": operation,
            "supported_operations": sorted(operation_catalog.keys())
        }), 400

    effective_auth_token = provided_auth_token
    if operation_meta.get("requires_auth_token") and not effective_auth_token:
        token_row = ABHAToken.query.filter_by(user_id=user.id).first()
        if token_row:
            refresh_ok, refresh_result = ABHAService.refresh_abha_token(user.id)
            if refresh_ok:
                effective_auth_token = refresh_result

    success, result, status_code = ABHAService.execute_operation(
        operation=operation,
        payload=payload,
        auth_token=effective_auth_token,
    )

    if success and operation in {"auth.confirm_aadhaar_otp", "auth.confirm_mobile_otp"}:
        token_value = result.get("token") or result.get("accessToken") or result.get("access_token")
        abha_id = result.get("healthId") or result.get("abhaAddress") or result.get("abhaId")
        if token_value:
            ABHAService.link_abha_account(user.id, token_value, abha_id)

    if success:
        return jsonify({
            "operation": operation,
            "endpoint": operation_meta.get("endpoint"),
            "response": result,
        }), status_code

    return jsonify({
        "operation": operation,
        "endpoint": operation_meta.get("endpoint"),
        "error": result,
    }), status_code or 500


@app.route("/api/abha/callback", methods=["POST"])
@token_required
def abha_callback(user):
    """Handle ABHA OAuth callback"""
    data = request.get_json(silent=True) or {}
    code = data.get("code")
    
    if not code:
        return jsonify({"error": "Authorization code missing"}), 400
    
    try:
        # Exchange code for token
        success, token_data, status_code = ABHAService.exchange_code_for_token(code)
        if not success:
            return jsonify({"error": token_data}), status_code or 500
        
        access_token = token_data.get("access_token")
        abha_id = token_data.get("abha_id", "")
        
        # Link ABHA account
        success, message = ABHAService.link_abha_account(user.id, access_token, abha_id)
        if not success:
            return jsonify({"error": message}), 500
        
        # Fetch and store health records
        success, message = ABHAService.fetch_and_store_health_records(user.id, access_token)
        
        return jsonify({
            "message": "ABHA account linked successfully",
            "abha_id": abha_id,
            "health_records_fetched": success
        }), 200
    except Exception as e:
        return jsonify({"error": f"ABHA callback failed: {str(e)}"}), 500


@app.route("/api/abha/health-data", methods=["GET"])
@token_required
def get_abha_health_data(user):
    """Fetch latest health data from ABHA"""
    if not user.abha_id:
        return jsonify({"error": "ABHA account not linked"}), 400
    
    try:
        # Refresh token if needed
        success, token = ABHAService.refresh_abha_token(user.id)
        if not success:
            return jsonify({"error": token}), 500
        
        # Fetch health data
        success, data = ABHAService.get_user_health_data(token)
        if not success:
            return jsonify({"error": data}), 500
        
        return jsonify({
            "abha_id": user.abha_id,
            "health_data": data
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to fetch ABHA health data: {str(e)}"}), 500


@app.route("/api/abha/link-dummy", methods=["POST"])
@token_required
def link_dummy_abha_data(user):
    """Link synthetic ABHA profile and seed random past illnesses for demo mode."""
    try:
        past_illnesses = _generate_dummy_abha_past_illnesses_for_user(user.id)

        user.abha_id = f"DUMMY-ABHA-{user.id:06d}"
        user.abha_linked_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()

        health_record = HealthRecord(
            user_id=user.id,
            abha_data={
                "source": "dummy_abha",
                "generated_at": datetime.utcnow().isoformat(),
                "records": past_illnesses,
            },
            past_illnesses=past_illnesses,
        )

        db.session.add(health_record)
        db.session.commit()

        return jsonify({
            "message": "Dummy ABHA data linked successfully",
            "abha_id": user.abha_id,
            "past_illnesses": past_illnesses,
            "record_id": health_record.id,
        }), 200
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": f"Failed to link dummy ABHA data: {str(exc)}"}), 500


@app.route("/api/abha/unlink", methods=["POST"])
@token_required
def unlink_abha_account(user):
    """Unlink ABHA account from user"""
    try:
        user.abha_id = None
        user.abha_token = None
        user.abha_linked_at = None
        user.updated_at = datetime.utcnow()
        
        # Delete associated ABHA tokens
        from models import ABHAToken
        ABHAToken.query.filter_by(user_id=user.id).delete()
        
        db.session.commit()
        
        return jsonify({
            "message": "ABHA account unlinked successfully"
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to unlink ABHA account: {str(e)}"}), 500


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                    ERROR HANDLERS                                          ║
# ╚════════════════════════════════════════════════════════════════════════════╝

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
    db.session.rollback()
    if app.debug:
        return jsonify({"error": f"Internal server error: {str(error)}"}), 500
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
