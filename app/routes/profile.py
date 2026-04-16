from flask import Blueprint, jsonify, request

from app.models.user_model import update_profile
from app.services.auth_service import login_required

profile_bp = Blueprint("profile", __name__)


def _public_user(user_doc: dict) -> dict:
    return {
        "id": str(user_doc["_id"]),
        "name": user_doc.get("name", ""),
        "email": user_doc.get("email", ""),
        "phone": user_doc.get("phone", ""),
        "gender": user_doc.get("gender", "unspecified"),
        "abha_records_count": len(user_doc.get("abha_records", [])),
    }


@profile_bp.patch("")
@login_required
def patch_profile(user_doc):
    payload = request.get_json(silent=True) or {}
    updated = update_profile(str(user_doc["_id"]), payload)
    return jsonify({"user": _public_user(updated), "message": "profile_updated"}), 200
