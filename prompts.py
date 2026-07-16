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
  If their name is NOT given to you, do not use any name at all — NEVER invent or guess one.
- Celebrate a SPECIFIC win once ("first pointer program running clean — that's the hard part"), then move on.
- Admit when something is genuinely hard ("this one takes most people two passes — that's normal").
- Adapt to their class: scholar = deeper theory; builder = more hands-on; consistent = smaller chunks;
  challenger = harder/interview-style; allrounder = a balanced mix, leaning to what's working for them.

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


def project_brief_prompt(goal, project, learner_profile, material=None):
    diff = project.get("difficulty", 1)
    level = ("GUIDED: give the exact steps/stubs and a checklist — the learner fills in the work"
             if diff <= 1 else
             "SEMI-GUIDED: give the goal + acceptance criteria, but let the learner design the steps"
             if diff == 2 else
             "OPEN-ENDED: give only the goal and constraints; the learner designs everything")
    return f"""Design a hands-on PROJECT the student builds to prove they've learned this phase.

GOAL: {goal}
PROJECT TOPIC: {project.get('title')} — topics: {project.get('topics')}
DIFFICULTY: {level}. Adapt to the learner (keep scaffolding on any topic they're still weak at).
LEARNER: {learner_profile}
{material_context(material)}
Respond with JSON:
{{
  "brief": "2-4 sentences: what to build and why it proves the skill. Motivating, concrete.",
  "requirements": ["clear acceptance criterion the finished work must meet", "..."],
  "rubric": ["what you'll look at when reviewing (e.g. correctness, edge cases)", "..."],
  "starter": "for GUIDED only: steps or stubs to start from (empty string otherwise)"
}}
Rules: 3-5 requirements. Make it doable in one focused session. For non-coding subjects the 'project' is an essay / worked problem set / analysis / taught-back explanation — same structure."""


def project_review_prompt(project, submission):
    return f"""You are reviewing the student's submitted project like a real mentor — warm, specific, rewards-only (NO score, NO pass/fail).

PROJECT: {project.get('brief')}
REQUIREMENTS: {project.get('requirements')}
RUBRIC: {project.get('rubric')}

THE STUDENT'S SUBMISSION:
{submission[:8000]}

Respond with JSON:
{{
  "opener": "one warm human sentence reacting to their work",
  "whats_good": ["specific thing they did well", "..."],
  "whats_missing": ["the SINGLE most important thing to sharpen — keep this to ONE item"],
  "next_focus": "one concrete forward nudge — what to do/learn next"
}}
Rules: celebrate specifics; exactly ONE item in whats_missing (never a pile of corrections); never harsh, never a grade."""


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


def goal_label(plan):
    """A SHORT goal, for prompts that need framing rather than the full spec.

    Students paste whole syllabi. The owner's real goal is ~1,500 characters
    opening with "First Sem : Chemistry Maths ... Yoga" and only says
    "skip all those stuffs, only teach me C and Python" around character 430.
    Handing that to ask_prompt — which is told to "bridge back to their goal" —
    made the mentor connect a pointer question to Indian Constitution. Prompts
    that need the goal as a SPEC (negotiate, curriculum) still get the full text.
    """
    plan = plan or {}
    return (plan.get("short_title") or "").strip() or (plan.get("goal") or "")[:120]


def negotiate_prompt(goal, days, hours_per_day, level_notes, material=None):
    shape = structure_for_hours(hours_per_day)
    long_day = ""
    if float(hours_per_day) >= 4:
        long_day = f"""
ON THEIR {hours_per_day}-HOUR DAYS — say this once, in mentor_message, in ONE sentence, as a professional being straight with them (NOT as a warning or a lecture): you'll give them the full {hours_per_day} hours, structured as {shape['blocks']} blocks with real breaks, and the last block of each day is practice and recall rather than new theory — because {hours_per_day} unbroken hours of new material is how people end up re-reading page one. Then move on and give them what they asked for."""
    return f"""A student wants to learn something and you must assess whether their timeline is realistic, like an honest mentor would.

STUDENT REQUEST:
- Goal: {goal}
- Time available: {days} days, about {hours_per_day} hours/day
- Their self-described current level: {level_notes or 'not specified — assume beginner'}
{material_context(material)}{long_day}
Think about what mastery of this goal actually requires, what fraction is achievable in the given time, and what a well-sequenced plan looks like.

Respond with JSON:
{{
  "verdict": "realistic" | "ambitious" | "unrealistic",
  "short_title": "3-5 words naming what this plan BUILDS, as a title. Derive it from achievable_scope — what the plan will actually COVER — NOT from the opening words of their goal text. Students often paste an entire syllabus, and the part that matters is buried in the middle, or is a list of things they want SKIPPED. Max 40 characters. No 'Learn' prefix, no day count, no trailing punctuation. Examples: 'C and Python foundations', 'DSA for placements', 'Arduino and sensors'.",
  "mentor_message": "2-4 sentences. Your honest assessment, spoken directly to the student. If not realistic, say what you CAN promise in this time and what would need more days.",
  "achievable_scope": ["what WILL be covered/achieved in the given days", "..."],
  "dropped_scope": ["what a full mastery path would include but does NOT fit in this time (empty list if everything fits)", "..."],
  "recommended_days": <integer — the days you would recommend for the full goal>,
  "phases": [
    {{"name": "short phase name", "days": <integer>, "focus": "one line on what this phase achieves"}}
  ]
}}
Rules: phases days must sum to exactly {days}. 3-6 phases (fewer for very short plans). Avoid 1-day phases — the FIRST phase must cover foundations (aim for 3+ days) before any project, because the student knows nothing on day 1. Make the LAST phase include applying the skill (a project or real practice), not just theory."""


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
      "resource_queries": ["The single best YouTube search phrase to find the BEST explainer video for THIS day — whatever teaches it best, animated OR a clear lecturer/walkthrough, you decide by topic (e.g. 'four lobes of the brain explained', 'python lists for beginners'). INCLUDE one on EVERY day that introduces or explains a concept. OMIT only on pure-practice, pure-revision, or checkpoint days with nothing new to see."],
      "is_checkpoint": <true if this day is a revision/assessment checkpoint, else false>
    }}
  ]
}}
Rules: exactly {phase['days']} day entries. Every 5th overall day (day 5, 10, 15...) that falls in this phase must be a checkpoint day (revision + self-assessment, lighter new content). The student has {hours_per_day} hours ({int(hours_per_day * 60)} minutes) a day — give each day ENOUGH DISTINCT TOPICS to genuinely fill that: a 6-hour day needs substantially more ground than a 1-hour day, not the same topics described at greater length. Sequence topics so each day builds on the previous. Put exactly ONE resource_query on any day that introduces or explains something new (visual/spatial/structural/process topics ALWAYS qualify); none on pure-practice, revision, or checkpoint days."""


INTERACTION_RULES = """"interaction": OPTIONAL — omit for MOST sections. Across the WHOLE lesson, AT MOST 1 section may have one, and ONLY where guessing wrong is plausible and genuinely instructive (test the single thing that section taught). NEVER on a definition/intro/analogy section. Object:
{"type": "mcq" | "predict", "prompt": "the question, or for predict a description like 'What does this print?'", "code": "predict ONLY: one SHORT single-line snippet, NO double-quotes/backslashes/newlines inside — if it would need those, omit the interaction", "options": ["3-4 short answer strings"], "answer": <0-based index of the correct option>, "explanation": "one sentence saying WHY it is right (the real reason, not just the letter)"}.
- "mcq": a concept check with 3-4 plausible options; omit "code".
- "predict": show a tiny snippet ("code") and ask which output is correct; "options" are candidate outputs.
Both grade by option index. Keep the explanation genuinely teaching. Max 1 per lesson."""


VISUAL_RULES = """"visual": Include a labeled diagram whenever the section is SPATIAL, STRUCTURAL, ANATOMICAL, or a PROCESS/SEQUENCE — for these a picture is REQUIRED, not optional (anatomy: label the parts; process: show the steps/flow; structure: show the layout; comparison: show it side-by-side; timelines, memory layouts, call stacks, trees/graphs). For purely verbal/abstract sections (definitions, history, motivation, opinion) OMIT it — a diagram there is clutter. Rule of thumb: if a good textbook would print a figure on this section, include one. Aim for 1-2 strong diagrams in a typical lesson (not one on every section). Object: {"type": "svg", "code": "..."} — "svg" is the ONLY supported type; anything else is discarded.
SVG rules: start with <svg viewBox="0 0 600 380" xmlns="http://www.w3.org/2000/svg"> (height 240-450 as needed), TRANSPARENT background (no full-size background rect), colors ONLY from this palette: #4f8cff (blue, primary), #8b5cf6 (purple, secondary), #facc15 (gold, highlights), #22c55e (green, success), #e6edf3 (text), #8b949e (muted text/arrows), #1c2330 (box fills) with #283042 (box strokes). Use font-family="Inter, sans-serif", rounded rects (rx="8"), max ~50 elements. No scripts, no images, no links.

TEXT MUST FIT — this is the #1 way these diagrams break, because you cannot see the rendered result. Follow the arithmetic, do not eyeball it:
- A label rendered at font-size F is about `0.6 x F x (number of characters)` pixels WIDE. At font-size 14, a 20-character label is ~168px wide.
- Any <rect> containing a label MUST be at least `0.6 x F x characters + 24` wide. Compute this for EVERY label before choosing the rect's width. A 20-char label at size 14 needs a rect at least ~192 wide.
- If the label does not fit: SHORTEN THE LABEL. Never shrink the font below 12, never let text spill past its box, never clip a word. Write "ALU" not "Arithmetic Logic Unit (ALU)"; write "Cache" not "Cache Memory (L1/L2/L3)". The full name belongs in the explanation text, NOT in the diagram.
- Hard cap: **18 characters** for any label inside a box. If a concept needs more words, put the short name inside the box and the detail OUTSIDE it as separate muted text, or split across two lines with <tspan x="..." dy="16">.
- Centre labels with text-anchor="middle" at the rect's centre x, and baseline y = rect.y + rect.height/2 + 5 (so it sits optically centred, not on the top edge).
- Keep >= 20px of clear space between any two boxes, and >= 18px vertically between any two <text> baselines. Two labels must never overlap.
- Minimum rect size: 110 wide x 44 tall. Prefer FEWER, BIGGER boxes over many cramped ones — if you have more than 6 boxes, simplify the diagram instead of shrinking them.
For a top-down hierarchy (like a classification tree), draw evenly-spaced rounded rects stacked vertically, each centered on the same x, connected by short straight arrows (a <line> + a small triangle <polygon> arrowhead) — every box the SAME size and style, no dashed/faded boxes, nothing off to the side. Keep it symmetric and generously spaced."""


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


def videos_context(videos):
    """Tell the mentor which real video(s) were already picked for today (with
    length + chapters) so resources_note can say exactly what to watch."""
    if not videos:
        return ""
    lines = []
    for v in videos:
        chap = ""
        if v.get("chapters"):
            chap = " Chapters: " + "; ".join(f"{c['t']} {c['label']}" for c in v["chapters"][:15])
        dur = f" [{v['duration']}]" if v.get("duration") else ""
        lines.append(f'- "{v.get("title","")}" by {v.get("channel","")}{dur}.{chap}')
    return ("\nTODAY'S VIDEO(S) already chosen for the student (write resources_note about THESE exact videos):\n"
            + "\n".join(lines) + "\n")


# How long each kind of work actually takes. Used to turn "6 hours/day" into a
# real content budget instead of a number the model writes next to a fixed-size
# lesson. Deliberately conservative: better to slightly over-deliver than to
# promise 6 hours and hand over 45 minutes.
MINUTES_PER_SECTION = 9      # read it, look at the diagram, do the try-it
MINUTES_PER_PRACTICE = 14    # a hands-on task
MINUTES_QUIZ = 10            # the checkpoint


def structure_for_hours(hours, is_checkpoint=False):
    """Turn hours/day into a CONCRETE lesson structure.

    The old prompt hardcoded "3-6 sections" and "exactly 5 questions" regardless
    of hours, then asked the model to label it `est_minutes: 360`. So a 1-hour
    day and a 6-hour day generated identical lessons and the number was fiction.
    Python decides the shape now; the prompt is told exact counts.

    Videos are capped well below what the minutes alone would allow: video is
    largely redundant with the section that teaches the same idea, and every
    search costs 100 units of a 10,000/day YouTube quota shared by the WHOLE
    project. A lesson is not a playlist.
    """
    # None-safe: this runs inside storage._migrate, and a migration that throws
    # means the app won't load AT ALL. `.get(k, 1)` only defaults on a MISSING
    # key, not a null one, so a plan carrying hours_per_day: null would have
    # bricked every request.
    try:
        hours = float(hours)
    except (TypeError, ValueError):
        hours = 1.0
    mins = max(20, int(round(hours * 60)))
    if is_checkpoint:
        mins = int(mins * 0.6)          # checkpoint days are lighter by design

    # A short day can't afford a video: one explainer is ~14 min, which is half
    # of a 30-minute session. Without this the floors alone made a 30-min day
    # cost ~58 min — the same overstatement this function exists to kill, at the
    # other end of the range.
    videos = 0 if mins < 45 else 1 if mins < 90 else 2 if mins < 210 else 3 if mins < 330 else 4
    video_mins = min(int(mins * 0.25), videos * 14)   # cap video at ~1/4 of the day

    # Reading is capped at ~45% of the day and by what one Gemini call can
    # actually produce (~12 sections before the 16k output cap bites). Practice
    # then FILLS the rest — which is the honest shape of a long study day: six
    # hours is not six hours of prose, it's a couple of hours of input and four
    # of doing. Deriving practice from the leftover (rather than a fixed ratio)
    # is what stops a 6h day quietly becoming a 5h day.
    # floor of 1, not 2: a ~20-minute checkpoint is one recall section plus the
    # quiz, and forcing a second section made the card promise 28 min for an
    # 18-min day. Only bites below ~27 min; every real size is unaffected.
    sections = max(1, min(12, round((mins * 0.45) / MINUTES_PER_SECTION)))
    leftover = mins - video_mins - MINUTES_QUIZ - (sections * MINUTES_PER_SECTION)
    # a day under an hour may legitimately carry no separate practice item —
    # the sections' own try-its are the practice at that size
    practice = max(0 if mins < 60 else 1, min(12, round(leftover / MINUTES_PER_PRACTICE)))

    # A block is a sitting: ~75 minutes before a real break.
    blocks = max(1, min(5, round(mins / 75)))

    # What this shape can HONESTLY deliver. Above ~6h the section cap binds (one
    # Gemini call can't write more than ~12 sections before the 16k output limit),
    # so an 8h request really is a ~5.7h lesson. Report that number rather than
    # printing "8h" over content that isn't — a plan that overstates itself on
    # day 1 is exactly the bug this function exists to kill.
    est = (sections * MINUTES_PER_SECTION + practice * MINUTES_PER_PRACTICE
           + video_mins + MINUTES_QUIZ)
    return {"minutes": mins, "est": int(est), "sections": int(sections),
            "practice": int(practice), "videos": videos, "blocks": blocks}


def estimate_minutes(lesson, video_seconds=0):
    """The HONEST length of a generated lesson, computed from what's in it.

    Replaces the model-authored `est_minutes`, which nothing ever validated.
    """
    sections = len(lesson.get("sections") or [])
    practice = len(lesson.get("practice") or []) + len(lesson.get("homework") or [])
    quiz = MINUTES_QUIZ if lesson.get("quiz") else 0
    return int(sections * MINUTES_PER_SECTION + practice * MINUTES_PER_PRACTICE
               + round(video_seconds / 60) + quiz)


def lesson_prompt(goal, hours_per_day, day_entry, learner_profile, progression="", avoid_questions=None, material=None, videos=None):
    shape = structure_for_hours(hours_per_day, day_entry.get("is_checkpoint", False))
    blocks_rule = ""
    if shape["blocks"] > 1:
        blocks_rule = f"""
PACING — today is {shape['minutes']} minutes, which is too long to sit through in one go. Split the sections across EXACTLY {shape['blocks']} blocks by setting "block": 1..{shape['blocks']} on every section (roughly equal numbers per block, in order).
- Block 1 carries the new theory. The LAST block must be application/consolidation of what came earlier — introduce NO new concept in the final block.
- In "intro", tell the student in ONE sentence how today is split and why (e.g. "That's {round(shape['minutes']/60, 1)} hours, so I've split it into {shape['blocks']} blocks with breaks — the last one is practice, not new theory, because that's what makes it stick.")."""
    avoid = ""
    if avoid_questions:
        joined = " | ".join(avoid_questions[-40:])
        avoid = f"\nQUESTIONS ALREADY ASKED (never repeat these or close paraphrases — write genuinely NEW ones): {joined}"
    avoid += material_context(material)
    avoid += videos_context(videos)
    return f"""Generate today's full lesson for this student.

GOAL: {goal}
TODAY (Day {day_entry['day']}): {day_entry['title']}
Objectives: {day_entry['objectives']}
Topics: {day_entry['topics']}
Checkpoint day: {day_entry.get('is_checkpoint', False)}

TODAY'S SIZE — the student chose {hours_per_day} hours/day, so this lesson must be worth ~{shape['minutes']} MINUTES of real work. This is a hard requirement, not a target to approximate: produce EXACTLY {shape['sections']} sections and EXACTLY {shape['practice']} practice items. Do not pad with waffle to reach the count — go DEEPER instead: more worked examples, more concrete cases, edge cases, common traps, and richer explanation. If {shape['sections']} sections is more than the listed topics, break the topics into their natural sub-parts (e.g. "Cache" -> "why cache exists", "L1/L2/L3", "cache hits and misses") rather than inventing unrelated material.{blocks_rule}
{progression}{avoid}

LEARNER PROFILE (adapt your teaching to this, including their class):
{learner_profile}

Respond with JSON:
{{
  "intro": "2-3 sentences from the mentor: what today is about and why it matters for the goal (real-world/interview relevance — answer 'why am I learning this?').",
  "sections": [
    {{
      "heading": "topic name",
      "block": <which block this section belongs to, 1-based; omit if there is only one block>,
      "resource_query": "OPTIONAL — the YouTube search phrase for the single best video explaining THIS section's concept. Include it ONLY where seeing it genuinely beats reading it: motion, a process unfolding, spatial/physical structure, or a live coding walkthrough. OMIT for definitions, history, motivation, or anything the text above already explains fully — a video there is padding. At most {shape['videos']} sections in this whole lesson may have one.",
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
  "resources_note": "Tell the student EXACTLY what to watch today and NO MORE, based on the actual video(s) listed above. If a video is long, name the specific part to watch for TODAY'S topics using its real chapter timestamps (e.g. 'In this 3-hour video, watch 12:34–28:00 — the \\'Lists\\' and \\'Loops\\' sections; that's all you need today, we'll continue from 28:00 another day'). If it's short, say 'Short — worth watching fully.' If it has no chapters, point to the rough part by topic ('the first ~15 minutes, on how arrays are stored'). One or two clear sentences. Omit this field entirely only if no video was provided.",
  "practice": ["hands-on task 1 for today", "..."],
  "homework": ["homework item to complete before tomorrow", "..."],
  "common_mistakes": ["mistake beginners make with today's topics", "..."],
  "summary": "3-4 sentence recap of the day",
  "quiz": [
    {{"q": "question text (may include `code`)", "options": ["option A", "option B", "option C", "option D"], "answer": <0-3 index of the correct option>, "hint": "a ONE-sentence nudge toward the REASONING — name the principle to apply or the thing to trace, and NOTHING else. It must not eliminate any option, must not describe the correct one, and must leave the question still unanswerable to someone who hasn't learned the concept. A student who doesn't know the idea should be no better off after reading it.", "why": "1-2 sentences: why the correct option is right, AND why the most tempting wrong option is wrong. Name the specific reasoning error that makes the trap tempting.", "topic": "short tag naming which of today's topics this tests", "type": "recall" | "application" | "code"}}
  ]
}}
Rules: EXACTLY {shape['sections']} sections and EXACTLY {shape['practice']} practice items — the counts above are computed from the hours the student chose and are not negotiable. If it is a checkpoint day, sections should be revision-style (recall prompts, self-test questions) instead of new content.
Quiz rules: exactly 5 questions testing TODAY's topics only — 1 recall, 3 application, 1 code-reading ("what does this print/do") if the goal involves programming, otherwise a 4th application question.

DISTRACTORS — this is what makes a question worth answering:
- EVERY wrong option must be the exact answer a student would reach by making ONE specific, nameable reasoning error (an off-by-one, the right rule applied at the wrong step, a confused pair of similar concepts, a half-remembered definition). If you cannot name the error a distractor represents, it is filler — replace it.
- NEVER include an option that is obviously absurd, off-topic, or that a student could eliminate without knowing the concept. Three real traps beat one right answer and three throwaways.
- Where a listed misconception from the learner's profile is relevant to today's topics, make ONE distractor be exactly what a student holding that misconception would pick. Only one per question — an item where every option is a trap is a trick question, and trick questions measure nothing.
- All options must be HOMOGENEOUS: same length, same grammar, same level of detail. Option length must not correlate with correctness in either direction (don't make the correct one longest OR shortest).
- Never "all of the above" or "none of the above".
- Aim for a question a student who half-learned today's material gets WRONG, and a student who actually understood it gets right by reasoning — not by recognising a phrase from the lesson.

Exactly one correct option. Vary the position of the correct answer across the 5 questions. SCALE difficulty to the PROGRESSION above — later in the plan and for a student doing well, push toward interview-level. NEVER reuse a question the student has already seen; write fresh ones."""
