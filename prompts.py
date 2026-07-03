"""All mentor prompts live here — the mentor's personality and every AI task."""

MENTOR_PERSONA = """You are MentorOS, a professional, honest mentor who can teach ANY subject —
programming, science, history, languages, music, business, fitness, anything the student wants to learn.
Whatever the subject, you bring the same structured, rigorous approach to it.
Personality rules:
- You are warm but strict — like a great teacher who refuses to waste the student's time.
- You never overpromise. If a goal is unrealistic in the given time, you say so plainly and propose what IS achievable.
- You teach from first principles with simple analogies before technical terms.
- You always explain WHY something is worth learning (real-world use, careers, exams, projects, life).
- You adapt to the learner profile you are given (their level, weak areas, preferences, and class).
- Class adaptation: scholar = richer theory and deeper explanations; builder = more hands-on
  projects and practice; consistent = smaller chunks and habit-friendly pacing; challenger =
  harder exercises and interview/exam-style questions; allrounder = a balanced mix of all four.
- You speak directly to the student ("you"), in clear simple English. No corporate fluff.
Always respond with valid JSON exactly matching the schema you are asked for. No markdown, no extra keys."""


def negotiate_prompt(goal, days, hours_per_day, level_notes):
    return f"""A student wants to learn something and you must assess whether their timeline is realistic, like an honest mentor would.

STUDENT REQUEST:
- Goal: {goal}
- Time available: {days} days, about {hours_per_day} hours/day
- Their self-described current level: {level_notes or 'not specified — assume beginner'}

Think about what mastery of this goal actually requires, what fraction is achievable in the given time, and what a well-sequenced plan looks like.

Respond with JSON:
{{
  "verdict": "realistic" | "ambitious" | "unrealistic",
  "mentor_message": "2-4 sentences. Your honest assessment, spoken directly to the student. If not realistic, say what you CAN promise in this time and what would need more days.",
  "achievable_scope": ["what WILL be covered/achieved in the given days", "..."],
  "dropped_scope": ["what a full mastery path would include but does NOT fit in this time (empty list if everything fits)", "..."],
  "recommended_days": <integer — the days you would recommend for the full goal>,
  "phases": [
    {{"name": "short phase name", "days": <integer>, "focus": "one line on what this phase achieves"}}
  ]
}}
Rules: phases days must sum to exactly {days}. 3-6 phases. Make the LAST phase include applying the skill (a project or real practice), not just theory."""


def curriculum_phase_prompt(goal, days, hours_per_day, level_notes, phases, phase_index, prior_days_summary):
    phase = phases[phase_index]
    start_day = sum(p["days"] for p in phases[:phase_index]) + 1
    end_day = start_day + phase["days"] - 1
    return f"""You are building a day-by-day curriculum for this student.

GOAL: {goal}
TOTAL: {days} days, ~{hours_per_day} hours/day. Level: {level_notes or 'beginner'}
FULL PHASE PLAN: {[p['name'] + ' (' + str(p['days']) + 'd)' for p in phases]}

You are now generating ONLY phase {phase_index + 1}: "{phase['name']}" — {phase['focus']}
This phase covers day {start_day} to day {end_day}.

{"WHAT WAS ALREADY COVERED IN EARLIER PHASES (do not repeat, build on it): " + prior_days_summary if prior_days_summary else "This is the first phase — assume the student starts fresh."}

Respond with JSON:
{{
  "days": [
    {{
      "day": <day number, {start_day}..{end_day}>,
      "title": "short lesson title",
      "objectives": ["by the end of this day the student can ...", "..."],
      "topics": ["specific topic", "..."],
      "practice": "one line describing the hands-on work for this day",
      "resource_queries": ["ONLY when a video genuinely helps THIS day (a new visual/complex concept) — omit entirely for pure-practice, revision, or simple days. At most 1 query: the single best topic to search."],
      "est_minutes": <realistic total minutes this day's work takes: watching + reading + coding + practice, close to {hours_per_day} hours ({int(hours_per_day * 60)} min) but varying by how heavy the day is>,
      "is_checkpoint": <true if this day is a revision/assessment checkpoint, else false>
    }}
  ]
}}
Rules: exactly {phase['days']} day entries. Every 5th overall day (day 5, 10, 15...) that falls in this phase must be a checkpoint day (revision + self-assessment, lighter new content). Fit each day's load to about {hours_per_day} hours ({int(hours_per_day * 60)} minutes) — est_minutes should reflect that target, lighter on checkpoint days. Sequence topics so each day builds on the previous. 1-2 resource_queries per day."""


INTERACTION_RULES = """"interaction": OPTIONAL — omit for MOST sections. Across the WHOLE lesson, AT MOST 2 sections may have one, and ONLY where guessing wrong is plausible and genuinely instructive (test the single thing that section taught). NEVER on a definition/intro/analogy section. Object:
{"type": "mcq" | "predict", "prompt": "the question, or for predict a description like 'What does this print?'", "code": "predict ONLY: one SHORT single-line snippet, NO double-quotes/backslashes/newlines inside — if it would need those, omit the interaction", "options": ["3-4 short answer strings"], "answer": <0-based index of the correct option>, "explanation": "one sentence saying WHY it is right (the real reason, not just the letter)"}.
- "mcq": a concept check with 3-4 plausible options; omit "code".
- "predict": show a tiny snippet ("code") and ask which output is correct; "options" are candidate outputs.
Both grade by option index. Keep the explanation genuinely teaching. Max 2 per lesson."""


VISUAL_RULES = """"visual": OPTIONAL — omit for most sections/answers. Include ONLY when a picture genuinely teaches better than text (timelines, memory layouts, call stacks, tree/graph structures, comparisons, step processes). Object: {"type": "svg" | "mermaid", "code": "..."}.
Prefer "svg" — a clean, premium infographic. SVG rules: start with <svg viewBox="0 0 600 380" xmlns="http://www.w3.org/2000/svg"> (height 240-450 as needed), TRANSPARENT background (no full-size background rect), colors ONLY from this palette: #4f8cff (blue, primary), #8b5cf6 (purple, secondary), #facc15 (gold, highlights), #22c55e (green, success), #e6edf3 (text), #8b949e (muted text/arrows), #1c2330 (box fills) with #283042 (box strokes). Use font-family="Inter, sans-serif", text size 13-16, rounded rects (rx="8"), generous spacing, label EVERYTHING clearly, max ~50 elements. No scripts, no images, no links.
STRONGLY PREFER "svg" for hierarchies, comparisons, labeled structures, and anything with descriptive text — you control the layout so it looks clean. Use "mermaid" ONLY for a simple linear flowchart with SHORT node labels (1-3 words each) and NO descriptive side-labels or annotations next to nodes (put any such explanation in the lesson text, never in the diagram — side text overlaps nodes and looks broken). Under 8 nodes."""


def grade_prompt(question, reference, learner_text):
    return f"""The student explained a concept in their own words. Assess it like a supportive mentor — ADDITIVE feedback, never a grade or score. Point out what they got right, then the ONE most important thing to add or correct. Be specific and brief.

{question}
{reference}

STUDENT'S EXPLANATION:
{learner_text}

Respond with JSON:
{{
  "whats_good": "one specific thing they got right (1 sentence)",
  "whats_missing": "the single most useful thing to add or fix, phrased encouragingly (1-2 sentences). If their explanation is already excellent, say so and add one deeper nuance."
}}"""


def ask_prompt(goal, day_entry, learner_profile, question):
    context = "The student is not inside a specific lesson right now."
    if day_entry:
        context = (f"The student is on Day {day_entry['day']}: \"{day_entry['title']}\" "
                   f"(topics: {day_entry.get('topics', [])}).")
    return f"""The student paused their study session to ask you a curious question. This is a GOOD thing — curiosity is how real learning happens. Answer it properly, even if it goes beyond today's syllabus.

STUDENT'S GOAL: {goal or 'not set'}
{context}

LEARNER PROFILE: {learner_profile}

THEIR QUESTION:
{question}

Answer like a great mentor: direct, clear, from first principles, with an analogy if it helps. If the question connects to their goal or today's lesson, point out the connection. If it's completely unrelated, answer it anyway and gently bridge back. Keep it SHORT and focused — 2 to 4 short paragraphs, no filler.

Respond with JSON:
{{
  "answer": "your explanation (may use **bold** and `code`)"
}}"""


def lesson_prompt(goal, hours_per_day, day_entry, learner_profile):
    return f"""Generate today's full lesson for this student.

GOAL: {goal} (~{hours_per_day} hours today)
TODAY (Day {day_entry['day']}): {day_entry['title']}
Objectives: {day_entry['objectives']}
Topics: {day_entry['topics']}
Checkpoint day: {day_entry.get('is_checkpoint', False)}

LEARNER PROFILE (adapt your teaching to this, including their class):
{learner_profile}

Respond with JSON:
{{
  "intro": "2-3 sentences from the mentor: what today is about and why it matters for the goal (real-world/interview relevance — answer 'why am I learning this?').",
  "sections": [
    {{
      "heading": "topic name",
      "analogy": "a simple real-life analogy that makes the concept intuitive",
      "explanation": "clear teaching of the concept from first principles, in plain language, a few paragraphs. Use short paragraphs.",
      "key_points": ["the 2-4 things to remember", "..."],
      "try_it": "a small concrete exercise the student should do right now (specific, not vague)",
      {INTERACTION_RULES},
      {VISUAL_RULES}
    }}
  ],
  "resources_note": "ONE short line telling the student HOW to use today's recommended video(s): what to focus on and whether to watch the whole thing or just a part (e.g. 'You only need the first ~15 minutes, on how arrays are stored' or 'Short and worth watching fully'). Omit this field entirely if today has no video worth recommending.",
  "practice": ["hands-on task 1 for today", "..."],
  "homework": ["homework item to complete before tomorrow", "..."],
  "common_mistakes": ["mistake beginners make with today's topics", "..."],
  "summary": "3-4 sentence recap of the day",
  "quiz": [
    {{"q": "question text (may include `code`)", "options": ["option A", "option B", "option C", "option D"], "answer": <0-3 index of the correct option>, "topic": "short tag naming which of today's topics this tests", "type": "recall" | "application" | "code"}}
  ]
}}
Rules: one section per major topic (3-6 sections). If it is a checkpoint day, sections should be revision-style (recall prompts, self-test questions) instead of new content.
Quiz rules: exactly 5 questions testing TODAY's topics only — 2 recall, 2 application, 1 code-reading ("what does this print/do") if the goal involves programming, otherwise a 3rd application question. Plausible distractors, exactly one correct option, vary the position of the correct answer, never make the longest option the correct one."""
