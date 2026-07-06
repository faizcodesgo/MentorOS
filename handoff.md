# MentorOS — Handoff (moving to a new laptop)

_Last updated: 6 July 2026. This is the paste-into-a-new-chat handoff AND the
new-machine setup guide. Read the memory file `mentor-app-project.md` alongside
it for the full history._

---

## 0. TL;DR — the two files GitHub does NOT have (carry these over!)

Everything else is in GitHub or the cloud. **These two are gitignored and exist
ONLY on your current laptop — copy them to the new one (USB / cloud drive):**

1. **`.env`** — all your secret keys (Gemini, YouTube, VAPID push keys, cron
   secret). Without it the app won't run locally. It lives at
   `C:\Users\user\Desktop\MentorOS\.env`.
2. **`MentorOS - Google Play package/`** folder — your Android app's **signing
   keystore + passwords**. If you lose this you can **never update the installed
   Android app** (you'd have to publish a brand-new app). Back it up somewhere safe.

Lose the repo? Re-clone from GitHub. Lose these two? They're gone. Copy them.

---

## 1. What MentorOS is

A personal AI learning-mentor web app. You set a goal + duration; the mentor
gives an honest assessment, generates a day-by-day curriculum, teaches stepped
lessons (with diagrams + the best YouTube video + what-part-to-watch guidance),
quizzes you (confidence wagers + visible combo), does spaced-review warm-ups,
tracks mastery ("Learning DNA" / skill map), runs mock interviews, assigns
build-it projects it reviews, and keeps you consistent (streaks, XP, a Study
mode). Owner: Faiz — beginner dev, sole user, prepping for RVCE CSE / placements.

**Status: feature-complete, live, and installed on the owner's phone as an
Android app.** The honest next phase is *using it*, not building more.

---

## 2. Where everything lives (all cloud — laptop-independent)

- **GitHub:** https://github.com/faizcodesgo/MentorOS (branch `main`)
- **Live site:** https://mentoros-c4ht.onrender.com (Render free tier,
  **auto-deploys from GitHub `main`**)
- **Database:** MongoDB Atlas (prod state), via `MONGO_URI` env on Render
- **Render env vars** (set in the Render dashboard, persist across laptops):
  `GEMINI_API_KEY`, `YOUTUBE_API_KEY`, `MONGO_URI`, and — once notifications are
  on — `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL`, `CRON_SECRET`.
- **UptimeRobot:** a monitor pings `/healthz` every 5 min (keeps Render warm).
  A second monitor on `/api/cron/push?key=mentoros-cron-7f3a` fires the daily
  reminder (add this when activating notifications).
- **Android app:** a TWA built with PWABuilder, sideloaded. `assetlinks.json`
  fingerprint is baked into `app.py` so it opens full-screen (no URL bar).

---

## 3. Setting up on the NEW laptop

1. **Install Python 3.12** (Node.js is NOT needed — the frontend is plain JS, no build).
2. **Clone the repo:**
   `git clone https://github.com/faizcodesgo/MentorOS.git`
3. **Copy your `.env`** from the old laptop into the cloned folder (see §0). It
   holds every secret key. The app reads it on startup.
4. **Install dependencies:** `pip install -r requirements.txt`
5. **Run it:** `python app.py` → open http://localhost:5000
   (Reset local state anytime with the "Start over" button, or `POST /api/reset`.)
6. **Copy the `MentorOS - Google Play package/` folder** somewhere safe (see §0)
   — needed only to update the Android app later.
7. First `git push` from the new machine will pop the **Git Credential Manager**
   sign-in (device-code) — approve it once; later pushes are cached.

That's it. No global config, no build step.

---

## 4. Deploy loop

Edit locally → `git add -A` → `git commit` → `git push` → **Render auto-redeploys
`main`** (~1–2 min). Verify live by curling the site or an endpoint.

---

## 5. Architecture + file map

Flask (Python) backend + vanilla JS frontend, no framework, no build step.
One JSON state document per user (`mentoros_data.json` locally; MongoDB in prod).
Gemini (free tier) over plain REST for all AI. State schema is at `SCHEMA=12`
in `storage.py` with an idempotent `_migrate()` chain.

- `app.py` — all Flask routes/endpoints (~1000 lines).
- `public/app.js` — ALL frontend logic (~1700 lines, one file).
- `public/index.html` — every screen (`<section class="view">` blocks).
- `public/style.css` — the whole design system (dark, one blue accent, token scales).
- `prompts.py` — the mentor persona + every AI prompt.
- `storage.py` — state load/save + schema migrations + `_empty_state()`.
- `dna.py` — Learning DNA (mastery from quiz data, no AI).
- `reviews.py` — spaced-review ladder. `push.py` — web-push digest + cron.
- `gemini.py` — REST client (model fallback + JSON repair/retry).
- `youtube.py` — video search + duration + chapter parsing.
- `public/sw.js` — service worker (push + minimal offline fallback).
- `public/manifest.json`, `public/privacy.html`, `public/offline.html`.
- `PHASE5.md` — the Android/TWA runbook. `AUDIT.md` — the original 4-auditor audit.
- Memory: `C:\Users\user\.claude\projects\C--Users-user-Desktop\memory\mentor-app-project.md`
  (the living project log — read it for full history).

---

## 6. Gotchas learned (save yourself the pain)

- **PowerShell + git commit messages:** quotes/apostrophes in `git commit -m "…"`
  break arg parsing. Write the message to a file and use `git commit -F file`.
- **`git commit -am` SKIPS NEW files** → caused a real deploy failure once. Always
  `git add -A` first. **And never `git add -A` with build output (keystore!) in the
  folder** — it's gitignored now, but that's how the key once leaked.
- **Gemini free tier is slow (~15–60s/call) and rate-limited.** Curriculum is now
  generated in parallel (`/api/plan/generate-all`) to cut the wait. Individual
  lessons are still slow — that's the model, not the app. A paid tier removes it.
- **`gemini-2.0-flash` has zero free quota** — removed. Uses `2.5-flash` →
  `2.5-flash-lite` with model-switch on 503/quota.
- **Render runs on UTC** — anything time-based (reminders) must use the user's
  timezone offset, not the server clock.
- **Preview screenshots time out** in the dev environment — verify via DOM/eval.
- **MONGO_URI** pasted from Atlas sometimes has glued options; `storage.py` strips
  the query string. Use a clean URI in Render.

---

## 7. Current feature state (all built + live)

Goal negotiation → **parallel** curriculum generation → stepped lessons (probe /
analogy / worked example / key points / try-it) with **required diagrams** on
spatial/anatomy/process topics + **best video** (any style) with **what-to-watch**
guidance (length + chapter timestamps) → in-lesson widget (max 1) → checkpoint
quiz (confidence wager + **visible combo**) → spaced-review warm-ups → Learning
DNA / skill map (misconceptions clear once re-mastered) → explain-it-back (daily) →
mock interview (per chapter) → build-it projects (final phase always a capstone;
never day 1) → recaps → **Study mode** (timer over the live lesson, no blank
takeover; "block distracting apps" deep-links to the phone's own Focus mode) →
streaks/shields → XP/levels/ranks + career chip → 5 learner classes (Balanced
default) → upload-your-material → floating Ask box → installable PWA/TWA.

A 5-LLM QA pass drove the live app end-to-end and fixed real bugs (invented
learner name, blank-brief 500s, progress-bar desync, XP-farm, stale
misconceptions, etc.). See the memory file for the full list.

---

## 8. Notifications

Fully built (web push, one gentle daily reminder at a **user-chosen time** +
quiet hours, per-user, timezone-correct). **Activation** (if not done yet): set
`VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CLAIMS_EMAIL` / `CRON_SECRET`
on Render, add the UptimeRobot monitor on `/api/cron/push?key=…`, then tap Enable
in the installed app. The public VAPID key + `CRON_SECRET=mentoros-cron-7f3a` are
in the memory file; the private key is in `.env`.

---

## 9. What's next (honest — none of it is urgent)

1. **Use it** — the real 50-day plan. Dogfooding drives the next real fixes.
2. **New app logo** — the icon is a generated "M"; owner wants a proper one.
3. **The "let's study" feel** — owner is gathering ChatGPT suggestions to refine it.
4. **A second in-app AI** (overseer/reviewer of the mentor) — parked until after
   real use shows whether it's needed.
5. **Public Play Store listing** — only if wanted (the $25 + 12-tester path).
6. **Multi-user** — the one real architectural rebuild (per-user identity +
   concurrency-safe writes); only needed if others use it.

Hard truth to remember: **a PWA/TWA can never block other apps** — that's the
phone's Focus mode's job (already deep-linked from Study mode). Don't rebuild for it.

---

## 10. How the owner likes to work

- **Council-first for milestones:** spawn 2–5 background LLM agents with different
  lenses, pressure-test, synthesize, THEN build. Owner's standing rule.
- **Don't just agree — pressure-test his asks too** (he values honest "no"s).
- Beginner dev: run the commands for him, keep explanations simple, be honest
  about trade-offs. He's good at cutting weak features himself.
- He likes game feel + diagrams + richness; his objection is *childish/cluttered*,
  not *rich* — different axes.
