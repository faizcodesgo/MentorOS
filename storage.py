"""Storage layer — one state document PER USER.

Local development: saved to mentoros_data/<user>.json next to the code.
Production (Render): set MONGO_URI and the same state lives in MongoDB Atlas,
so it survives redeploys (Render's disk is wiped on every deploy).

The user is resolved HERE, from flask.g, rather than threaded through callers.
That's deliberate: load_state()/save_state() keep their original signatures, so
the ~54 call sites in app.py needed no edit — and a missed one can't silently
read the wrong person's data, because _uid() RAISES rather than defaulting.
"""
import datetime
import json
import os
import secrets

DATA_DIR = os.path.join(os.path.dirname(__file__), "mentoros_data")
LEGACY_FILE = os.path.join(os.path.dirname(__file__), "mentoros_data.json")
LEGACY_ID = "default"     # the single doc everyone shared before accounts existed

_mongo = None


def _db():
    global _mongo
    if _mongo is None:
        from pymongo import MongoClient  # imported here so local dev doesn't need it
        # Strip the query string entirely — pasted URIs often carry duplicated or
        # glued-together options (seen in the wild: "w=majorityretryWrites=true").
        # We pass the options we need as arguments instead, and always use our own db.
        base = os.environ["MONGO_URI"].split("?")[0]
        client = MongoClient(base, retryWrites=True, w="majority")
        _mongo = client["mentoros"]
    return _mongo


def _collection():
    return _db()["state"]


def _users():
    return _db()["users"]


def using_mongo():
    return bool(os.environ.get("MONGO_URI"))


def _uid():
    """The current user, or an exception. NEVER a default.

    A fallback here would turn "an endpoint I forgot to gate" into "silently
    reads and writes someone else's plan" — the exact bug accounts exist to fix,
    but invisible. Raising is loud and fixable in five minutes.
    """
    from flask import g
    uid = getattr(g, "user_id", None)
    if not uid:
        raise RuntimeError("storage accessed with no user in context")
    return uid


SCHEMA = 16


def load_state():
    return load_state_for(_uid())


def save_state(state):
    return save_state_for(_uid(), state)


def _file_for(uid):
    return os.path.join(DATA_DIR, f"{uid}.json")


def load_state_for(uid):
    if using_mongo():
        doc = _collection().find_one({"_id": uid})
        state = doc["state"] if doc else _empty_state()
    else:
        path = _file_for(uid)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                state = json.load(f)
        else:
            state = _empty_state()
    return _migrate(state)


def save_state_for(uid, state):
    if using_mongo():
        _collection().replace_one({"_id": uid}, {"_id": uid, "state": state}, upsert=True)
    else:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(_file_for(uid), "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)


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

    # v16: drop STALE cached lessons so they regenerate at the right length.
    #
    # v14 recomputed each day's est_minutes from the chosen hours — but a lesson
    # already generated and cached under the old code is still the old ~45-minute
    # lesson. So the card promised "5h 40m" over content that wasn't. Fixing the
    # label without fixing the content just moved the lie.
    #
    # A cached lesson with no `est_minutes` predates the hours fix. If its day
    # isn't completed yet, the cache is disposable — it regenerates on open, at
    # the correct size. COMPLETED days are history and are never touched.
    # Any saved Q&A is carried across so regenerating can't cost the learner
    # anything they wrote.
    plan = state.get("plan")
    if plan and plan.get("curriculum"):
        progress = state.get("progress") or {}
        lessons = state.get("lessons") or {}
        for entry in plan["curriculum"]:
            day = str(entry.get("day"))
            lesson = lessons.get(day)
            if not lesson or lesson.get("est_minutes"):
                continue                                   # absent, or already new
            if progress.get(day, {}).get("completed"):
                continue                                   # done = history, leave it
            carried = lesson.get("explorations") or []
            if carried:
                entry["carried_explorations"] = carried
            lessons.pop(day, None)

    state["schema"] = SCHEMA
    return state


USERS_FILE = os.path.join(DATA_DIR, "_users.json")


def _load_users():
    if using_mongo():
        return {u["_id"]: u for u in _users().find({})}
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_user(uid):
    if using_mongo():
        return _users().find_one({"_id": uid})
    return _load_users().get(uid)


def create_user(uid, name, pw_hash):
    """Create an account. Returns False if the name is taken.

    `_id` IS the lowercased name, so uniqueness is structural — Mongo enforces
    it, and a duplicate raises rather than quietly creating a second account
    that login would then pick between arbitrarily. No index to forget.

    NOTE: pw_hash lives in the USERS collection, never in state. /api/state
    serialises the whole state dict to the browser (minus lessons), so a hash
    stored there would be handed out on every dashboard load.
    """
    doc = {"_id": uid, "name": name, "pw_hash": pw_hash,
           "created_at": datetime.datetime.now().isoformat()}
    if using_mongo():
        from pymongo.errors import DuplicateKeyError
        try:
            _users().insert_one(doc)
        except DuplicateKeyError:
            return False
        return True
    users = _load_users()
    if uid in users:
        return False
    users[uid] = doc
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)
    return True


def user_count():
    if using_mongo():
        return _users().count_documents({})
    return len(_load_users())


# Whose plan the pre-accounts document is. NOT "whoever signs up first": the app
# is on a public URL, so a stranger (or a bot) creating an account before the
# owner did would have inherited his 50-day plan. Naming the owner removes the
# race entirely — anyone else signing up gets a clean slate, as they should.
LEGACY_OWNER = os.environ.get("LEGACY_OWNER", "faiz").strip().lower()


def legacy_waiting():
    """Is there a pre-accounts plan still waiting for its owner to sign up?

    Used only to put a line on the sign-in screen. Without it the owner opens the
    app after the accounts deploy, sees a signup form and an empty dashboard, and
    concludes his 50 days are gone — which is exactly when people press
    destructive buttons.
    """
    try:
        if get_user(LEGACY_OWNER):
            return False              # already claimed
        if using_mongo():
            doc = _collection().find_one({"_id": LEGACY_ID}, {"state.plan.days": 1})
            return bool(((doc or {}).get("state") or {}).get("plan"))
        if os.path.exists(LEGACY_FILE):
            with open(LEGACY_FILE, encoding="utf-8") as f:
                return bool(json.load(f).get("plan"))
    except Exception:
        pass
    return False


def claim_legacy_state(uid):
    """Give the pre-accounts document to its rightful owner, once.

    Before accounts, everything lived in one doc (`_id: "default"`) that every
    browser shared. That doc is the owner's real 50-day plan. Once _uid() is
    live nothing addresses "default" any more, so without this the plan — and
    its snapshot — are orphaned by the very commit that adds accounts.

    COPY, never move: the legacy documents are left exactly where they are,
    forever. Worst case here is "nothing happened", which is the only
    acceptable worst case for this operation.
    """
    if uid != LEGACY_OWNER:
        return False
    copied = False
    if using_mongo():
        legacy = _collection().find_one({"_id": LEGACY_ID})
        if legacy and legacy.get("state", {}).get("plan"):
            _collection().replace_one({"_id": uid}, {"_id": uid, "state": legacy["state"]}, upsert=True)
            copied = True
        # the snapshot is keyed off the user id too — re-key it in the same
        # breath, or /api/restore silently looks for a document that can't exist
        snap = _collection().find_one({"_id": f"{LEGACY_ID}__backup"})
        if snap:
            new = dict(snap)
            new["_id"] = f"{uid}__backup"
            _collection().replace_one({"_id": new["_id"]}, new, upsert=True)
    else:
        if os.path.exists(LEGACY_FILE):
            with open(LEGACY_FILE, encoding="utf-8") as f:
                state = json.load(f)
            if state.get("plan"):
                save_state_for(uid, state)
                copied = True
    return copied


def snapshot(reason=""):
    """Copy the CURRENT saved state aside before a destructive write.

    There are no backups anywhere else: Mongo saves are whole-document
    replaces and free-tier Atlas has no automated backup, so an unguarded
    overwrite is permanent. Anything that clears a plan calls this first.
    Best-effort by design — a failed snapshot must never block the request.
    """
    try:
        uid = _uid()
        current = load_state_for(uid)
        if not current.get("plan"):
            return None  # nothing worth keeping
        snap = {
            "_id": f"{uid}__backup",
            "state": current,
            "reason": reason,
            "saved_at": datetime.datetime.now().isoformat(),
        }
        if using_mongo():
            _collection().replace_one({"_id": snap["_id"]}, snap, upsert=True)
        else:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(os.path.join(DATA_DIR, f"{uid}__backup.json"), "w", encoding="utf-8") as f:
                json.dump(snap, f, indent=2)
        return snap["saved_at"]
    except Exception:
        return None


def load_snapshot():
    """The last snapshot, or None. Used by the restore endpoint."""
    try:
        uid = _uid()
        if using_mongo():
            return _collection().find_one({"_id": f"{uid}__backup"})
        path = os.path.join(DATA_DIR, f"{uid}__backup.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def secret_key():
    """A signing key that SURVIVES RESTARTS, without a manual env var.

    Render's free tier spins down after ~15 minutes idle. A key generated at
    boot would therefore change constantly and log everyone out several times a
    day — and forgetting to set an env var would silently cause exactly that.
    So: use SECRET_KEY if provided, otherwise generate one ONCE and persist it
    beside the data. Losing it only invalidates cookies; no data is at risk.
    """
    env = os.environ.get("SECRET_KEY", "").strip()
    if env:
        return env
    if using_mongo():
        doc = _db()["config"].find_one({"_id": "secret"})
        if doc and doc.get("key"):
            return doc["key"]
        key = secrets.token_hex(32)
        _db()["config"].replace_one({"_id": "secret"}, {"_id": "secret", "key": key}, upsert=True)
        return key
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "_secret.txt")
    if os.path.exists(path):
        return open(path, encoding="utf-8").read().strip()
    key = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as f:
        f.write(key)
    return key


def notif_user_ids():
    """Users who could actually receive a push — the cron never loads anyone else."""
    if using_mongo():
        return [d["_id"] for d in
                _collection().find({"state.notifications.enabled": True}, {"_id": 1})
                if not str(d["_id"]).endswith("__backup")]
    if not os.path.isdir(DATA_DIR):
        return []
    out = []
    for f in os.listdir(DATA_DIR):
        if not f.endswith(".json") or f.startswith("_") or f.endswith("__backup.json"):
            continue
        uid = f[:-5]
        if (load_state_for(uid).get("notifications") or {}).get("enabled"):
            out.append(uid)
    return out


def save_notifications_for(uid, notif):
    """Surgical $set — the cron must not clobber a write the user just made.

    run_cron only ever touches `subscriptions` and `last_notified`, but it runs
    every few minutes against every user; a whole-document replace here would
    race the user's own session and silently undo their work.
    """
    if using_mongo():
        _collection().update_one({"_id": uid}, {"$set": {"state.notifications": notif}})
    else:
        s = load_state_for(uid)
        s["notifications"] = notif
        save_state_for(uid, s)


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
