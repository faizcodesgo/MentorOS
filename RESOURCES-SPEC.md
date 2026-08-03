# MentorOS — Resource Mentor Spec (Scout + Monitor)

**Status: SPECCED 27 Jul 2026 — BUILD AFTER the ~1 Aug deploy is verified live (owner's decision).**
Written from a 5-agent council (feasibility ground-truth / day design / architecture / red team /
critic-referee) run against the real repo, with API facts verified against official docs the same
day. Where seats disagreed, the critic's rulings (with primary sources) are what this spec states.

The one-line vision: **the mentor finds the world's best learning material for ANY subject by
itself, weaves it into the plan as real lesson days, and quietly adapts the plan to how the
learner is actually doing.** The learner — a beginner — never names a resource.

---

## 0. Locked decisions (owner, 27 Jul — do not relitigate)

- **D1 — Wrapped, never raw.** A resource-led day = short generated mentor intro (why this +
  what to watch for) → the external resource segment → try-it + checkpoint generated from the
  topic. The active layer (XP/streak/DNA/warm-ups) survives on every day.
- **D2 — Monitor runs on checkpoint submit.** Mostly deterministic; prose only via the next
  lesson's existing generation call (see §6 — the council found this makes the "one LLM call"
  nearly free).
- **D3 — Spec now, build after Aug 1 verification.** Nothing here ships before the 10 queued
  commits are seen working live.
- **D4 — Discovery is automatic at plan creation** (a "Scout" role, grounded web search).
  Any subject, not just CS. Long resources are segmented across chapters; a narrow ask gets
  only the relevant slice.
- **D5 — Second AI = second ROLE, not a second service.** Budget: ~10 calls per plan for
  Scout + resolution, Monitor ~free (see §6). The always-on reviewer rejected on 5 Jul stays
  rejected.

---

## 1a. PROBE RESULTS — empirical, real key, 28 Jul (`tools/grounding_probe.py`)

The council's secondary-sourced claims are now **run against the real key** and all hold,
with one design-shaping addition:

- **Grounding works** on `gemini-2.5-flash` with the free key: `tools:[{google_search:{}}]`
  → HTTP 200, `groundingMetadata` present. It returned a genuinely good pick (freeCodeCamp's
  Git course) with a **real, direct URL**.
- **Grounding + `responseMimeType:application/json` → HTTP 400**, exact message *"Tool use
  with a response mime type: 'application/json' is unsupported"*. **The 2-call Scout shape is
  mandatory, confirmed.**
- **`groundingChunks` only populates when the answer COMPLETES** (a `maxOutputTokens` cap that
  truncates the answer returns zero chunks — just `searchEntryPoint` + `webSearchQueries`).
  When present, its `uri` is the **expiring `vertexaisearch.../grounding-api-redirect/...`
  redirect** — never store it.
- **The reliable URL source is the PROSE, not the chunks.** Asked to "state the full https
  URL explicitly," the model puts a real direct URL in its text. **Scout design: extract
  URLs from the grounded prose (regex, strip trailing markdown like `**`), verify them, and
  give the grounded call enough output budget to finish.** groundingChunks (redirect-resolved)
  is a secondary source, not the primary one. This refines the spec's original "chunks carry
  the URLs" toward "prose carries the URLs."

## 1. Verified ground truth (do not re-derive; re-verify only where flagged)

| Fact | Status |
|---|---|
| Grounding with Google Search on the app's REST path: `"tools": [{"google_search": {}}]` in the v1beta `generateContent` body. Supported on **gemini-2.5-flash AND 2.5-flash-lite** — both models in `gemini.py`'s fallback chain. (Note: the fallback is 2.5-flash-lite; "2.0-flash" notes elsewhere are stale — its free quota is zero.) | **VERIFIED** (official docs) |
| Grounding free quota: **500 RPD on the FREE tier** ("Free of charge, up to 500 RPD, limit shared with Flash-Lite RPD" — pricing page fetched 28 Jul as a primary source). The oft-quoted 1,500 RPD is the **paid Tier 1** row — two council seats misread it and one probe of the pricing page settled it. Grounded calls also consume ordinary request quota; on an unpaid key, exceeding = 429, never charges. Scout's ≤10/plan is **2% of the daily cap**. | **VERIFIED** (primary source) — still run one empirical probe with the real key before building; costs nothing |
| **Grounding + forced JSON are mutually exclusive on 2.5** — combining `google_search` with `responseMimeType: application/json` returns 400. Structured-output-with-tools is Gemini-3-only. `gemini.py:53` hardcodes the mime type ⇒ Scout needs a new entry point `ask_grounded_text()` reusing the sweep/retry skeleton minus JSON mode; extract JSON locally (`_parse_json`/`_repair_json` on the prose, fallback: one ungrounded `ask_json` structuring call). **The Scout is a 2-call shape by necessity, not choice.** | **STRONG but secondary-sourced** (GitHub issues + forums, not docs) — confirm in slice 2's probe: one grounded call with and without the mime type |
| **`groundingChunks[].uri` are Google REDIRECT URLs** (`vertexaisearch.cloud.google.com/grounding-api-redirect/…`), not real source URLs, and they expire (~30 days, exact window unverified). **Never store or show them.** Resolving the 302 during the verification pass yields the real URL for free; also instruct the Scout to state URLs in its prose as a second recovery path. | **VERIFIED** (python-genai#1512) |
| GitHub API: search = 10 req/min unauthenticated (enough for Scout), 30/min with a token; code search needs a token outright. | **VERIFIED** — `GITHUB_TOKEN` is an OPTIONAL env var, never a setup prerequisite |
| gunicorn: `--workers 2 --threads 4 --timeout 180`. A `ThreadPoolExecutor` inside one request does not consume request slots — precedented at `app.py:546` (cap 4) and `app.py:1483` (cap 6). | **VERIFIED** (`render.yaml:10`) |
| Exact current free-tier RPM/RPD for 2.5-flash: dashboard-only now, not in static docs. Keep combined Gemini concurrency ≤4 (matches `app.py:546`). | **UNVERIFIED — design defensively** |

Sources: ai.google.dev grounding/pricing/rate-limits/structured-output docs, googleapis/python-genai
issues #665 and #1512, Google AI dev forum grounding-quota thread, docs.github.com rate limits,
Cloudflare WAF bot-management docs.

---

## 2. Schema (all new state; migration = schema 17, `setdefault` only — old docs behave as today)

**`state.plan.resource_spine`** — written ONCE at plan creation (whole-doc write fine there).
2–5 entries, ≤8KB total:

```
{ id, title, platform, url, kind,            # kind: video|course|docs|repo
  total_length,                              # seconds for video, else null
  segments: [ { chapter_idx, day_offset?,    # day_offset only when confident
                label, start, end } ],       # start/end ONLY from parsed chapter data (§4)
  verified_at, why }                         # why: one line, mentor-voice, level+pace based
```

**`state.plan.resource_slots`** — a PARALLEL MAP keyed by stable day id (same keying as
`lessons`/`progress`/`quizzes`), NOT fields inside the curriculum array. ~50 bytes/day.
`{"<day_id>": {spine: id, segment: idx, modality: "resource"}}`
*Why a map:* one surgical `$set` on `state.plan.resource_slots`; writing into the curriculum
array needs positional `arrayFilters` updates — a complexity tax, and an H1 clobber risk.
Slot segment content carries `{start_s, end_s, start_label, end_label, chapters_covered[]}`.

**`state.monitor`** — the ONLY subtree any async monitor path may write. Hard-capped ≤2KB:
`{ last_compose_day, trend: [≤10], log: [≤20 short strings], compose: null | {day_id, directive} }`

**`plan.phases[i].deeper`** — optional, one per chapter, emitted in the same Scout pass:
`{url, title, duration_seconds, note}` — the go-deeper shelf (§6 R4).

**Global `resource_cache` collection** (NEW — beside `state`/`users`/`config`): **ONE
collection, keyed by normalized topic string** (lowercase, trimmed, punctuation-stripped — NOT
a goal hash: two users "learning Git" phrase goals differently, but Scout queries per-topic, so
topic keys are what make cross-user hits happen). Each entry carries its resolved URLs WITH
verification metadata inline: `{resolved: [{url, platform, kind, title, total_length,
chapters_raw, status, verified_at}], created_at}`. *(The critic rejected a second, URL-keyed
collection as a second index for a user base of one.)* Mongo **TTL index on `created_at`,
30 days — matching `_CACHE_TTL_DAYS` (`youtube.py:21`)**. ~2KB/entry cap (top ~5 resources,
URLs+metadata only, never page content). All writes surgical `update_one($set, upsert=True)` —
the `save_notifications_for` pattern (`storage.py:480-492`). **Never in the per-user doc**:
whole-doc rewrite (H1) + M0 size. Not covered by `backup.py` and doesn't need to be — it is
rebuildable by construction.

---

## 3. The Scout — automatic discovery

**Hook: a NEW `POST /api/plan/scout`.** Not `negotiate` (user hasn't committed; retries would
burn grounded calls), not `plan_init` (plan creation must never depend on discovery), not inside
generation. The frontend calls it once when generation reports `done: true` — which both
generation paths already return, so `generate_phase` AND `generate_all` need **zero changes**
and the H3 dual-path trap dissolves. **This also covers the ~1 Aug plan restart automatically:
Start over → generate → `done` → Scout runs on the new plan.** Idempotent: returns early if
`plan.resource_spine` exists.

**G1 — the backfill rule (critical; every seat missed it, the critic caught it):** the owner's
real bootcamp plan is created ~1 Aug, BEFORE this feature ships — and "no mid-plan re-scout"
would exclude the only actual user. Mandate: **on dashboard load, if a plan exists with no
`resource_spine` and no scout attempt recorded in the last 24h, fire the scout endpoint once,
covering the REMAINING days only.** The same rule heals `/api/restore` of a pre-Scout snapshot.
(This is a one-time backfill through the same idempotent endpoint — it is NOT the "mid-plan
re-scout" that §9 bans, which is *re-running discovery over an already-scouted plan*.)

**G5 — claim the quota win:** a resolved YouTube slot replaces the day-level `search.list`
(~100 units, `app.py:663-669`) with a 1-unit `videos.list`. Across a 40-day plan the Scout
PAYS for itself in YouTube quota.

**Pipeline (server, inside the one request, time-sliced):**
1. Read the saved curriculum (day titles, topics, `resource_queries`, hours/day, level, class).
2. ≤10 `ask_grounded_text` calls, sequential, each try/except, `max_retries=1`, **no second
   sweep** (the full `ask_json` ladder is ~18 HTTP attempts — a 503 night would storm). Partial
   spine is fine.
3. Extract JSON locally (2-call shape, §1).
4. **Resolve every candidate — no model-authored URL ever reaches the UI:**
   - YouTube: `videos.list` by id (~1 unit — never a 100-unit search when Scout gave a URL),
     duration + chapters via the existing parser (`youtube.py:87-100`). Add `regionCode=IN`;
     reject results whose `contentDetails.regionRestriction` blocks IN.
   - Redirect URLs from grounding: resolve the 302 to the real URL first (§1).
   - Non-YouTube: GET with `Range: bytes=0-1023` + browser User-Agent (NOT HEAD — CDNs 405 it),
     5s timeout, one retry on timeout only, all URLs concurrent in a ThreadPoolExecutor, wave
     capped ~8s. **Three-way verdict:** DEAD (DNS fail / refused / 404 / 410) → drop;
     UNVERIFIED (403/401/405/429/challenge page) → keep, mark, show without timestamps — *a 403
     is evidence the site is alive enough to defend itself, never drop on it*; LIVE (2xx/3xx).
     A redirect landing on a login/paywall URL = verification failure → drop to search-link.
5. Segment mapping (§4), dedup check: **the pair (videoId, segment) must be unique across the
   plan** — deterministic Python, not a prompt hope.
6. ONE `update_one` `$set` writing `resource_spine` + `resource_slots` (+ `phases[i].deeper`),
   and upserts into `resource_cache`.

**Budget (enforced, not aspirational):** plan creation + Scout ≤90s wall, soft target 60s;
Scout gets a **45s time slice** — on expiry or 503/429 exhaustion the plan ships WITHOUT
resources and today's machinery (`resource_queries` → YouTube search → search links) carries
every day. Degradation chain for the calls themselves: grounded 2.5-flash → grounded
2.5-flash-lite (same body, same pool — the existing model-switch carries grounding) →
ungrounded proposal verified through `youtube.search_videos` → no spine.

**The Scout prompt must contain, verbatim (red team, mandated):**

> *"Choose for THIS learner: level {level_notes}, goal {goal}, {days} days at {hours}h/day.
> Judge fit ONLY by: (1) prerequisites this learner already meets; (2) pace — the relevant
> slice must fit today's {video_mins}-minute video budget; (3) direct coverage of today's
> objectives. Fame, production quality, and general acclaim are NOT criteria. A famous full
> course whose relevant slice exceeds the day budget is a WRONG answer. For each pick, state
> in one line which prerequisite and pace check it passed; if you cannot, reject it."*

> *"Prefer resources that are free, watchable without any account or sign-in, and available in
> India. NPTEL and Indian university lectures are first-class candidates for engineering and
> placement topics when the pace fits this learner. Reject anything paywalled, login-walled,
> or region-restricted."*

(`video_mins` piped from `structure_for_hours` — the pace check is numeric, not vibes. NPTEL's
YouTube channels flow through existing machinery; no new integration.)

---

## 4. Segmentation honesty (the anti-"fake timestamp" rule)

- A `start–end` timestamp may be shown **only when both boundaries are literal parsed chapter
  timestamps** (`youtube.py:87-100`; note the parser requires a 0:00 first chapter and ≥3
  entries — absence is common, not an edge case).
- Anything model-interpolated → **whole-resource mode**: "Watch this 23m video — you need the
  parts on X and Y; stop when it moves to Z." Named landmarks, never invented minutes.
- Shown timestamps are attributed — *"the 'Lists' chapter, 12:34 per the video's own chapters"* —
  so an author's off-by-minutes error reads as the video's, not the app's.
- Numeric fit rule: `end - start` must fit the day's `video_mins` budget; too long → shorter
  slice or different resource.
- **This amends `prompts.py:613`**, which currently *instructs* fake precision ("the first ~15
  minutes") — replace with named-landmark phrasing; minute numbers only from chapter data.
- No chapters and `duration ≤ video budget × 1.25` → whole video is the segment; longer →
  the day degrades to text-led with the video as an ordinary supplement.

---

## 5. The wrapped resource-led day

**Lookup & resolve:** extend `get_lesson` (no new endpoint — it already blocks 15-60s on
Gemini; a millisecond slot lookup + `resource_cache` read is invisible, and a second endpoint
means a second loading state and a second failure mode). Before the existing day-level video
block (`app.py:~659-669`): read `plan.resource_slots[str(day)]` → `resource_cache` doc →
if `verified_at` < 30 days, build segment context; if stale, ONE 3s re-verify, try/except,
never blocking. A YouTube slot **replaces** the day-level search — zero quota. Verification
of remaining URLs runs concurrently with lesson generation in the same request: added wall ≈ 0.

**Generation:** a slim `resource_lesson_prompt` variant — intro (why this resource + 2-3
things to watch for), exactly 2 sections ("before you watch" primer, "after you watch"
consolidation with `try_it`), practice + quiz. Output is small ⇒ resource days generate
FASTER than text days. The segment passes through the existing `videos_context` /
`resources_note` machinery, which already knows how to say "watch 12:34–28:00 today."

**The stepped UI** gains one step kind `{kind:"watch"}` after the intro: the mentor's
watch-for note + one large **link-out card** (`start_label–end_label`, chapters covered,
duration). **Link out, never embed** — four reasons, all load-bearing: the app currently loads
ZERO external resources in a lesson (a YouTube iframe pulls ~1MB of player JS into a TWA
WebView on a budget phone); an autoplaying thumbnail is continuous decoration (banned); an
external link fires the Android intent into the real YouTube app (native resume, speed,
background audio — an embedded player gets none); an embed can't enforce the segment anyway.
The deep link carries `?t={start_s}` so it at least *starts* right; the end bound is held by
the mentor's note + the checkpoint, which is the real gate.

**`est_minutes` honesty:** on resource days the segment counts at its REAL length
(`(end_s-start_s)/60 + wrap`), not the supplemental-video cap — the video IS the lesson. The
Today card then honestly says "· 48m today."

**Checkpoint:** generated from **topic + objectives + `chapters_covered` labels** — the
warm-up precedent (`warmup_generate_prompt` proves quizzes need no lesson text). Red-team
mandate: *"the checkpoint tests ONLY concepts named in SEGMENT COVERAGE; a concept in the
resource but outside the segment is out of bounds."* No transcript fetching (new quota surface,
new failure mode; chapter labels suffice). Grading stays pure-Python. Didn't watch it?
Nothing punitive — rewards-only holds; the result line notices kindly: *"If you didn't get to
the video, no harm — tomorrow covers the same ground my way."*

---

## 6. The Monitor — on checkpoint submit

**Insertion:** in `submit_quiz`, AFTER the DNA recompute and the existing revision-insert
trigger, BEFORE the existing single `save_state` — its inline writes ride the request's
existing read-modify-write window, so **H1 is not widened by one byte**. Sequence mandate:
grade → decide → ONE save (unchanged shape). Response text built from a post-write re-read,
never from in-memory intent.

**Deterministic decision table (complete, closed set):**

| # | Condition | Action |
|---|---|---|
| R1 | score <50%, day was TEXT-led, spine has an UNUSED segment covering a wrong topic | the auto-inserted revision day (existing machinery) gets that segment: `resource_slots[new_id] = {spine, segment, modality:"resource"}` — the retry teaches through the other modality. No spine segment available → `resource_queries: topics[:1]` and the existing day-level search resolves it at revision open |
| R2 | score <50%, day was RESOURCE-led | revision day gets `modality:"text"`, no slot — that route just failed; don't repeat it |
| R3 | score 50-80% | no structural change; append to `monitor.trend`; wrong topics already enter the review ladder |
| R4 | score ≥80% on a resource-led day | log "worked"; later slots in the phase keep resource modality. Chapter topics mastered → the `phases[i].deeper` shelf row becomes visible (recap block + Skill-map row). **Deepen, never skip** (26 Jul council) |
| R5 | live misconception maps to an unwatched spine segment | `monitor.compose = {day_id: next, directive: "point at segment X"}` — no new day |
| R6 | caps | the existing one-revision-per-boss guard (`app.py:931-933`) holds. **A "1-per-5-days plan cap" does NOT exist in code — the council brief overstated it (critic-verified); the Monitor therefore adds an explicit `monitor.last_action_day` cooldown, ≥5 days between structural changes.** Every Monitor-created day carries `monitor_key = "{trigger_day}:{action}"` — skip if present (idempotent). Modality writes are ABSOLUTE target state, never a toggle (a doubled write must be a no-op). Order = midpoint between neighbours, not `+0.5` (collision-proof) |
| R7 | **prose** | NO LLM call at submit, ever. The immediate result-screen line is a template; anything composed folds into the NEXT lesson's existing generation call as an ADAPTATION note beside PROGRESSION — the "one Monitor LLM call" costs zero extra calls |

*(R7 is the council's synthesis: the architecture seat proposed a post-save daemon thread, the
red team proposed deferred compose. Deferred-into-existing-call wins — simpler than threads,
zero marginal cost, and the score is durable before any of it.)*

**Visibility — five mentor lines, five existing surfaces (exact copy in the day-design
report; templates, no AI):** result screen (modality-switch explanation: *"reading it once
didn't stick, and that's normal… this time you'll watch it happen instead"*), dashboard
greeting (*"different door, same room"*), the revision lesson's intro (ADAPTATION note in the
already-happening generation call), the revision recap carry line, the chapter-recap deeper
row (*"you're past 80% here, so I left something deeper on the shelf — optional"*).

---

## 7. Degradation ladder (every rung silent; rung N fails onto rung N+1, which already ships)

verified segment with timestamps → verified resource, whole-resource mode (no timestamps
promised) → unverified spine link (marked, no timestamps) → today's day-level YouTube video →
search link → text-only lesson. **Scout dead entirely = exactly today's app.** A plan must
never fail, slow past budget, or block because discovery failed.

## 8. Cost guards

Scout `max_retries=1`, no second sweep · `videos.list` (1u) over `search.list` (100u), always
behind `youtube_quota_reserve` · verify at resolve, re-verify only on TTL expiry or a user
"link broken" tap — never on render · compose cooldown ≥5 days (`last_compose_day`) · a
`scout_quota_reserve` daily counter in `config` (same shape as the YouTube one; fail-open —
the fallback is cheap) · combined Gemini concurrency ≤4.

## 9. NOT in v1 (rulings, one line each)

Embeds/iframes (link-out only) · transcript/caption fetching · timestamps on non-YouTube
platforms (chapters are a YouTube concept; others get whole-resource mode) · paid platforms ·
user ratings (a "link broken" report only) · mid-plan Scout re-runs (the Monitor may swap to
an already-resolved alternate, never trigger new discovery) · more than one primary + one
fallback resource per day · per-section resources (existing `_attach_section_videos` keeps
that job) · Monitor-driven re-pacing (pace-check owns it) · any mutation outside the closed
set (insert revision day, set modality, surface deeper) — the LLM composes wording, never
invents mutations.

## 10. Build order (after Aug 1 verify; each slice locally verifiable headless + revertible)

1. **Schema 17** + `resource_cache` helpers + empty spine/slots/monitor. *Verify: migrate a
   prod-shaped doc copy; diff shows only new empty fields.*
2. **`ask_grounded_text`** in gemini.py (+ the empirical grounding probe with the real key —
   the one red-team precondition) + redirect resolution + the 3-way URL verifier. *Verify:
   probe returns groundingMetadata; a Cloudflare-403 URL classifies UNVERIFIED, not DEAD.*
3. **Scout endpoint + prompt + frontend one-liner** on generation-done. *Verify: local plan →
   spine JSON sane, dedup holds, kill mid-run → plan intact; run twice → idempotent.*
4. **Resource-led days**: get_lesson branch + `resource_lesson_prompt` + watch step + link-out
   card + est_minutes. *Verify: hand-written slot renders; delete spine → byte-identical to
   today; segment-coverage rule visible in the generated quiz topics.*
5. **Monitor deterministic table + visibility templates.** *Verify: scripted submits at
   40/65/90% against fixtures assert R1/R2 writes, caps, idempotency keys, absolute-state
   modality; the H1 window's shape unchanged.*
6. **Deeper shelf + ADAPTATION note injection.** *Verify: mastered fixture shows the recap
   row; next lesson's prompt contains the note.*

## 11. Known gaps, risks & defaults (accepted, eyes open)

- **Offline (G3):** a resource-led day needs network for the video; the text wrap is cached
  like any lesson. Two mandates soften it: the wrap must be **self-sufficient** (primer +
  consolidation teach the core even unwatched), and **resource-led days are capped at ~1 in 3**
  (default O3 below) so a bad-network day is never a lost day.
- **Sequencing (G2):** the five visibility copy-lines land on surfaces the visual redesign's
  slices 4-6 also touch (greeting, Today card, recap, result). **Resource UI slices build
  AFTER redesign slices 4-6**, and the watch card obeys the locked visual rules (Archivo, one
  accent, no continuous decoration).
- **TWA deep-link behaviour** (`?t=` into the YouTube app) is high-confidence but untested on
  the real phone — test after Aug 1, before slice 4.
- **Chapter markers are author-written** — sometimes wrong. The attribution rule (§4) makes
  that the video's error, not the app's; the "link broken" report is the relief valve.

**Owner-overridable defaults** (the council's three remaining decisions, applied as defaults
rather than blockers — say the word and any of them flips):
- **O1 — GitHub scope:** v1 hunts videos/articles/docs only; no repo hunting, no token.
- **O2 — Backfill:** when this ships mid-bootcamp, it DOES backfill the remaining days of the
  running plan (G1's rule).
- **O3 — Mix:** resource-led days capped at roughly 1 in 3, even when great videos exist —
  offline safety + variety; the cap is a Scout-prompt constraint plus a deterministic
  post-check.

## 12. The owner's three questions, answered

1. **"Is learning from resources instead of long texts a good idea?"** Yes — wrapped (D1).
   Raw consumption is the fluency illusion; wrapped keeps retrieval. And on resource days the
   generated text SHRINKS to an intro + consolidation, which is your actual complaint answered.
2. **"How will it find resources when the user can't name any?"** The Scout, automatically, at
   plan creation, via real grounded Google Search — for any subject. You never type a resource
   name. Verified free at your scale (500 grounded requests/day on the free tier; a plan uses
   ~10 — 2% of one day's cap).
3. **"Another AI for this and monitoring?"** Yes as roles (Scout at plan time; Monitor on
   checkpoint submit), no as a service. Total added cost: ~10 calls per plan + zero per
   checkpoint (R7). The 5 Jul objection to an always-on reviewer stays satisfied.
