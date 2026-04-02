import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
import threading


# Lightweight in-memory collection fallback when MongoDB is not available.
class _InMemoryQuery:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, key, direction):
        reverse = bool(direction == -1)
        try:
            self._docs.sort(key=lambda d: d.get(key), reverse=reverse)
        except Exception:
            pass
        return self

    def __iter__(self):
        return iter(self._docs)


class _InMemoryCollection:
    def __init__(self):
        self._docs = []
        self._lock = threading.Lock()

    def create_index(self, *args, **kwargs):
        return None

    def find(self):
        return _InMemoryQuery(self._docs)

    def find_one(self, filt):
        if not filt:
            return None
        # support lookup by _id or policy_number
        if "_id" in filt:
            target = filt["_id"]
            for d in self._docs:
                if d.get("_id") == target:
                    return d
        if "policy_number" in filt:
            for d in self._docs:
                if d.get("policy_number") == filt["policy_number"]:
                    return d
        return None

    def insert_one(self, document):
        with self._lock:
            doc = dict(document)
            if "_id" not in doc:
                doc["_id"] = ObjectId()
            # enforce unique policy_number if provided
            pn = doc.get("policy_number")
            if pn:
                for d in self._docs:
                    if d.get("policy_number") == pn:
                        raise DuplicateKeyError("duplicate key error")
            self._docs.append(doc)
            class _Res: pass
            res = _Res()
            res.inserted_id = doc["_id"]
            return res

    def update_one(self, filt, update):
        with self._lock:
            target = None
            if "_id" in filt:
                tid = filt["_id"]
                for d in self._docs:
                    if d.get("_id") == tid:
                        target = d
                        break
            if not target:
                class _Res: pass
                r = _Res()
                r.modified_count = 0
                return r
            # apply $set
            sets = update.get("$set", {})
            for k, v in sets.items():
                target[k] = v
            class _Res: pass
            r = _Res()
            r.modified_count = 1
            return r

    def delete_one(self, filt):
        with self._lock:
            target = None
            if "_id" in filt:
                tid = filt["_id"]
                for i, d in enumerate(self._docs):
                    if d.get("_id") == tid:
                        target = i
                        break
            if target is None:
                class _Res: pass
                r = _Res()
                r.deleted_count = 0
                return r
            self._docs.pop(target)
            class _Res: pass
            r = _Res()
            r.deleted_count = 1
            return r


MONGO_URI = os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGODB_DB", "secure_gig_guardian")
MONGO_COLLECTION = os.getenv("MONGODB_COLLECTION", "insurance_policies")

client = None
collection = None

# Only attempt to initialize MongoDB if a URI is explicitly provided.
if MONGO_URI:
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGO_DB]
        collection = db[MONGO_COLLECTION]
        collection.create_index("policy_number", unique=True, sparse=True)
    except PyMongoError as exc:
        print(f"MongoDB initialization error: {exc}")
        client = None
        collection = _InMemoryCollection()
        print("Using in-memory policy store as fallback.")
else:
    print("MONGODB_URI not set; using in-memory policy store.")
    collection = _InMemoryCollection()


def _serialize_policy(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return {}

    return {
        "id": str(doc.get("_id")),
        "worker_name": doc.get("worker_name", ""),
        "policy_number": doc.get("policy_number", ""),
        "coverage_type": doc.get("coverage_type", ""),
        "weekly_premium": float(doc.get("weekly_premium", 0)),
        "active": bool(doc.get("active", True)),
        "notes": doc.get("notes", ""),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
    }


def _require_collection() -> Any:
    if collection is None:
        raise RuntimeError("MongoDB collection is not initialized. Check MONGODB_URI and connection settings.")
    return collection


def list_policies() -> List[Dict[str, Any]]:
    coll = _require_collection()
    return [_serialize_policy(doc) for doc in coll.find().sort("created_at", -1)]


def get_policy(policy_id: str) -> Optional[Dict[str, Any]]:
    coll = _require_collection()
    try:
        document = coll.find_one({"_id": ObjectId(policy_id)})
    except Exception as exc:
        raise ValueError(f"Invalid policy id: {policy_id}") from exc
    return _serialize_policy(document) if document else None


def create_policy(payload: Dict[str, Any]) -> Dict[str, Any]:
    coll = _require_collection()
    document = {
        "worker_name": str(payload.get("worker_name", "")).strip(),
        "policy_number": str(payload.get("policy_number", "")).strip(),
        "coverage_type": str(payload.get("coverage_type", "Basic Coverage")).strip(),
        "weekly_premium": float(payload.get("weekly_premium", 0)),
        "active": bool(payload.get("active", True)),
        "notes": str(payload.get("notes", "")).strip(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    try:
        result = coll.insert_one(document)
        return get_policy(str(result.inserted_id))
    except DuplicateKeyError as exc:
        raise ValueError("A policy with this policy number already exists.") from exc
    except PyMongoError as exc:
        raise RuntimeError(f"Failed to create policy: {exc}") from exc


def update_policy(policy_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    coll = _require_collection()
    update_fields = {}

    if "worker_name" in payload:
        update_fields["worker_name"] = str(payload["worker_name"]).strip()
    if "policy_number" in payload:
        update_fields["policy_number"] = str(payload["policy_number"]).strip()
    if "coverage_type" in payload:
        update_fields["coverage_type"] = str(payload["coverage_type"]).strip()
    if "weekly_premium" in payload:
        update_fields["weekly_premium"] = float(payload["weekly_premium"])
    if "active" in payload:
        update_fields["active"] = bool(payload["active"])
    if "notes" in payload:
        update_fields["notes"] = str(payload["notes"]).strip()

    if not update_fields:
        return get_policy(policy_id)

    update_fields["updated_at"] = datetime.utcnow()

    try:
        coll.update_one({"_id": ObjectId(policy_id)}, {"$set": update_fields})
        return get_policy(policy_id)
    except Exception as exc:
        raise ValueError(f"Invalid policy id: {policy_id}") from exc


def delete_policy(policy_id: str) -> bool:
    coll = _require_collection()
    try:
        result = coll.delete_one({"_id": ObjectId(policy_id)})
    except Exception as exc:
        raise ValueError(f"Invalid policy id: {policy_id}") from exc
    return result.deleted_count > 0
