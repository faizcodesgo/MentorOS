# MentorOS — Professional Audit (flag-only, 4 October 2026)

> **DECISION (Faiz): VOICE = (A) confident mentor. EXECUTE THE ENTIRE AUDIT — all batches A/B/C/D + the voice rename.**
> **STATUS: EXECUTED IN FULL — 4 July 2026.** Batch A (commits `2150bfc`, `9801ce8`), Batch B voice+copy (`df80cb0`), Batch C visual system (`0b6ac67`), Batch D de-clutter + dead code (final commit). Notes: weekly report was THINNED to a one-line dismissible row (not cut); study-reminders button now shows only in the installed PWA or when reminders are already on; combo/crit XP math still runs server-side but the UI no longer advertises it. The multi-user architecture item remains open (deliberately — single-user for now).
> **Execution plan for a fresh session (context was full when approved):**
> - **A (bugs):** guard /api/reset (require JSON confirm + same-origin header; note real fix = auth), validate AI JSON shape in generate_phase/get_lesson/interview_start, bind quiz answers by id, fix int(_current_order) truncation, MAX_CONTENT_LENGTH, remove duplicate manifest.webmanifest.
> - **B (copy) + VOICE A:** rename Quest/Boss Check/Main Quest/Quest Log → Today / Checkpoint / your plan / (plain); delete all reassurance ("never spam never guilt" etc.), neutralize loading/error narration, unify label casing to sentence-case, drop "AI" from tagline. One term per concept.
> - **C (visual):** strip ~80% uppercase-mono labels; named font-size/radius/shadow scales; unify --brand/--accent (delete aliases); add elevation + reduce borders; fix primary-btn hover inversion; kill perpetual orb + glow-hover; add :focus-visible; cap prose at ~65ch; move raw px to --s* scale.
> - **D (declutter):** dashboard = Today + Skill Map only (warm-up→thin row, weekly/saved conditional); cut career chip; thin/cut weekly report; cut explain-it-back; max 1 in-lesson widget; hide reminders in settings; material scope→default+advanced; drop All-Rounder class; mute combo/crit math; DELETE dead code (study_anchor/api/anchor, today_goal, mermaid loader ~80 lines).


Four independent auditors (copy, visual design, features/clutter, code quality) read the real source. Nothing was changed. Verdict: **a genuinely well-built app with real learning-science backing** — what keeps it from feeling like a $1000 pro-team product is (1) a few real bugs, (2) copy that "reassures" like a chatbot, (3) an incompletely-systematized design system, and (4) it has out-run its own "don't overdo it" rule (8+ dashboard cards).

Findings are grouped into approval batches. Execute in any combination.

---

## BATCH A — Real bugs & security (recommend fixing regardless)
1. **`showBanner` is undefined but called on project submit** (`app.js` ~1368) → the "milestone built" celebration throws a ReferenceError at the highest-XP moment. **[BUG]**
2. **`/api/reset` is unguarded** — any anonymous POST wipes all plan/progress/XP (client `confirm()` is not protection). Gate it like `/api/cron/push`. **[RISK]**
3. **Duplicate manifest** — `index.html` links both `manifest.webmanifest` and `manifest.json`; both files exist. Keep one. **[cruft]**
4. **`debug=True`** in the `python app.py` entrypoint → Werkzeug RCE if run directly. Default off. **[RISK]**
5. **Global error handler returns `str(e)` to the browser** — leaks internal detail (Mongo URIs, paths, raw Gemini errors). Return a generic message; log the real one. **[RISK]**
6. **AI-JSON shape not validated** in `generate_phase`/`get_lesson`/`interview_start` — a malformed model response 500s (can brick onboarding). Add the same defensive checks warm-up already has. **[BUG]**
7. **`submit_quiz` grades answers positionally** (no id binding) — fine today, silently corrupts XP/DNA if order ever drifts. **[latent bug]**
8. **`int(_current_order)` truncates a revision's `.5` order** → spaced-review can quietly stop surfacing on a revision day. **[edge bug]**
9. No upload size limit (`MAX_CONTENT_LENGTH` unset) — a huge file is read fully before the 15k cap. **[hardening]**

## BATCH B — Copy that "screams AI" (the reassurance & narration)
The through-line: **confident products state; they don't reassure, apologize, or narrate.**
1. **"Never spam, never guilt"** (reminders) — defending against an accusation nobody made. → "Get a daily reminder when something's due, or your study window opens." *(already approved)*
2. **Focus note** "cheers you on… Staying is on you." → "Keeps your screen awake for the session. It won't block other apps."
3. **"YOUR PERSONAL AI MENTOR"** kicker — leading with "AI" is the tell. → sell the outcome, drop "AI".
4. **"I'll be honest about what's achievable"** (hero) — announcing honesty is what makes it sound generated. → plain promise.
5. **Loading narration** — "Reading it like a mentor…", "Weighing each answer…", "Fresh questions, not repeats…" → neutral: "Reviewing your answers…", "Preparing your questions…".
6. **Welcome-back over-comfort** — "no problem… Nothing lost… goal still on track" (three pats in one line) → one clean sentence.
7. **Error copy** "hit a snag… retrying may help" → "Couldn't finish building your plan. Try again."
8. **Reset** "Start over (wipes plan)" + "Sure?" → "Start over" + "This permanently deletes your plan and progress. Continue?"
9. **Misc**: "Your seat was saved", "on the house", "Short on time?… keeps your streak alive", chatty placeholders ("What should I call you?"), decorative glyphs in copy (✦ ✓ ◆) → move to CSS.
10. **VOICE INCONSISTENCY (biggest):** the same quiz feature is called **"Boss Check"** AND **"Checkpoint"**; "Milestone — Build it" vs "MILESTONE · BUILD IT". Label casing is half ALL-CAPS, half sentence-case. → **needs a voice decision (see below).**

## BATCH C — Visual polish (premium systematization)
1. **Strip ~80% of the UPPERCASE-mono labels** — they're on every field/section (the #1 "AI dashboard" tell). Reserve for 1–2 true dividers/view.
2. **Collapse the font-size sprawl** (~14 ad-hoc rem sizes) into ~5 named steps; same for **radii** (7 values → a scale) and **shadows** (bespoke → `--shadow-1/2/3`).
3. **Unify the token system** — `--brand`/`--accent` and `--gold`/`--xp` are aliases of each other; `--accent-2` secretly equals `--brand` so every "second accent" renders identical blue. Pick one set, delete aliases.
4. **Reduce border-everywhere; add real elevation** — nearly every surface is a 1px outline (outline-pill overload). Introduce subtle shadows + lighter-panel steps.
5. **Fix the primary-button hover inversion** (near-black text flips to white on hover — reads as a glitch).
6. **Kill the perpetual violet "thinking orb"** (two infinite animations, the only violet in the app — an AI-assistant cliché) and colored glow-on-hover.
7. **Add `:focus-visible` rings** to all interactive elements (only inputs have them now).
8. **Cap prose line length (~65ch)** on all reading blocks; unify line-heights.
9. Convert raw px margins to the existing `--s*` spacing scale (dashboard/quiz use raw px, newer components use tokens — two vocabularies).

## BATCH D — Feature de-clutter (flag only, your call)
Core loop to protect: **Today's Quest → stepped lesson → Checkpoint quiz → XP/recap → Skill Map.**
1. **Dashboard: 2 persistent cards only** (Today + Skill Map). Warm-up → thin one-line row; weekly/saved → conditional & lighter. *(60% of the de-clutter)*
2. **Cut the Career-XP chip** — duplicates current XP on a first plan (keep the backend field for later).
3. **Weekly report → cut or thin** — restates recap + skill map; fires ~7× total.
4. **Explain-it-back → cut** — the Viva does self-explanation better and rarer (or keep as the cheaper daily version — trade-off).
5. **In-lesson widgets → max 1/lesson** — currently a 3rd testing mechanic alongside quiz + warm-up.
6. **Study-reminders entry → hide in settings** (not a dashboard footer button) until native.
7. **Material scope radios → default "essentials" + advanced disclosure** (three decisions before any value is heavy at onboarding).
8. **Drop "All-Rounder" class** (dilutes a meaningful choice; plan specced 4).
9. **Mute the combo/crit math** on the quiz (keep the confidence wager — it's the DNA signal).
10. **Dead code to remove:** `study_anchor`/`/api/anchor` chain (dormant, still injected into prompts), `today_goal` (written, never read), the whole **Mermaid loader** (~80 lines + a CDN script the prompts forbid).

## THE ARCHITECTURAL ONE (only if going multi-user)
Every request loads/saves one global `"default"` document with a full-document overwrite — so **two users would share one brain and clobber each other's writes**. Fine for you-as-sole-user; it's the one real blocker before real users. Needs per-user identity + concurrency-safe writes. Flagged, not urgent for dogfooding.

---

## The one decision that unlocks the most: VOICE
The app is half-RPG (Quest, Boss Check, Main Quest, class, rank, shield) and half-serious-mentor. **That inconsistency is the biggest "amateur" tell.** Pick one:
- **(A) Confident mentor** — drop most RPG words; keep only XP/levels/streak as quiet progress. Feels like a premium pro tool.
- **(B) Own the RPG** — commit fully and consistently (one name per thing). Feels like a polished game.
Recommendation: **(A)** for a placement-prep product adults will trust.
