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
      "resource_queries": ["a YouTube search query for the single best video topic today", "..."],
      "is_checkpoint": <true if this day is a revision/assessment checkpoint, else false>
    }}
  ]
}}
Rules: exactly {phase['days']} day entries. Every 5th overall day (day 5, 10, 15...) that falls in this phase must be a checkpoint day (revision + self-assessment, lighter new content). Fit each day's load to ~{hours_per_day} hours. Sequence topics so each day builds on the previous. 1-2 resource_queries per day."""


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
      "try_it": "a small concrete exercise the student should do right now (specific, not vague)"
    }}
  ],
  "practice": ["hands-on task 1 for today", "..."],
  "homework": ["homework item to complete before tomorrow", "..."],
  "common_mistakes": ["mistake beginners make with today's topics", "..."],
  "summary": "3-4 sentence recap of the day"
}}
Rules: one section per major topic (3-6 sections). If it is a checkpoint day, sections should be revision-style (recall prompts, self-test questions) instead of new content."""
