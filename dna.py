"""Learning DNA — a picture of what the learner knows, built ONLY from quiz data.

No AI calls: pure Python over stored checkpoint answers. Recomputed on every
quiz submit. The Mentor's Notes text is template-assembled from the numbers.
"""
import re

# Words to strip from a topic tag so "For Loops", "basic loops", "loops concept"
# all collapse to "loops". Order doesn't matter; applied as whole words.
_QUALIFIERS = {"the", "a", "an", "basic", "basics", "intro", "introduction", "to",
               "using", "concept", "concepts", "advanced", "simple", "fundamentals",
               "of", "and", "in", "with"}

# Hand-written synonym map — grow it when duplicates show up in the Skills tab.
_SYNONYMS = {
    "iteration": "loops", "for loop": "loops", "while loop": "loops",
    "for loops": "loops", "while loops": "loops", "loop": "loops",
    "conditional": "if-else", "conditionals": "if-else", "if statement": "if-else",
    "if else": "if-else", "func": "functions", "funcs": "functions",
    "function": "functions", "var": "variables", "variable": "variables",
    "data type": "data types", "datatype": "data types",
}


def norm_topic(topic):
    """Collapse free-form model topic tags into a stable, comparable key."""
    t = (topic or "general").lower().strip()
    t = re.sub(r"[^a-z0-9\- ]", " ", t)          # drop punctuation
    t = re.sub(r"\s+", " ", t).strip()
    words = [w for w in t.split(" ") if w and w not in _QUALIFIERS]
    t = " ".join(words) or "general"
    return _SYNONYMS.get(t, t)


def band(mastery, attempts):
    """A word, never a naked percentage. Thin data stays honest."""
    if attempts < 3:
        return "new"          # not enough data yet
    if mastery < 0.50:
        return "weak"
    if mastery < 0.80:
        return "developing"
    return "mastered"


def compute(state):
    """Build the DNA dict from every quiz answer recorded so far."""
    topics = {}
    misconceptions = []
    for day, quiz in (state.get("quizzes") or {}).items():
        for a in quiz.get("answers", []):
            key = norm_topic(a.get("topic"))
            r = topics.setdefault(key, {"correct": 0, "total": 0})
            r["total"] += 1
            if a.get("correct"):
                r["correct"] += 1
            elif a.get("confidence") == "allin":
                # high-confidence miss = misconception, highest re-teach priority
                misconceptions.append(key)

    for r in topics.values():
        # Bayesian shrinkage — one question can't swing a small sample wildly.
        r["mastery"] = round((r["correct"] + 1) / (r["total"] + 2), 3)
        r["attempts"] = r["total"]
        r["band"] = band(r["mastery"], r["total"])

    total = sum(r["total"] for r in topics.values())
    correct = sum(r["correct"] for r in topics.values())
    rated = {k: r for k, r in topics.items() if r["attempts"] >= 3}
    ranked = sorted(rated, key=lambda k: rated[k]["mastery"])

    # a misconception clears once the topic reaches the mastered band — otherwise
    # a confident-miss on day 2 would nag the student (and jump the review queue)
    # forever, even after they've re-learned it.
    live_misconceptions = sorted({
        k for k in set(misconceptions)
        if topics.get(k, {}).get("band") != "mastered"
    })

    dna = {
        "topics": topics,
        "total_answered": total,
        "overall_mastery": round(correct / total, 3) if total else 0,
        "weakest": ranked[0] if ranked else None,
        "strongest": ranked[-1] if ranked else None,
        "misconceptions": live_misconceptions,
    }
    dna["notes"] = build_notes(dna)
    return dna


def build_notes(dna):
    """First-person mentor observations — every line anchored to real data."""
    if dna["total_answered"] < 3:
        return "Finish a checkpoint or two and I'll start learning how you learn."

    lines = []
    strong, weak = dna["strongest"], dna["weakest"]
    topics = dna["topics"]

    if strong and topics[strong]["band"] == "mastered":
        lines.append(f"You've genuinely got **{strong}** down — it shows in your quizzes.")
    if dna["misconceptions"]:
        m = dna["misconceptions"][0]
        lines.append(f"Watch **{m}**: you answered confidently but got it wrong, so let's re-nail it — those stick best once fixed.")
    elif weak and weak != strong and topics[weak]["band"] in ("weak", "developing"):
        lines.append(f"**{weak}** is our next mountain — a rematch there is where your biggest gains are.")

    if not lines:
        lines.append("Solid, steady progress across the board. Keep the streak going.")
    return " ".join(lines)


def summary_for_prompt(dna):
    """~2-line block injected into mentor prompts so lessons adapt to the DNA."""
    if not dna or dna["total_answered"] < 3:
        return "No quiz history yet."
    parts = []
    if dna["strongest"]:
        parts.append(f"strong at {dna['strongest']}")
    if dna["weakest"] and dna["weakest"] != dna["strongest"]:
        parts.append(f"weaker at {dna['weakest']}")
    if dna["misconceptions"]:
        parts.append("misconceptions to correct: " + ", ".join(dna["misconceptions"][:3]))
    return "Learner so far: " + "; ".join(parts) + "."
