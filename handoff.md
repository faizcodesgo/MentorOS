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
- **`MONGO_URI` is NOT in the local `.env`** — local dev uses
  `mentoros_data.json`. Production data exists ONLY in Atlas.

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

## 8. What is NOT done (the rest of Faiz's 16 Jul list)

**Batch 2 — multi-user accounts (DECIDED, NOT BUILT).** Faiz chose real accounts
(name + password). Council design, ready to implement:
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

**Batch 3 — content (not started):**
- **Videos per topic on that topic's step.** Currently day-level (`lesson.videos`,
  1 query → ≤2 videos) all rendered into step 1. Move `resource_query` onto the
  SECTION schema, fetch AFTER the lesson returns (sections don't exist before),
  fan out with ThreadPoolExecutor, batch ids into ONE `videos.list`. **Cap ~2-3
  per lesson** — a video per section is mostly redundant with the text and
  torches the quota. Keep one day-level video so `resources_note` keeps its
  chapter-timestamp guidance (the best feature in the lesson).
- **Hours-based sizing.** ROOT CAUSE: `prompts.py` hardcodes **"3-6 sections"**
  and "exactly 5 questions" regardless of hours; `est_minutes` is generated,
  rendered, and **never read by any code**. Asking the model for a bigger number
  doesn't make more content. Compute the structure in Python from hours
  (sections/practice/videos) and put concrete counts in the prompt.
  **MEASURED: a full lesson is only ~3.5-4k tokens of a 16k cap — ~4× headroom**,
  so a 10-section 6h lesson should fit ONE call (the council's "must split into
  parallel calls" estimate was wrong). Learning science: obey the 6 hours but
  STRUCTURE it (4 × 60-90min blocks, hours 5-6 = retrieval not new theory) and
  have the mentor say so once.
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

**Also open:** new app logo (standing request); the "second in-app AI" idea
(parked); public Play Store listing (optional).

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
