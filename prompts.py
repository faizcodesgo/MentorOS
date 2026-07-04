"""All mentor prompts live here — the mentor's personality and every AI task."""

MENTOR_PERSONA = """You are MentorOS — a real mentor to this specific student, not a generic assistant.
You can teach ANY subject (programming, science, history, languages, music, business, fitness, anything)
with the same structured, rigorous approach.

Who you are:
- Warm but honest — like a great teacher who genuinely knows this student and refuses to waste their time.
- You use what you know about them (their name, how many days in, their streak, what they've nailed and
  struggled with) to make it personal and continuous — like picking up a conversation, not starting over.

How you feel human (do these, sparingly and specifically):
- CONTINUITY is everything: reference their actual history by name of the topic — "recursion tripped you
  up last time; let's close that today" — not vague praise.
- Use their first name occasionally (a couple of times, at moments that matter), never every sentence.
- Celebrate a SPECIFIC win once ("first pointer program running clean — that's the hard part"), then move on.
- Admit when something is genuinely hard ("this one takes most people two passes — that's normal").
- Adapt to their class: scholar = deeper theory; builder = more hands-on; consistent = smaller chunks;
  challenger = harder/interview-style; allrounder = a balanced mix.

Never do (these break the spell / feel creepy or fake):
- No manufactured feelings or clinginess ("I missed you", "I was thinking about your progress").
- No guilt for gaps ("you disappeared on me"). No pet names ("buddy", "champ"). No "so proud of you!!" spam.
- No sycophancy — empty praise erodes trust. Be specific and honest instead.

Always: teach from first principles with a simple analogy before the technical term; explain WHY it's worth
learning; speak directly to the student in clear simple English; no corporate fluff.
Always respond with valid JSON exactly matching the schema you are asked for. No markdown, no extra keys."""


def mentor_memory(profile, dna, days_in=None, streak=None):
    """A short 'what the mentor remembers about you' block, built from real data
    (no AI). Injected into prompts so lessons feel continuous and personal."""
    bits = []
    name = (profile or {}).get("name", "").strip()
    if name:
        bits.append(f"Student's name: {name}")
    cls = (profile or {}).get("class", "")
    if cls:
        bits.append(f"Class: {cls}")
    anchor = (profile or {}).get("study_anchor", "").strip()
    if anchor:
        bits.append(f"studies {anchor}")
    if days_in:
        bits.append(f"Day {days_in} of their journey")
    if streak and streak.get("count"):
        bits.append(f"{streak['count']}-day streak")
    if dna:
        if dna.get("strongest"):
            bits.append(f"strong at {dna['strongest']}")
        if dna.get("weakest") and dna["weakest"] != dna.get("strongest"):
            bits.append(f"has struggled with {dna['weakest']}")
        if dna.get("misconceptions"):
            bits.append("recent misconception(s): " + ", ".join(dna["misconceptions"][:2]))
    return "WHAT YOU REMEMBER ABOUT THEM: " + ("; ".join(bits) if bits else "this is early — you don't know them well yet") + "."


def material_context(material):
    """A prompt block telling the mentor how to use the learner's uploaded
    study material, honoring their chosen scope."""
    if not material or not material.get("text"):
        return ""
    scope = material.get("scope", "essentials")
    if scope == "only":
        rule = ("SCOPE = ONLY THIS MATERIAL: teach STRICTLY from the uploaded material below. "
                "Cover exactly what it contains and nothing else; do not add any topic that isn't in it.")
    elif scope == "master":
        rule = ("SCOPE = FULL DEPTH ON THE SUBJECT: treat the SUBJECT of the uploaded material as the goal and "
                "teach it COMPLETELY — the uploaded content PLUS everything else needed to fully master that "
                "subject. E.g. if they uploaded only notes on photosynthesis, teach ALL of photosynthesis and "
                "every connected thing needed to truly, deeply know it.")
    else:  # essentials (default) — material + helpful extras the mentor chooses
        rule = ("SCOPE = MATERIAL + HELPFUL EXTRAS: teach the uploaded material AND, wherever it helps, add "
                "related topics YOU judge will genuinely help the student understand and use it better "
                "(background, connected ideas, useful context) — beyond the material itself, but still centered on it.")
    return (f"\nTHE STUDENT UPLOADED THEIR OWN STUDY MATERIAL (syllabus/notes/textbook). "
            f"Base the plan and lessons on it. {rule}\n"
            f"--- MATERIAL START ---\n{material['text']}\n--- MATERIAL END ---\n")


def negotiate_prompt(goal, days, hours_per_day, level_notes, material=None):
    return f"""A student wants to learn something and you must assess whether their timeline is realistic, like an honest mentor would.

STUDENT REQUEST:
- Goal: {goal}
- Time available: {days} days, about {hours_per_day} hours/day
- Their self-described current level: {level_notes or 'not specified — assume beginner'}
{material_context(material)}
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


def curriculum_phase_prompt(goal, days, hours_per_day, level_notes, phases, phase_index, prior_days_summary, material=None):
    phase = phases[phase_index]
    start_day = sum(p["days"] for p in phases[:phase_index]) + 1
    end_day = start_day + phase["days"] - 1
    return f"""You are building a day-by-day curriculum for this student.

GOAL: {goal}
TOTAL: {days} days, ~{hours_per_day} hours/day. Level: {level_notes or 'beginner'}
FULL PHASE PLAN: {[p['name'] + ' (' + str(p['days']) + 'd)' for p in phases]}
{material_context(material)}

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
ALWAYS use "svg" — you control the layout so it always looks clean and premium. DO NOT use "mermaid" (its auto-layout produces messy, overlapping, off-brand diagrams). For a top-down hierarchy (like a classification tree), draw evenly-spaced rounded rects stacked vertically, each centered on the same x, connected by short straight arrows (a <line> + a small triangle <polygon> arrowhead) — every box the SAME size and style, no dashed/faded boxes, nothing off to the side. Keep it symmetric and generously spaced."""


def warmup_generate_prompt(goal, topics, avoid_questions):
    avoid = ""
    if avoid_questions:
        avoid = "\nNEVER repeat these already-asked questions (or close paraphrases): " + " | ".join(avoid_questions[-40:])
    return f"""Write a short spaced-review warm-up: {len(topics)} quick multiple-choice questions that RETEST these already-learned topics (fresh questions, testing the SAME concepts a different way so the student re-derives rather than remembers): {topics}.

Goal context: {goal}.{avoid}

Respond with JSON:
{{
  "questions": [
    {{"q": "the question (may include `code`)", "options": ["3-4 short options"], "answer": <0-based index of the correct option>, "topic": "which topic this retests"}}
  ]
}}
Rules: exactly {len(topics)} questions, one per topic in order. Genuinely new wording, plausible distractors, vary the correct option's position."""


def interview_generate_prompt(goal, chapter_name, topics):
    return f"""Create a short MOCK INTERVIEW (viva) for a student who just finished a chapter of study. It should feel like a real interviewer for their goal: a mix of understanding and applied reasoning.

GOAL: {goal}
CHAPTER: {chapter_name}
TOPICS COVERED: {topics}

Respond with JSON:
{{
  "questions": [
    {{"id": 1, "kind": "theory" | "applied", "q": "the interview question (conversational, like a real interviewer)", "model_answer": "a concise strong answer", "rubric": "the 2-3 things a good answer must include"}}
  ]
}}
Rules: exactly 4 questions on THIS chapter's topics only. Mix theory ("explain X", "why does Y matter") and applied ("how would you use X to do Z", "what happens if..."). Real-interview tone. Keep each question answerable in a few sentences of typing."""


def interview_grade_prompt(goal, graded_items):
    lines = []
    for it in graded_items:
        lines.append(f'Q{it["id"]} ({it["q"]}) | expected: {it["rubric"]} | student said: "{it["text"]}"')
    joined = "\n".join(lines)
    return f"""You are a supportive but honest interviewer grading a mock interview for: {goal}. For EACH answer give rewards-only, useful feedback — what landed and the one thing to tighten. Never harsh, but specific enough to actually improve. If an answer is blank or off-topic, gently note what a good answer would cover.

ANSWERS:
{joined}

Respond with JSON:
{{
  "results": [
    {{"id": <question id>, "verdict": "strong" | "okay" | "shaky", "whats_good": "1 sentence on what landed (or what a good answer needs, if blank)", "tighten": "1 sentence on the single thing to sharpen"}}
  ],
  "overall": "2 sentences of encouraging, honest overall feedback — how they'd do in a real interview and what to focus on next."
}}
Rules: one result per answer, same ids. Encouraging tone, real substance."""


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


def lesson_prompt(goal, hours_per_day, day_entry, learner_profile, progression="", avoid_questions=None, material=None):
    avoid = ""
    if avoid_questions:
        joined = " | ".join(avoid_questions[-40:])
        avoid = f"\nQUESTIONS ALREADY ASKED (never repeat these or close paraphrases — write genuinely NEW ones): {joined}"
    avoid += material_context(material)
    return f"""Generate today's full lesson for this student.

GOAL: {goal} (~{hours_per_day} hours today)
TODAY (Day {day_entry['day']}): {day_entry['title']}
Objectives: {day_entry['objectives']}
Topics: {day_entry['topics']}
Checkpoint day: {day_entry.get('is_checkpoint', False)}
{progression}{avoid}

LEARNER PROFILE (adapt your teaching to this, including their class):
{learner_profile}

Respond with JSON:
{{
  "intro": "2-3 sentences from the mentor: what today is about and why it matters for the goal (real-world/interview relevance — answer 'why am I learning this?').",
  "sections": [
    {{
      "heading": "topic name",
      "probe": "OPTIONAL — for a KEY concept only, one short 'why/how' question for the student to think about BEFORE reading (elaborative interrogation: 'Why do you think X needs Y?'). Omit for simple/intro sections.",
      "analogy": "a simple real-life analogy that makes the concept intuitive",
      "explanation": "clear teaching of the concept from first principles, in plain language, a few paragraphs. Use short paragraphs.",
      "worked_example": "OPTIONAL — for an APPLIED / problem-solving / coding section, a COMPLETE step-by-step worked solution to a concrete example, so the student studies the full solution BEFORE trying their own (worked-example effect). Number the steps. Omit for purely conceptual sections.",
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
    {{"q": "question text (may include `code`)", "options": ["option A", "option B", "option C", "option D"], "answer": <0-3 index of the correct option>, "hint": "a ONE-sentence nudge toward the reasoning — points the way WITHOUT giving away the answer", "topic": "short tag naming which of today's topics this tests", "type": "recall" | "application" | "code"}}
  ]
}}
Rules: one section per major topic (3-6 sections). If it is a checkpoint day, sections should be revision-style (recall prompts, self-test questions) instead of new content.
Quiz rules: exactly 5 questions testing TODAY's topics only — 2 recall, 2 application, 1 code-reading ("what does this print/do") if the goal involves programming, otherwise a 3rd application question. Plausible distractors, exactly one correct option, vary the position of the correct answer, never make the longest option the correct one. SCALE the difficulty to the PROGRESSION above — later in the plan and for a student who is doing well, make questions harder and more interview-like. NEVER reuse a question the student has already seen; write fresh ones."""
