"""Storage layer — one state document per user.

Local development: saved to mentoros_data.json next to the code.
Production (Render): set MONGO_URI and the same state lives in MongoDB Atlas,
so it survives redeploys (Render's disk is wiped on every deploy).
"""
import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), "mentoros_data.json")
USER_ID = "default"  # single-user for now; becomes a real user id later

_mongo = None


def _collection():
    """Lazy-connect to Mongo only if MONGO_URI is configured."""
    global _mongo
    if _mongo is None:
        from pymongo import MongoClient  # imported here so local dev doesn't need it
        client = MongoClient(os.environ["MONGO_URI"])
        _mongo = client["mentoros"]["state"]
    return _mongo


def load_state():
    if os.environ.get("MONGO_URI"):
        doc = _collection().find_one({"_id": USER_ID})
        return doc["state"] if doc else _empty_state()
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return _empty_state()


def save_state(state):
    if os.environ.get("MONGO_URI"):
        _collection().replace_one({"_id": USER_ID}, {"_id": USER_ID, "state": state}, upsert=True)
    else:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)


def _empty_state():
    return {
        "plan": None,          # goal, days, hours, phases, curriculum days
        "progress": {},        # day number -> {completed: bool, completed_at: iso}
        "lessons": {},         # day number -> generated lesson content (cache)
        "profile": {           # Learning DNA — grows over time
            "level_notes": "",
            "weak_topics": [],
            "strong_topics": [],
            "preferences": {},
        },
    }
