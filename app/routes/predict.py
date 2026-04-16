from flask import Blueprint, jsonify, request

from app.models.prediction_model import list_predictions_for_user, store_prediction
from app.models.user_model import attach_abha_records
from app.services.auth_service import login_required
from app.services.prediction_service import LLMTimeoutError, run_prediction
from utils.abha_parser import parse_dummy_health_data, pick_random_records

predict_bp = Blueprint("predict", __name__)


@predict_bp.post("/predict")
@login_required
def predict(user_doc):
    payload = request.get_json(silent=True) or {}
    input_text = payload.get("text", "").strip()
    if not input_text:
        return jsonify({"error": "text is required"}), 400

    try:
        result = run_prediction(input_text=input_text, user_profile=user_doc, explicit_gender=None)
        store_prediction(
            user_id=str(user_doc["_id"]),
            payload={
                "input_text": input_text,
                "extracted": result["extracted"],
                "prediction": {"disease": result["disease"]},
                "confidence": result["confidence"],
                "reasoning_note": result["reasoning_note"],
            },
        )
        return (
            jsonify(
                {
                    "disease": result["disease"],
                    "confidence": result["confidence"],
                    "confidence_label": result.get("confidence_label", f"{result['confidence']}%"),
                    "llm_used": result.get("llm_used", False),
                    "reasoning_note": result["reasoning_note"],
                    "terminal_status": "OK",
                }
            ),
            200,
        )
    except LLMTimeoutError:
        return (
            jsonify(
                {
                    "terminal_status": "SYSTEM_FAILURE",
                    "message": "LLM timeout during diagnostic pipeline",
                }
            ),
            504,
        )
    except Exception as exc:
        return jsonify({"error": str(exc), "terminal_status": "SYSTEM_FAILURE"}), 500


@predict_bp.post("/abha/link")
@login_required
def link_abha(user_doc):
    records = parse_dummy_health_data()
    selected = pick_random_records(records)
    updated = attach_abha_records(str(user_doc["_id"]), selected)
    return (
        jsonify(
            {
                "message": "ABHA linked",
                "records_linked": len(selected),
                "abha_records": updated.get("abha_records", []),
            }
        ),
        200,
    )


@predict_bp.get("/history")
@login_required
def history(user_doc):
    records = list_predictions_for_user(str(user_doc["_id"]))
    return jsonify({"history": records}), 200
