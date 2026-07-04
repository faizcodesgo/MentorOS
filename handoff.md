# MentorOS — Handoff

_Paste-this-in-a-new-chat handoff. Read `AUDIT.md` (checklist at the very top) and the memory file `mentor-app-project.md` alongside this._

---

## 1. Goal

**Immediate goal:** Execute the approved audit end-to-end. The owner (Faiz) approved:
- **Voice = (A) confident mentor** — drop most RPG words (Quest / Boss Check / Main Quest / Quest Log → Today / Checkpoint / your plan / plain language); keep XP/levels/streak as quiet progress.
- **Do the ENTIRE audit** — all batches A (bugs), B (copy), C (visual), D (de-clutter).

The full itemized checklist is the **blockquote at the top of `AUDIT.md`** — execute from there.

**Product goal:** MentorOS is a personal AI learning mentor. A user sets a goal + duration; the mentor negotiates a realistic plan, generates a day-by-day curriculum, teaches stepped lessons, quizzes with spaced review, tracks mastery ("Learning DNA"), assigns build-it projects it reviews, and keeps the learner consistent. Owner is a beginner dev prepping for RVCE CSE / placements; he'll start his real 50-day plan only once there's a native Play Store app (Phase 5, later).

---

## 2. Current state

- **Feature-complete and deployed live.** Everything works.
- **Local repo:** `C:\Users\user\Desktop\MentorOS`
- **GitHub:** https://github.com/faizcodesgo/MentorOS (branch `main`)
- **Live:** https://mentoros-c4ht.onrender.com (Render free tier, **auto-deploys from GitHub main**)
- **Stack:** Flask (Python) + vanilla JS (no framework/build). One JSON state document per user (local `mentoros_data.json` in dev; MongoDB Atlas in prod via `MONGO_URI`). Gemini free tier over plain REST. YouTube Data API (video links), pypdf (material upload), pywebpush (notifications).
- **State schema is at v12** (`storage.py`, `SCHEMA = 12`), with an idempotent `_migrate()` chain.
- **Audit complete** (4 independent auditors: copy, visual, features, code) → `AUDIT.md`. **3 critical bugs already fixed** (commit `2150bfc`): the milestone-banner crash, error-message leakage, and `debug=True`. Everything else in the audit is still TODO.

Built and live: goal negotiation → adaptive curriculum → **stepped lessons** (one section per step, progress bar) → interactive widgets + SVG diagrams + worked examples + "think-first" probes → **checkpoint quiz** (confidence wagers/combo) → **spaced-review warm-ups** (fresh questions, never repeats) → **Learning DNA / skill map** → mentor's notes → bookmarks → explain-it-back → **mock interview (viva)** → day/chapter recaps → **projects/milestones** (AI-reviewed) → **weekly report** → streaks/shields → focus timer → **upload-your-material** (3 scopes) → floating Ask button → **push notifications** (installable PWA) → XP/levels/ranks. Mentor is "humanized" (name + memory injected into prompts). Progressive difficulty ramps lessons+quizzes+projects.

---

## 3. Active files

- `app.py` — Flask routes (~920 lines). All endpoints.
- `public/app.js` — ALL frontend logic (~1600 lines, monolith).
- `public/index.html` — all screens/`<section class="view">` blocks.
- `public/style.css` — the whole design system (this is where most of Batch C lives).
- `prompts.py` — mentor persona + every AI prompt (negotiate / curriculum / lesson / quiz / warm-up / interview / project brief+review / material scope).
- `storage.py` — state load/save + `_migrate()` schema chain (currently v12) + `_empty_state()`.
- `dna.py` — Learning DNA (mastery from quiz data, no AI). `reviews.py` — spaced-review ladder. `push.py` — web-push digest + cron logic. `gemini.py` — REST client (model fallback + repair/retry). `youtube.py` — video search.
- `AUDIT.md` — **the execution checklist (top blockquote) + full findings.** START HERE.
- `mentor-app-plan.md` — the whole product plan / all council decisions (sections 1–15).
- `requirements.txt`, `render.yaml`, `public/manifest.json` (+ a stray `manifest.webmanifest` to delete — Batch A), `public/sw.js`, `public/icon-192/512.png`.
- Memory: `C:\Users\user\.claude\projects\C--Users-user-Desktop\memory\mentor-app-project.md` (living project log; also MEMORY.md index + user-faiz-beginner.md).

---

## 4. Changes made (recent → older)

- **Audit + critical fixes (commit `2150bfc`, `95f3b05`):** 4-auditor audit → `AUDIT.md`. Fixed: `showBanner` crash → `rewardPill` (milestone celebration), error handler no longer leaks `str(e)`, `debug=True` → `FLASK_DEBUG` env-gated.
- **Notifications / PWA (`cfcc258`):** web push (Android-first), one opt-in daily digest, quiet hours, `push.py`, endpoints (`/api/push/subscribe`, `/api/push/settings`, `/api/cron/push?key=SECRET`, `/api/vapid-public-key`), installable (manifest + push-only `sw.js`, no cache), "Study reminders" sheet. schema 12.
- **Weekly report:** verified already fully built + working (no build needed).
- **Projects (`2bce2e5`):** last day of each phase = "◆ MILESTONE" (300 XP), lazy AI brief (difficulty ramps), submit → rewards-only AI review, `#view-project`. schema 11.
- Earlier this session: material scopes reworded to only/helpful-extras/full-depth premium cards; upload-your-material feature; no-repeat questions + progressive difficulty; stepped lessons; floating Ask FAB; revision label + SVG-only diagrams; mentor humanization; premium redesign; interactive widgets; skill map / DNA; warm-ups; streaks; focus session; recaps; viva; bookmarks; explain-it-back.
- **Deploy loop:** edit locally → `git add -A` → commit → `git push` → Render auto-redeploys `main`.

---

## 5. Failed attempts / gotchas (LEARN FROM THESE)

- **PowerShell + git commit messages:** apostrophes/quotes in `git commit -m "…"` or `-m @'…'@` **break argument parsing** and create bogus pathspecs. FIX: write the message to a scratch file and use `git commit -F path\to\msg.txt`.
- **`git commit -am` SKIPS NEW files** → this caused a real deploy failure once (`youtube.py` not committed → `ModuleNotFoundError` on Render). ALWAYS `git add -A` first for new files.
- **Preview MCP flakiness:** `preview_screenshot` frequently times out this environment — **verify via `preview_eval` DOM checks instead**. Also `location.reload()` **inside** the same eval that then reads the DOM → "Inspected target navigated or closed"; do the reload in a separate call, or fetch state and re-render via JS without reloading.
- **Gemini free tier:** `gemini-2.0-flash` has **zero** free quota (429 "limit: 0") — removed; use `gemini-2.5-flash` → `gemini-2.5-flash-lite`. Daily cap resets ~**12:30 PM IST**; heavy testing can exhaust it (lessons/reviews then fail with quota until reset). Intermittent 503 "high demand" — client switches models.
- **MONGO_URI corruption:** pasted URIs sometimes carry duplicated/glued options (`w=majorityretryWrites=true`) that crash pymongo — `storage.py` now strips the query string. Use a clean URI in Render env anyway.
- **Machine facts:** **Node is NOT installed** (Python 3.12 IS). No `gh` CLI. `git push` uses the Git Credential Manager popup (device-code) — the FIRST push in a fresh clone needs the user to approve the on-screen dialog; later pushes are cached/instant.
- **Env in dev:** `.env` (gitignored) holds real secrets locally; `app.py` has a tiny parser that loads it. To run: `python app.py` then open http://localhost:5000 (or the Claude_Preview MCP with `launch.json` config name `mentoros`, port 5000). Reset state with `POST /api/reset`.
- **Design pattern learned:** avoid "AI-generated" tells — no over-reassurance copy, no uppercase-mono labels everywhere, one accent color, restrained motion. (That's literally what the audit is about.)

---

## 6. Next steps (in order)

1. **Execute the audit** — work the checklist at the top of `AUDIT.md`, batch by batch, testing each change (DOM eval + `python -c "import app"`), committing per batch. Recommended order: finish **A (bugs)** → **B (copy)+voice rename** → **C (visual system)** → **D (de-clutter)**. The riskiest is the voice rename (touches every screen) and the dashboard restructure — do those carefully.
2. **Verify live** after each push (`curl` the app.js / an endpoint) — Render auto-deploys `main`.
3. **Then Phase 5** — the native Play Store Android app (the owner's gate to start his real 50-day plan). Council-first; the honest options are wrapping this PWA (Capacitor/TWA) vs. a real native build.

---

## 7. Anything else you need

- **Council workflow (owner's standing rule):** run an LLM council (spawn 2–4 background `Agent`s with different lenses: pedagogy / engineering / product-premium) BEFORE building each milestone, synthesize, then build. The owner values "don't just agree — only build if it's genuinely good," and "don't overdo it / keep it premium, not childish."
- **Owner profile:** beginner developer; keep explanations simple, run the commands for him, don't assume CLI fluency. He decides features; be honest about trade-offs (he's good at cutting weak features himself).
- **Standing reminders to re-raise until he answers:** (1) how the mock-interview Viva *feels* on a real chapter; (2) does the SVG diagram look clean on a fresh lesson; (3) does he want more animation anywhere specific; (4) he wants to **change the app logo** (remind him).
- **Notifications activation is PENDING the owner** (do NOT assume it's on): set on Render env → `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL=mailto:faiz.codes.go@gmail.com`, `CRON_SECRET=mentoros-cron-7f3a`; install the PWA on Android + tap Enable; point a cron-job.org job at `/api/cron/push?key=mentoros-cron-7f3a` hourly. (VAPID keypair already generated and in local `.env`; public key also in memory.)
- **Keys already in place (Render env):** `GEMINI_API_KEY`, `YOUTUBE_API_KEY`, `MONGO_URI`. The Gemini/YouTube keys are the owner's; they're in local `.env` too.
- **Single-user architecture:** everything keys off one `"default"` state doc (no auth). Fine for the owner-as-sole-user; going multi-user is the one real architectural rebuild (per-user identity + concurrency-safe writes) — flagged in AUDIT.md, not urgent.
- **Context note:** this handoff exists because the audit was approved when the prior session's context window was full. A fresh session has room to execute the whole thing cleanly.
