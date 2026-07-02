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
        # Strip the query string entirely — pasted URIs often carry duplicated or
        # glued-together options (seen in the wild: "w=majorityretryWrites=true").
        # We pass the options we need as arguments instead, and always use our own db.
        base = os.environ["MONGO_URI"].split("?")[0]
        client = MongoClient(base, retryWrites=True, w="majority")
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
        "xp": 0,               # current Main Quest XP — resets when a new goal starts
        "lifetime_xp": 0,      # career total — quest XP rolls in here, never resets
        "profile": {           # Learning DNA — grows over time
            "level_notes": "",
            "class": "",       # scholar | builder | consistent | challenger
            "weak_topics": [],
            "strong_topics": [],
            "preferences": {},
        },
    }
