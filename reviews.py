"""Spaced-review warm-ups — resurface earlier quiz questions on a fixed ladder.

Zero AI cost: questions are reused from lessons[day].quiz[]. A concept seen on
"day index" D comes back at D+1, D+3, D+7, then graduates. Misconceptions
(confident-wrong answers) jump to the front of the queue.
"""
import dna as dna_engine

LADDER = [1, 3, 7]   # gaps, in quest-order units


def enqueue_quiz(state, src_day, quiz, order):
    """After a checkpoint is graded, add its questions to the review ladder."""
    q = state.setdefault("reviews", {"queue": [], "done_upto": 0})["queue"]
    base = order   # keep a revision day's x.5 order — truncating shifts due dates
    misc = set(dna_engine.norm_topic(t) for t in (state.get("dna") or {}).get("misconceptions", []))
    for i, question in enumerate(quiz):
        topic = question.get("topic", "")
        q.append({
            "ref": [src_day, i],
            "topic": topic,
            "stage": 0,
            "due": base + LADDER[0],
            "priority": 1 if dna_engine.norm_topic(topic) in misc else 0,
        })


def due_items(state, today, limit=3):
    """Questions due for review at this quest-order, misconceptions first."""
    q = (state.get("reviews") or {}).get("queue", [])
    due = [r for r in q if r["due"] <= today]
    due.sort(key=lambda r: (-r["priority"], r["due"], r["stage"]))
    return due[:limit]


def resolve(state, item):
    """Turn a queue item into a real question from the lesson cache (or None)."""
    src_day, qi = item["ref"]
    lesson = (state.get("lessons") or {}).get(str(src_day))
    if not lesson:
        return None
    quiz = lesson.get("quiz") or []
    if qi >= len(quiz):
        return None
    question = quiz[qi]
    return {
        "ref": item["ref"],
        "topic": item["topic"],
        "q": question.get("q", ""),
        "options": question.get("options", []),
        "answer": question.get("answer", 0),
    }


def advance(state, served_refs, correct_refs, today):
    """After a warm-up is submitted, move served items up the ladder.
    Correct → next rung (or graduate). Wrong → reset to the first rung."""
    q = state.setdefault("reviews", {"queue": [], "done_upto": 0})["queue"]
    served = {tuple(r) for r in served_refs}
    correct = {tuple(r) for r in correct_refs}
    keep = []
    for r in q:
        key = tuple(r["ref"])
        if key not in served:
            keep.append(r)
            continue
        if key in correct:
            r["stage"] += 1
            if r["stage"] >= len(LADDER):
                continue  # graduated — drop it
            r["due"] = today + LADDER[r["stage"]]
        else:
            r["stage"] = 0
            r["due"] = today + LADDER[0]
        r["priority"] = 0  # reviewed once, no longer jump-the-queue
        keep.append(r)
    state["reviews"]["queue"] = keep
    state["reviews"]["done_upto"] = today
