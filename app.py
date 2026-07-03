"""MentorOS — AI mentor that plans, teaches, and tracks a learning goal.

Phase 1: goal negotiation -> day-by-day curriculum -> daily lessons -> progress.
Run locally:  python app.py   (then open http://localhost:5000)
"""
import datetime
import os

from flask import Flask, jsonify, request, send_from_directory

import dna as dna_engine
import gemini
import prompts
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


@app.errorhandler(Exception)
def handle_error(e):
    """API calls should always get JSON back, with the real reason."""
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return jsonify({"error": e.description}), e.code
    return jsonify({"error": str(e)}), 500


@app.get("/")
def index():
    return send_from_directory("public", "index.html")


@app.get("/api/state")
def get_state():
    state = storage.load_state()
    # lessons can get big — the dashboard doesn't need them
    slim = {k: v for k, v in state.items() if k != "lessons"}
    return jsonify(slim)


@app.post("/api/negotiate")
def negotiate():
    body = request.get_json(force=True)
    goal = body.get("goal", "").strip()
    days = int(body.get("days", 0))
    hours = float(body.get("hours_per_day", 0))
    level = body.get("level_notes", "").strip()
    if not goal or days < 1 or hours <= 0:
        return jsonify({"error": "Please fill in the goal, days, and hours per day."}), 400

    result = gemini.ask_json(
        prompts.MENTOR_PERSONA,
        prompts.negotiate_prompt(goal, days, hours, level),
    )
    return jsonify(result)


@app.post("/api/plan/init")
def plan_init():
    """Create the plan shell after the student accepts the negotiated outline."""
    body = request.get_json(force=True)
    state = storage.load_state()
    # Season model: XP earned on the previous Main Quest rolls into the career total
    state["lifetime_xp"] = state.get("lifetime_xp", 0) + state.get("xp", 0)
    state["xp"] = 0
    state["plan"] = {
        "goal": body["goal"],
        "days": int(body["days"]),
        "hours_per_day": float(body["hours_per_day"]),
        "phases": body["phases"],           # accepted outline from /api/negotiate
        "mentor_message": body.get("mentor_message", ""),
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
            plan["phases"], idx, prior,
        ),
    )
    for entry in result["days"]:
        entry["order"] = entry["day"]        # display position (day is the stable id)
        entry["kind"] = "checkpoint" if entry.get("is_checkpoint") else "quest"
        plan["next_day"] = max(plan.get("next_day", 1), entry["day"] + 1)
    plan["curriculum"].extend(result["days"])
    plan["phases_generated"] = idx + 1
    storage.save_state(state)
    return jsonify({
        "done": plan["phases_generated"] >= len(plan["phases"]),
        "phases_generated": plan["phases_generated"],
        "total_phases": len(plan["phases"]),
    })


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
    profile_text = (
        f"Level: {profile.get('level_notes') or 'beginner'}. "
        f"Class: {profile.get('class') or 'not chosen'}. "
        f"{dna_engine.summary_for_prompt(state.get('dna'))}"
    )
    lesson = gemini.ask_json(
        prompts.MENTOR_PERSONA,
        prompts.lesson_prompt(plan["goal"], plan["hours_per_day"], entry, profile_text),
    )
    lesson["day"] = day
    lesson["title"] = entry["title"]
    lesson["resource_queries"] = entry.get("resource_queries", [])
    lesson["is_checkpoint"] = entry.get("is_checkpoint", False)

    # Direct video links via YouTube API (cached with the lesson); falls back
    # to search links in the UI when empty.
    videos = []
    for query in lesson["resource_queries"][:2]:
        videos.extend(youtube.search_videos(query, max_results=2))
    lesson["videos"] = videos[:4]
    state["lessons"][str(day)] = lesson
    storage.save_state(state)
    return jsonify(lesson)


@app.post("/api/quiz/<int:day>/submit")
def submit_quiz(day):
    """Grade a Boss Check — pure Python, no AI call. XP is rewards-only:
    wrong answers still earn scouting XP and never subtract anything."""
    body = request.get_json(force=True)
    answers = body.get("answers") or []
    state = storage.load_state()
    lesson = state["lessons"].get(str(day))
    if not lesson or not lesson.get("quiz"):
        return jsonify({"error": "No Boss Check exists for this day."}), 404
    if str(day) in state.get("quizzes", {}):
        return jsonify({"error": "Boss Check already cleared for this day."}), 400

    quiz = lesson["quiz"]
    wager_mult = {"safe": 1.0, "confident": 1.5, "allin": 2.0}
    xp = 0
    correct_count = 0
    combo = 0
    crits = 0
    wrong_topics = []
    graded = []

    for i, q in enumerate(quiz):
        a = answers[i] if i < len(answers) and isinstance(answers[i], dict) else {}
        chosen = a.get("chosen", -1)
        confidence = a.get("confidence", "safe")
        is_correct = chosen == q.get("answer")
        if is_correct:
            correct_count += 1
            combo += 1
            combo_mult = 1.0 if combo == 1 else (1.5 if combo == 2 else 2.0)
            gained = round(10 * wager_mult.get(confidence, 1.0) * combo_mult)
            if confidence == "allin":
                crits += 1
        else:
            combo = 0
            gained = 2  # scouting XP — the wrong answer revealed a weak point
            if q.get("topic"):
                wrong_topics.append(q["topic"])
        xp += gained
        graded.append({"chosen": chosen, "confidence": confidence,
                       "topic": q.get("topic", ""), "correct": is_correct, "xp": gained})

    perfect = correct_count == len(quiz)
    if perfect:
        xp += 25

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
    return jsonify({"score": correct_count, "total": len(quiz), "xp_gained": xp,
                    "crits": crits, "perfect": perfect, "xp": state["xp"],
                    "mastered": just_mastered, "revision": revision})


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
    """Today's spaced-review warm-up: a few earlier questions, misconceptions
    first. Optional — never gates the lesson. Shuffled so answers aren't memorized."""
    state = storage.load_state()
    if not state.get("plan"):
        return jsonify({"questions": []})
    today = int(_current_order(state))
    if (state.get("reviews") or {}).get("done_upto", 0) >= today:
        return jsonify({"questions": [], "done": True})   # already done today

    items = review_engine.due_items(state, today, limit=3)
    questions = []
    for it in items:
        q = review_engine.resolve(state, it)
        if not q:
            continue
        # shuffle options deterministically (no Math.random in this env for the
        # server) — rotate by the source day so it differs from the original
        opts = q["options"]
        shift = (it["ref"][0] + it["ref"][1]) % max(len(opts), 1)
        rotated = opts[shift:] + opts[:shift]
        new_answer = (q["answer"] - shift) % len(opts) if opts else 0
        questions.append({"ref": q["ref"], "topic": q["topic"], "q": q["q"],
                          "options": rotated, "answer": new_answer})
    return jsonify({"questions": questions, "today": today})


@app.post("/api/warmup/submit")
def warmup_submit():
    """Grade the warm-up, advance the ladder, fold results into DNA, small XP."""
    body = request.get_json(force=True)
    results = body.get("results") or []   # [{ref, topic, correct}]
    state = storage.load_state()
    today = int(_current_order(state))

    served = [r["ref"] for r in results]
    correct_refs = [r["ref"] for r in results if r.get("correct")]
    review_engine.advance(state, served, correct_refs, today)

    # fold into DNA so warm-up retrieval counts toward mastery
    graded = [{"topic": r.get("topic", ""), "correct": bool(r.get("correct")),
               "confidence": "safe", "chosen": -1} for r in results]
    if graded:
        state.setdefault("quizzes", {})[f"w{today}"] = {
            "score": sum(1 for r in results if r.get("correct")),
            "total": len(results), "answers": graded, "warmup": True,
            "taken_at": datetime.datetime.now().isoformat(),
        }
        state["dna"] = dna_engine.compute(state)

    gained = 15 if results else 0
    state["xp"] = state.get("xp", 0) + gained
    storage.save_state(state)
    return jsonify({"xp_gained": gained, "xp": state["xp"],
                    "score": sum(1 for r in results if r.get("correct")), "total": len(results)})


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

    profile = state["profile"]
    profile_text = (
        f"Level: {profile.get('level_notes') or 'beginner'}. "
        f"Class: {profile.get('class') or 'not chosen'}. "
        f"{dna_engine.summary_for_prompt(state.get('dna'))}"
    )
    result = gemini.ask_json(
        prompts.MENTOR_PERSONA,
        prompts.ask_prompt(plan["goal"] if plan else "", entry, profile_text, question),
    )
    item = {"q": question, "a": result.get("answer", ""), "visual": result.get("visual")}

    # persist inside the lesson so the Q&A stays with that day forever
    if day is not None and str(day) in state["lessons"]:
        state["lessons"][str(day)].setdefault("explorations", []).append(item)
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


def _bump_streak(state):
    """Rewards-only streak: a day of activity extends it; consecutive-day
    milestones grant Shields. Never decrements here (gaps are handled by the
    re-pace welcome-back, which spends a shield or just pauses)."""
    s = state.setdefault("streak", {"count": 0, "shields": 0, "last_day": None})
    today = _today()
    if s["last_day"] == today:
        return None  # already counted today
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    if s["last_day"] == yesterday or s["last_day"] is None:
        s["count"] += 1
    else:
        # returning after a gap that the welcome-back already reconciled
        s["count"] = max(s["count"], 1)
    s["last_day"] = today
    event = None
    if s["count"] > 0 and s["count"] % 5 == 0 and s["shields"] < 3:
        s["shields"] += 1
        event = {"type": "shield", "count": s["count"], "shields": s["shields"]}
    return event


@app.post("/api/pace-check")
def pace_check():
    """Called when the dashboard loads. If the user has fallen behind, re-pace
    the plan forward from today and return a welcome-back payload (once/day)."""
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

    # re-pace: nothing is regenerated or lost — we just award a comeback bonus
    # and (if available) auto-spend a shield so the streak pauses, not breaks.
    bonus = 50
    state["xp"] = state.get("xp", 0) + bonus
    s = state.setdefault("streak", {"count": 0, "shields": 0, "last_day": None})
    shield_used = False
    if s["shields"] > 0:
        s["shields"] -= 1
        shield_used = True
    else:
        s["shields"] = s.get("shields", 0) + 1  # gift one on return
    state["repaced_at"] = _today()
    storage.save_state(state)
    return jsonify({
        "behind": True,
        "days_away": days_away,
        "bonus_xp": bonus,
        "shield_used": shield_used,
        "streak": s,
    })


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
    return jsonify({"saved": saved, "count": len(marks)})


@app.post("/api/explain")
def explain():
    """Explain-it-back: grade a short self-explanation. Additive feedback,
    never a score. One AI call; degrades gracefully."""
    body = request.get_json(force=True)
    concept = (body.get("concept") or "").strip()
    text = (body.get("text") or "").strip()[:800]
    day = body.get("day")
    if not text:
        return jsonify({"error": "Write your explanation first."}), 400
    state = storage.load_state()
    lesson = state["lessons"].get(str(day)) if day is not None else None
    reference = (lesson or {}).get("summary", "")

    result = _grade_free_text(
        f"Concept the student is explaining back: {concept}",
        f"Reference (today's lesson summary): {reference}",
        text,
    )
    # soft signal into DNA: a weak self-explanation nudges the topic as shaky
    gained = 20
    state["xp"] = state.get("xp", 0) + gained
    storage.save_state(state)
    return jsonify({"whats_good": result.get("whats_good", ""),
                    "whats_missing": result.get("whats_missing", ""),
                    "xp_gained": gained, "xp": state["xp"]})


def _grade_free_text(question, reference, learner_text):
    """Shared grader for explain-it-back and the interviewer. Returns
    {whats_good, whats_missing}; degrades to a safe message if the model fails."""
    try:
        return gemini.ask_json(prompts.MENTOR_PERSONA,
                               prompts.grade_prompt(question, reference, learner_text))
    except Exception:
        return {"whats_good": "Thanks for putting it in your own words.",
                "whats_missing": "I couldn't fully check it this time — compare yours to the lesson summary and see what you'd add."}


@app.post("/api/focus/done")
def focus_done():
    """A voluntary focus session finished — rewards-only XP (a bit more if
    the session ran unbroken)."""
    body = request.get_json(force=True)
    state = storage.load_state()
    gained = 40 if body.get("unbroken") else 25
    state["xp"] = state.get("xp", 0) + gained
    storage.save_state(state)
    return jsonify({"xp_gained": gained, "xp": state["xp"]})


@app.post("/api/reset")
def reset():
    """Start over — wipes the plan and progress."""
    storage.save_state(storage._empty_state())
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
