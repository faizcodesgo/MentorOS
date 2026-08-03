# MentorOS — Project History (scratch → now)

**The one living narrative of the whole project.** Every other doc is a slice: `handoff.md`
is setup + recent sessions, the `COUNCIL-*` files are single councils, `DESIGN-DECISIONS.md`
is the standing rules, `RESOURCES-SPEC.md`/`REDESIGN-PHASES.md` are forward specs. This file
is the through-line from day one, and it is **appended to as work happens** — newest phase at
the bottom, "What's left" kept current at the very end.

Owner: **Faiz** — beginner dev, solo user, building this as the companion for his own 40-day
RVCE placement-prep bootcamp. Stack: Flask + vanilla JS (no build step, no Node on the
laptop), Gemini API, MongoDB Atlas M0, deployed on Render free tier, wrapped as an Android
TWA. Working style: council-before-build, direct opinionated answers, "don't overdo it",
push back on his asks rather than just agreeing.

---

## Phase 0 — The idea & its evaluation (2 Jul 2026)

Faiz pitched an AI mentor app: set a goal + duration ("learn X in N days"), get an adaptive
curriculum, a mentor with persistent memory of your strong/weak areas, proactive quiz
notifications, assigned+reviewed projects, and **forced app-blocking** during study /
on missed deadlines.

A 4-evaluator + 1-researcher LLM council scored it (product 5, VC 3, engineering 4→7
descoped, learning-science 6) and reached two verdicts that still shape everything:
- **Drop forced lockout.** Impossible on iOS, uninstall-bait on Android, and pedagogically
  harmful. Replaced with opt-in strictness. (This has been re-confirmed as *technically
  impossible in a PWA/TWA* three more times since — it is settled.)
- **Verticalize to Indian engineering/placement prep; build PWA-first with free Gemini;**
  native Android later. Faiz is user #1; his own 50→40-day CSE plan is the first content.

Market research: no product combines curriculum + mentor memory + proactive quizzes +
outcome-based blocking (closest: StudyLock, QuizScreen). Full founding doc:
`mentor-app-plan.md` (now carrying a "historical" banner — several sections were later
reversed).

---

## Phase 1 — Built & deployed (2 Jul)

Phase 1 shipped the same day. Files that still anchor the app: `app.py` (routes),
`prompts.py` (all Gemini prompts), `gemini.py` (REST client, model fallback, JSON repair),
`storage.py` (local JSON in dev, Mongo in prod), `public/` (the whole frontend).

Flow: **negotiate** (mentor assesses the goal honestly) → **generate plan** (per-phase, to
dodge timeouts) → **dashboard** → **lesson** (cached) → **complete**. Verified end-to-end
with Faiz's real Gemini key; deployed to **mentoros-c4ht.onrender.com**; pushed to GitHub.

Free-tier realities learned here and never forgotten: ~30–60s cold start after idle; Gemini
503/429 under rapid calls (→ model switching); Render's 750h/month pool is *shared* with his
other app (TriVi).

---

## Phase 2 — The learning engine (2–3 Jul)

This is what makes it a mentor rather than a lesson generator. Each piece got its own
mini-council.

- **Checkpoints** — 5-ish MCQs bundled *into* the lesson generation call (one AI call/day),
  graded in pure Python. Each answer carries a **confidence wager** (Guessing / Fairly sure /
  Certain) with visible odds.
- **Learning DNA** (`dna.py`) — built from quiz answers only, no AI: Bayesian mastery per
  topic, bands (new/weak/developing/mastered), misconception flags (confident-but-wrong),
  and template-assembled "Mentor's Notes". Surfaced as a Skill map.
- **Dynamic roadmap** (`reviews.py` + app.py) — stable day-ids with a float `order` so days
  can be inserted mid-plan; **auto revision days** when a checkpoint scores <50%; pace-check
  re-pacing after an absence; rewards-only streaks with earned shields (never zeroes).
- **Warm-ups** — spaced-repetition ladder (X+1/X+3/X+7) that regenerates fresh questions on
  due topics. (Later proof that quizzes need no lesson text — a fact the resource feature
  leans on.)
- **Study mode** — a voluntary focus session; honest that a PWA can't block apps, deep-links
  to the phone's own Focus mode instead.

---

## Phase 3 — The design wars (3–5 Jul)

The hardest-won lessons in the project.

- RPG pass (dark UI, XP, classes, purple accent) → Faiz: **"it screams AI-generated, make it
  feel like Riot/Discord."** → premium pass: **one blue accent**, richer near-black,
  **deleted** the starfield / glows / progress-shine / thinking-orb (they gave his Android
  measured lag) → standing rule: *transform + opacity only; never continuously animate
  box-shadow/background-position/filter.*
- **The regression cycle that taught the project's core discipline:** the visible combo
  counter was cut, restored at Faiz's request (`a7fc965`), cut again by a later "declutter"
  pass, and restored again (`5f34644`). Batch D over-cut four features (All-Rounder,
  explain-it-back, combo, career chip) — all restored the next day. The rule that came out:
  **"declutter duplicates and chrome; THIN distinct things, never delete them"** — and the
  deeper cause: *decisions that live only in commit messages are invisible to the next pass.*
- Also shipped across these days: real YouTube videos with exact "watch 12:34–28:00"
  guidance, hand-drawn SVG diagrams (Mermaid deprecated — it produced messy taxonomy
  diagrams), stepped lessons, a floating Ask button, milestone **projects**, mock-interview
  **viva**, weekly report, human-mentor memory + greeting continuity, and the honest
  **"app-blocking is impossible"** answer (asked a 2nd and 3rd time).
- Voice **A** locked: confident mentor, one term per concept (Today / Checkpoint / Your plan),
  no reassurance or narration, no "AI" in the tagline.

---

## Phase 4 — Android + accounts (5–16 Jul)

- **Phase 5 (native) path chosen:** wrap the PWA as a **Trusted Web Activity** via
  PWABuilder's cloud build (dodges the no-Node/no-SDK blocker; one codebase forever). Reality:
  a new personal Play account can't publish publicly without a ~3-week closed test, so the
  gate is **sideload onto Faiz's phone**, not a public listing. In-repo prep: assetlinks,
  `/healthz` keep-warm, privacy policy, offline fallback. Runbook: `PHASE5.md`.
- **Push notifications** built (`push.py`, `sw.js`, the Study-reminders sheet) — but **never
  activated** (needs Render env vars + a cron pinger + in-app enable; still pending).
- **16 Jul, 5-LLM council** — the big one:
  - Found and fixed a **plan-wipe bug**: `/api/plan/init` cleared everything on any post,
    with no backups. Now guarded + `snapshot`/`restore` + `backup.py`.
  - **The wager math was broken** (flat wrong-payoff made "Certain" strictly dominant, and
    poisoned the misconception flags). Fixed with Gardner-Medwin CBM scoring (14/12 · 16/8 ·
    18/0); combo moved out of the multiplier to a flat end-of-run bonus.
  - **Measured 2× speed win**: `thinkingConfig` off = 18.8s vs 38.5s per lesson, same output.
    Corrected my own past claim that the latency was "inherent to the free tier."
  - **Real accounts** (name+password) — resolved inside `storage.py` so ~54 call sites
    changed by zero lines; `_uid()` raises, never defaults; per-user isolation verified.

---

## Phase 5 — The long gap (26 Jul)

- **Netflix-smooth pass** (`116bf5d`): View Transitions, instant cold-open from a
  localStorage snapshot, in-memory lesson cache + today/tomorrow prefetch, chapter-grouped
  plan list. Self-review caught 2 regressions it introduced (dead resume; unfitted diagrams)
  → fixed (`659a9c9`), producing the rule: *anything that measures rendered content must run
  inside `show(view, after)`.*
- **Audit council** — found warm-ups had been **100% dead in production since 16 Jul** (a
  list used as a dict key threw on every call, hidden by a generic toast) and per-section
  videos never attached (a `NameError` swallowed by a bare except). Both fixed.
- **Google/Gmail sign-in: dropped** (Faiz's call, heard the trade-off) — `reset_password.py`
  solves the real "people forget passwords" worry offline instead.
- **8-phase plan restart** agreed and dry-run locally ([8,10,4,6,5,3,3,1] = 40 days in 34s).
- **Render suspended** — the free 750h pool ran out (24/7 UptimeRobot pinging + shared with
  TriVi). Everything from here queues for the ~1 Aug monthly reset.

---

## Phase 6 — Full redesign, resource spec, doc hygiene (27–28 Jul) — 20 commits

Production stayed suspended throughout, so **everything below is verified locally by computed
style + behavior checks — nothing has been seen on a real screen.** Commits `c03ac05` →
`c41dee4`, all on `main`, all queued for the Aug-1 auto-deploy.

**Councils first** (Faiz's standing rule):
- 4-agent redesign council → `COUNCIL-2026-07-27-REDESIGN.md`. Diagnosis: the app looks
  machine-generated not because of its hue but because **16 components are the same 10px
  outlined box and the whole game layer renders smaller than the body text.** Produced the
  **DOM contract** (every class/id/element JS depends on) and 10 locally-runnable checks.
- 5-agent resource council → `RESOURCES-SPEC.md` (Phase 6, step "resource mentor").

**Bugs first** (`c03ac05`):
- `_day_unlocked()` — the `.locked` CSS class was the **only** thing sequencing the 40-day
  plan (both endpoints validated nothing); now server-gated (403).
- Back-button crash on the result screen; three safe-area misses; the `fitSvgText` font race.

**The visual redesign — direction "SIGNAL" (surfaces defined by light, not outlines):**
- Slice 1 tokens (`44b675b`): measured surface ramp (first attempt was invisible 1.084 mush —
  the exact failure the red team predicted; shipped at 1.24/1.19/1.29), inset-highlight
  elevation, radii 8/14/22, `--faint` accessibility fix, and `--brand-dim` fixing the
  skill-map weak/developing collision **within one accent**.
- Slice 2 type (`ff0dbe7`): **Archivo** replaces Space Grotesk (Faiz's call), the wordmark
  finally set in the display face, one 18px reading size for all lesson prose.
- Slice 3 surfaces (`32e6577`): borders → transparent fills, diagram gets its own plate.
  Second measurement catch: `--faint` had been fixed against `--bg` but `.label` sits on
  cards → moved to `--muted`.
- Slice 4 account sheet (`7258391`): topbar avatar → account sheet, **dashboard footer
  deleted**, all six `window.confirm/prompt` replaced with an in-app modal, **sign-out now
  confirmed**, the finished-plan card no longer contradicts itself.
- Slice 6a (`5efee0c`): sticky, **named** lesson bar ("Block 4 of 5 · Section 8 of 12"),
  tappable step index, and **bookmarks finally land on their section** (M6 closed).
- Slice 6b (`b2856e9`): full day list + saved sections moved to Your plan; dashboard keeps a
  3-row window.
- Slice 6c (`7640750`): `#view-result` deleted; the checkpoint review is now the recap's
  Checkpoint segment — **reachable forever** instead of exactly once.
- Slice 5 motion (`1ce8609`): skeleton-flash fixed the objective way (180ms delay-gate); the
  three feel questions (transitions/pills/haptics) left for Faiz's phone, each now a one-line
  token.

**Interaction phases** (`c44c67d` + `REDESIGN-PHASES.md`): tap ripple built; verdict
word-reveal, level ring, and Skills constellation/bento **specced but gated**. ~45 Magic UI
components rejected with reasons recorded.

**Design gallery** (`7961d95`): `tools/build_design_gallery.py` generates 13 component cards
that inline the real `style.css`; pushed to the claude.ai/design **"MentorOS"** project — the
only way Faiz can *see* the redesign before Aug 1 (screenshots time out in this environment).

**Diagram palette** (`ab6f509` + `bdb5397`): `prompts.py` still drew every diagram in the old
off-token palette — **including the purple the 3-Jul pass thought it deleted.** All colours
mapped to tokens; `migrateDiagramPalette()` remaps already-cached lessons at render time
(delete it after the Aug-1 regeneration).

**Resource Mentor** (`36ed318` → `RESOURCES-SPEC.md`): the mentor auto-finds the web's best
material for **any** subject (a grounded "Scout" at plan creation — you never name a
resource), weaves segments into the plan as **wrapped** days (mentor intro → the segment →
checkpoint on the segment), and adapts on every checkpoint (a "Monitor": fail a text day →
revision comes back as video, and vice versa; mastery unlocks optional depth). Verified: free
grounding is **500/day** (a plan uses ~10); the backfill rule ensures Faiz's own Aug-1 plan
gets resources too. **Specced, not built** — build gated on the deploy verify.

**Doc hygiene** (`b3f73b0` + `c41dee4`): session logged as `handoff.md` §14; council
postscript added; **`AUDIT.md` finally carries the SUPERSEDED banner** on its Batch D (the
#1 landmine — it still read as instructions to cut features Faiz had restored); new
**`DESIGN-DECISIONS.md`** (31 standing rules with provenance); `mentor-app-plan.md` marked
historical. This closes the pattern behind the project's worst regressions.

---

## What's left

**Faiz, ~1 Aug (when Render's free hours reset):**
1. **Verify the deploy** on the real phone: `/healthz` returns 200, then walk one lesson →
   one checkpoint → the account sheet → a bookmark jump. *(20 commits land at once — ~3× the
   council's "6 is the max sensible batch"; this walk-through is load-bearing.)*
2. **Fix UptimeRobot** — restrict the ping to study hours (or pause TriVi's) or the app
   suspends again ~31 Aug, mid-bootcamp.
3. **Restart the plan** — Start over → paste the 8-phase prompt → 40 days, 8h/day (costs
   nothing; the live account holds a 0-XP plan).
4. **Activate notifications** — Render env vars (VAPID + CRON_SECRET) + an UptimeRobot cron on
   `/api/cron/push` + in-app Enable. All built, never switched on.
5. **Judge the feel** and report back: transitions premium or sluggish? pill sequence a
   celebration or a parade? haptics right? does the new ramp/type read premium on-device?

**Claude, after Faiz's verdict:**
6. Tune the feel knobs (`--vt-out`/`--vt-in`, `MOTION`) from his answers · **delete
   `DIAGRAM_PALETTE_MIGRATION`** once the restart regenerates all lessons.
7. Gated interaction phases still open: verdict word-reveal, and the Skills constellation +
   bento (needs ~a week of real quiz data). *(Level ring DONE, `ad5d45b`.)*
8. **Resource Mentor — FUNCTIONALLY COMPLETE.** Slices 1–5 all built and locally verified:
   schema/cache (`9f635fe`), grounding+verify (`b83a936`), Scout (`147f37c`), resource-led
   days (`0cb5efe`), Monitor (`322dc0c`), + the probe (`a6cb290`). Discovery → visible →
   adaptive. **On-device follow-ups:** confirm the TWA YouTube deep-link opens the app; then
   the v1 polish (real resource titles, YouTube `?t=` segment timestamps, shrink text on
   resource days) as slice 6.
9. Remaining known items: the 17 remaining full-box borders vs the council's ~4 target,
   dashboard tiering, and the open blue-stripe question. *(H2 timezone bug DONE, `ae520f9`.)*

**Captured ideas (not scheduled — explore AFTER dogfooding):**
- **Dashboard / chat visual refresh** using Bklit UI and Magic UI as inspiration (Faiz's
  idea, 28 Jul). Constraints still bind: transform/opacity only, one accent, no continuous
  decoration — Magic UI was already mined this session and ~45 of its components rejected on
  exactly those grounds, so this is a *curation* pass, not adoption. "Bklit UI" needs a
  proper look first (unfamiliar reference). "For chats" implies a more conversational mentor
  than today's Ask box — that is NEW scope and must be weighed against the one-hub rule
  before any build. Do this only after Faiz has lived with the current redesign on-device;
  layering a new dashboard look on an unjudged redesign is the rework pattern to avoid.

**Reality check (28 Jul):** the app is NOT "feature complete + polish only." Two real
features remain unbuilt — the **Resource Mentor** (specced, ~0 lines) and the **gated
interaction phases** — plus the H2 timezone bug. Immediate next step is dogfooding + UX
tuning, but real feature-building follows it.

**The point of all of it:** Faiz's real 40-day placement bootcamp, run inside his own app.
That's the finish line every phase above was building toward.

---

## Phase 7 — Post-redesign backlog: real bug + first features (28 Jul, continued)

With the redesign shipped, Faiz said "do the remaining ones." Worked in dependency order,
building only what could be **verified locally** and flagging what needs his device/key.

- **H2 timezone streak bug FIXED** (`ae520f9`). `_bump_streak` / every `_today()` used the
  server's UTC date, so the daily boundary fell at 05:30 IST — a 22:00-Mon + 00:30-Tue pair
  is one UTC day, so Tuesday earned no credit and Wednesday could break a genuine two-day
  run. The `api()` helper now sends `X-TZ-Offset` on every request; `_local_date()`/`_today()`
  convert UTC→local; absent header → UTC (old behaviour, safe degrade). All six `_today()`
  guards became zone-aware for free. 12/12 units incl. the exact collision; live-verified
  (this env reports -330, Faiz's own zone).
- **Level ring BUILT** (`ad5d45b`, interaction phase 3 — its blocker, the account-sheet
  avatar, had shipped in slice 4). Gold XP-to-next-level arc around the avatar, driven by the
  same `lvFrac` the XP meter uses; additive (doesn't replace any width-meter), drawn inside
  the button's clip so the ripple's `overflow:hidden` can't crop it. Verified at 360px: no
  collision with the widest status, ring uncropped, letter above ring, still ripples.
- **Resource Mentor slice 1 BUILT** (`9f635fe`, schema 17 + global cache). Empty containers
  only (`plan.resource_spine`, `plan.resource_slots`, `state.monitor`) so a plan with no
  spine behaves exactly like today; new `resource_cache` collection (topic-keyed, 30-day TTL,
  surgical upsert, local-file fallback). 13/13 units. Purely additive, device-independent.

**Held at a real gate:** the next resource slice (`ask_grounded_text` in gemini.py) hinges on
the grounding probe, which **spends Faiz's Gemini quota / needs his key** — not run without
his OK. The resource UI slices need his phone (TWA deep-link) and his own D3 gate (verify the
deploy first). So the resource *backend foundation* is in; the *grounding + UI* wait for him.

Faiz then said **"run the probe and do everything else"** — clearing the quota gate. Continued:

- **Grounding probe RUN** (`a6cb290`, `tools/grounding_probe.py`, his key). All three spec
  assumptions confirmed empirically: grounding works on 2.5-flash free; grounding+JSON = 400
  (2-call shape mandatory); `groundingChunks` are expiring redirect URLs — the reliable URL
  source is the model's PROSE. Spec §1a records it.
- **Resource slice 2 BUILT** (`b83a936`): `gemini.ask_grounded_text()` (grounded, no JSON,
  lean) + `resources.py` — `normalize_topic`, `extract_urls`, and the 3-way `verify_url`
  (live / unverified / dead; a 403 is "alive enough to defend itself", never dropped; a
  redirect into a login wall = dead). 20/20 incl. live grounding end-to-end (found LearnVern's
  Python course, verified live).
- **Resource slice 3 — THE SCOUT — BUILT** (`147f37c`): `POST /api/plan/scout` +
  `resources.build_spine` (parallel discovery, cap 4, 70s budget) + surgical
  `save_plan_resources` + `maybeScout()` fire-and-forget from the dashboard (also the G1
  backfill). **Proven against Faiz's real 8-chapter plan: all 8 resolved, every URL LIVE** —
  NPTEL for Computer Fundamentals, learngitbranching.js.org for git, w3schools SQL, real
  YouTube courses for C/DSA/Python. 14/14 units + the live end-to-end. Idempotent, additive,
  never fails a plan.

Faiz then said **"build slices 4 and 5 now"** (overriding the D3 gate). Both built:

- **Resource slice 4 — resource-led days BUILT** (`0cb5efe`): `get_lesson` attaches the
  Scout's verified resource as `resource_segment` on every serve (cache or fresh, since the
  slot is plan-level); the stepped lesson gains a **"Watch" step** after the intro — the
  mentor's pick, link-out (never embed: TWA opens the native app), rewards-only. Verified
  end-to-end: opened dev day 2, rendered "Your mentor's pick · NPTEL" → the real course.
- **Resource slice 5 — the Monitor BUILT** (`322dc0c`): on checkpoint submit, inside the
  existing save (H1 untouched, no LLM call), the **modality switch** — fail a text day → the
  revision returns through the chapter's resource; fail a resource day → the revision goes to
  text; the mentor says why on the result screen. 16/16 units + live (fail day 4 → revision
  resource-led pointing at NPTEL; fail day 2 → revision text).

**THE RESOURCE MENTOR IS FUNCTIONALLY COMPLETE: discovery (Scout) → visible (resource-led
days) → adaptive (Monitor).** It finds real resources, weaves them into the plan, and adapts
to how you learn — the whole feature Faiz asked for.

**Still not built (correctly deferred):** verdict word-reveal (taste call, needs his eye on a
phone); Skills constellation/bento (needs ~a week of real quiz data). v1 resource limits
noted in the slice-4 commit (domain-as-title, no YouTube `?t=` segment timestamps yet, text
doesn't shrink on resource days, TWA deep-link untested without a device).

---

*Maintenance note for Claude: append each new phase at the bottom as a `## Phase N` section,
and keep "What's left" current — move done items out, add new ones. This file is the summary
Faiz asked to always exist.*
