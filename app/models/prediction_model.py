from datetime import datetime, timezone
from typing import Any, Dict

from bson import ObjectId
from flask import current_app

from app.extensions import mongo


def _database():
    if mongo.db is not None:
        return mongo.db
    db_name = current_app.config.get("MONGO_DBNAME", "disease_prediction")
    try:
        default_db = mongo.cx.get_default_database()
        if default_db is not None:
            db_name = default_db.name
    except Exception:
        pass
    return mongo.cx[db_name]


def predictions_collection():
    return _database().predictions


def store_prediction(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    doc = {
        "user_id": ObjectId(user_id),
        "input_text": payload.get("input_text", ""),
        "extracted": payload.get("extracted", {}),
        "prediction": payload.get("prediction", {}),
        "confidence": payload.get("confidence", 0.0),
        "reasoning_note": payload.get("reasoning_note", ""),
        "created_at": datetime.now(timezone.utc),
    }
    inserted = predictions_collection().insert_one(doc)
    doc["_id"] = inserted.inserted_id
    return doc


def list_predictions_for_user(user_id: str, limit: int = 20) -> list[Dict[str, Any]]:
    cursor = (
        predictions_collection()
        .find({"user_id": ObjectId(user_id)})
        .sort("created_at", -1)
        .limit(limit)
    )
    results: list[Dict[str, Any]] = []
    for doc in cursor:
        results.append(
            {
                "id": str(doc.get("_id")),
                "input_text": doc.get("input_text", ""),
                "prediction": doc.get("prediction", {}),
                "confidence": doc.get("confidence", 0),
                "reasoning_note": doc.get("reasoning_note", ""),
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else "",
            }
        )
    return results
