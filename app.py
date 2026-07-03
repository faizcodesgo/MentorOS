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
        "created_at": datetime.datetime.now().isoformat(),
    }
    state["progress"] = {}
    state["lessons"] = {}
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

    storage.save_state(state)
    return jsonify({"score": correct_count, "total": len(quiz), "xp_gained": xp,
                    "crits": crits, "perfect": perfect, "xp": state["xp"],
                    "mastered": just_mastered})


def _mastered_set(dna):
    if not dna:
        return set()
    return {k for k, r in dna.get("topics", {}).items() if r.get("band") == "mastered"}


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
    if not already_done:  # XP is awarded once per quest
        plan = state.get("plan") or {}
        entry = next((d for d in plan.get("curriculum", []) if d["day"] == day), None)
        gained = 150 if (entry and entry.get("is_checkpoint")) else 100
        state["xp"] = state.get("xp", 0) + gained

    storage.save_state(state)
    return jsonify({"ok": True, "xp_gained": gained, "xp": state.get("xp", 0)})


@app.post("/api/reset")
def reset():
    """Start over — wipes the plan and progress."""
    storage.save_state(storage._empty_state())
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
