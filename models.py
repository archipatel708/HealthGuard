"""MongoDB-backed data models with a SQLAlchemy-like API surface."""
from datetime import datetime, timedelta
import secrets

from flask import current_app
from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError


class IntegrityError(Exception):
    """Compatibility error type for unique constraint violations."""


class _OrderField:
    def __init__(self, name):
        self.name = name

    def desc(self):
        return _SortSpec(self.name, -1)

    def asc(self):
        return _SortSpec(self.name, 1)


class _SortSpec:
    def __init__(self, field, direction):
        self.field = field
        self.direction = direction


class _PaginationResult:
    def __init__(self, items, total, page, per_page):
        self.items = items
        self.total = total
        self.pages = (total + per_page - 1) // per_page if per_page else 0
        self.page = page
        self.per_page = per_page


class _Query:
    def __init__(self, model_cls, filters=None, sort=None):
        self.model_cls = model_cls
        self.filters = filters or {}
        self.sort = sort

    def filter_by(self, **kwargs):
        merged = dict(self.filters)
        merged.update(kwargs)
        return _Query(self.model_cls, filters=merged, sort=self.sort)

    def order_by(self, sort_spec):
        if isinstance(sort_spec, _SortSpec):
            return _Query(self.model_cls, filters=self.filters, sort=sort_spec)
        return self

    def first(self):
        cursor = self.model_cls._collection().find(self.filters)
        if self.sort:
            direction = DESCENDING if self.sort.direction < 0 else ASCENDING
            cursor = cursor.sort(self.sort.field, direction)
        doc = next(cursor.limit(1), None)
        return self.model_cls.from_doc(doc) if doc else None

    def all(self):
        cursor = self.model_cls._collection().find(self.filters)
        if self.sort:
            direction = DESCENDING if self.sort.direction < 0 else ASCENDING
            cursor = cursor.sort(self.sort.field, direction)
        return [self.model_cls.from_doc(doc) for doc in cursor]

    def delete(self):
        result = self.model_cls._collection().delete_many(self.filters)
        return result.deleted_count

    def paginate(self, page=1, per_page=10):
        page = max(1, int(page))
        per_page = max(1, int(per_page))
        skip = (page - 1) * per_page
        cursor = self.model_cls._collection().find(self.filters)
        if self.sort:
            direction = DESCENDING if self.sort.direction < 0 else ASCENDING
            cursor = cursor.sort(self.sort.field, direction)
        items = [self.model_cls.from_doc(doc) for doc in cursor.skip(skip).limit(per_page)]
        total = self.model_cls._collection().count_documents(self.filters)
        return _PaginationResult(items=items, total=total, page=page, per_page=per_page)

    def get(self, pk):
        try:
            pk = int(pk)
        except (TypeError, ValueError):
            return None
        doc = self.model_cls._collection().find_one({"id": pk})
        return self.model_cls.from_doc(doc) if doc else None


class _QueryProxy:
    def __get__(self, instance, owner):
        return _Query(owner)


class _Session:
    def add(self, obj):
        obj.save()

    def commit(self):
        return None

    def rollback(self):
        return None


class MongoDB:
    def __init__(self):
        self.client = None
        self.database = None
        self.session = _Session()

    def init_app(self, app):
        uri = app.config.get("MONGODB_URI", "mongodb://localhost:27017")
        db_name = app.config.get("MONGODB_DB", "disease_prediction")
        self.client = MongoClient(uri)
        self.database = self.client[db_name]

    def create_all(self):
        if self.database is None:
            return
        self.database.users.create_index("email", unique=True)

        # Migrate legacy indexes that incorrectly enforce uniqueness on null values.
        user_indexes = self.database.users.index_information()
        for legacy_name in ("phone_1", "abha_id_1"):
            if legacy_name in user_indexes:
                try:
                    self.database.users.drop_index(legacy_name)
                except Exception:
                    pass

        # Enforce uniqueness only when fields are non-empty strings.
        self.database.users.create_index(
            "phone",
            unique=True,
            name="phone_unique_non_null",
            partialFilterExpression={"phone": {"$type": "string", "$ne": ""}},
        )
        self.database.users.create_index(
            "abha_id",
            unique=True,
            name="abha_id_unique_non_null",
            partialFilterExpression={"abha_id": {"$type": "string", "$ne": ""}},
        )
        self.database.otps.create_index([("email", ASCENDING), ("created_at", DESCENDING)])
        self.database.prediction_history.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        self.database.health_records.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        self.database.abha_tokens.create_index("user_id", unique=True)

    def _next_id(self, sequence_name):
        counters = self.database.counters
        result = counters.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(result["seq"])


db = MongoDB()


class MongoModel:
    collection_name = None
    query = _QueryProxy()

    def __init__(self, **kwargs):
        self._persisted = False
        for key, value in kwargs.items():
            object.__setattr__(self, key, value)

    @classmethod
    def _collection(cls):
        return db.database[cls.collection_name]

    @classmethod
    def from_doc(cls, doc):
        if not doc:
            return None
        payload = {k: v for k, v in doc.items() if k != "_id"}
        obj = cls(**payload)
        object.__setattr__(obj, "_persisted", True)
        return obj

    def _serialize(self):
        payload = {
            k: v
            for k, v in self.__dict__.items()
            if not k.startswith("_")
        }
        return payload

    def save(self):
        now = datetime.utcnow()
        payload = self._serialize()
        if payload.get("id") is None:
            payload["id"] = db._next_id(self.collection_name)
            if payload.get("created_at") is None:
                payload["created_at"] = now
        payload["updated_at"] = now

        try:
            self._collection().replace_one({"id": payload["id"]}, payload, upsert=True)
        except DuplicateKeyError as exc:
            raise IntegrityError(str(exc)) from exc

        for key, value in payload.items():
            object.__setattr__(self, key, value)
        object.__setattr__(self, "_persisted", True)
        return self

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        if name.startswith("_"):
            return
        if getattr(self, "_persisted", False):
            self.save()


class User(MongoModel):
    """User model for storing user account information."""

    collection_name = "users"

    def __init__(self, **kwargs):
        defaults = {
            "is_active": True,
            "is_verified": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def __repr__(self):
        return f"<User {getattr(self, 'email', None)}>"

    def to_dict(self):
        return {
            "id": self.id,
            "email": getattr(self, "email", None),
            "phone": getattr(self, "phone", None),
            "first_name": getattr(self, "first_name", None),
            "last_name": getattr(self, "last_name", None),
            "age": getattr(self, "age", None),
            "gender": getattr(self, "gender", None),
            "abha_id": getattr(self, "abha_id", None),
            "is_verified": getattr(self, "is_verified", False),
            "created_at": self.created_at.isoformat() if getattr(self, "created_at", None) else None,
        }


class OTP(MongoModel):
    """OTP model for email-based authentication."""

    collection_name = "otps"
    created_at = _OrderField("created_at")

    def __init__(self, **kwargs):
        defaults = {
            "is_used": False,
            "attempts": 0,
            "created_at": datetime.utcnow(),
            "verified_at": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def __repr__(self):
        return f"<OTP {getattr(self, 'email', None)}>"

    def is_valid(self):
        return (
            not getattr(self, "is_used", False)
            and getattr(self, "attempts", 0) < 3
            and datetime.utcnow() < getattr(self, "expires_at", datetime.utcnow())
        )

    def is_expired(self):
        expires_at = getattr(self, "expires_at", None)
        return datetime.utcnow() > expires_at if expires_at else True

    @staticmethod
    def create_otp(email, validity_minutes=5):
        otp_code = "".join(secrets.choice("0123456789") for _ in range(6))
        expires_at = datetime.utcnow() + timedelta(minutes=validity_minutes)
        return OTP(email=email, otp_code=otp_code, expires_at=expires_at)


class PredictionHistory(MongoModel):
    """Store user's prediction history."""

    collection_name = "prediction_history"
    created_at = _OrderField("created_at")

    def __init__(self, **kwargs):
        defaults = {
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def __repr__(self):
        return f"<PredictionHistory {getattr(self, 'id', None)} - {getattr(self, 'predicted_disease', None)}>"

    def to_dict(self):
        return {
            "id": self.id,
            "symptoms": getattr(self, "symptoms", []),
            "predicted_disease": getattr(self, "predicted_disease", None),
            "confidence_score": getattr(self, "confidence_score", None),
            "top3_predictions": getattr(self, "top3_predictions", []),
            "notes": getattr(self, "notes", None),
            "severity_level": getattr(self, "severity_level", None),
            "created_at": self.created_at.isoformat() if getattr(self, "created_at", None) else None,
        }


class HealthRecord(MongoModel):
    """Store detailed health records linked to predictions."""

    collection_name = "health_records"
    created_at = _OrderField("created_at")

    def __init__(self, **kwargs):
        defaults = {
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def __repr__(self):
        return f"<HealthRecord {getattr(self, 'id', None)}>"

    def to_dict(self):
        return {
            "id": self.id,
            "blood_pressure": getattr(self, "blood_pressure", None),
            "heart_rate": getattr(self, "heart_rate", None),
            "temperature": getattr(self, "temperature", None),
            "oxygen_saturation": getattr(self, "oxygen_saturation", None),
            "blood_sugar": getattr(self, "blood_sugar", None),
            "allergies": getattr(self, "allergies", None),
            "medications": getattr(self, "medications", None),
            "past_illnesses": getattr(self, "past_illnesses", None),
            "created_at": self.created_at.isoformat() if getattr(self, "created_at", None) else None,
        }


class ABHAToken(MongoModel):
    """Store ABHA authentication tokens and session info."""

    collection_name = "abha_tokens"

    def __init__(self, **kwargs):
        defaults = {
            "token_type": "Bearer",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def is_expired(self):
        expires_at = getattr(self, "expires_at", None)
        return datetime.utcnow() > expires_at if expires_at else False

    def __repr__(self):
        return f"<ABHAToken {getattr(self, 'user_id', None)}>"
