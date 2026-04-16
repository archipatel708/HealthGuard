from datetime import datetime, timezone
from typing import Any, Dict, Optional

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


def users_collection():
    return _database().users


def create_user(name: str, email: str, password_hash: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc = {
        "name": name,
        "email": email.lower().strip(),
        "password_hash": password_hash,
        "phone": "",
        "gender": "unspecified",
        "abha_records": [],
        "created_at": now,
        "updated_at": now,
    }
    inserted = users_collection().insert_one(doc)
    doc["_id"] = inserted.inserted_id
    return doc


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    return users_collection().find_one({"email": email.lower().strip()})


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    try:
        return users_collection().find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


def update_profile(user_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    update_doc = {"updated_at": datetime.now(timezone.utc)}
    for field in ("name", "email", "phone", "gender"):
        if field in payload and payload[field] is not None:
            value = payload[field].strip() if isinstance(payload[field], str) else payload[field]
            if field == "email":
                value = value.lower()
            if field == "gender":
                token = str(value).lower()
                if token not in {"male", "female", "other", "unspecified"}:
                    token = "unspecified"
                value = token
            update_doc[field] = value

    users_collection().update_one({"_id": ObjectId(user_id)}, {"$set": update_doc})
    return get_user_by_id(user_id)


def attach_abha_records(user_id: str, records: list[dict]) -> Optional[Dict[str, Any]]:
    users_collection().update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"abha_records": records, "updated_at": datetime.now(timezone.utc)}},
    )
    return get_user_by_id(user_id)
