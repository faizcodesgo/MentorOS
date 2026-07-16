# MentorOS — Handoff

_Last updated: 16 July 2026. Paste this into a new chat AND use it as the
new-machine setup guide. Read `mentor-app-project.md` +
`mentoros-council-findings-jul16.md` in the memory folder alongside it._

---

## 0. TL;DR — the two things GitHub does NOT have (carry these over!)

Everything else is in GitHub or the cloud. **These are gitignored and exist ONLY
on this laptop — copy them somewhere safe before wiping it:**

1. **`.env`** — every secret key (Gemini, YouTube, VAPID push, cron secret).
   Lives at `C:\Users\user\Desktop\mentoros\MentorOS\.env`.
2. **`MentorOS - Google Play package/`** — the Android **signing keystore +
   passwords**. Lose it and you can never update the installed Android app.

Lose the repo? Re-clone. Lose these two? Gone forever.

**NOTE the path changed:** the repo now lives at
`C:\Users\user\Desktop\mentoros\MentorOS` (nested one level — `mentoros/`
contains `MentorOS/` and `MentorOS - Google Play package/`).

---

## 1. What MentorOS is

A personal AI learning-mentor web app. Set a goal + duration; it negotiates
honestly, generates a day-by-day curriculum, teaches stepped lessons (diagrams,
best YouTube video, what-part-to-watch), quizzes you with confidence wagers,
runs spaced-review warm-ups, tracks mastery ("Learning DNA"), runs mock
interviews, assigns projects it reviews, and keeps you consistent (streak, XP,
Study mode). Owner: **Faiz** — beginner dev, sole user, prepping for RVCE CSE
(Mechanical diploma → CSE lateral entry via DCET).

**Status: live, installed on the owner's phone as a sideloaded TWA.**

---

## 2. Where everything lives (all cloud — laptop-independent)

- **GitHub:** https://github.com/faizcodesgo/MentorOS (branch `main`)
- **Live:** https://mentoros-c4ht.onrender.com (Render free, auto-deploys `main`)
- **DB:** MongoDB Atlas (`MONGO_URI` env on Render). **M0 has NO backups.**
- **Render env:** `GEMINI_API_KEY`, `YOUTUBE_API_KEY`, `MONGO_URI`,
  `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL`, `CRON_SECRET`.
  Optional: `GEMINI_THINKING` (default 0), `GEMINI_MODEL`.
- **UptimeRobot:** pings `/healthz` every 5 min (keeps Render warm). Second
  monitor on `/api/cron/push?key=…` fires the daily reminder.
- **Local `.env` has `MONGO_URI_BACKUP`, NOT `MONGO_URI`** — that is deliberate.
  `storage.py` switches to Mongo whenever `MONGO_URI` is set, so that name in a
  local `.env` makes `python app.py` connect to **production** and every local
  test rewrite the real plan. Local dev = `mentoros_data.json`. Render keeps its
  own `MONGO_URI`; the deploy is unaffected.
- **`python backup.py`** dumps prod to the Desktop (read-only). Atlas M0 has NO
  automated backups and every save is a whole-document replace — run it before
  touching `storage.py`, and now and then regardless.

---

## 3. Setting up on a NEW laptop

1. Install **Python 3.12** (Node is NOT needed — plain JS, no build step).
2. `git clone https://github.com/faizcodesgo/MentorOS.git`
3. Copy `.env` in from the old laptop (§0).
4. `pip install -r requirements.txt`
5. `python app.py` → http://localhost:5000
6. Copy the `MentorOS - Google Play package/` folder somewhere safe.
7. First `git push` pops Git Credential Manager — approve once.

Preview config for Claude Code lives at `Desktop/.claude/launch.json`
(name `mentoros`, port 5000, autoPort). **Flask debug is OFF, so the dev server
does NOT auto-reload — restart it after editing Python or you'll test stale code.**
(This bit me during the 16 Jul session.)

---

## 4. Deploy loop

Edit → `git add -A` → `git commit -F msgfile` → `git push` → Render
auto-redeploys `main` (~1-2 min). Verify with a **read-only** curl.

**NEVER probe `/api/plan/init` against production** — it is the endpoint that
replaces the plan. Test destructive endpoints locally only.

---

## 5. Architecture + file map

Flask + vanilla JS, no framework, no build. One JSON state doc per user
(`mentoros_data.json` local; MongoDB in prod). Gemini free tier over plain REST.
Schema `SCHEMA = 13` in `storage.py` with an idempotent `_migrate()` chain.

- `app.py` — all routes (~1100 lines)
- `public/app.js` — ALL frontend (~1750 lines, one file)
- `public/index.html` — every screen (`<section class="view">`)
- `public/style.css` — the design system (dark, one blue accent)
- `prompts.py` — mentor persona + every AI prompt
- `storage.py` — load/save + migrations + **snapshot/restore**
- `dna.py` — Learning DNA (mastery from quiz data, no AI)
- `reviews.py` — spaced-review ladder · `push.py` — web push + cron
- `gemini.py` — REST client (model fallback, JSON repair, thinking budget)
- `youtube.py` — video search + duration + chapters
- `PHASE5.md` — Android/TWA runbook · `AUDIT.md` — the July 4 audit

---

## 6. Gotchas (save yourself the pain)

- **Flask dev server does NOT auto-reload** (debug off). Restart after Python edits.
- **PowerShell + git commit messages:** quotes/apostrophes break arg parsing.
  Write the message to a file, use `git commit -F file`.
- **`git commit -am` SKIPS NEW files.** Always `git add -A`.
- **Never `git add -A` with the keystore present** (it's gitignored now).
- **`gemini-2.0-flash` has zero free quota** — removed. 2.5-flash → 2.5-flash-lite.
- **Render runs UTC** — anything time-based must use the user's tz offset.
- **Preview screenshots time out** — verify via DOM/`javascript_tool` eval instead.
- **YouTube `search.list` costs 100 quota units**; free cap is 10,000/day.
  A video per section on a 6-section lesson = 600/lesson ≈ **16 lessons/day for
  the WHOLE project** (quota is per-project, not per-user).
- **Never project fields out of a Mongo doc you then `replace_one` back** —
  it permanently deletes everything you projected away (e.g. all lessons).

---

## 7. What changed on 16 July 2026 (five-LLM council + two batches)

### Batch 0 — `ffc8e68` — stop the data-loss path, then make it fast
- **`/api/plan/init` had NO guard.** It cleared progress/lessons/quizzes/dna/
  streak on any POST, saved by whole-doc replace, no backups anywhere. A
  double-submit or stale tab **permanently destroyed the 50-day plan**. Now
  409s unless `{replace: true}`.
- **`storage.snapshot()` + `/api/restore`** — any wipe (replace or start-over) is
  now recoverable. This is the app's only backup. Don't remove it.
- **`/api/cron/push` failed OPEN** (`if secret and ...`) → now fails closed.
- **Gemini `thinkingConfig` was never set**, so 2.5-flash ran dynamic thinking on
  every call, billed as output + wall-clock. **Measured: lesson generation
  38.5s → 18.8s (2× faster), same structure.** Tunable via `GEMINI_THINKING`,
  with a self-heal that drops the field if a model 400s on it.
  → **The "Gemini free tier is just slow" claim in older notes was WRONG.**
- **gunicorn ran ONE sync worker**, so a 15-60s lesson gen blocked every other
  request (part of the bookmark lag). Now `--workers 2 --threads 4`.

### Batch 1 — `d7345aa` — make the mechanics honest
- **The confidence wager was mathematically broken.** Correct paid `10×wager`,
  wrong paid a flat `2` → `EV(certain) − EV(guessing) = 10p > 0` for all p:
  "Certain" strictly dominated and the signal was noise. Worse, `dna.py` flags a
  high-confidence miss as a misconception, so rational play made **every** wrong
  answer a phantom misconception, poisoning the skill map + review queue.
  Now Gardner-Medwin CBM under `2x+12`: **guessing 14/12, fairly sure 16/8,
  certain 18/0** — honest reporting is XP-optimal at every level, nothing is ever
  subtracted, and the chips show the odds. Combo is a flat end-of-run bonus
  (multiplying the payoff destroyed the thresholds).
  **`PAYOFF` in `app.py` and `app.js` MUST stay in step.**
- **The streak counted activity days, not consecutive days** (`max(count,1)` on a
  gap = no-op; nothing ever reset it). Now breaks honestly; `best` is permanent;
  one earned shield covers ONE missed day.
- **`pace-check` paid +50 XP + a shield for being away**, re-armed daily while
  `days_away` was measured from the last *completed* day → **infinite XP farm**
  (this is how Faiz hit LV3 without studying). Removed. It also never actually
  re-paced anything despite saying so.
- **XP faucets closed:** focus (+30/call — and the client ends a session on every
  navigate-away), explain (+20/call), warmup (+15/call) — all now guarded.
- **`warmup/submit` trusted the CLIENT's `correct`**, feeding DNA + the review
  ladder. Server now caches what it served and grades it.
- **Hints tracked** → hinted-correct = half credit toward mastery (topic returns
  in a warm-up). **No XP penalty** — penalising help-seeking causes help
  avoidance, which is the real failure mode.
- **`.quiz-feedback` borrowed the TOAST keyframe** (`translate(-50%)`) → text
  shoved half its width off-screen ("Correct" → "rect"). Own keyframe now.
- **`#view-quiz` had no exit** (only view in the app). Added.
- **Built `#view-result`** — "See results" previously led to no results. Score,
  XP ledger, level meter, and a **per-question review with `why`**. That review
  never existed; the answer was discarded after ~1s. It's also the prerequisite
  for harder distractors (plausible traps without feedback teach the mistake).
- **Quiz prompt rewritten**: every distractor must encode a nameable reasoning
  error; options homogeneous; DNA misconceptions feed one distractor; no filler.
- **Bookmarks optimistic** (were: POST + full state refetch = the 4-5s lag).
- **Android back** closes the Ask sheet → view → app. There was **zero** History
  API use anywhere. `show()` is the choke point; `suppressHistory` guards the
  popstate re-entry. Lesson steps deliberately get NO history entry.
- **Recap ⇄ Full session** segmented control on finished days.
- **`/api/ask` explorations capped at 10/lesson** — appended forever at 1-3KB
  inside the ONE doc every request rewrites, against Mongo's 16MB hard limit.
- **Topbar** no longer wraps into the logo at 360px; safe-area inset added.

---

### Batch 3a — `cc47be8` — the hours are real, videos are per-topic
- **The 6-hours bug.** `prompts.py` hardcoded "3-6 sections" and "exactly 5
  questions" regardless of hours, then asked the model to label it
  `est_minutes: 360`. Nothing ever read that number. `structure_for_hours()`
  now computes sections/practice/videos/blocks in **Python** and the prompt gets
  exact counts as a hard requirement ("go deeper, don't pad"). `est_minutes` is
  derived twice — from the shape at plan time, from real content + real video
  durations at lesson time.
  **MEASURED: 1h → 3 sections / 79 min / 16k chars; 6h → 14 sections / 15
  practice / 5 blocks / 346 min / 42k chars.** Both were ~45 min before.
  Fits in ONE call (~10.5k of 16k).
- **Long days are blocked**, not just longer: sections carry `block`, the step
  engine inserts a real Break step, the last block is consolidation only, and
  the mentor explains the split once. Above ~6h the section cap binds, so an 8h
  ask honestly reports ~5h42m rather than printing "8h" over a 5h lesson.
- **Per-section videos** (`resource_query` on the section), fetched AFTER
  generation (sections don't exist before it), fanned out in parallel, capped by
  `structure_for_hours`, with a search-link fallback. One day-level video is
  kept so `resources_note` keeps its what-to-watch guidance.
  **Quota reality: `search.list` = 100 units of 10,000/day for the WHOLE
  project.** That's why videos are capped, not per-section-unconditional.

### `938c70b` — Batch 4a: the dashboard, and the 1,500-char goal
- The owner's real `plan.goal` is **~1,471 characters** — his whole pasted
  syllabus. `.kicker` (12px/600/`--brand`, a class for 2-3 word labels) rendered
  it as ~530px of bold blue above the title. That is why the Today card was 9th.
- **Never truncate that goal to a prefix.** Its first 50 chars are
  "First Sem : Chemistry Maths PLC(…" — the subjects he asked to SKIP. The real
  sentence is at ~char 600. Prefixes are worse than useless here.
- `short_title` (≤40) now comes from negotiate, derived from `achievable_scope`.
  **Migration v15 does not guess**: tidy goal → itself; syllabus → `""` → UI says
  "Your plan" + a rename button (`POST /api/plan/title`). A generic correct label
  beats a specific wrong one.
- Measured on 360×640 with his real string: goal 530px→**29px**, "Start today"
  9th element→**455px (above the fold)**, blue elements 7→**1**.
- **New `#view-plan`** — `achievable_scope`/`dropped_scope` were computed, shown
  once on the negotiate screen, and thrown away (the client sent only phases +
  mentor_message). They're the promise he accepted and his "skip all those
  stuffs" receipt. Stored + shown, with per-phase progress and the verbatim goal
  (collapsed; NEVER truncated in storage — it's the contract).
- **`prompts.goal_label()`** — `ask_prompt` got the full syllabus AND is told to
  "bridge back to their goal", so a pointer question was bridged back to Yoga and
  Indian Constitution. Six framing prompts now get the short goal; negotiate +
  curriculum keep the FULL text (his "Module 1 — CPU — RAM" IS the spec). This
  was a **quality** bug, not the token cost (~$1/year).
- `#inGoal` was a single-line `<input>` — he pasted 1,471 chars into a ~40-char
  box. Now a textarea, `maxlength=2000` (his paste WORKS — don't break it),
  counter past 1,200, loud toast instead of silent truncation.
- `#levelChip` was a byte-identical copy of the topbar chip; deleted,
  `animateXpChip` retargeted to the topbar. **Topbar innerHTML is built BEFORE
  the animation** — rewriting it after wipes the count-up mid-flight.
- `.btn { transition: background }` (later in the file, equal specificity)
  REPLACED the shared `transition: transform,…` → every button snapped instead of
  pressing. One deleted line, app-wide.
- Ask sheet: `#explorations` sat ABOVE the textarea, so each answer pushed the
  input down — **that**, not thread length, was "the conversation is too long".
  Flex column, composer pinned, history scrolls, newest first.

### `6b66a6b` — real logo + est_minutes backfill (schema 14)
Icons generated from `logo.jpeg` (mark auto-detected, luminance-keyed onto
`--bg`, 22% maskable safe zone). Schema 14 recomputes `est_minutes` on plans
built before the hours fix — his live plan's day 1 went 180 (invented) → 342.

### `4f3dc91` — diagram labels no longer overflow their boxes
Reported from real use (a CPU diagram printing "Control Unit (CU" across
"Arithmetic Logic Unit"). Two halves, because **neither works alone**:
1. `VISUAL_RULES` now gives the model *arithmetic* instead of adjectives: a
   label at font-size F is ~`0.6*F*chars` wide; a rect holding it must be that
   + 24; if it won't fit, **shorten the label** ("ALU", not "Arithmetic Logic
   Unit (ALU)" — the full name belongs in the prose). 18-char cap in a box.
2. `fitSvgText()` (app.js) measures the **actual rendered text** after
   insertion, finds the tightest rect the label sits in, steps the font down,
   and squeezes with `textLength` as a last resort.

**Half 2 is not belt-and-braces.** Verified against live Gemini: the model still
emits 29-char labels despite the explicit cap, so the prompt alone would NOT
have fixed it. The browser can measure; it gets the final say. Don't delete
`fitSvgText` thinking the prompt covers it.

---

## 8. What is NOT done (the rest of Faiz's 16 Jul list)

**Batch 2 — multi-user accounts: BUILT AND LIVE (16 Jul, `813d20f`).**
Superseded the NO-GO once a real backup existed. Kept below for the reasoning.

**HOW IT WORKS NOW**
- The user resolves INSIDE `storage.py` from `flask.g`, so `load_state()` /
  `save_state()` kept their signatures — **all ~54 call sites needed ZERO edits**.
- **`storage._uid()` RAISES; it never defaults.** Do not "fix" this with a
  fallback: that turns a missed route into silently reading someone else's plan.
- `before_request` 401s every `/api/` route outside `OPEN_PATHS`. Verified: all
  23 gated routes 401 without an account.
- `pw_hash` lives in the **`users` collection, never in state** — `/api/state`
  serialises the whole state dict to the browser.
- `_id` = lowercased name → uniqueness is structural (no index to forget).
- `SECRET_KEY` needs **no manual env var**: generated once and persisted
  (`mentoros.config` in prod, `mentoros_data/_secret.txt` locally), because
  Render free spins down at 15 min and a boot key would log everyone out daily.
  Boot degrades to a temporary key rather than dying if the DB is unreachable.
- **`LEGACY_OWNER`** (env, default `faiz`) decides who inherits the pre-accounts
  `default` doc. NOT "first signup" — the app is on a public URL and a bot could
  have claimed his 50 days. `claim_legacy_state()` re-keys **both** `default`
  AND `default__backup`, copying and never moving; the legacy docs stay forever.
- The cron has no session by nature: it iterates `notif_user_ids()` and writes
  back ONLY the notifications subtree via `$set`, so it can't race a user's save.
- `legacy_waiting` on `/api/auth/me` puts a line on the signup screen so the
  owner doesn't think his plan vanished.
- **No password reset** (no mail server). Forgotten password = edit Atlas by hand.

**`python backup.py`** dumps prod (read-only) — reads `MONGO_URI_BACKUP`, NOT
`MONGO_URI`, because that name in a local `.env` makes `python app.py` write to
PRODUCTION. Owner's dumps live in `Desktop/mentoros/.claude/` (outside the repo).

---

**The original NO-GO reasoning (kept — the traps it found were real):**
- **`storage.snapshot()` keys the backup `f"{USER_ID}__backup"`** (`storage.py`).
  The moment `USER_ID` becomes `_uid()`, `load_snapshot()` looks for
  `<newuid>__backup` and the existing `default__backup` becomes **unreachable by
  any code path** (`_uid()` must raise, never default). So the auth migration
  would orphan the live doc AND the only backup, in one commit. Whoever builds
  this must re-key BOTH documents, in order.
- Zero other users exist. Person B only ever sees his plan if he sends B the URL
  — that's a decision, not a leak. **"B shouldn't see my plan" is ~1 hour (one
  `APP_PASSWORD` + session cookie, `USER_ID` untouched, zero call sites).
  "B should have their own plan" is ~12 hours.** He asked for the second, but the
  first is the pre-baked answer for the day he wants to show someone.
- No password reset (no mail server) → the failure mode is lockout from the one
  asset he's about to depend on for 50 days.
- **Do it the afternoon before he shares the link**, starting from a fresh
  `python backup.py`. Design below is sound and still stands:
- `storage.py:13` is `USER_ID = "default"` — one hardcoded Mongo `_id`, so every
  browser on earth shares one document. **There are no sessions; there is no
  session bug.** This was flagged in `AUDIT.md:67` and deliberately deferred.
- Resolve the user **inside `storage.py`** via `flask.g` so `load_state()` /
  `save_state()` keep identical signatures → **all 51 call sites change by ZERO
  lines**, including the 3 conditional saves (`app.py` ~424/453/733) that a
  decorator would break.
- `_uid()` must **RAISE**, never default. A fallback re-creates the original bug
  invisibly.
- **`pw_hash` MUST live in a separate `users` collection** — `/api/state`
  (`app.py:85`) ships the whole state dict to the browser minus `lessons`.
- `_id = name.lower()` gives uniqueness structurally (DuplicateKeyError = "name
  taken"); no index to forget.
- Flask session cookie (NOT localStorage): `api()` is one wrapper and cookies
  ride same-origin fetch for free. **`session.permanent = True`** or a TWA
  swipe-away logs you out. **`SECRET_KEY` must be a real Render env var** —
  Render free spins down at 15 min idle, so a boot-generated key = constant
  logouts. `werkzeug.security` scrypt defaults; no new dependency; pin werkzeug.
- `/api/cron/push` has no user context → must iterate users and `$set` only the
  `notifications` subtree (a full replace would clobber the user's own writes).
- **Migration = COPY, NEVER MOVE.** Back up `_id:"default"` to a file first, sign
  up, then copy `state` onto the new `_id`. Never delete the legacy doc.
- **Red team dissented: "YAGNI, cut it"** — no password reset (no mail server),
  whole-doc replace, beginner maintainer. Counter: Batch 0's snapshot/restore
  removes the "no undo" objection, and the zero-call-site design shrinks the
  blast radius. **Faiz's call stands, but do it carefully and locally first.**

**Batch 3b — DONE (`0e8fae4`).**
- **Ask remembers the on-screen step.** `/api/ask` gets `{section, step_kind}`
  (identity, not content); the server reads that section from ITS cached lesson
  and `prompts.ask_focus()` builds context incl. the try-it verbatim. "the try
  it now you gave me, explain it" now works — verified live.
- **`try_it_answer`** on the lesson schema, revealed only after a committed
  attempt (a one-line guess box gates it). Old lessons lack the field → no reveal.
- **Study mode auto-starts** — asked once (`profile.preferences.study_auto` via
  `POST /api/pref`), then a lightweight open-ended session per lesson with a
  one-tap End. Full commit-intent sheet still behind the Study mode button.

**Batch 3b — original notes (superseded, kept for context):**
- **Ask context.** `/api/ask` sends only `{question, day}`; the prompt sees only
  day title + topics, so "explain the try-it-now you gave me" is unanswerable.
  Send `{day, step:{kind,i}}` and pull the section from the **server-side cached
  lesson** (don't ship content up). ~+800 tokens input — free, input isn't latency.
- **Ask sheet feels endless — the real bug is CSS.** `#explorations` sits ABOVE
  the textarea (`index.html`), so each answer pushes the input further down.
  Make `.sheet` a flex column, `#explorations` `flex:1; overflow-y:auto`,
  composer `position:sticky; bottom:0`. Do that BEFORE scoping threads per step.
- **`try_it` has no answer field at all.** Add `{task, approach, solution, why}`;
  gate the reveal behind a one-line "your answer" commit (an unsuccessful
  attempt still improves later learning — a bare "Show answer" gets reflex-clicked).
- **Study mode auto-start** — Faiz chose: ask once, then auto-start each lesson
  with a visible "Turn off".

**Batch 4 — the premium design pass (not started).** Full spec came from the
design council. Highlights:
- **The goal text: Faiz is right, I was wrong.** It's `.kicker` (12px/600/
  `--brand` — an editorial-eyebrow class) fed arbitrary user free-text with no
  width cap = the loudest blue on screen. But **don't hide it behind a click**
  (hiding a constant behind an interaction is more chrome). Make it ONE muted
  truncated line that's tappable → opens plan detail. His tap; reveals MORE.
- **Dashboard**: Today card is item #9, below the fold. Order should be
  greeting → goal line → plan strip (progress + XP-to-next) → **Today card**.
  Cut `#dashDayTitle`/`#dashCount` (merge into the strip). `LV·XP` + streak are
  **already in the topbar** — the dashboard duplicates them (~60px free).
- **Accent discipline**: blue = actionable or moving. Delete the 5 decorative
  blue card left-borders; kickers → `--faint`; the blue italic mentor note →
  merge into `#skillMapSub` (a hardcoded placeholder today).
- **Card hierarchy** from size/contrast/elevation, not colour (`.card-primary`
  already added in Batch 1 for the result view — reuse it).
- **`.btn`'s `transition: background` (style.css) clobbers the shared transform
  transition → press animation is DEAD on every button. Deleting one line turns
  tactile press on app-wide.** Cheapest premium win in the file.
- Touch targets: `.btn.small` = 34px (every back link), `.bookmark-btn` 23px,
  `✕` 20×24. (`.wager-chip` fixed in Batch 1.)
- Guard every `:hover` in `@media (hover:hover)` — they fire on touch tap-hold.
- `.toast` and `.reward-pill` share `z-index:50` AND `bottom:22px` — they collide.
- Prose is 15.2px with `white-space: pre-line` (no paragraph spacing) — that's
  exactly why it reads like a README. Real `<p>` + 16px + line-height 1.7.
- Skeletons instead of the full-screen blackout for sub-second fetches.

**Also open:** new app logo — Faiz has a logo image he wants used as the app
icon; **the file was never handed over**, so ask him for the path. Icons are
generated by a Pillow script (192/512/maskable, see PHASE5.md + manifest.json).
Also: the "second in-app AI" idea (parked); public Play Store listing (optional).

**Diagrams: DONE** (`4f3dc91`) — no longer in this list.

---

## 9. Faiz's live data — read this before touching prod

His real plan is in Atlas ONLY (`_id: "default"`). As of 16 Jul: **LV 3, 365 XP,
Day 2 of a 50-day plan, 1-day streak, 1 shield.** A chunk of that 365 XP was
farmed by the pace-check bug (now fixed) — his XP is inflated but was left alone
deliberately; resetting it is his call, not ours.

**Before ANY multi-user work: back the doc up to a file first.** `MONGO_URI` is
not in the local `.env`, so you'll need to paste it in to do that.

---

## 10. How the owner likes to work

- **Council-first for milestones:** spawn 3-5 background agents with different
  lenses, pressure-test, synthesize, THEN build. Standing rule.
- **Don't just agree — pressure-test his asks too.** He explicitly wants honest
  "no"s, and on 16 Jul the council overruled *me* twice (goal text; "display not
  mechanics") and caught me citing a shield bug that didn't exist.
- **Trust measurements over estimates.** Two council estimates were wrong
  (lesson token size; auth refactor cost). Measure.
- Beginner dev: run the commands for him, keep explanations simple, be honest
  about trade-offs. He is good at cutting weak features himself.
- He likes game feel + diagrams + richness; his objection is *childish/cluttered*,
  not *rich* — different axes.
- **A PWA/TWA can never block other apps** (browser sandbox). That's the phone's
  Focus mode, already deep-linked from Study mode. Asked and answered 3×.
