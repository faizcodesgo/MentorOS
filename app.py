"""MentorOS — AI mentor that plans, teaches, and tracks a learning goal.

Phase 1: goal negotiation -> day-by-day curriculum -> daily lessons -> progress.
Run locally:  python app.py   (then open http://localhost:5000)
"""
import datetime
import os

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

import dna as dna_engine
import gemini
import prompts
import push as push_engine
import reviews as review_engine
import storage
import youtube

# Load .env if present (tiny parser — avoids an extra dependency)
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

app = Flask(__name__, static_folder="public", static_url_path="")
# reject oversized uploads early with a 413 instead of reading them into memory
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
try:
    app.secret_key = storage.secret_key()
except Exception:
    # Never let a slow/unreachable DB at boot take the whole app down. A random
    # key only means "everyone signs in again"; a failed import means a total
    # outage. Degrade, don't die.
    import secrets as _secrets
    app.secret_key = _secrets.token_hex(32)
    app.logger.warning("SECRET_KEY unavailable at boot — using a temporary key; sessions won't persist.")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,   # unreachable from JS, so an XSS in model output can't steal it
    SESSION_COOKIE_SAMESITE="Lax",  # no cross-site context exists; Lax also blocks CSRF on POSTs
    SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")),   # off on localhost http
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=365),
)

# Routes that must work with NO user: static, health, the TWA asset links, the
# auth handshake itself, and the cron (an external pinger sends no cookie).
OPEN_PATHS = {
    "/api/auth/signup", "/api/auth/login", "/api/auth/logout", "/api/auth/me",
    "/api/cron/push", "/api/vapid-public-key",
}


@app.before_request
def _resolve_user():
    """Resolve the signed-in user for every API request, or 401.

    This gate is the riskiest line in the accounts change. A route missing from
    OPEN_PATHS fails LOUDLY (401 / RuntimeError from storage._uid) — annoying,
    obvious, fixed in minutes. A gate that DEFAULTED instead would silently mix
    two students' plans together, which is the bug accounts exist to remove.
    """
    p = request.path
    if not p.startswith("/api/") or p in OPEN_PATHS:
        return None
    uid = session.get("uid")
    if not uid:
        return jsonify({"error": "Sign in to continue.", "auth_required": True}), 401
    g.user_id = uid
    return None


def _norm_name(name):
    return (name or "").strip().lower()[:40]


@app.get("/api/auth/me")
def auth_me():
    uid = session.get("uid")
    if not uid or not storage.get_user(uid):
        if uid:
            session.clear()           # account gone from under a live cookie
        return jsonify({
            "signed_in": False,
            "any_accounts": storage.user_count() > 0,
            # An in-progress plan predating accounts, still unclaimed. Say so on
            # the sign-in screen: otherwise the owner opens the app, sees a
            # signup form and no plan, and reasonably concludes it's all gone.
            "legacy_waiting": storage.legacy_waiting(),
        })
    return jsonify({"signed_in": True, "name": storage.get_user(uid).get("name", uid)})


@app.post("/api/auth/signup")
def auth_signup():
    body = request.get_json(force=True)
    name = (body.get("name") or "").strip()[:40]
    pw = body.get("password") or ""
    uid = _norm_name(name)
    if not uid:
        return jsonify({"error": "Pick a name."}), 400
    if len(pw) < 8:
        return jsonify({"error": "Use at least 8 characters for the password."}), 400
    # scrypt (werkzeug default). No new dependency, and no home-rolled hashing.
    if not storage.create_user(uid, name, generate_password_hash(pw)):
        return jsonify({"error": "That name is taken. Try another."}), 409
    session.clear()                   # no session fixation
    session["uid"] = uid
    session.permanent = True          # else the cookie dies when the TWA is swiped away
    # The first account inherits the pre-accounts plan. COPY, never move.
    claimed = storage.claim_legacy_state(uid)
    return jsonify({"ok": True, "name": name, "claimed_existing_plan": claimed})


@app.post("/api/auth/login")
def auth_login():
    body = request.get_json(force=True)
    uid = _norm_name(body.get("name"))
    pw = body.get("password") or ""
    user = storage.get_user(uid) if uid else None
    # one message for both cases — don't reveal which names exist
    if not user or not check_password_hash(user.get("pw_hash", ""), pw):
        return jsonify({"error": "Wrong name or password."}), 401
    session.clear()
    session["uid"] = uid
    session.permanent = True
    return jsonify({"ok": True, "name": user.get("name", uid)})


@app.post("/api/auth/logout")
def auth_logout():
    session.clear()
    return jsonify({"ok": True})


@app.errorhandler(Exception)
def handle_error(e):
    """API calls always get JSON back. Real errors are logged server-side, not
    leaked to the client (they can contain URIs/paths/upstream detail)."""
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return jsonify({"error": e.description}), e.code
    app.logger.exception("Unhandled error")
    return jsonify({"error": "Something went wrong. Please try again."}), 500


@app.get("/")
def index():
    return send_from_directory("public", "index.html")


@app.get("/healthz")
def healthz():
    """Tiny no-op for an uptime pinger. Keeps the free Render instance warm so
    the installed Android app doesn't open to a 30-60s cold-start spinner.
    Loads no state — cheap to hit every ~10 minutes."""
    return jsonify({"ok": True})


@app.get("/.well-known/assetlinks.json")
def assetlinks():
    """Digital Asset Links — lets the installed TWA open MentorOS full-screen
    (no browser URL bar). The upload-key fingerprint from PWABuilder is baked in
    so no Render config is needed. When Play App Signing is turned on later, add
    Google's re-signing SHA-256 to the ANDROID_CERT_SHA256 env (comma-separated)
    and it gets appended here too."""
    package = os.environ.get("ANDROID_PACKAGE_NAME", "com.onrender.mentoros_c4ht.twa").strip()
    fingerprints = ["E9:EF:79:F5:A8:29:58:D9:5B:FE:33:C6:5B:21:28:14:FE:ED:4A:DD:13:EC:53:CE:BF:BD:E7:4E:BF:D8:BC:DC"]
    extra = os.environ.get("ANDROID_CERT_SHA256", "").strip()
    fingerprints += [s.strip() for s in extra.split(",") if s.strip()]
    return jsonify([{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {"namespace": "android_app", "package_name": package,
                   "sha256_cert_fingerprints": fingerprints},
    }])


@app.get("/privacy")
def privacy():
    return send_from_directory("public", "privacy.html")


@app.get("/api/state")
def get_state():
    state = storage.load_state()
    # lessons can get big — the dashboard doesn't need them
    slim = {k: v for k, v in state.items() if k != "lessons"}
    # don't ship raw push subscriptions or material text to the client
    if slim.get("notifications"):
        n = dict(slim["notifications"])
        n["subscriptions_count"] = len(n.get("subscriptions", []))
        n.pop("subscriptions", None)
        slim["notifications"] = n
    return jsonify(slim)


MATERIAL_CAP = 15000  # chars — keep prompts within token limits
# Goals are allowed to be long: pasting a whole syllabus WORKS and produces a
# good plan (the owner's real goal is ~1,500 chars and did exactly that). This
# only stops an unbounded paste — past ~2k the model starts silently ignoring
# the middle, which is worse than refusing.
MAX_GOAL = 2000


@app.post("/api/material")
def upload_material():
    """Accept a pasted text OR an uploaded .txt/.md/.pdf; extract, cap, store."""
    state = storage.load_state()
    text, name = "", ""

    if request.files.get("file"):
        f = request.files["file"]
        name = f.filename or "material"
        if name.lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
                reader = PdfReader(f.stream)
                text = "\n".join((p.extract_text() or "") for p in reader.pages)
            except Exception as e:
                return jsonify({"error": f"Couldn't read that PDF ({e}). Try pasting the text instead."}), 400
        else:
            text = f.stream.read().decode("utf-8", errors="ignore")
    else:
        body = request.get_json(silent=True) or {}
        text = body.get("text", "")
        name = body.get("name", "pasted notes")

    text = " ".join(text.split())          # normalise whitespace
    if len(text) > MATERIAL_CAP:
        text = text[:MATERIAL_CAP]
    if not text.strip():
        return jsonify({"error": "No readable text found."}), 400

    state["material"] = {"text": text, "scope": "", "name": name[:80]}
    storage.save_state(state)
    return jsonify({"ok": True, "chars": len(text), "name": name[:80]})


@app.post("/api/negotiate")
def negotiate():
    body = request.get_json(force=True)
    goal = body.get("goal", "").strip()[:MAX_GOAL]
    days = int(body.get("days", 0))
    hours = float(body.get("hours_per_day", 0))
    level = body.get("level_notes", "").strip()
    if not goal or days < 1 or hours <= 0:
        return jsonify({"error": "Please fill in the goal, days, and hours per day."}), 400

    state = storage.load_state()
    material = state.get("material") or {}
    if material.get("text") and body.get("material_scope"):
        material = {**material, "scope": body["material_scope"]}
    result = gemini.ask_json(
        prompts.MENTOR_PERSONA,
        prompts.negotiate_prompt(goal, days, hours, level, material=material),
    )
    # shape guard: the negotiate screen breaks on a list/empty response — reject
    # so the user gets a retry instead of a half-rendered dead end
    if not isinstance(result, dict) or not isinstance(result.get("phases"), list) or not result["phases"]:
        return jsonify({"error": "Couldn't assess that goal — try adjusting it."}), 502
    return jsonify(result)


@app.post("/api/plan/init")
def plan_init():
    """Create the plan shell after the student accepts the negotiated outline."""
    body = request.get_json(force=True)
    state = storage.load_state()

    # This endpoint CLEARS progress/lessons/quizzes/dna/streak below, and saves
    # with a whole-document replace. Unguarded, a stray re-POST (double submit,
    # stale tab, back button into onboarding) permanently destroys an in-progress
    # plan — there is no other backup. Refuse unless the caller says "replace",
    # and snapshot first either way.
    if state.get("plan") and not body.get("replace"):
        done = sum(1 for p in state.get("progress", {}).values() if p.get("completed"))
        return jsonify({
            "error": "plan_exists",
            "goal": state["plan"].get("goal", ""),
            "days_done": done,
            "message": "You already have a plan in progress. Starting a new one erases it.",
        }), 409
    if state.get("plan"):
        storage.snapshot("plan_init")

    # Season model: XP earned on the previous Main Quest rolls into the career total
    state["lifetime_xp"] = state.get("lifetime_xp", 0) + state.get("xp", 0)
    state["xp"] = 0
    phases = body["phases"]
    # Trust the phase breakdown for the day count, not the raw ask — the model
    # doesn't always make phase days sum to the requested total, and a mismatch
    # would strand the progress bar below 100% forever.
    total_days = sum(int(p.get("days", 0)) for p in phases) or int(body.get("days", 0))
    state["plan"] = {
        "goal": body["goal"][:MAX_GOAL],
        # 3-5 words naming what the plan BUILDS. A pasted syllabus is not its own
        # title — the owner's real goal opens with the subjects he asked to SKIP,
        # so any prefix of it is worse than useless as a label.
        "short_title": (body.get("short_title") or "").strip()[:40],
        "days": total_days,
        "hours_per_day": float(body["hours_per_day"]),
        "phases": phases,                   # accepted outline from /api/negotiate
        "mentor_message": body.get("mentor_message", ""),
        # The negotiation showed these once and threw them away. They're the
        # promise the student accepted — what's in, and what got cut — and the
        # only place to check the mentor against later.
        "achievable_scope": body.get("achievable_scope") or [],
        "dropped_scope": body.get("dropped_scope") or [],
        "curriculum": [],                    # filled phase by phase
        "phases_generated": 0,
        "next_day": 1,                       # id counter (bumped as days are added)
        "created_at": datetime.datetime.now().isoformat(),
    }
    state["progress"] = {}
    state["lessons"] = {}
    state["quizzes"] = {}
    state["dna"] = None
    state["streak"] = {"count": 0, "shields": 0, "last_day": None}
    state["repaced_at"] = None
    state["profile"]["level_notes"] = body.get("level_notes", "")
    state["profile"]["class"] = body.get("learner_class", "")
    state["profile"]["name"] = (body.get("name") or "").strip()[:24]
    if state.get("material", {}).get("text") and body.get("material_scope"):
        state["material"]["scope"] = body["material_scope"]
    storage.save_state(state)
    return jsonify({"ok": True, "total_phases": len(body["phases"])})


@app.post("/api/plan/generate-phase")
def generate_phase():
    """Generate one phase of the curriculum. The frontend calls this in a loop."""
    state = storage.load_state()
    plan = state.get("plan")
    if not plan:
        return jsonify({"error": "No plan started."}), 400

    idx = plan["phases_generated"]
    if idx >= len(plan["phases"]):
        return jsonify({"done": True, "phases_generated": idx})

    prior = ""
    if plan["curriculum"]:
        prior = "; ".join(
            f"Day {d['day']}: {d['title']}" for d in plan["curriculum"]
        )

    result = gemini.ask_json(
        prompts.MENTOR_PERSONA,
        prompts.curriculum_phase_prompt(
            plan["goal"], plan["days"], plan["hours_per_day"],
            state["profile"].get("level_notes", ""),
            plan["phases"], idx, prior, material=state.get("material"),
        ),
    )
    # a malformed model response must not brick onboarding — reject and let the
    # frontend retry this phase (nothing has been saved yet)
    days = result.get("days") if isinstance(result, dict) else None
    if (not isinstance(days, list) or not days
            or not all(isinstance(d, dict) and isinstance(d.get("day"), int) and d.get("title")
                       for d in days)):
        return jsonify({"error": "Couldn't build this part of the plan. Try again."}), 502
    for entry in days:
        entry["order"] = entry["day"]        # display position (day is the stable id)
        entry["kind"] = "checkpoint" if entry.get("is_checkpoint") else "quest"
        entry["est_minutes"] = _plan_minutes(plan, entry)
        plan["next_day"] = max(plan.get("next_day", 1), entry["day"] + 1)
    # the LAST day of a phase becomes a build-it PROJECT milestone — the capstone
    # of a substantial phase, and ALWAYS the plan's final phase ("apply what you
    # learned"). But NEVER the first phase and NEVER within the first 3 days: a
    # beginner can't build something before they've learned anything.
    phase = plan["phases"][idx]
    is_last_phase = idx == len(plan["phases"]) - 1
    last = days[-1]
    if idx >= 1 and last["day"] > 3 and (phase.get("days", 0) >= 3 or is_last_phase):
        pid = f"p{last['day']}"
        last["kind"] = "project"
        last["project_id"] = pid
        plan.setdefault("projects", {})[pid] = {
            "title": last["title"], "topics": last.get("topics", []),
            "phase_index": idx, "difficulty": idx,   # first project (phase 1) = GUIDED
            "status": "assigned",
            "brief": "", "requirements": [], "rubric": [],
            "submission": None, "review": None,
        }
    plan["curriculum"].extend(days)
    plan["phases_generated"] = idx + 1
    storage.save_state(state)
    return jsonify({
        "done": plan["phases_generated"] >= len(plan["phases"]),
        "phases_generated": plan["phases_generated"],
        "total_phases": len(plan["phases"]),
    })


@app.post("/api/plan/generate-all")
def generate_all():
    """Generate the WHOLE curriculum in ONE request, all phases IN PARALLEL —
    much faster than the sequential per-phase loop on the free tier (total time
    ~= the slowest single phase instead of the sum). One save at the end avoids
    the concurrent-write clobber a parallel client loop would cause."""
    from concurrent.futures import ThreadPoolExecutor
    state = storage.load_state()
    plan = state.get("plan")
    if not plan:
        return jsonify({"error": "No plan started."}), 400
    phases = plan["phases"]
    goal, days_total, hpd = plan["goal"], plan["days"], plan["hours_per_day"]
    level = state["profile"].get("level_notes", "")
    material = state.get("material")

    def gen(idx):
        # each phase is told what EARLIER phases cover (from the accepted outline)
        # so they coordinate without the not-yet-generated prior days
        prior = "; ".join(f'Phase {i + 1} "{p["name"]}": {p.get("focus", "")}'
                          for i, p in enumerate(phases[:idx]))
        result = gemini.ask_json(
            prompts.MENTOR_PERSONA,
            prompts.curriculum_phase_prompt(goal, days_total, hpd, level,
                                            phases, idx, prior, material=material))
        d = result.get("days") if isinstance(result, dict) else None
        if (not isinstance(d, list) or not d
                or not all(isinstance(x, dict) and isinstance(x.get("day"), int) and x.get("title") for x in d)):
            return None
        return d

    # cap concurrency so a big plan doesn't trip the free-tier per-minute limit
    with ThreadPoolExecutor(max_workers=min(len(phases), 4)) as ex:
        per_phase = list(ex.map(gen, range(len(phases))))
    if any(p is None for p in per_phase):
        return jsonify({"error": "Couldn't build the plan. Try again."}), 502

    curriculum, projects, next_day = [], {}, 1
    for idx, dlist in enumerate(per_phase):
        for entry in dlist:
            entry["order"] = entry["day"]
            entry["kind"] = "checkpoint" if entry.get("is_checkpoint") else "quest"
            entry["est_minutes"] = _plan_minutes(plan, entry)
            next_day = max(next_day, entry["day"] + 1)
        phase = phases[idx]
        last = dlist[-1]
        is_last = idx == len(phases) - 1
        if idx >= 1 and last["day"] > 3 and (phase.get("days", 0) >= 3 or is_last):
            pid = f"p{last['day']}"
            last["kind"] = "project"
            last["project_id"] = pid
            projects[pid] = {"title": last["title"], "topics": last.get("topics", []),
                             "phase_index": idx, "difficulty": idx, "status": "assigned",
                             "brief": "", "requirements": [], "rubric": [],
                             "submission": None, "review": None}
        curriculum.extend(dlist)

    plan["curriculum"] = curriculum
    plan["projects"] = projects
    plan["phases_generated"] = len(phases)
    plan["next_day"] = next_day
    storage.save_state(state)
    return jsonify({"done": True, "phases_generated": len(phases), "total_phases": len(phases)})


@app.get("/api/lesson/<int:day>")
def get_lesson(day):
    state = storage.load_state()
    plan = state.get("plan")
    if not plan:
        return jsonify({"error": "No plan yet."}), 400

    cached = state["lessons"].get(str(day))
    if cached:
        return jsonify(cached)

    entry = next((d for d in plan["curriculum"] if d["day"] == day), None)
    if not entry:
        return jsonify({"error": f"Day {day} is not in the curriculum."}), 404

    profile = state["profile"]
    done_count = sum(1 for p in state["progress"].values() if p.get("completed"))
    profile_text = (
        f"Level: {profile.get('level_notes') or 'beginner'}. "
        f"{prompts.mentor_memory(profile, state.get('dna'), days_in=done_count + 1, streak=state.get('streak'))} "
        f"{dna_engine.summary_for_prompt(state.get('dna'))}"
    )
    # difficulty ramps with progress and with how well they're doing
    total = plan.get("days", 1)
    avg = round((state.get("dna") or {}).get("overall_mastery", 0) * 100)
    progression = (
        f"PROGRESSION: day {entry['day']} of {total}. Ramp difficulty as the plan advances — "
        f"early days build foundations, later days get harder and more interview-like. "
        f"Their overall quiz mastery so far is {avg}% — if high (>80%), push harder; if low (<50%), reinforce fundamentals first."
    )
    # ONE day-level video, fetched FIRST (with length + chapters) so the mentor can
    # say exactly which part to watch today rather than "here's a 10-hour course".
    # It used to grab up to 4 and dump them all on the intro step; the per-topic
    # videos now live on their own sections instead (see _attach_section_videos).
    # query-level cache lives in the user's state doc: a cache hit costs ZERO quota,
    # which is what makes REGENERATING a lesson free. The daily guard is a hard stop.
    yt_cache = state.setdefault("yt_cache", {})
    videos = []
    for query in entry.get("resource_queries", [])[:1]:
        videos.extend(youtube.search_videos(query, max_results=1,
                                             cache=yt_cache, guard=storage.youtube_quota_reserve))
    videos = videos[:1]

    lesson = gemini.ask_json(
        prompts.MENTOR_PERSONA,
        prompts.lesson_prompt(prompts.goal_label(plan), plan["hours_per_day"], entry, profile_text,
                              progression=progression, avoid_questions=state.get("asked_questions", []),
                              material=state.get("material"), videos=videos),
    )
    # shape guard: a malformed lesson is rejected (nothing cached), not 500ed
    if isinstance(lesson, dict):
        lesson["sections"] = [s for s in lesson.get("sections") or [] if isinstance(s, dict)]
    if not isinstance(lesson, dict) or not lesson["sections"]:
        return jsonify({"error": "Couldn't build this lesson. Try again."}), 502
    # keep only well-formed quiz questions (a bad answer key would corrupt grading)
    lesson["quiz"] = [
        q for q in (lesson.get("quiz") or [])
        if isinstance(q, dict) and q.get("q")
        and isinstance(q.get("options"), list) and len(q["options"]) >= 2
        and isinstance(q.get("answer"), int) and 0 <= q["answer"] < len(q["options"])
    ]
    lesson["day"] = day
    lesson["title"] = entry["title"]
    lesson["resource_queries"] = entry.get("resource_queries", [])
    lesson["is_checkpoint"] = entry.get("is_checkpoint", False)
    lesson["videos"] = videos
    _attach_section_videos(lesson, plan.get("hours_per_day", 1), entry, cache=yt_cache)
    # the honest length, measured from what was actually generated — replaces the
    # model's own `est_minutes`, which nothing ever checked. Video counts toward the
    # day (watching IS studying), but CAPPED at the day's reserved video budget: the
    # picked explainers guide the student to the relevant part (chapters / what-to-
    # watch), so a "4-hour" day stays ~4 hours instead of ballooning when the model
    # attaches ten long videos on top.
    _shape = prompts.structure_for_hours(plan.get("hours_per_day", 1),
                                         bool(entry.get("is_checkpoint")))
    vid_secs = sum(v.get("duration_seconds", 0) for v in videos)
    vid_secs += sum((s["video"].get("duration_seconds", 0))
                    for s in lesson["sections"] if s.get("video"))
    vid_secs = min(vid_secs, _shape["video_mins"] * 60)
    lesson["est_minutes"] = prompts.estimate_minutes(lesson, vid_secs)
    # Q&A rescued from a stale lesson we dropped (see storage v16) — regenerating
    # a lesson must never cost the learner something they wrote.
    if entry.get("carried_explorations"):
        lesson["explorations"] = entry.pop("carried_explorations")

    # remember every quiz question so it's never asked again (cap the list)
    asked = state.setdefault("asked_questions", [])
    for q in lesson.get("quiz") or []:
        if q.get("q"):
            asked.append(q["q"])
    state["asked_questions"] = asked[-200:]

    state["lessons"][str(day)] = lesson
    storage.save_state(state)
    return jsonify(lesson)


@app.get("/api/project/<pid>")
def get_project(pid):
    """Return a project, generating its brief lazily on first open (1 AI call,
    difficulty calibrated to current mastery), then caching it."""
    state = storage.load_state()
    proj = (state.get("plan") or {}).get("projects", {}).get(pid)
    if not proj:
        return jsonify({"error": "Project not found."}), 404

    if not proj.get("brief"):
        profile = state["profile"]
        name = (profile.get("name") or "").strip()
        profile_text = ((f"Student's name: {name}. " if name else "")
                        + f"Level: {profile.get('level_notes') or 'beginner'}. "
                        + dna_engine.summary_for_prompt(state.get("dna")))
        gen = gemini.ask_json(
            prompts.MENTOR_PERSONA,
            prompts.project_brief_prompt(prompts.goal_label(state["plan"]), proj, profile_text,
                                         material=state.get("material")))
        # shape guard: don't cache a blank brief (it would stick forever) or 500
        if not isinstance(gen, dict) or not gen.get("brief"):
            return jsonify({"error": "Couldn't build this project. Try again."}), 502
        proj["brief"] = gen.get("brief", "")
        proj["requirements"] = gen.get("requirements", [])
        proj["rubric"] = gen.get("rubric", [])
        proj["starter"] = gen.get("starter", "")
        storage.save_state(state)
    return jsonify(proj)


@app.post("/api/project/<pid>/submit")
def submit_project(pid):
    """Store the submission and review it (1 AI call, rewards-only). On review
    the project day is marked complete and XP awarded."""
    body = request.get_json(force=True)
    content = (body.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Add your work first."}), 400

    state = storage.load_state()
    plan = state.get("plan") or {}
    proj = plan.get("projects", {}).get(pid)
    if not proj:
        return jsonify({"error": "Project not found."}), 404

    proj["submission"] = {"type": body.get("type", "describe"), "content": content[:8000],
                          "submitted_at": datetime.datetime.now().isoformat()}
    proj["status"] = "submitted"

    try:
        review = gemini.ask_json(prompts.MENTOR_PERSONA,
                                 prompts.project_review_prompt(proj, content))
        if not isinstance(review, dict):
            raise ValueError("review was not an object")
    except Exception:
        storage.save_state(state)   # keep the submission so they can retry
        return jsonify({"error": "The review couldn't be generated — please submit again."}), 503

    proj["review"] = {**review, "reviewed_at": datetime.datetime.now().isoformat()}
    proj["status"] = "reviewed"

    # award XP + mark the project day complete (rewards-only)
    day = int(pid[1:]) if pid[1:].isdigit() else None
    gained = 0
    if day is not None and not state["progress"].get(str(day), {}).get("completed"):
        gained = 300
        state["xp"] = state.get("xp", 0) + gained
        state["progress"][str(day)] = {"completed": True,
                                       "completed_at": datetime.datetime.now().isoformat()}
        _bump_streak(state)
    storage.save_state(state)
    return jsonify({"review": proj["review"], "xp_gained": gained, "xp": state.get("xp", 0)})


# Confidence payoffs: (XP if right, XP if wrong).
#
# The old table paid `10 x wager` when right and a FLAT 2 when wrong, which made
# "Certain" strictly dominant — EV(certain) - EV(guessing) = 10p for every p > 0,
# so no honest student should ever have picked anything else, and the confidence
# signal was noise. That mattered beyond XP: dna.py treats a high-confidence miss
# as a misconception, so rational play turned every wrong answer into a phantom
# misconception and quietly poisoned the skill map and the review queue.
#
# This is Gardner-Medwin certainty-based marking (correct +1/+2/+3, wrong 0/-2/-6)
# under the affine transform 2x+12, which preserves its indifference thresholds
# exactly: honest reporting is now the XP-maximising strategy at p<0.67 (guessing),
# 0.67-0.80 (fairly sure) and p>0.80 (certain). +12 keeps every cell >= 0, so the
# rewards-only pillar holds — a confident miss costs the difference, never your XP.
PAYOFF = {"safe": (14, 12), "confident": (16, 8), "allin": (18, 0)}


@app.post("/api/quiz/<int:day>/submit")
def submit_quiz(day):
    """Grade a checkpoint quiz — pure Python, no AI call. XP is rewards-only:
    nothing is ever subtracted; an honest wrong answer still pays."""
    body = request.get_json(force=True)
    answers = body.get("answers") or []
    state = storage.load_state()
    lesson = state["lessons"].get(str(day))
    if not lesson or not lesson.get("quiz"):
        return jsonify({"error": "No checkpoint exists for this day."}), 404
    if str(day) in state.get("quizzes", {}):
        return jsonify({"error": "This checkpoint is already done."}), 400

    quiz = lesson["quiz"]
    xp = 0
    correct_count = 0
    combo = 0
    best_combo = 0
    crits = 0
    wrong_topics = []
    graded = []

    # bind each answer to its question by explicit index — never by list position
    by_index = {a["i"]: a for a in answers
                if isinstance(a, dict) and isinstance(a.get("i"), int)}
    for i, q in enumerate(quiz):
        a = by_index.get(i) or (answers[i] if i < len(answers) and isinstance(answers[i], dict) else {})
        chosen = a.get("chosen", -1)
        confidence = a.get("confidence", "safe")
        hinted = bool(a.get("hint_used"))
        is_correct = chosen == q.get("answer")
        gained = PAYOFF.get(confidence, PAYOFF["safe"])[0 if is_correct else 1]
        if is_correct:
            correct_count += 1
            combo += 1
            best_combo = max(best_combo, combo)
            if confidence == "allin":
                crits += 1
        else:
            combo = 0
            if q.get("topic"):
                wrong_topics.append(q["topic"])
        xp += gained
        graded.append({"chosen": chosen, "confidence": confidence,
                       "topic": q.get("topic", ""), "correct": is_correct,
                       "hint_used": hinted, "xp": gained})

    perfect = correct_count == len(quiz)
    if perfect:
        xp += 25
    # Combo is a flourish, not a measurement. It used to MULTIPLY the per-question
    # payoff, which made the honest-reporting thresholds depend on what happened on
    # the previous question — that destroys the calibration the wager exists to
    # train. It's a flat end-of-run bonus now, so the drama stays and the maths
    # stays sound.
    combo_bonus = 10 if best_combo >= 3 else 0
    xp += combo_bonus

    state.setdefault("quizzes", {})[str(day)] = {
        "score": correct_count,
        "total": len(quiz),
        "wrong_topics": wrong_topics,
        "answers": graded,
        "xp_earned": xp,
        "taken_at": datetime.datetime.now().isoformat(),
    }
    state["xp"] = state.get("xp", 0) + xp

    # rebuild Learning DNA from all quiz data (pure Python, no AI)
    old_mastered = _mastered_set(state.get("dna"))
    state["dna"] = dna_engine.compute(state)
    state["notes_seen"] = False
    new_mastered = _mastered_set(state["dna"])
    just_mastered = sorted(new_mastered - old_mastered)

    # struggled badly → the mentor inserts a revision quest (local, no AI)
    revision = None
    if len(quiz) and correct_count / len(quiz) < 0.5:
        revision = _insert_revision(state, day, wrong_topics)

    # add this checkpoint's questions to the spaced-review ladder for warm-ups
    entry = next((d for d in (state["plan"] or {}).get("curriculum", []) if d["day"] == day), None)
    review_engine.enqueue_quiz(state, day, quiz, (entry or {}).get("order", day))

    storage.save_state(state)
    # Per-question review: what you picked, what was right, and WHY. The app
    # showed a one-line verdict for ~1s and then threw the answer away forever,
    # which is the biggest learning gap in the product — a checkpoint you can't
    # review is a score, not a lesson. Safe to reveal now: it's been graded.
    review = [{
        "q": q.get("q", ""),
        "options": q.get("options", []),
        "answer": q.get("answer"),
        "chosen": g["chosen"],
        "correct": g["correct"],
        "topic": g.get("topic", ""),
        "why": q.get("why", ""),
        "hint_used": g.get("hint_used", False),
        "xp": g["xp"],
    } for q, g in zip(quiz, graded)]
    return jsonify({"score": correct_count, "total": len(quiz), "xp_gained": xp,
                    "crits": crits, "perfect": perfect, "xp": state["xp"],
                    "mastered": just_mastered, "revision": revision,
                    "review": review,
                    "breakdown": {"questions": xp - (25 if perfect else 0) - combo_bonus,
                                  "perfect": 25 if perfect else 0,
                                  "combo": combo_bonus, "best_combo": best_combo}})


def _insert_revision(state, after_day, wrong_topics):
    """Add a revision quest right after `after_day`. No AI — the lesson for it
    is generated on demand when opened, like any other day."""
    plan = state["plan"]
    curriculum = plan["curriculum"]
    after = next((d for d in curriculum if d["day"] == after_day), None)
    if not after:
        return None
    # cap: only one revision trailing any given boss
    if any(d.get("kind") == "revision" and d.get("revision_for") == after_day
           for d in curriculum):
        return None

    seen, deduped = set(), []
    for t in wrong_topics:
        if t.lower() not in seen:
            seen.add(t.lower())
            deduped.append(t)
    topics = deduped[:3] or after.get("topics", [])[:2]
    new_id = plan["next_day"]
    plan["next_day"] = new_id + 1
    entry = {
        "day": new_id,
        "order": after["order"] + 0.5,       # sits just after the boss in the log
        "title": "Revision: " + ", ".join(topics),
        "objectives": ["Re-master " + t for t in topics],
        "topics": topics,
        "practice": "Redo the parts that tripped you up.",
        "resource_queries": topics[:1],
        "is_checkpoint": False,
        "kind": "revision",
        "revision_for": after_day,
    }
    curriculum.append(entry)
    return {"title": entry["title"], "topics": topics}


def _mastered_set(dna):
    if not dna:
        return set()
    return {k for k, r in dna.get("topics", {}).items() if r.get("band") == "mastered"}


def _current_order(state):
    """Display-order of the next not-completed quest (the 'today' index)."""
    plan = state.get("plan") or {}
    ordered = sorted(plan.get("curriculum", []), key=lambda d: d.get("order", d["day"]))
    for d in ordered:
        if not state["progress"].get(str(d["day"]), {}).get("completed"):
            return d.get("order", d["day"])
    return ordered[-1].get("order", ordered[-1]["day"]) if ordered else 0


@app.get("/api/warmup")
def warmup():
    """Cheap check (no AI): is a warm-up due today? The questions are generated
    only when the student taps Start (/api/warmup/start)."""
    state = storage.load_state()
    if not state.get("plan"):
        return jsonify({"available": False})
    today = _current_order(state)   # may be x.5 on a revision day — don't truncate
    if (state.get("reviews") or {}).get("done_upto", 0) >= today:
        return jsonify({"available": False, "done": True})
    items = review_engine.due_items(state, today, limit=3)
    return jsonify({"available": bool(items), "count": len(items)})


@app.post("/api/warmup/start")
def warmup_start():
    """Generate FRESH questions for today's due topics (1 AI call, never repeats)."""
    state = storage.load_state()
    if not state.get("plan"):
        return jsonify({"questions": []})
    today = _current_order(state)
    items = review_engine.due_items(state, today, limit=3)
    if not items:
        return jsonify({"questions": []})
    topics = [it["topic"] or "review" for it in items]

    try:
        gen = gemini.ask_json(prompts.MENTOR_PERSONA,
                              prompts.warmup_generate_prompt(prompts.goal_label(state["plan"]),
                                                             topics, state.get("asked_questions", [])))
        fresh = gen.get("questions", [])
    except Exception:
        return jsonify({"questions": []})   # skip warm-up rather than break the day

    questions, asked = [], state.setdefault("asked_questions", [])
    for it, q in zip(items, fresh):
        if not q.get("q") or not isinstance(q.get("options"), list) or len(q["options"]) < 2:
            continue
        ans = q.get("answer", 0)
        if not isinstance(ans, int) or ans < 0 or ans >= len(q["options"]):
            ans = 0
        questions.append({"ref": it["ref"], "topic": it["topic"],
                          "q": q["q"], "options": q["options"], "answer": ans})
        asked.append(q["q"])
    state["asked_questions"] = asked[-200:]
    # Remember what we served so the SERVER can grade the submission. Without
    # this the client told us which answers were right, and that verdict fed
    # straight into the Learning DNA and the review ladder — so any front-end
    # bug silently corrupted the app's model of what the student knows.
    state["warmup_pending"] = {
        "day": today,
        "answers": {q["ref"]: {"answer": q["answer"], "topic": q["topic"]} for q in questions},
    }
    storage.save_state(state)
    return jsonify({"questions": questions, "today": today})


@app.post("/api/warmup/submit")
def warmup_submit():
    """Grade the warm-up, advance the ladder, fold results into DNA, small XP."""
    body = request.get_json(force=True)
    results = body.get("results") or []   # [{ref, chosen}]
    state = storage.load_state()
    today = _current_order(state)

    # Grade against what WE served, not what the client claims. Falls back to the
    # client's verdict only for old clients that still post `correct`.
    pending = state.get("warmup_pending") or {}
    key = pending.get("answers") or {}
    graded_results = []
    for r in results:
        ref = r.get("ref")
        truth = key.get(ref)
        if truth is not None and "chosen" in r:
            correct = r.get("chosen") == truth["answer"]
            topic = truth["topic"]
        else:
            correct = bool(r.get("correct"))
            topic = r.get("topic", "")
        graded_results.append({"ref": ref, "topic": topic, "correct": correct})

    served = [r["ref"] for r in graded_results]
    correct_refs = [r["ref"] for r in graded_results if r["correct"]]
    review_engine.advance(state, served, correct_refs, today)

    # fold into DNA so warm-up retrieval counts toward mastery
    graded = [{"topic": r["topic"], "correct": r["correct"],
               "confidence": "safe", "chosen": -1} for r in graded_results]
    score = sum(1 for r in graded_results if r["correct"])
    if graded:
        state.setdefault("quizzes", {})[f"w{today}"] = {
            "score": score, "total": len(graded_results), "answers": graded,
            "warmup": True, "taken_at": datetime.datetime.now().isoformat(),
        }
        state["dna"] = dna_engine.compute(state)

    # once per day — this used to pay +15 on every post, re-postable forever
    awarded = state.setdefault("awarded", {})
    akey = f"warmup:{_today()}"
    gained = 0 if (awarded.get(akey) or not graded_results) else 15
    if gained:
        awarded[akey] = True
        state["xp"] = state.get("xp", 0) + gained
    streak_event = None
    # tiny-habits "minimum day": even a 2-minute warm-up keeps the streak alive
    if graded_results:
        streak_event = _bump_streak(state)
    state["warmup_pending"] = None
    storage.save_state(state)
    return jsonify({"xp_gained": gained, "xp": state["xp"], "streak": state.get("streak"),
                    "streak_event": streak_event,
                    "score": score, "total": len(graded_results)})


@app.get("/api/skills")
def skills():
    """Skills tab data — marks the Mentor's Notes as seen."""
    state = storage.load_state()
    state["notes_seen"] = True
    storage.save_state(state)
    return jsonify({"dna": state.get("dna"), "class": state["profile"].get("class", "")})


@app.post("/api/ask")
def ask():
    """Curious-question box: the student asks anything, mid-lesson or not."""
    body = request.get_json(force=True)
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Type a question first."}), 400

    state = storage.load_state()
    plan = state.get("plan")
    day = body.get("day")
    entry = None
    if plan and day is not None:
        entry = next((d for d in plan["curriculum"] if d["day"] == day), None)

    # Resolve the exact part of the lesson the student is looking at, from OUR
    # cached copy — so a reference like "that try-it-now" has a concrete thing
    # to point at. We take only the section identity from the client, never its
    # content. `section` is the index within lesson["sections"]; step_kind lets
    # us name a non-section step (practice/summary/intro) too.
    section = None
    lesson = state["lessons"].get(str(day)) if day is not None else None
    sec_i = body.get("section")
    if lesson and isinstance(sec_i, int):
        secs = lesson.get("sections") or []
        if 0 <= sec_i < len(secs):
            section = secs[sec_i]
    focus = prompts.ask_focus(lesson, section, body.get("step_kind"))

    profile = state["profile"]
    name = (profile.get("name") or "").strip()
    profile_text = (
        (f"Student's name: {name}. " if name else "")
        + f"Level: {profile.get('level_notes') or 'beginner'}. "
        + f"Class: {profile.get('class') or 'not chosen'}. "
        + dna_engine.summary_for_prompt(state.get("dna"))
    )
    result = gemini.ask_json(
        prompts.MENTOR_PERSONA,
        prompts.ask_prompt(prompts.goal_label(plan), entry, profile_text, question, focus=focus),
    )
    answer = result.get("answer", "") if isinstance(result, dict) else ""
    if not answer:
        return jsonify({"error": "Couldn't answer that one — try rephrasing it."}), 502
    item = {"q": question, "a": answer, "visual": result.get("visual") if isinstance(result, dict) else None}

    # persist inside the lesson so the Q&A stays with that day
    if day is not None and str(day) in state["lessons"]:
        ex = state["lessons"][str(day)].setdefault("explorations", [])
        ex.append(item)
        # Capped. These append forever at 1-3KB each (more with a visual), and
        # they live INSIDE the one state document that every single request
        # loads and rewrites — MongoDB's hard ceiling is 16MB per document.
        # Unbounded, a chatty term would eventually make the app unopenable.
        del ex[:-EXPLORATIONS_PER_LESSON]
        storage.save_state(state)
    return jsonify(item)


@app.post("/api/day/<int:day>/complete")
def complete_day(day):
    state = storage.load_state()
    already_done = state["progress"].get(str(day), {}).get("completed", False)
    state["progress"][str(day)] = {
        "completed": True,
        "completed_at": datetime.datetime.now().isoformat(),
    }

    gained = 0
    streak_event = None
    if not already_done:  # XP is awarded once per quest
        plan = state.get("plan") or {}
        entry = next((d for d in plan.get("curriculum", []) if d["day"] == day), None)
        gained = 150 if (entry and entry.get("is_checkpoint")) else 100
        state["xp"] = state.get("xp", 0) + gained
        streak_event = _bump_streak(state)

    storage.save_state(state)
    return jsonify({"ok": True, "xp_gained": gained, "xp": state.get("xp", 0),
                    "streak": state.get("streak"), "streak_event": streak_event})


def _today():
    return datetime.date.today().isoformat()


def _bump_streak(state, today_date=None):
    """An HONEST streak: it counts CONSECUTIVE days and it can break.

    `today_date` is injectable so the day-gap logic can actually be tested
    without faking the system clock.

    It used to do `count = max(count, 1)` on a gap — a no-op — so nothing in the
    app ever reset a streak and "12-day streak" really meant "12 days I did
    something, ever". A counter that can't go down isn't a streak.

    Breaking it is not a punishment: no XP is ever taken away and no progress is
    lost. `best` is permanent, so the identity ("I did 9 days straight") survives
    the reset — that's what stops one missed day turning into quitting.
    Shields are EARNED at milestones only and auto-spend to cover one gap.
    """
    s = state.setdefault("streak", {"count": 0, "shields": 0, "last_day": None, "best": 0})
    s.setdefault("best", s.get("count", 0))
    d = today_date or datetime.date.today()
    today = d.isoformat()
    if s["last_day"] == today:
        return None  # already counted today

    event = None
    gap = None
    if s["last_day"]:
        gap = (d - datetime.date.fromisoformat(s["last_day"])).days

    missed = 0 if gap is None else gap - 1
    if gap is None or gap == 1:
        s["count"] += 1                      # first ever, or a clean consecutive day
    elif 0 < missed <= s.get("shields", 0):
        # ONE shield covers ONE missed day. Without the `missed <=` bound a single
        # shield silently covered an arbitrary gap — a fortnight away kept the run.
        s["shields"] -= missed
        s["count"] += 1
        event = {"type": "shield_spent", "shields": s["shields"], "days_missed": missed}
    else:
        broke_at = s["count"]
        s["count"] = 1                       # honest reset — the run restarts today
        if broke_at > 1:
            event = {"type": "streak_broken", "was": broke_at, "best": s.get("best", 0)}

    s["last_day"] = today
    s["best"] = max(s.get("best", 0), s["count"])
    # Shields are earned every 5 consecutive days, capped at 3. Never gifted.
    if not event and s["count"] > 0 and s["count"] % 5 == 0 and s["shields"] < 3:
        s["shields"] += 1
        event = {"type": "shield", "count": s["count"], "shields": s["shields"]}
    return event


@app.post("/api/pace-check")
def pace_check():
    """Called when the dashboard loads. If the user has been away, say so —
    honestly, once a day, and without paying them for it.

    This used to award +50 XP and hand out a shield just for loading the
    dashboard after 3 days away. Because `days_away` is measured from the last
    COMPLETED day but the guard only blocked it once per CALENDAR day, it paid
    out +50 every single day forever as long as you never studied — an infinite
    XP faucet that rewarded absence. It also claimed to "re-pace your plan" in
    both its docstring and its modal while touching nothing but a timestamp.
    Now it reports, and that's all it does.
    """
    state = storage.load_state()
    plan = state.get("plan")
    if not plan or not plan.get("curriculum"):
        return jsonify({"behind": False})

    completed = [p for p in state["progress"].values() if p.get("completed")]
    total_quests = sum(1 for d in plan["curriculum"] if d.get("kind") != "revision")
    if not completed or len(completed) >= total_quests:
        return jsonify({"behind": False})

    last_iso = max(p["completed_at"] for p in completed)
    last_date = datetime.date.fromisoformat(last_iso[:10])
    days_away = (datetime.date.today() - last_date).days

    if days_away < 3:
        return jsonify({"behind": False})
    if state.get("repaced_at") == _today():
        return jsonify({"behind": False})  # already welcomed back today

    # No XP, no gifted shield. Being away isn't an achievement. Nothing is taken
    # away either — the plan, the XP and the lessons are all exactly where they
    # were. The streak itself is settled by _bump_streak on the next real day of
    # work, which is the only place that should touch it.
    s = state.setdefault("streak", {"count": 0, "shields": 0, "last_day": None, "best": 0})
    state["repaced_at"] = _today()
    storage.save_state(state)
    return jsonify({"behind": True, "days_away": days_away, "streak": s})


@app.post("/api/interview/start")
def interview_start():
    """Generate (and cache) a mock-interview question set for a chapter. 1 AI call."""
    body = request.get_json(force=True)
    chapter = int(body.get("chapter", 0))
    state = storage.load_state()
    plan = state.get("plan") or {}
    interviews = state.setdefault("interviews", {})

    cached = interviews.get(str(chapter))
    if cached and cached.get("questions"):
        # don't leak model answers/rubric to the client
        qs = [{"id": q["id"], "kind": q.get("kind", "theory"), "q": q["q"]} for q in cached["questions"]]
        return jsonify({"questions": qs, "done": bool(cached.get("results"))})

    phases = plan.get("phases", [])
    if chapter >= len(phases):
        return jsonify({"error": "No such chapter."}), 404
    cum = sum(p["days"] for p in phases[:chapter])
    end = cum + phases[chapter]["days"]
    topics = []
    for d in plan.get("curriculum", []):
        if d.get("kind") != "revision" and cum < d["day"] <= end:
            topics.extend(d.get("topics", []))
    topics = sorted(set(topics))

    result = gemini.ask_json(
        prompts.MENTOR_PERSONA,
        prompts.interview_generate_prompt(prompts.goal_label(plan), phases[chapter]["name"], topics),
    )
    # shape guard: only cache a set we can actually run and grade
    questions = result.get("questions", []) if isinstance(result, dict) else []
    questions = [q for q in questions
                 if isinstance(q, dict) and q.get("id") is not None and q.get("q")]
    if not questions:
        return jsonify({"error": "Couldn't set up the interview. Try again."}), 502
    interviews[str(chapter)] = {"questions": questions, "results": None}
    storage.save_state(state)
    qs = [{"id": q["id"], "kind": q.get("kind", "theory"), "q": q["q"]} for q in questions]
    return jsonify({"questions": qs, "done": False})


@app.post("/api/interview/submit")
def interview_submit():
    """Batch-grade a completed mock interview. 1 AI call, rewards-only."""
    body = request.get_json(force=True)
    chapter = int(body.get("chapter", 0))
    answers = body.get("answers", [])   # [{id, text}]
    state = storage.load_state()
    interviews = state.setdefault("interviews", {})
    iv = interviews.get(str(chapter))
    if not iv or not iv.get("questions"):
        return jsonify({"error": "Start the interview first."}), 400

    # already graded once — return the cached result, never re-award the XP
    # (this endpoint has no other once-guard, so re-submitting would farm XP)
    if iv.get("results"):
        cached = iv["results"]
        models = {q["id"]: q.get("model_answer", "") for q in iv["questions"]}
        for res in cached.get("results", []):
            res["model_answer"] = models.get(res.get("id"), "")
        return jsonify({"results": cached.get("results", []), "overall": cached.get("overall", ""),
                        "xp_gained": 0, "xp": state.get("xp", 0)})

    by_id = {a["id"]: (a.get("text") or "").strip()[:800] for a in answers}
    graded_items = [{"id": q["id"], "q": q["q"], "rubric": q.get("rubric", ""),
                     "text": by_id.get(q["id"], "")} for q in iv["questions"]]
    try:
        graded = gemini.ask_json(prompts.MENTOR_PERSONA,
                                 prompts.interview_grade_prompt(prompts.goal_label(state["plan"]), graded_items))
        if not isinstance(graded, dict):
            raise ValueError("grade was not an object")
    except Exception:
        graded = {"results": [{"id": it["id"], "verdict": "okay",
                               "whats_good": "You showed up and gave it a real go.",
                               "tighten": "Compare your answer to the model answer and note what you'd add."}
                              for it in graded_items],
                  "overall": "I couldn't fully grade this run, but showing up for a mock interview is exactly the practice that counts."}

    iv["results"] = graded
    gained = 60
    state["xp"] = state.get("xp", 0) + gained
    storage.save_state(state)
    # attach the model answers now (safe to reveal after submitting)
    models = {q["id"]: q.get("model_answer", "") for q in iv["questions"]}
    for res in graded.get("results", []):
        res["model_answer"] = models.get(res.get("id"), "")
    return jsonify({"results": graded.get("results", []), "overall": graded.get("overall", ""),
                    "xp_gained": gained, "xp": state["xp"]})


@app.post("/api/weekly/seen")
def weekly_seen():
    """Snapshot progress when a weekly report is dismissed, so the next one
    can show deltas. Pure state."""
    state = storage.load_state()
    plan = state.get("plan") or {}
    done_real = sum(1 for d in plan.get("curriculum", [])
                    if d.get("kind") != "revision"
                    and state["progress"].get(str(d["day"]), {}).get("completed"))
    mastered = sorted(k for k, r in (state.get("dna") or {}).get("topics", {}).items()
                      if r.get("band") == "mastered")
    state["weekly"] = {"last_shown": done_real, "snap_xp": state.get("xp", 0),
                       "snap_mastered": mastered}
    storage.save_state(state)
    return jsonify({"ok": True})


@app.post("/api/bookmark/toggle")
def bookmark_toggle():
    """Star/unstar a lesson section. Pure state, no AI."""
    body = request.get_json(force=True)
    day = body.get("day")
    idx = body.get("sectionIndex")
    heading = (body.get("heading") or "").strip()
    if day is None or idx is None:
        return jsonify({"error": "missing day/section"}), 400
    state = storage.load_state()
    marks = state.setdefault("bookmarks", [])
    existing = next((m for m in marks if m["day"] == day and m["sectionIndex"] == idx), None)
    if existing:
        marks.remove(existing)
        saved = False
    else:
        marks.append({"day": day, "sectionIndex": idx, "heading": heading})
        saved = True
    storage.save_state(state)
    # return the list so the client can update in place — it used to refetch the
    # WHOLE state right after this call just to learn one boolean
    return jsonify({"saved": saved, "count": len(marks), "bookmarks": marks})


@app.post("/api/explain")
def explain():
    """Explain-it-back: grade a short daily self-explanation. Additive feedback,
    never a score. One AI call; degrades gracefully. Cheap daily retrieval
    practice — the per-chapter mock interview doesn't replace it."""
    body = request.get_json(force=True)
    concept = (body.get("concept") or "").strip()
    text = (body.get("text") or "").strip()[:800]
    day = body.get("day")
    if not text:
        return jsonify({"error": "Write your explanation first."}), 400
    state = storage.load_state()
    lesson = state["lessons"].get(str(day)) if day is not None else None
    reference = (lesson or {}).get("summary", "")

    try:
        result = gemini.ask_json(prompts.MENTOR_PERSONA,
                                 prompts.grade_prompt(
                                     f"Concept the student is explaining back: {concept}",
                                     f"Reference (today's lesson summary): {reference}",
                                     text))
    except Exception:
        result = {"whats_good": "Thanks for putting it in your own words.",
                  "whats_missing": "I couldn't fully check it this time — compare yours to the lesson summary and see what you'd add."}
    # Once per LESSON-day, ever — not per calendar day (contrast warm-up/focus,
    # which are daily). Re-opening an old recap shouldn't pay again; this used to
    # award +20 for any text, on every single call.
    awarded = state.setdefault("awarded", {})
    key = f"explain:{day}"
    gained = 0 if awarded.get(key) else 20
    if gained:
        awarded[key] = _today()   # value is for debugging; the guard is presence
        state["xp"] = state.get("xp", 0) + gained
    storage.save_state(state)
    return jsonify({"whats_good": result.get("whats_good", ""),
                    "whats_missing": result.get("whats_missing", ""),
                    "xp_gained": gained, "xp": state["xp"]})


FOCUS_XP_DAILY_CAP = 40
EXPLORATIONS_PER_LESSON = 10   # keep the newest N Q&As per day (see /api/ask)


def _attach_section_videos(lesson, hours, entry, cache=None):
    """Put each topic's video ON that topic's step, not all in a pile at step 1.

    Videos were day-level: one search, up to 2 results, every one of them
    rendered into the intro — so you got a wall of links before you knew what
    they were for, and nothing next to the concept it explained.

    Ordering note: this HAS to run after generation, because sections don't
    exist until the model has written them. Searches fan out in parallel — done
    sequentially they'd add 4-6s to a call that's already slow.

    Cost: every search.list is 100 units of a 10,000/day YouTube quota shared by
    the whole project. The count is capped by structure_for_hours() (now up to one
    per section, ceiling 10), and a section only gets one if the MODEL wrote a
    resource_query — the prompt asks for one wherever a video genuinely helps and
    omits it for pure definitions/history. `cache` (the user's yt_cache) makes a
    repeat search free; storage.youtube_quota_reserve is the hard daily-budget stop.
    """
    shape = prompts.structure_for_hours(hours, bool(entry.get("is_checkpoint")))
    wanted = [s for s in lesson["sections"] if (s.get("resource_query") or "").strip()][:shape["videos"]]
    if not wanted:
        return
    try:
        # concurrency 6 (was 4): a rich lesson can want ~10 videos; 6 threads keeps
        # the added latency to ~2 waves without hammering the free-tier CPU.
        with ThreadPoolExecutor(max_workers=min(len(wanted), 6)) as ex:
            found = list(ex.map(
                lambda s: youtube.search_videos(s["resource_query"], max_results=1,
                                                cache=cache, guard=storage.youtube_quota_reserve),
                wanted))
    except Exception:
        return   # a video is never worth failing a lesson over
    for section, vids in zip(wanted, found):
        if vids:
            section["video"] = vids[0]


def _plan_minutes(plan, entry):
    """The day's time budget, from the hours the student chose.

    This used to be model-authored (`est_minutes`) and was never read by any
    code — the model wrote "360" next to a lesson it had generated at a fixed
    3-6 sections regardless. Now it's derived, so the plan can't lie about
    how long a day is before the lesson even exists.
    """
    shape = prompts.structure_for_hours(plan.get("hours_per_day", 1),
                                        bool(entry.get("is_checkpoint")))
    return shape["est"]


@app.post("/api/focus/done")
def focus_done():
    """A study session finished — rewards-only XP. No penalties, ever.

    Guarded now: this had no once-check of any kind and paid per HTTP call, and
    the client ends a session on EVERY navigate-away from a lesson — so it was
    quietly minting XP during ordinary use. XP is now proportional to real
    minutes actually studied and capped per day.
    """
    body = request.get_json(force=True)
    state = storage.load_state()
    minutes = max(0, int(body.get("elapsed_seconds") or 0)) // 60
    if minutes < 5:
        return jsonify({"xp_gained": 0, "xp": state.get("xp", 0)})  # too short to count

    awarded = state.setdefault("awarded", {})
    key = f"focus:{_today()}"
    used = awarded.get(key, 0)
    want = 30 if body.get("completed") else 15
    gained = max(0, min(want, FOCUS_XP_DAILY_CAP - used))
    if gained:
        awarded[key] = used + gained
        state["xp"] = state.get("xp", 0) + gained
        storage.save_state(state)
    return jsonify({"xp_gained": gained, "xp": state["xp"]})


@app.get("/api/vapid-public-key")
def vapid_public_key():
    return jsonify({"key": os.environ.get("VAPID_PUBLIC_KEY", "")})


@app.post("/api/push/subscribe")
def push_subscribe():
    """Store a browser push subscription + the user's reminder prefs."""
    body = request.get_json(force=True)
    sub = body.get("subscription")
    if not sub:
        return jsonify({"error": "No subscription."}), 400
    state = storage.load_state()
    notif = state["notifications"]
    # de-dupe by endpoint
    notif["subscriptions"] = [s for s in notif["subscriptions"] if s.get("endpoint") != sub.get("endpoint")]
    notif["subscriptions"].append(sub)
    notif["enabled"] = True
    if body.get("daily_time"):
        notif["daily_time"] = body["daily_time"]
    if body.get("tz_offset") is not None:
        notif["tz_offset"] = int(body["tz_offset"])   # so the daily time is in the user's zone
    storage.save_state(state)
    return jsonify({"ok": True})


@app.post("/api/push/settings")
def push_settings():
    """Update reminder prefs (on/off, daily time, quiet hours)."""
    body = request.get_json(force=True)
    state = storage.load_state()
    notif = state["notifications"]
    if "enabled" in body:
        notif["enabled"] = bool(body["enabled"])
    if body.get("daily_time"):
        notif["daily_time"] = body["daily_time"]
    if body.get("quiet_hours"):
        notif["quiet_hours"] = body["quiet_hours"]
    if body.get("tz_offset") is not None:
        notif["tz_offset"] = int(body["tz_offset"])
    storage.save_state(state)
    return jsonify({"ok": True, "notifications": {k: v for k, v in notif.items() if k != "subscriptions"}})


@app.route("/api/cron/push", methods=["GET", "POST"])
def cron_push():
    """Hit by the external uptime pinger on a schedule (GET or POST — a simple
    UptimeRobot monitor uses GET). Sends at most one gentle digest per day.
    Gated by CRON_SECRET — fails CLOSED: with no secret configured the endpoint
    is disabled rather than public."""
    secret = os.environ.get("CRON_SECRET", "")
    if not secret or request.args.get("key") != secret:
        return jsonify({"error": "unauthorized"}), 401
    # No session here — an uptime pinger sends no cookie — so this is the one
    # place that legitimately works across users. It only loads people who could
    # actually receive a push, and writes back ONLY the notifications subtree:
    # this runs every few minutes against everyone, and a whole-document save
    # would race each user's own session and silently undo their work.
    sent = 0
    for uid in storage.notif_user_ids():
        try:
            state = storage.load_state_for(uid)
            result = push_engine.run_cron(state)
            if result.get("changed"):
                storage.save_notifications_for(uid, state["notifications"])
            sent += result.get("sent", 0)
        except Exception:
            continue          # one user's bad state must not stop everyone's digest
    return jsonify({"sent": sent})


@app.post("/api/reset")
def reset():
    """Start over — wipes the plan and progress. Guarded against blind
    cross-site POSTs: requires the app's own header (cross-origin pages can't
    set custom headers without a CORS preflight, which this app never grants)
    plus an explicit confirm in the body. Real protection is auth (multi-user)."""
    body = request.get_json(silent=True) or {}
    if request.headers.get("X-Requested-With") != "MentorOS" or body.get("confirm") is not True:
        return jsonify({"error": "Reset must be confirmed from inside the app."}), 403
    saved_at = storage.snapshot("reset")   # recoverable via /api/restore
    storage.save_state(storage._empty_state())
    return jsonify({"ok": True, "backup_saved_at": saved_at})


@app.post("/api/pref")
def set_pref():
    """Store one learner UI preference. Small keys only (study-mode opt-in etc.);
    not a general KV store."""
    body = request.get_json(force=True)
    key = (body.get("key") or "").strip()[:40]
    allowed = {"study_auto"}
    if key not in allowed:
        return jsonify({"error": "unknown preference"}), 400
    state = storage.load_state()
    state["profile"].setdefault("preferences", {})[key] = body.get("value")
    storage.save_state(state)
    return jsonify({"ok": True})


@app.post("/api/plan/title")
def plan_title():
    """Name the plan. Nothing else — this touches one field.

    A pasted syllabus has no derivable title (the owner's opens with the subjects
    he asked to SKIP), and spending an AI call to guess one would still be a
    guess. His own five words beat a model's every time.
    """
    body = request.get_json(force=True)
    title = (body.get("short_title") or "").strip()[:40]
    if not title:
        return jsonify({"error": "Give the plan a name first."}), 400
    state = storage.load_state()
    if not state.get("plan"):
        return jsonify({"error": "No plan to name."}), 404
    state["plan"]["short_title"] = title
    storage.save_state(state)
    return jsonify({"ok": True, "short_title": title})


@app.post("/api/restore")
def restore():
    """Undo the last destructive wipe (start-over or a replaced plan).

    The snapshot is written by storage.snapshot() before anything clears a
    plan. This exists so that a mis-tap is recoverable instead of terminal.
    """
    if request.headers.get("X-Requested-With") != "MentorOS":
        return jsonify({"error": "Restore must be run from inside the app."}), 403
    snap = storage.load_snapshot()
    if not snap or not snap.get("state", {}).get("plan"):
        return jsonify({"error": "There's no backup to restore."}), 404
    storage.save_state(snap["state"])
    return jsonify({"ok": True, "goal": snap["state"]["plan"].get("goal", ""),
                    "saved_at": snap.get("saved_at", "")})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)),
            debug=os.environ.get("FLASK_DEBUG") == "1")
