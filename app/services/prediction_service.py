from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import warnings

import joblib
import numpy as np
from sklearn.exceptions import InconsistentVersionWarning

from utils.llm_engine import LLMTimeoutError, extract_structured_input, run_reasoning_step

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_DIR / "model"

_clf = None
_symptoms = []
_symptom_index = {}
_FEMALE_ONLY_HINTS = (
    "menstrual",
    "period",
    "pregnan",
    "ovary",
    "ovarian",
    "uterus",
    "uterine",
    "endometri",
    "pcos",
)


def _is_valid_estimator(candidate: Any) -> bool:
    return hasattr(candidate, "predict")


def _load_artifact(path: Path):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", InconsistentVersionWarning)
        obj = joblib.load(path)
    has_version_warning = any(
        issubclass(item.category, InconsistentVersionWarning) for item in caught
    )
    return obj, has_version_warning


def _ensure_valid_artifacts():
    from train import train_and_save_model

    clf, symptoms, _ = train_and_save_model(str(BASE_DIR), str(MODEL_DIR))
    if not _is_valid_estimator(clf):
        raise RuntimeError("Trained artifact is invalid: missing predict()")
    return clf, symptoms


def _smoke_test_model(clf: Any, symptoms: list[str]) -> bool:
    try:
        probe = np.zeros((1, len(symptoms)), dtype=np.float32)
        clf.predict(probe)
        if hasattr(clf, "predict_proba"):
            clf.predict_proba(probe)
        return True
    except Exception:
        return False


def _load_model_assets():
    global _clf, _symptoms, _symptom_index
    if _clf is not None and _symptoms:
        return

    try:
        loaded_clf, model_warn = _load_artifact(MODEL_DIR / "model.pkl")
        loaded_symptoms, symptoms_warn = _load_artifact(MODEL_DIR / "symptom_list.pkl")
        if model_warn or symptoms_warn:
            raise ValueError("Incompatible sklearn model version detected")
        if not _is_valid_estimator(loaded_clf) or not isinstance(loaded_symptoms, list):
            raise ValueError("Invalid model assets format")
        if not _smoke_test_model(loaded_clf, loaded_symptoms):
            raise ValueError("Model artifact failed compatibility smoke test")
        _clf = loaded_clf
        _symptoms = loaded_symptoms
    except Exception:
        _clf, _symptoms = _ensure_valid_artifacts()

    _symptom_index = {symptom: idx for idx, symptom in enumerate(_symptoms)}


def _normalize_gender(value: Any) -> str | None:
    if not value:
        return None
    token = str(value).strip().lower()
    if token in {"male", "m", "man", "boy"}:
        return "male"
    if token in {"female", "f", "woman", "girl"}:
        return "female"
    return "other"


def _is_female_only_disease(name: str) -> bool:
    token = str(name).strip().lower()
    return any(hint in token for hint in _FEMALE_ONLY_HINTS)


def _select_gender_safe_prediction(
    predicted_label: str,
    confidence: float,
    proba_row: np.ndarray | None,
    classes: np.ndarray | None,
    gender: str | None,
) -> tuple[str, float, str]:
    if gender != "male":
        return predicted_label, confidence, ""

    if not _is_female_only_disease(predicted_label):
        return predicted_label, confidence, ""

    if proba_row is not None and classes is not None:
        ranked = sorted(
            ((str(label), float(score)) for label, score in zip(classes, proba_row)),
            key=lambda item: item[1],
            reverse=True,
        )
        for label, score in ranked:
            if not _is_female_only_disease(label):
                return label, round(score * 100, 2), (
                    "Gender safety guardrail replaced a female-specific diagnosis for male context."
                )

    return predicted_label, confidence, "Gender safety guardrail could not find an alternative class."


def run_prediction(input_text: str, user_profile: dict, explicit_gender: str | None = None) -> Dict[str, Any]:
    global _clf, _symptoms, _symptom_index
    _load_model_assets()
    extracted = extract_structured_input(input_text, _symptoms, user_profile)
    extracted_gender = _normalize_gender(extracted.get("gender"))
    profile_gender = _normalize_gender(user_profile.get("gender"))
    request_gender = _normalize_gender(explicit_gender)
    effective_gender = request_gender or extracted_gender
    if profile_gender in {"male", "female", "other"}:
        effective_gender = profile_gender
    extracted["gender"] = effective_gender

    vector = np.zeros(len(_symptoms))
    for symptom in extracted.get("symptoms", []):
        if symptom in _symptom_index:
            vector[_symptom_index[symptom]] = 1

    try:
        prediction = _clf.predict([vector])[0]
    except Exception:
        # If runtime predict fails due to latent serialization incompatibility, self-heal once.
        _clf, _symptoms = _ensure_valid_artifacts()
        _symptom_index = {symptom: idx for idx, symptom in enumerate(_symptoms)}
        vector = np.zeros(len(_symptoms))
        for symptom in extracted.get("symptoms", []):
            if symptom in _symptom_index:
                vector[_symptom_index[symptom]] = 1
        prediction = _clf.predict([vector])[0]

    proba_row = None
    class_labels = None
    confidence = 0.0
    if hasattr(_clf, "predict_proba"):
        proba_row = _clf.predict_proba([vector])[0]
        confidence = float(np.max(proba_row) * 100)
        class_labels = getattr(_clf, "classes_", None)

    prediction, confidence, gender_guardrail_note = _select_gender_safe_prediction(
        predicted_label=str(prediction),
        confidence=confidence,
        proba_row=proba_row,
        classes=class_labels,
        gender=effective_gender,
    )

    reasoning_note = ""
    llm_used = False
    if confidence < 40:
        reasoning_result = run_reasoning_step(
            input_text=input_text,
            base_prediction=prediction,
            extracted=extracted,
            confidence=confidence,
            abha_records=user_profile.get("abha_records", []),
        )
        reasoning_note = reasoning_result.get("note", "")
        llm_used = bool(reasoning_result.get("llm_used", False))
        refined = reasoning_result.get("refined_disease")
        if refined and isinstance(refined, str):
            refined_clean = refined.strip()
            if refined_clean:
                if effective_gender == "male" and _is_female_only_disease(refined_clean):
                    reasoning_note = (
                        (reasoning_note + " ") if reasoning_note else ""
                    ) + "Refined diagnosis rejected by gender safety guardrail."
                else:
                    prediction = refined_clean
                    reasoning_note = (
                        (reasoning_note + " ") if reasoning_note else ""
                    ) + "Diagnosis refined via secondary LLM verification."

    if gender_guardrail_note:
        reasoning_note = ((reasoning_note + " ") if reasoning_note else "") + gender_guardrail_note

    return {
        "disease": prediction,
        "confidence": round(confidence, 2),
        "confidence_label": "AI - generated" if llm_used else f"{round(confidence, 2)}%",
        "llm_used": llm_used,
        "extracted": extracted,
        "reasoning_note": reasoning_note,
    }


__all__ = ["run_prediction", "LLMTimeoutError"]
