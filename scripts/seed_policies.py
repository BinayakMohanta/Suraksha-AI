#!/usr/bin/env python3
"""Seed sample insurance policies into the configured MongoDB.

Usage:
  MONGODB_URI="mongodb+srv://user:pass@host" python scripts/seed_policies.py

The script reads MONGODB_URI, MONGODB_DB (default secure_gig_guardian), and
MONGODB_COLLECTION (default insurance_policies) from the environment.
"""
import os
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError


def main():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB", "secure_gig_guardian")
    coll_name = os.getenv("MONGODB_COLLECTION", "insurance_policies")

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[db_name]
    coll = db[coll_name]
    coll.create_index("policy_number", unique=True, sparse=True)

    samples = [
        {
            "worker_name": "Alice",
            "policy_number": "POL-001",
            "coverage_type": "Basic Coverage",
            "weekly_premium": 12.5,
            "active": True,
            "notes": "Seeded policy for Alice",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "worker_name": "Bob",
            "policy_number": "POL-002",
            "coverage_type": "Premium Coverage",
            "weekly_premium": 25.0,
            "active": True,
            "notes": "Seeded policy for Bob",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "worker_name": "Carol",
            "policy_number": "POL-003",
            "coverage_type": "Basic Coverage",
            "weekly_premium": 15.0,
            "active": False,
            "notes": "Seeded inactive policy",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
    ]

    inserted = []
    for doc in samples:
        try:
            res = coll.insert_one(doc)
            inserted.append(str(res.inserted_id))
            print(f"Inserted policy {doc['policy_number']} -> id {res.inserted_id}")
        except DuplicateKeyError:
            existing = coll.find_one({"policy_number": doc["policy_number"]})
            print(f"Policy {doc['policy_number']} already exists as id {existing.get('_id')}")

    print(f"Done. Inserted {len(inserted)} new policies.")


if __name__ == "__main__":
    main()
