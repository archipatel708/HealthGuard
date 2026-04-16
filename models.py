"""MongoDB data models and helpers for the Disease Prediction backend."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

import certifi
from bson import ObjectId
from pymongo import ASCENDING, MongoClient
from pymongo.database import Database


_mongo_client: Optional[MongoClient] = None
_mongo_database: Optional[Database] = None
_indexes_ensured = False


def _resolve_mongodb_uri() -> str:
    uri = (os.getenv("MONGODB_URI") or "").strip()
    if not uri:
        raise ValueError("MONGODB_URI environment variable not set")
    return uri


def _resolve_database_name(uri: str) -> str:
    explicit_db = (os.getenv("MONGODB_DB") or "").strip()
    if explicit_db:
        return explicit_db

    if "/" in uri:
        tail = uri.rsplit("/", 1)[-1]
        name = tail.split("?", 1)[0].strip()
        if name:
            return name

    return "healthguard"


def initialize_mongodb() -> None:
    """Initialize the MongoDB client and database singletons."""
    global _mongo_client, _mongo_database

    if _mongo_database is not None:
        return

    uri = _resolve_mongodb_uri()
    database_name = _resolve_database_name(uri)

    mongo_kwargs: Dict[str, Any] = {
        "serverSelectionTimeoutMS": 5000,
        "connectTimeoutMS": 20000,
        "socketTimeoutMS": 20000,
        "connect": False,
    }
    if uri.startswith("mongodb+srv://"):
        mongo_kwargs["tlsCAFile"] = certifi.where()

    client = MongoClient(uri, **mongo_kwargs)
    database = client[database_name]

    _mongo_client = client
    _mongo_database = database


def _ensure_indexes(database: Database) -> None:
    global _indexes_ensured
    if _indexes_ensured:
        return

    database.users.create_index([("email", ASCENDING)], unique=True)
    database.users.create_index(
        [("phone", ASCENDING)],
        unique=True,
        sparse=True,
        partialFilterExpression={"phone": {"$type": "string"}},
    )
    database.prediction_history.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    database.health_records.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    database.abha_tokens.create_index([("user_id", ASCENDING)], unique=True)
    _indexes_ensured = True


def get_mongo_database() -> Database:
    """Return the initialized MongoDB database."""
    if _mongo_database is None:
        initialize_mongodb()

    _ensure_indexes(_mongo_database)
    return _mongo_database


def _stringify_object_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


@dataclass
class User:
    email: str
    password_hash: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    abha_id: Optional[str] = None
    abha_token: Optional[str] = None
    abha_linked_at: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    mongo_id: Optional[str] = None

    @property
    def id(self) -> Optional[str]:
        return self.mongo_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "password_hash": self.password_hash,
            "phone": self.phone,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "age": self.age,
            "gender": self.gender,
            "abha_id": self.abha_id,
            "abha_token": self.abha_token,
            "abha_linked_at": self.abha_linked_at,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_public_dict(self) -> Dict[str, Any]:
        payload = self.to_dict()
        payload.pop("password_hash", None)
        payload.pop("abha_token", None)
        return payload

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "User":
        return User(
            email=(data.get("email") or "").strip().lower(),
            password_hash=data.get("password_hash"),
            phone=data.get("phone"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            age=data.get("age"),
            gender=data.get("gender"),
            abha_id=data.get("abha_id"),
            abha_token=data.get("abha_token"),
            abha_linked_at=data.get("abha_linked_at"),
            is_active=bool(data.get("is_active", True)),
            is_verified=bool(data.get("is_verified", False)),
            created_at=data.get("created_at") or datetime.utcnow().isoformat(),
            updated_at=data.get("updated_at") or datetime.utcnow().isoformat(),
            mongo_id=_stringify_object_id(data.get("_id")),
        )


def get_user_by_id(user_id: str) -> Optional[User]:
    if not user_id:
        return None
    try:
        object_id = ObjectId(user_id)
    except Exception:
        return None

    doc = get_mongo_database().users.find_one({"_id": object_id})
    if not doc:
        return None
    return User.from_dict(doc)


def get_user_by_email(email: str) -> Optional[User]:
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return None

    doc = get_mongo_database().users.find_one({"email": normalized_email})
    if not doc:
        return None
    return User.from_dict(doc)


def save_user(user: User) -> User:
    database = get_mongo_database()
    user.updated_at = datetime.utcnow().isoformat()
    payload = user.to_dict()
    payload.pop("id", None)

    if user.mongo_id:
        database.users.update_one({"_id": ObjectId(user.mongo_id)}, {"$set": payload}, upsert=False)
    else:
        user.created_at = payload.get("created_at") or datetime.utcnow().isoformat()
        payload["created_at"] = user.created_at
        result = database.users.insert_one(payload)
        user.mongo_id = str(result.inserted_id)

    return user
