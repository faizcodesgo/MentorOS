# MentorOS — Handoff

_Last updated: 26 July 2026 (the "Netflix-smooth" session — see §13). Paste
this into a new chat AND use it as the new-machine setup guide. Read
`mentor-app-project.md` + `mentoros-council-findings-jul16.md` in the memory
folder alongside it._

> **SAVE CHECKLIST — copy these to Drive to lose NOTHING (do this now):**
> 1. `C:\Users\user\Desktop\MentorOS\.env`  ← 7 secret keys, gitignored
> 2. `C:\Users\user\Desktop\MentorOS - Google Play package\`  ← Android keystore
> 3. (optional) the whole `C:\Users\user\Desktop\MentorOS\` folder — but the code
>    is already safe on GitHub `main`, so a re-clone restores everything except #1 and #2.
>
> As of this session the git working tree is **CLEAN and pushed** (latest commit
> `a500145` "Batch 4: kickers muted"), so there is no uncommitted code to lose.
> Only #1 and #2 above live outside git.
> **See §12 for the complete done/pending summary of this session.**

---

## 0. TL;DR — the two things GitHub does NOT have (carry these over!)

Everything else is in GitHub or the cloud. **These are gitignored and exist ONLY
on this laptop — copy them somewhere safe before wiping it:**

1. **`.env`** — every secret key (Gemini, YouTube, VAPID push, cron secret).
   Lives at `C:\Users\user\Desktop\MentorOS\.env`. Verified present this session:
   `GEMINI_API_KEY`, `YOUTUBE_API_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`,
   `VAPID_CLAIMS_EMAIL`, `CRON_SECRET`, `MONGO_URI_BACKUP`.
2. **`MentorOS - Google Play package/`** — the Android **signing keystore +
   passwords**. Lose it and you can never update the installed Android app.
   Lives at `C:\Users\user\Desktop\MentorOS - Google Play package\` (contains
   `signing.keystore`, `signing-key-info.txt`, `MentorOS.aab/.apk`, `assetlinks.json`).

Lose the repo? Re-clone. Lose these two? Gone forever.

**CURRENT PATHS (this laptop):** the repo is at `C:\Users\user\Desktop\MentorOS`
(NOT nested — the earlier `mentoros/MentorOS` layout is gone). The keystore
folder sits beside it at `C:\Users\user\Desktop\MentorOS - Google Play package`.
Local backups from `python backup.py` are written to the Desktop.

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

---

## 11. Session log — 16 July 2026 (later session)

**Context:** opened the project on a DIFFERENT (borrowed) laptop, restored from
Drive, worried something had been lost. Full forensic check done.

### Recovery / "did I lose anything?" — NO.
- **`app.py` was missing from the folder** (only `__pycache__/app.cpython-312.pyc`
  remained), which looked alarming. It was only a working-tree deletion — the file
  is intact in git and on GitHub `main`. Verified the leftover `.pyc`'s recorded
  source size (67,496 B) EXACTLY matches the committed `app.py`, and Render serves
  prod straight from `main`, so the live site IS running `HEAD:app.py`. Restored it
  with `git checkout HEAD -- app.py`. Nothing lost.
- **The only genuinely unpushed work** was `public/app.js` + `public/style.css`
  (uncommitted local edits = the Batch 4 design start). Committed as **`b4a2e93`
  "Batch 4 start: real paragraphs, 44px touch targets, toast/reward fix"** and
  **pushed to GitHub** — now safe. Working tree is CLEAN.
- Both gitignored must-keep assets confirmed present (see SAVE CHECKLIST at top).

### Batch 4 (premium design pass) — STARTED (`b4a2e93`), most still TODO.
DONE in this commit: `fmtProse()` renders lesson prose as real `<p>` paragraphs
(kills the "reads like a README" feel); 44px touch targets on `.btn.small` /
`.bookmark-btn` / `.weekly-x` / `.sheet-x` / `.dur-chip`; `.toast` vs
`.reward-pill` collision fixed + safe-area insets. STILL TODO (from §8 Batch 4):
dashboard reorder, accent discipline, card hierarchy, the dead `.btn` press
animation (one-line fix), `@media (hover:hover)` guards, skeleton loaders, the
"top XP/level looks bad" topbar polish, "quiz XP display not proper".

### Videos + visuals richness — DONE (`e0b578a`).
Owner tested a **4-hour** plan: got 17 sections but only **~2 videos**. Two limiters
were throttling it; both fixed, plus quota safety. (3-lens LLM council: systems/quota,
learning-science, product/UX — all converged.)
- **`prompts.structure_for_hours`:** video count now **scales with sections**
  (`videos = 0 if mins<45 else min(sections, 10)`) instead of a flat max of 4.
  **Measured: 4h → up to 9–10 videos (was 3); 1h → 2; 0.5h → 0.**
- **`structure_for_hours` budgets TOP-DOWN so the TOTAL day ≈ the chosen hours**
  (owner's rule: watching a video IS studying — count it, don't pile it on top).
  **FINAL model (`7668130`, superseding the earlier 28% reserve): THREE pools of
  `usable` (mins − quiz): video 0.40 · reading 0.23 · practice 0.37.** Owner's later
  ask — "videos could be more than text if more helpful" — so video is the LARGEST
  reserve and structurally exceeds reading at every duration ≥1h, while active work
  (practice + quiz + per-section try-its) stays ~40%+ so it's never all-passive.
  **Measured totals ≈ chosen hours: 1h→53, 2h→123, 4h→240, 6h→357, 8h→474** (8h now
  honestly ~8h; the old section-only model capped it at ~5.7h). Returns `video_mins`.
  `app.py` caps counted video seconds at that reserve, so many long videos can't
  balloon the day past its hours; a low-video day honestly runs SHORT rather than
  padding with marginal videos. **Do NOT reintroduce the old `video_mins=mins*0.15`
  or `*0.28` reserves — those capped video below reading and overshoot/under-serve.**
- **`resource_query` prompt gate rewritten** — the REAL reason only ~2 showed. Was
  "include ONLY where it beats reading… OMIT for definitions/history"; now "default to
  including one on every concept section… omit only true padding, never two for the
  same idea, prose must stand alone." (The cap change is inert without this.)
- **`VISUAL_RULES`:** the "aim for 1-2 diagrams" ceiling → "a diagram on every section
  where a picture genuinely helps; no upper limit." **Anti-overflow arithmetic + the
  browser-side `fitSvgText` left UNTOUCHED — do not remove them.**
- **Quota safety (so more searches can't blow the shared 10k/day):**
  - `youtube.py` **query-level cache** — normalized query, 30-day TTL, 200-entry cap,
    lives in the user's `state["yt_cache"]`. A cache HIT costs ZERO quota, so
    regenerating a lesson is now free (this was the biggest retry-storm risk).
  - `storage.youtube_quota_reserve()` — **hard daily-budget stop**, Mongo-backed
    (survives the 2 gunicorn workers + Render spin-down), keyed by ~Pacific date,
    budget 8,000 units, **FAIL-OPEN** on DB error. Over budget → `search_videos`
    returns `[]` → the existing graceful fallback shows a search LINK.
  - `_attach_section_videos` concurrency 4→6; per-lesson search count is bounded by
    the cap (≤10 section + 1 day-level).
- **UI (product/UX council):** section video demoted from a bordered card to a slim
  **borderless "▶ Watch · 8 min" chip** (44px tap target, muted truncating
  title/channel). Verified in-browser: borderless, single line, long titles ellipsis
  without overflowing the card. Videos stay LINKS (never 15 iframe embeds).
- **Verified:** `python -c "import app"` boots clean (40 routes); cache/TTL/trim/guard
  unit-tested (guard stops at budget, cache hit skips network+guard); chip computed
  styles confirmed in the live dev server.
- **NOT done from the UX council (deferred to the Batch 4 design pass):** the
  "core vs +optional video" honest time estimate replacing the raw "N / 21" step
  counter; chaptering the progress bar by block; diagram two-size + caption treatment.
- **Also fixed this session:** `Desktop/.claude/launch.json` still pointed at the dead
  nested path `Desktop/mentoros/MentorOS/app.py`; corrected to
  `C:/Users/user/Desktop/MentorOS/app.py` so `preview_start` (name `mentoros`, port
  5000) works. `MentorOS/.claude/launch.json` also exists (name `mentoros-audit`).

### Batch 4 progress
**Correction to §8:** the dead `.btn { transition: background }` press animation was
ALREADY fixed in `938c70b` (the `.btn` rule carries no transition shorthand — see the
comment at style.css ~161). Don't redo it.

**DONE — dashboard plan strip + XP-to-next (`0135231`).** Merged the day title, day
count, and days-progress bar into one `.plan-strip` above the Today card, and added
the missing **XP-to-next-level meter** (the council's motivator). The day title was an
`<h1>` competing with the Today card's heading → now a quiet `<span>`. LV/XP is NOT
duplicated (topbar only); the streak stays split (topbar compact / dashboard detail),
already reconciled in code — left as-is. Removed dead `.dash-head*` rules.
**Verified in-browser (375×812): order greeting→goal→plan strip→Today card; Today card
top 256px and its "Start today" button fully above the fold.** (Verify design changes
via `read_page`/`javascript_tool` positions — pixel screenshots time out here.)

**Genuinely remaining Batch 4 items:**
- **Accent discipline**: blue only for actionable/moving; drop decorative blue card
  left-borders; kickers → `--faint`.
- **Card hierarchy** via size/contrast/elevation (reuse `.card-primary`).
- Guard every `:hover` in `@media (hover:hover)` (they stick on touch tap-hold).
- **Skeleton loaders** instead of the full-screen blackout for sub-second fetches.
- **Honest time estimate** (UX council): "core vs +optional video" + chapter the
  progress bar by block, replacing the raw "N / 21" step counter.
NOTE: pixel screenshots time out in this env (known gotcha) — verify design changes
via `read_page` + `javascript_tool` computed styles/positions (how the video chip was
verified). The dashboard needs a logged-in account + a plan to render.

### How to keep this handover current
Owner's standing rule (highest priority): **update this file after EVERY change**,
commit + push so it's never only on one laptop. Live prod state before any new
work this session: LV 3, 365 XP, Day 2 of 50, 1-day streak, 1 shield (unchanged).

---

## 12. COMPLETE SESSION SUMMARY (16 Jul 2026, later session) — the backup

**Read this first next time.** Self-contained snapshot of everything done + pending.

### 12.1 Was anything lost? NO.
- `app.py` was deleted from the working folder (only its `.pyc` remained) but was
  intact in git + live on Render; restored via `git checkout HEAD -- app.py`. Proven
  not-lost by matching the `.pyc`'s recorded source size to the committed file.
- The only unpushed work (Batch 4 design start in `app.js`/`style.css`) was committed
  and pushed. `.env` + keystore both confirmed present (see SAVE CHECKLIST up top).

### 12.2 Everything DONE this session (all committed + pushed to GitHub `main`)
Commit order (oldest→newest):
1. `b4a2e93` — Batch 4 start (rescued unpushed work): real `<p>` paragraphs
   (`fmtProse`), 44px touch targets, toast/reward-pill collision fix.
2. `e0b578a` — **Videos + visuals richness.** Video cap scales with sections; video
   prompt gate rewritten to include a video wherever it helps; diagram "1-2" ceiling
   lifted; `youtube.py` query cache + `storage.youtube_quota_reserve` daily guard;
   section videos → slim "▶ Watch" chips.
3. `dea7ead` — video time counted INSIDE the day budget (first cut, 28% reserve).
4. `0135231` — **Dashboard plan strip + XP-to-next meter**, Today card above the fold.
5. `7668130` — **Video can be the LARGEST medium when helpful** (owner's refinement):
   final 3-pool budget video 0.40 / reading 0.23 / practice 0.37; video structurally
   exceeds reading while active work stays ~40%+; total ≈ chosen hours. PLUS the
   council correctness-audit fixes (cache-trim lock, `escAttr` href, skip day-level
   video on tiny days).
6. `0aea972` — **Low-video under-run fixed: practice is ELASTIC.** `structure_for_hours`
   returns `practice_max` (= practice + video_mins/14, cap 12); the prompt gives a
   RANGE and tells the model to use MORE practice when it adds few videos, so active
   work backfills whatever video doesn't — in ONE call (no 2nd API call). Verified:
   2h→123/121, 4h→240/232 whichever way the model leans. Long no-video days (6-8h)
   still honestly under-run (one Gemini call caps ~12 sections+12 practice) — unavoidable.
7. `20e5b7f` — **Batch 4: accent discipline.** Neutralized decorative blue left-borders
   on peripheral info cards (`.viva-overall`/`.explain-card`/`.notes-card` → `--line`);
   blue reserved for actionable/active (Today card keeps it). Verified in-browser.
8. `8995b99` — **Quiz scales with the day + harder.** Was hardcoded 5 questions;
   `prompts.quiz_count_for(mins)` now scales (floor 6, cap 15): 1-2h→6, 4h→9, 6h→14,
   8h→15. Quiz minutes come out of the budget (quiz×2), `structure_for_hours` returns
   `"quiz"`, `estimate_minutes` counts the real question count; total est still ≈ hours.
   Prompt biases HARD (≈65% application/multi-step, later questions harder, spread
   across subtopics). Frontend/grading already used `len(quiz)` — no UI change needed.
(Plus handoff.md commits keeping this file current, and the `launch.json` path fix.)

**What the owner asked for on the original 16-Jul list — status map:**
- Multi-user accounts · view-whole-session toggle · study-mode auto · goal-text fix ·
  harder quizzes · back-to-dashboard · confidence/hint XP tiers · plan sized to hours ·
  streak/shield honesty · per-topic videos · Ask remembers the step · try-it answers ·
  bookmark speed · Android back · diagram overflow → **ALL DONE in earlier commits**
  (see §7). The image issues (diagrams / XP-level / quiz-XP) — owner confirmed DONE.
- More videos per topic + total time = chosen hours + videos-can-exceed-text +
  more diagrams → **DONE this session** (commits 2,3,5).
- Dashboard "unprofessional goal text" + motivation-first → **DONE** (`938c70b`+`0135231`).

### 12.3 Everything PENDING (nothing here is started in code)
**Batch 4 — remaining premium-design polish** (dashboard + accent discipline done):
- Accent discipline — MOSTLY DONE (`20e5b7f` + `a500145`): 3 decorative content-card
  borders neutralized, and all 14 `.kicker` eyebrow labels → `--muted` (were blue).
  Still to consider: `.lesson-intro`/`.exploration`/`.probe` blue left-borders — left
  because they use the border as part of their structure; needs the owner's eye.
- Card hierarchy via size/contrast/elevation (reuse `.card-primary`).
- Guard every `:hover` in `@media (hover:hover)` (sticks on touch).
- Skeleton loaders instead of full-screen blackout on sub-second fetches.
- Honest lesson time estimate ("core vs +optional video") + chapter the step
  progress bar by block, replacing the raw "N / 21" counter (UX council).
- Diagram variety — two sizes (inline vs full-width) + optional caption, to avoid
  monotony now that lessons can have many diagrams (UX council).
**Why these are deferred, not done blind:** pixel screenshots time out in this env,
so visual/taste changes can't be seen rendered. The dashboard + accent-discipline
bits were done because they're verifiable via DOM measurement; the rest (card
hierarchy, diagram sizing, skeleton transitions, hover-on-touch) genuinely need the
owner looking at the live site — doing them blind risks degrading the design, which
the owner explicitly warned against. Recommend pairing on these on the live URL.

**Verification still owed (needs the owner's plan + spends Gemini/YouTube quota):**
- Generate ONE real lesson end-to-end to confirm the model now emits many
  videos/diagrams and the day totals the chosen hours. All plumbing is unit-verified;
  only the live model-behaviour proof is outstanding. **Existing Day 1–2 lessons are
  cached — richness shows on NEW days or on regeneration, not retroactively.**

**Parked / low priority (owner's call):** per-step separate Ask threads (the "too long"
CSS cause is already fixed); the "second in-app AI" idea; public Play Store listing;
resetting the inflated 365 XP from the old pace-check farm bug (his call, left alone).

### 12.4 Video-budget under-run — FIXED (`0aea972`)
Earlier trade-off (a low-video day ran short) is resolved: practice is now ELASTIC.
`structure_for_hours` returns `practice_max`; the prompt gives the model a practice
RANGE and tells it to add more practice when it uses fewer videos, so ACTIVE work
backfills whatever video doesn't — in the SAME generation call (no 2nd API call).
Realistic days (1-4h) now hit the target whether the model leans video or practice.
REMAINING honest limit: a 6-8h day with NO video-worthy topics still under-runs,
because one Gemini call can't emit more than ~12 sections + 12 practice before the
16k output cap — unavoidable, and unrealistic for a CS curriculum.

### 12.5 How to run / verify locally (this laptop)
- `cd C:\Users\user\Desktop\MentorOS` → `python app.py` → http://localhost:5000
  (local uses `mentoros_data.json`; `MONGO_URI` is deliberately NOT in local `.env`).
- Or Claude Code preview: `preview_start` name `mentoros` (port 5000). **Pixel
  screenshots time out here — verify via `read_page` + `javascript_tool` computed
  styles/positions** (that's how the chip + dashboard were verified this session).
- Quick shape check: `python -c "import prompts as p; print(p.structure_for_hours(4))"`.
- Two 3-lens LLM councils were run this session (video/visuals design; then video-share
  + correctness audit). Audit found NO high-severity bugs; the 3 actionable low/med
  items were fixed in `7668130`.

---

## 13. Session log — 26 July 2026: the "Netflix-smooth" pass

**Context:** owner asked for smoother, more "addictive" UI/UX (Netflix as the
reference), features frozen. Also: `app.py` had vanished from the working tree
AGAIN (same as §12.1) — restored from git via `git show HEAD:app.py > app.py`,
nothing lost. Four-agent council ran first (motion craft / engagement
psychology / perceived performance / red team); everything below is the
intersection of their proposals that survived the red team.

### Shipped (one commit, frontend-only — `app.py` untouched except line endings)

**Feel layer (style.css + small JS):**
- Native tap layer: `-webkit-tap-highlight-color: transparent` +
  `touch-action: manipulation` + `user-select: none` on all controls; presses
  land instantly (0.05s) and release eases back.
- `overscroll-behavior-y: contain` — pull-to-refresh can no longer reload the
  app mid-quiz.
- Easing tokens `--ease-out` (quintic) + `--ease-pop` (overshoot, REWARDS ONLY)
  in `:root`; progress/XP/step bars now surge-and-settle (0.45-0.55s).
- View Transitions API in `show()` — old view crossfades to new under a PINNED
  topbar (`view-transition-name: topbar`). CRITICAL: only the DOM swap is
  inside `startViewTransition`; the history push stays synchronous, so the
  `suppressHistory` popstate window is untouched. `html.vt` suppresses the
  legacy `viewIn` during a transition. Skipped under reduced-motion.
- Direction-aware lesson steps: Next slides from the right, Back from the left
  (`--step-dx`, `stepDir`).
- Toast + reward pill got exit animations. `rewardPill` now QUEUES (pillChain)
  so concurrent pills play in sequence — still awaitable, same ~1.5s each.
- Checkpoint result choreography: score/ledger rows stagger in, total counts
  up (`countUp`), level meter fills at +450ms. Haptics (`buzz`) at exactly
  three moments: wager reveal (12ms / 25ms wrong), level-up (10-40-14).
- Ask FAB scales in via `@starting-style`; hover lifts (day rows, options)
  gated behind `@media (hover: hover)`.

**Perceived speed (app.js):**
- **Instant cold-open:** full state snapshotted to `localStorage`
  (`mos_state_snap`) on every `/api/state` fetch (all refetches go through
  `refreshState()` — DO NOT add raw `state = await api("/api/state")` lines
  back). `boot()` paints the dashboard from the snapshot in ~50ms and
  reconciles after. Snapshot cleared on sign-out AND on any 401 (`api()`), so
  user B can never see user A's dashboard. `#view-onboarding` is now hidden by
  default — the returning-user "wrong screen flash" is gone. sw.js untouched:
  this caches DATA, never code.
- **Lesson cache + prefetch:** in-memory `lessonCache` Map (lessons are
  immutable server-side); `renderDashboard` prefetches today's lesson, the
  frontier recap prefetches tomorrow's. "Start today" is usually instant now.
  Projects are NEVER prefetched (mastery-calibrated at open). Revisit-opens
  show an in-place skeleton (`.skel`, opacity pulse only); true first-opens
  keep the narrated overlay (now content-specific lines).
- **No more double round-trips:** quiz submit / day complete / warm-up /
  explain / viva / project paint from the MUTATION RESPONSE (server-authoritative
  fields: `r.xp`, `r.streak`, `r.score`…) and reconcile with a background
  `refreshState()`. Nothing paints un-acked numbers — this is NOT optimistic XP.
- **Ask is non-blocking:** the question posts inline into `#explorations` with
  a skeleton answer block; you can keep reading the lesson while Gemini
  thinks. On error the question is handed back into the composer.
- Skills view opens synchronously from `state.dna` (background fetch just
  marks notes seen). Warm-up availability check cached per day (`warmupInfo`).
  Day list uses ONE delegated listener (was 50 per render).

**Netflix framing (engagement council, all-honest reframes):**
- **The locked-days wall is gone:** done days keep +XP receipts, today is
  marked, the next day is an "Up next" teaser (crosses chapter boundaries),
  the rest of the current chapter sits quiet, future chapters collapse into
  one expandable `chapter-row` each ("Chapter 3 · C Control Flow — 3 days").
  Nothing unlocked that wasn't; locked taps still toast.
- Plan strip: "Chapter 2 · Pointers — day 3 of 8" (goal-gradient framing; the
  /50 total stays in the count chip) + `#nextLandmark` line ("Milestone
  project · 2 days away" — days of WORK, never clock time).
- Recap reordered for peak-end: covered → say it back → today's take →
  **Tomorrow card** (`#tomorrowCard`: next day's title + first objective +
  "+150 XP waiting"). Frontier-day recaps only; NO start-now button by design
  (spacing is the point — the council explicitly rejected autoplay).
- **Mid-lesson resume:** step position in `localStorage` (`mos_resume`);
  Today button becomes "Continue · step 4 of 9"; cleared on completion.
- Streak celebration at the moment it's earned: "N days running" (+ "New
  personal best") pills after day-complete, from `r.streak` — rewards-only,
  break copy unchanged. Warm-up reframed "Previously on your plan".

### Verified (headless, mock user `tester`/`testpass123` local only)
Full flow driven in the dev preview via DOM checks: dashboard shape, chapter
expand/collapse, instant lesson open from cache, step direction, diagrams
non-blank after reveal (fitSvgText intact), complete → pill queue → checkpoint
(3 wagers, correct payouts 18/12/16) → result choreography → recap order →
Tomorrow card → back-gesture invariants (sheet closes first, views walk back,
no phantom entries) → cold reload paints dashboard instantly. PAYOFF three-way
sync confirmed untouched. No server errors. Mock data lives in gitignored
`mentoros_data/` (delete `tester.json` + `_users.json` to reset local dev).

### Gotcha found this session
A `replace_all` of `state = await api("/api/state")` → `await refreshState()`
also rewrote the line INSIDE `refreshState` itself → infinite recursion, app
booted to a blank page with NO console error (the rejection died inside
boot's catch). If the app ever boots blank: check `refreshState` first.

### Still needs the OWNER'S EYES on the live site (can't be judged headlessly)
- Whether the View Transition crossfade feels premium or sluggish on his phone
  (durations are 0.15s out / 0.24s in — tune, don't delete).
- Skeleton flash risk on fast connections (150ms+ fetches only by design).
- Whether the pill queue after a big day (day + streak + level) feels like a
  celebration or a parade (cut the streak pill first if it's too much).
- Haptic strength on his device.
