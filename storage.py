"""Storage layer — one state document per user.

Local development: saved to mentoros_data.json next to the code.
Production (Render): set MONGO_URI and the same state lives in MongoDB Atlas,
so it survives redeploys (Render's disk is wiped on every deploy).
"""
import datetime
import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), "mentoros_data.json")
BACKUP_FILE = os.path.join(os.path.dirname(__file__), "mentoros_data.backup.json")
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


SCHEMA = 15


def load_state():
    if os.environ.get("MONGO_URI"):
        doc = _collection().find_one({"_id": USER_ID})
        state = doc["state"] if doc else _empty_state()
    elif os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            state = json.load(f)
    else:
        state = _empty_state()
    return _migrate(state)


def _migrate(state):
    """Bring an older saved state up to the current schema. Idempotent."""
    if state.get("schema", 1) >= SCHEMA:
        return state

    # self-heal the core containers for very old docs so later code that reads
    # state["profile"] / progress / lessons directly can't KeyError on upgrade
    state.setdefault("progress", {})
    state.setdefault("lessons", {})
    state.setdefault("quizzes", {})
    state.setdefault("xp", 0)
    state.setdefault("profile", {"level_notes": "", "name": "", "class": "",
                                 "weak_topics": [], "strong_topics": [], "preferences": {}})

    # v3: give each curriculum entry a stable display `order` and add the
    # id counter + streak fields. `day` was already a stable unique key, so
    # lessons/progress/quizzes dicts keyed by it need no rewrite.
    plan = state.get("plan")
    if plan and plan.get("curriculum"):
        max_day = 0
        for i, entry in enumerate(plan["curriculum"]):
            entry.setdefault("order", entry.get("day", i + 1))
            entry.setdefault("kind", "checkpoint" if entry.get("is_checkpoint") else "quest")
            max_day = max(max_day, entry.get("day", i + 1))
        plan.setdefault("next_day", max_day + 1)
    state.setdefault("streak", {"count": 0, "shields": 0, "last_day": None})
    state.setdefault("repaced_at", None)

    # v4: spaced-review queue for morning warm-ups
    state.setdefault("reviews", {"queue": [], "done_upto": 0})

    # v5: learner-chosen bookmarks
    state.setdefault("bookmarks", [])

    # v6: the mentor gets to know you — the learner's name
    if "profile" in state:
        state["profile"].setdefault("name", "")

    # v7: remember every question asked so none is ever repeated
    state.setdefault("asked_questions", [])

    # (v8's study_anchor and v6's today_goal were removed in the audit —
    # old docs may still carry the fields; they're simply ignored)

    # v9: weekly progress report snapshot
    state.setdefault("weekly", {"last_shown": 0, "snap_xp": 0, "snap_mastered": []})

    # v10: learner-uploaded study material the mentor teaches from
    state.setdefault("material", {"text": "", "scope": "", "name": ""})

    # v11: build-it milestone projects
    if state.get("plan"):
        state["plan"].setdefault("projects", {})

    # v12: push notifications (opt-in, one gentle daily digest)
    state.setdefault("notifications", {
        "enabled": False,
        "daily_time": "19:00",
        "quiet_hours": {"start": "22:00", "end": "08:00"},
        "subscriptions": [],
        "last_notified": {},
    })

    # v13: honest streak + XP once-guards.
    # `best` is the permanent record of the longest run — it never resets, which
    # is what makes breaking the current run survivable rather than a reason to
    # quit. Seed it from the existing count so nobody's history is erased by the
    # upgrade. `awarded` backs the once-per-day guards on warm-up/explain/focus.
    st = state.setdefault("streak", {"count": 0, "shields": 0, "last_day": None})
    st.setdefault("best", st.get("count", 0))
    state.setdefault("awarded", {})
    state.setdefault("warmup_pending", None)

    # v14: backfill est_minutes on plans built before the hours fix.
    # Those entries carry a model-authored number invented next to a lesson that
    # was hardcoded to 3-6 sections regardless of hours — i.e. fiction. Lessons
    # generated from now on are sized properly, so recompute the plan's estimate
    # from the hours the student actually chose. Import is local: prompts imports
    # nothing from storage, but keeping it here avoids a module-level cycle if
    # that ever changes.
    plan = state.get("plan")
    if plan and plan.get("curriculum"):
        import prompts
        for entry in plan["curriculum"]:
            shape = prompts.structure_for_hours(plan.get("hours_per_day", 1),
                                                bool(entry.get("is_checkpoint")))
            entry["est_minutes"] = shape["est"]

    # v15: every plan gets a short_title for the dashboard line.
    # A tidy goal IS its own title. A pasted syllabus is NOT, and no string
    # operation can make it one — the owner's real goal opens with the subjects
    # he asked to SKIP, so a prefix would label his plan with the opposite of
    # what it teaches. Deriving one needs an AI call we won't spend on a
    # migration, so leave it blank: the UI falls back to "Your plan" and lets him
    # name it himself. A generic correct label beats a specific wrong one.
    plan = state.get("plan")
    if plan is not None and not plan.get("short_title"):
        goal = (plan.get("goal") or "").strip()
        plan["short_title"] = goal if 0 < len(goal) <= 40 else ""
    if plan is not None:
        plan.setdefault("achievable_scope", [])
        plan.setdefault("dropped_scope", [])

    state["schema"] = SCHEMA
    return state


def save_state(state):
    if os.environ.get("MONGO_URI"):
        _collection().replace_one({"_id": USER_ID}, {"_id": USER_ID, "state": state}, upsert=True)
    else:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)


def snapshot(reason=""):
    """Copy the CURRENT saved state aside before a destructive write.

    There are no backups anywhere else: Mongo saves are whole-document
    replaces and free-tier Atlas has no automated backup, so an unguarded
    overwrite is permanent. Anything that clears a plan calls this first.
    Best-effort by design — a failed snapshot must never block the request.
    """
    try:
        current = load_state()
        if not current.get("plan"):
            return None  # nothing worth keeping
        snap = {
            "_id": f"{USER_ID}__backup",
            "state": current,
            "reason": reason,
            "saved_at": datetime.datetime.now().isoformat(),
        }
        if os.environ.get("MONGO_URI"):
            _collection().replace_one({"_id": snap["_id"]}, snap, upsert=True)
        else:
            with open(BACKUP_FILE, "w", encoding="utf-8") as f:
                json.dump(snap, f, indent=2)
        return snap["saved_at"]
    except Exception:
        return None


def load_snapshot():
    """The last snapshot, or None. Used by the restore endpoint."""
    try:
        if os.environ.get("MONGO_URI"):
            return _collection().find_one({"_id": f"{USER_ID}__backup"})
        if os.path.exists(BACKUP_FILE):
            with open(BACKUP_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _empty_state():
    return {
        "schema": SCHEMA,
        "plan": None,          # goal, days, hours, phases, curriculum days, next_day
        "progress": {},        # day-id -> {completed: bool, completed_at: iso}
        "lessons": {},         # day-id -> generated lesson content (cache)
        "xp": 0,               # current Main Quest XP — resets when a new goal starts
        "lifetime_xp": 0,      # career total — quest XP rolls in here, never resets
        "quizzes": {},         # day-id -> checkpoint result (score, answers, xp_earned)
        "dna": None,           # Learning DNA — computed from quiz data on each submit
        "notes_seen": True,    # False when DNA updated since the user last viewed Skills
        "streak": {"count": 0, "shields": 0, "last_day": None, "best": 0},  # honest streak: breaks, but `best` never does
        "repaced_at": None,    # date the plan was last re-paced (avoid repeat nudges)
        "reviews": {"queue": [], "done_upto": 0},  # spaced-review ladder for warm-ups
        "bookmarks": [],       # learner-flagged lesson sections [{day, sectionIndex, heading}]
        "asked_questions": [],  # every question text asked, so none repeats
        "weekly": {"last_shown": 0, "snap_xp": 0, "snap_mastered": []},  # weekly report snapshot
        "material": {"text": "", "scope": "", "name": ""},  # uploaded syllabus/textbook
        "awarded": {},         # once-per-day XP guards (warm-up / explain / focus)
        "warmup_pending": None,  # questions we served, so the SERVER grades them
        "notifications": {"enabled": False, "daily_time": "19:00", "tz_offset": 0,
                          "quiet_hours": {"start": "22:00", "end": "08:00"},
                          "subscriptions": [], "last_notified": {}},
        "profile": {           # Learning DNA — grows over time
            "level_notes": "",
            "name": "",        # the learner's first name (used sparingly, for familiarity)
            "class": "",       # scholar | builder | consistent | challenger | allrounder
            "weak_topics": [],
            "strong_topics": [],
            "preferences": {},
        },
    }
