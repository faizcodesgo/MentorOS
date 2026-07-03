# AI Mentor App — Idea Evaluation & Plan (LLM Council Report)

*Prepared by Claude for Faiz, 2 July 2026. Method: 4 independent evaluators (product/UX, startup/VC, engineering feasibility, learning science) + 1 web market researcher, then synthesized. Reviewed by ChatGPT (see section 10). This document is self-contained — share it with any AI or person for review.*

---

## 1. The idea (as proposed)

An AI mentor app where the user sets any **goal + duration** (e.g., "learn Python in 10 days"). The app:
1. Generates a structured, adaptive curriculum and schedule
2. Acts as a professional AI mentor with persistent memory of strong/weak areas
3. Recommends external resources (YouTube videos, free courses)
4. Sends surprise quizzes through push notifications
5. Assigns projects, reviews submitted work, re-teaches weak areas
6. **Enforces focus**: blocks distracting apps during study sessions; if a project deadline is missed, blocks the entire phone until the work is submitted

Goal and duration are variables so it works for anyone, not just the builder.

---

## 2. Council scores

| Lens | Score | One-line verdict |
|---|---|---|
| Product / UX | 5/10 | Great accountability insight wrapped around a coercive mechanic most users will uninstall rather than obey |
| Startup / VC | 3/10 | Zero-moat AI-tutor category; the enforcement hook is the only differentiated sliver |
| Engineering (for this builder) | 4/10 as specced, **7/10 with enforcement descoped** | Features 1–5 are a doable stretch; feature 6 is the trap |
| Learning science | 6/10 | Evidence-based core (retrieval practice, projects, adaptivity) undermined by punishment architecture |

**Overall: ~4.5/10 as specced → ~7/10 with the changes below.** The idea is good; one feature (forced full-phone lockout) is dragging every score down, and it happens to also be the technically hardest one.

---

## 3. Does it already exist? (market research, mid-2026)

- **AI tutoring is commoditized.** ChatGPT Study Mode (Jul 2025), Gemini Guided Learning (Aug 2025), Khanmigo (~2M users), TutorAI, StudyFetch, Sololearn (21M+) — all generate lessons/plans. None enforce anything; all are "pull-based" (user must open the app). Free frontier-model study modes make a generic AI tutor a *feature*, not a product.
- **Blocking apps are a real category** — Opal, Forest, AppBlock, one sec, Brick — but blocking is tied to *time schedules*, never to *learning outcomes*.
- **The overlap is emerging but thin**: StudyLock (block apps, pass an AI quiz on your uploaded notes to unlock), QuizScreen and 1Question (kids answer questions to unlock the phone). These validate the mechanic but are flashcard-level — no curriculum generation, no mentor memory, no project review.
- **Nobody combines** goal→curriculum + mentor memory + proactive quizzes + project review + outcome-based blocking. That exact loop is genuinely unoccupied.
- **Market warning signs**: edtech VC funding down ~72%; Chegg collapsed ($14.7B → ~$100M), Byju's app delisted. Winners are narrow and vertical: Speak ($1B valuation, AI English tutoring only). Commitment-device businesses (Beeminder, stickK, Forfeit) are real but small.

**Startup potential verdict:** as a general "learn anything" app — weak, the giants give it away free. As a **narrow, verticalized commitment-device learning app** (e.g., Indian engineering students prepping DSA/placements) — a plausible niche with real distribution via college networks. Realistically: an outstanding portfolio project with a small-business ceiling, not a VC-scale startup as specced. That's still very valuable — it touches LLM orchestration, memory, notifications, scheduling, and Android system APIs, which is a killer placement-interview story.

---

## 4. The hard technical truth about phone blocking

- **iOS: full-phone lockout by a third-party app is essentially impossible.** The Screen Time API (FamilyControls/DeviceActivity) requires special Apple approval, only shields selected apps, and the user can always disable it in Settings. Treat iOS blocking as off the table.
- **Android: aggressive app-blocking is possible, true lockout is not.** UsageStats + overlay permission can detect and cover distracting apps (how AppBlock/Forest work). AccessibilityService is more reliable but Google Play frequently rejects that use. "Block the ENTIRE phone" needs Device-Owner/kiosk mode — not realistic for consumers. The user can always uninstall.
- **Conclusion:** enforcement must be designed as *strong friction the user opts into*, not an unbreakable lock — because an unbreakable lock cannot be built.

## 5. The learning-science verdict on punishment

Precommitment ("Ulysses contracts") genuinely improves completion — but the evidence supports **voluntary, self-chosen** constraints. App-imposed punishment violates self-determination theory: it destroys autonomy, the strongest predictor of sustained learning, and users learn to avoid the app rather than to learn. Also, a deadline-miss lockout punishes life events (illness, exams, family), not laziness.

**The inviolable design principle: the app may offer chains; the learner must choose to wear them — and be able to renegotiate the goal without punishment.**

What the idea gets *right* per research: surprise quizzes ≈ the testing effect (retrieval practice — one of the most robust findings in learning science); project-based assessment + re-teaching ≈ Bloom's mastery learning; adaptive difficulty + memory ≈ desirable difficulties.

---

## 6. Recommended changes (council consensus)

1. **Replace "punishment" with "strictness levels the user chooses"** at goal creation: Chill (reminders only) / Standard (streaks + app blocking during sessions) / Strict mode (Android: missed milestone → distracting apps blocked until submission — user consented upfront and can do an "honorable renegotiation" that resets the streak instead). This keeps the differentiator, drops the churn bomb.
2. **Realistic-duration negotiation**: if the user asks for "Python in 10 days," the mentor should push back like a real mentor — "here's what's achievable in 10 days; full goal needs 30" — instead of generating a doomed plan.
3. **Replace "random" surprise quizzes with spaced repetition (FSRS/SM-2)** driving notification timing from each topic's forgetting curve, within user-set quiet hours. Feels like surprise, works like science.
4. **Confidence-calibrated quizzes**: user rates confidence before seeing the answer; high-confidence wrong answers get priority re-teaching (hypercorrection effect).
5. **Make the memory visible**: a "what your mentor knows about you" skill map screen — turns the invisible differentiator into a trust-building, shareable artifact.
6. **Verticalize first**: launch for one audience you deeply understand — Indian engineering students (semester subjects, DSA, placement prep). "Learn anything" comes later.

---

## 7. Feature priority

**MVP (build first):** goal + duration onboarding → AI-generated curriculum; daily lesson screen; quiz + progress tracking; mentor chat with persistent memory; resource recommendations (YouTube Data API).

**V2:** push-notification quizzes (spaced repetition); project assignment + AI review with re-teach loop; skill map screen; streaks.

**V3 (Android app phase):** wrap as Android app (TWA/WebView), opt-in focus mode (block chosen apps during study sessions), strict mode.

**Later / reconsider:** flashcards, code playground (embed an existing one, don't build), iOS.

**Cut:** full-phone lockout (impossible + harmful), building for "everyone" on day one.

---

## 8. Build plan (for a beginner developer, part-time)

**Stack:** what Faiz already knows — web app (HTML/JS or React later), Node/Express or Flask backend, SQLite/Postgres, deployed on Render, Gemini API (free tier) with strict JSON-schema outputs. PWA + Web Push for notifications. Android native comes only in Phase 3.

- **Phase 1 (weeks 1–3): Curriculum engine + lessons.** Goal/duration input → mentor negotiates a realistic plan → generates day-by-day curriculum as JSON → daily lesson screen. One vertical (e.g., Python or DSA).
- **Phase 2 (weeks 4–6): Quizzes + memory.** Quiz after each lesson; results stored per-topic; a learner profile (strong/weak topics, quiz history summary) injected into every mentor prompt; mentor chat screen.
- **Phase 3 (weeks 7–9): Proactive layer.** PWA install + Web Push; spaced-repetition scheduler picks quiz times; resource recommendations via YouTube API.
- **Phase 4 (weeks 10–13): Projects.** Milestone projects; submission (text/code/GitHub link); AI review → weak-area re-teach; skill map screen.
- **Phase 5 (months 4–6): Android + focus mode.** Wrap the PWA, add opt-in session blocking (UsageStats + overlay), strict mode with consent and renegotiation.

**Realistic MVP timeline: 8–12 weeks part-time.** Biggest risk: starting with the blocking feature before the mentor is good — build the mentor first; the mentor is the product, blocking is a feature.

---

## 9. Decisions locked (2 July 2026, confirmed by Faiz)

1. **Strictness levels adopted** exactly as in section 6.1: Chill (reminders) / Standard (streaks + app blocking during study sessions) / Strict (missed milestone → distracting apps stay blocked until submission, consented upfront, with "honorable renegotiation" escape that costs the streak). No forced full-phone lockout.
2. **All five council suggestions adopted**: mentor negotiates duration; spaced repetition (FSRS/SM-2) drives quiz notifications; confidence ratings on quiz answers; visible "what your mentor knows about you" skill map; PWA-first build order with Gemini, Android focus-mode wrapper in Phase 5. The mentor is the product; blocking is a feature.
3. **First vertical = Faiz's own 50-day CSE prep** (DSA/CSE fundamentals). He is user #1 and will dogfood it during his actual prep.
4. **His phone is Android** — focus mode targets Android only.
5. **API costs parked**: MVP runs on the free Gemini tier (fine for one user). Multi-user cost model deferred until the app has proven itself.

---

## 10. ChatGPT review — triage (2 July 2026)

ChatGPT reviewed this plan and proposed 15 additions plus a broader vision ("an AI Operating System for Learning": plan → teach → test → review projects → build portfolio → prep interviews → guide career → track growth → keep accountable). It also endorsed the same removals as the council (no custom code playground, Android-first, one vertical, minimal gamification). Triage:

### Adopted into MVP (cheap, high-value, mostly prompt/data work)
- **Mentor personality (GPT #1)**: the mentor notices patterns and adapts ("You've struggled with recursion three times — let's visualize the call stack instead"). Implemented via the mentor system prompt + learner profile injection. Free to build; the core differentiator.
- **Learning DNA v1 (GPT #2)**: extend the learner profile beyond weak/strong topics — preferred format (video vs reading), usual study time, quiz-rushing behavior, average session length. Start with a handful of fields; grow over time. This is what makes every user's mentor unique.
- **Dynamic roadmap (GPT #4)**: made explicit — every quiz result mutates the plan (mastered fast → skip lessons; failed → auto-insert revision days). This was always the intent of "adaptive"; now it's a hard requirement.
- **"Why am I learning this?" (GPT #3, lite)**: every lesson includes a real-world/interview relevance section (Binary Trees → used in databases, asked at Google/Amazon). One extra field in lesson generation — near-zero cost, big motivation payoff for the placement vertical.

### Adopted into V2
- **AI Interviewer (GPT #6)**: mock interviews after each chapter (theory + coding + follow-ups). Perfect fit for the placement-prep vertical; it's a chat mode, not a new system.
- **Socratic AI Debugger (GPT #7)**: paste code → mentor asks "which of these three issues would you investigate first?" instead of fixing it. Another chat mode.
- **Weekly report (GPT #9)**: Sunday summary — hours studied, improvement %, strongest/weakest, next-week recommendation. Cheap: a scheduled job over data we already store.
- **Project choice (GPT #5, simplified)**: each milestone offers 2–3 project options teaching the same concepts, instead of one fixed project.
- **Burnout prediction (GPT #13)**: falling scores + shrinking sessions + postponements → mentor proactively reduces tomorrow's load. Aligns with the "no punishment" principle; simple heuristics on existing data.
- **Memory timeline (GPT #15)**: merged into the skill-map screen as a progress-journal view ("Week 1: didn't know variables → Week 8: first API").
- **XP v1 (GPT #8, minimal)**: XP for outcomes (bugs fixed, projects shipped, revision done) not app-opens; no coins/leaderboards yet.

### Deferred to V3+
- **Auto-portfolio (GPT #10)**: every project → GitHub repo + README + resume bullet. Genuinely great for the vertical, but it's a whole subsystem (GitHub API, deployment); build after the core loop works.
- **Mission mode (GPT #11)**: mission-framed curriculum ("Build a chatbot — you'll need: variables ✓ loops ✓ APIs") — a UX re-skin of the roadmap; do it when redesigning UI.
- **Mentor council (GPT #12)**: specialized mentors (coding/career/interview/motivation) with a router choosing who responds. Mostly prompt-persona work but adds complexity; revisit when the single mentor is strong.

### Parked
- **Community challenges (GPT #14)**: requires a user base that doesn't exist yet. Revisit at product-market fit.
- **"AI OS for Learning" vision**: kept as the north star, not the spec. Note the tension in the review itself: it says "focus on one vertical until PMF" and also "become an operating system" — the answer is sequence, not both at once. MVP stays: mentor + curriculum + quizzes + memory for one vertical.

---

## 11. RPG direction (adopted 2 July 2026)

Faiz wants the app to feel like a game so studying is addictive. ChatGPT's framing adopted: **"premium productivity app inspired by RPGs, not a game"** — dark mode default, indigo/purple accents, Discord/Notion-level polish, RPG language inside the experience but plain navigation (Home / Learn / Projects / Mentor / Progress).

Mapping onto the existing plan:
- Goal → **Main Quest** (progress %). Daily lessons → **Quests**. Checkpoint days become assessment quests.
- XP v1 (already adopted from GPT review) becomes the core loop: XP for completing lessons/practice/homework — outcomes, not app-opens. Level + rank derived from XP.
- Skill map (already adopted) becomes the **Skill Tree** with per-topic levels and locked future topics.
- Projects → **Boss Battles** (V2, with project review). Mock interviews → **Arena** (V2). Debugging practice → **Dungeon** (V2).
- **Class selection at onboarding** (Scholar/Builder/Consistent/Challenger) — adopted: a fun skin over Learning DNA preferences that seeds the mentor's teaching style on day one.
- Restraint rule: core navigation stays plain; RPG terms only where they add motivation. Aligned with the learning-science council: rewards yes, punishment no.

## 12. Resources & visuals decisions (2 July 2026)

- **Video links**: current build uses YouTube *search* links (honest, can't be wrong). Direct links generated by the LLM are rejected — models hallucinate URLs. Upgrade path: **YouTube Data API** (free quota) — the app searches the mentor's query and links the actual top-ranked videos. Ships with the RPG pass; falls back to search links when no YouTube API key is set.
- **Visual explanations**: adopted with restraint — the lesson generator may attach a **diagram** (Mermaid syntax, rendered client-side) ONLY when a concept is genuinely visual (call stack, memory layout, trees/graphs, flow of control). Invalid diagrams are silently hidden. Explicit instruction to the model: most sections need no diagram.

## 13½. Phase 2 spec — LLM council merged verdict (2 July 2026)

Four-specialist council (learning science, engineering, product/UX, game design). Merged decisions:

**Quiz = "Boss Check" (M1)**
- Generated **in the same Gemini call as the lesson** (1 call/day total; graded locally from stored answers — zero extra quota). Malformed quiz → lesson still saves, quiz backfilled later.
- Optional, after marking the quest complete — **never gates completion or base XP** (bonus only, no nagging; card persists as "Boss Check available").
- 5 questions (2 recall / 2 application / 1 code-reading), one-at-a-time full-screen on mobile.
- **Confidence = wager**: before reveal, stake the question — Safe (1×) / Confident (1.5×) / All-in (2×). This is simultaneously the fun mechanic AND the metacognition data (correct+All-in = mastery; wrong+All-in = misconception flag, top re-teach priority; correct+guess = lucky, half mastery credit).

**XP economy rework (M1)**
- Triangular levels: level N costs 50×N XP (level-up on Day 1 — instant hook; ~L13 by 5000 XP).
- Quiz income: +10 XP per correct; combo multiplier ×1→×1.5→×2 for consecutive corrects (wrong = missed bonus, never a loss); **critical hit** (All-in + correct = 2× with restrained VFX); +2 "scouting XP" for wrong answers (framed "weak point revealed" — recon for the mentor, not shame); +25 perfect clear. Quiz XP stays 10–20% of economy so lessons remain the main income.

**Learning DNA (M2)**
- Per-topic: mastery (rolling avg of last 5 question scores), attempts, misconceptions, avg confidence, calibration. Global: overconfidence rate, best/worst question type, avg score. All derived from real quiz data — nothing speculative. Recomputed locally on each submit (no AI call); summarized into an ~80-token block injected into every mentor prompt.
- **Skills tab**: honest "constellation list" (no fake branching) — per-topic gold mastery bars, states Unvisited/Learning/Solid/Mastered, next topic glowing as the frontier, fill-up animation reusing the banner style. Plus a first-person **"Mentor's Notes"** card with evidence ("You second-guess correct answers on trees — trust yourself more"), correctable by the user (tap "not quite") — the trust move.

**Dynamic roadmap (M3)**
- Local mutation, AI only at phase boundaries: quiz <50% → insert a **revision day from a local template** (no AI call; its lesson generates on-demand like any day). Cap: max 1 insertion per 5 days. Misconception → re-teach section prepended to next lesson. ≥90% all-certain → **offer** (never force) merging tomorrow into a compressed day. Two straight fails on one topic → mentor conversation, different approach.
- Presentation: mentor voice + evidence + before/after ("I noticed recursion gave you trouble — I've added a light revision day tomorrow"), skips framed as rewards. Max one adaptation message/day.
- **Prerequisite refactor first**: key lessons/progress by stable ids, not positional day numbers (the riskiest piece per engineering — renumbering breaks caches keyed by day).
- DNA weak-topics fed into generate-phase prompts so later phases adapt at the source.

**Retention (M4)**
- Morning warm-up "Daily Quest": 3 questions from the spaced ladder (concept resurfaces day X+1, X+3, X+7; wrong resets the rung) — optional, never gates the lesson. Priority: misconceptions > weak topics > due items.
- Streak with **earned shields**: every 7 days auto-earn one shield that silently covers a missed day (streak "pauses," never visibly breaks); milestone banners at 3/7/14/30.
- **Second Wind**: first day back after 2+ missed days = +50% XP (guilt moment → pull).

**Explicitly rejected by council**: currency/cosmetic shop (economy-balancing trap, extrinsic-motivation trap), mechanically-different classes (balance nightmare — classes stay teaching-style flavor), push notifications in Phase 2 (iOS PWA pain for near-zero value at one user — in-app badge now, real push in Phase 3), per-section mini-quizzes, adaptation approval flows (auto-apply with one-line notice instead).

**Build order**: M1 quiz+XP rework → M2 DNA+Skills tab → M3 stable-id refactor+revision days → M4 warm-up+streak.

## 13⅝. Phase 2 M2 — refined by a focused 3-agent council (3 July 2026)

Learning DNA + Skills tab. Council refinements to the original spec:

**Mastery math (pedagogy):**
- Bayesian shrinkage, not raw ratio: `mastery = (correct + 1) / (total + 2)` — kills false precision at ~5 questions/topic.
- Gate thin data: 0–2 attempts → show **"Not enough data yet"** (no number); n≥3 provisional; n≥5 solid.
- Bands (show the WORD, not a naked %): <50% weak · 50–79% developing · ≥80% mastered.
- Hypercorrection: an **all-in + wrong** answer is a misconception (not a gap) — flag it; it becomes the first review item next day ("You were sure about this — here's why it's actually X"). Prioritized above ordinary wrong answers.
- **CUT** confidence-calibration analytics (Brier scores/curves) — not enough data at this scale, pure UI bloat. Keep only the raw all-in-wrong flag.

**Engineering:**
- Compute DNA **on quiz submit** (eager, pure Python, folded into the existing save), never lazily. Skills tab just reads `state["dna"]`.
- Mentor's Notes = **template-assembled from the numbers, NOT an AI call** (free, instant, deterministic): 1 named strength + 1 prioritized fix + 1 next action, every line data-anchored.
- Topic normalization (the sneaky-hard part): `norm_topic()` = lowercase/trim/collapse → strip qualifiers (for/while/basic/intro/concepts) → small hand-written synonym map → passthrough fallback. Also nudge the lesson prompt to reuse consistent topic tags at the source.
- Flat `dna` key in state: `{topics:{name:{correct,total,mastery,attempts}}, overall_mastery, weakest, strongest, misconceptions:[], notes}`.

**Product/UX (phone-first, cheap animation only):**
- Skills = **vertical constellation list** (one column): state dot (hollow purple weak / half blue developing / solid gold mastered) + topic name + thin 4px mastery bar + band word. Thin-data rows show a "low confidence" ghost label (the anti-ChatGPT honesty move).
- Future/untested topics in ONE collapsed "Undiscovered" band at the bottom — not inline locks (which read as debt).
- Navigation: a **"Skill Map" card on the dashboard** opens Skills full-screen. NO bottom tab bar yet (two destinations don't justify permanent chrome).
- **"TOPIC MASTERED"** banner (distinct from LEVEL UP, rarer) when a bar first crosses mastered. Weak topics styled as unlit "quest available" nodes with a "→ Sharpen this" link — never red, never ❌.
- Mentor's Notes: full card at top of Skills + a one-line italic peek under the dashboard greeting. A **gold dot badge** on the Skill Map card when notes updated since last view — pull, not push; no toast/modal.

## 13¾. Phase 2 M3 — dynamic roadmap + accountability (3-agent council, 3 July 2026)

Faiz asked for schedule-adherence ("I did Day 1 then ghosted, keep me on track") and a device blocker. Council verdict + build plan:

**Device blocker — REJECTED as asked, redirected.** A PWA physically cannot block apps or lock the phone (browser sandbox; only native apps with OS permissions can). A forced "lock my whole phone until a milestone" also violates the project's no-punishment pillar (self-determination theory → reactance → uninstall) and fails empirically (users route around it). The good, autonomy-respecting version = a **voluntary in-app Focus Session** the user starts himself (fullscreen + timer + honor commitment, leave anytime, reward on completion). Deferred to M4/Phase 5.

**What actually keeps a lapsed learner (ranked):** reminders + implementation intentions > forgiving streaks > comeback/fresh-start bonus > opt-in commitment devices > safe loss-aversion > social (skip, solo user). Never hard daily streaks with visible failure counters (shame spiral = day-5 quit).

**M3 BUILD SCOPE (build now):**
1. **Stable-id refactor + migration (riskiest, do first).** Each curriculum entry gets a monotonic `sid` ("d1","d2"…, counter `plan.next_sid`), never renumbered; positional `day` is display-only. Re-key lessons/progress/quizzes by sid. One-time `migrate` in load_state guarded by `schema` version, idempotent, backs up the doc before rewriting. (Live + local state currently empty, so low real-data risk, but must be correct for real plans.)
2. **Revision-day insertion.** On a Boss Check <50%, insert a revision entry from a LOCAL template (no AI at insert; lesson generated on open) right after the boss; cap 1 per boss; `kind:"revision"`. Shows as a distinct "Mentor Adjustment / Revision" node in the Quest Log + a one-line mentor banner ("Arrays tripped you up — added a quick revision before we move on"). Never a gap/strikethrough/overdue.
3. **Schedule-awareness (no cron — compute on app open from timestamps).** From `created_at` + `completed_at`s: if `behind ≥ 2` days or `>3 days` since last activity with plan incomplete → silently re-pace (anchor remaining active days forward from today, don't regenerate/punish) and show a **"Welcome Back" modal**: days away, "I re-paced your roadmap — goal still on track", comeback bonus (+50 XP + a Streak Shield), one button "Resume Quest" → easiest next quest. Store `repaced_at` so it doesn't repeat same session.
4. **Rewards-only streak + earned Shields.** Streak counts up; a miss FREEZES (never zeroes). Shields earned (+1 per 5-day streak or Boss crit, max 3), auto-spent to hold a streak on a missed day. Dashboard: flame + number + up to 3 shield dots (opacity/transform only — keep it cheap post-lag-fix).

**Deferred to M4:** skip-ahead/compress on high performance (status field, offer never force), voluntary Focus Session timer, adaptive revision difficulty, push/notification nudges (needs native shell / Phase 3).

## 13.9 Phase 2 M4 — spaced review + focus (3-agent council, 3 July 2026)

Councils cut 4 candidate features to 2 (owner's "don't overdo it"):
- **CUT — Second Wind** (named comeback bonus): manipulative engagement-hack, could incentivize lapses, breaks premium tone. Welcome Back already makes return frictionless.
- **CUT — Skip-ahead**: illusion-of-mastery / Dunning-Kruger risk for a beginner; breaks streak/quest math. Ace is rewarded via gold "Sure and correct", not fast-forward.

**BUILD — Morning warm-up (anchor, highest value, zero AI cost):**
- Reuses questions already stored in `lessons[day].quiz[]` (no Gemini call). `reviews.queue` in state; ladder X+1/X+3/X+7 by `stage`, then graduate. Prioritize misconception-flagged topics first (hypercorrection). Cap 3 questions (~60s). Shuffle option order on re-serve (prevent memorizing the letter).
- Optional, default-on, framed as reward ("+15 XP", never nag/gate). First step of the day, ABOVE today's lesson; collapses to a one-line done-row after. Warm-up answers stored into `quizzes["w<n>"]` so `dna.compute` counts them toward mastery automatically.
- No cron: build on app open from a day-index (current quest `order`); advance ladder on submit, not build (skip = stays due).

**BUILD — Focus Session (minimal, honest):**
- Browser CAN: Fullscreen API, Wake Lock (screen on), Page Visibility (detect leaving), JS timer. CANNOT: block/close other apps, prevent app-switch. UI must call it a *voluntary* timer — no false "blocker" promise.
- The one detail that makes it work (per pedagogy): **pre-commitment intention** before start — "What will you finish?" + self-chosen duration (15/25/45, default 25).
- Lives as a small "Focus" text-button on the today card (NOT its own card). Fullscreen the lesson, thin top progress line (tap → "18:20 left"), no ticking clock. Complete → reward pill "Focus complete · +40 XP" (gold if unbroken + on-quest). Leave early → "Paused — pick up anytime", no XP, no punishment. Re-request wake lock on visibility-visible; fullscreen exit = pause not fail.

**Layout discipline (product council):** at most ONE active "do something now" card visible; completed steps collapse to thin done-rows; Focus is a text-button never a card; Second Wind never a card. Persistent cards: today's quest, Skill Map.

**Sequence:** warm-up first (anchor, migrate schema→4 for reviews), then Focus Session (UI-heavy, riskiest — ship fullscreen+timer, wake lock second).

## 14. Batch 3 — assessment tools (3-agent council, 3 July 2026)

Council cut 4→3. **CUT Socratic debugger** (recognition-not-generation, duplicates the ask-mentor box — paste code there instead). Build sequence = cheapest→riskiest:
1. **Bookmarks** (zero AI): star toggle on lesson sections → `state.bookmarks=[{day,sectionIndex,heading}]`; a "Saved" list surfaced from the dashboard only when non-empty (progressive disclosure). Learner-chosen, complements system-chosen spaced review.
2. **Explain-it-back** (1 AI call, self-explanation effect): optional "Say it back" step in the day Recap — one concept, 2-line box, skippable. Shared grader returns {whats_good, whats_missing} — ADDITIVE feedback, never a score; soft signal to DNA. Small +XP for doing it.
3. **AI mock interviewer** (2 AI calls, riskiest — build last): optional "Viva" after a CHAPTER. Call 1 generates+caches a question set {questions:[{id,kind:theory|coding,q,model_answer,rubric}]}; UI shows one Q at a time (canned "next" between — no per-turn AI); submit → 1 batch grade call → {results:[{score,whats_good,whats_missing}],overall}. Rewards-only ("what landed / what to tighten", XP, links back to weak lesson), NO stinging score. Dynamic follow-ups DEFERRED to v2. Shared grader + repair path; graceful degrade to model_answer if JSON fails.

**Anti-clutter rule reaffirmed:** only ONE net-new surface this batch (the Viva). Explain-it-back + bookmarks are slots inside existing screens; nothing new in any menu.

## 13¾. Pending user actions
- **YouTube Data API key** (for direct video links — Faiz will get it; remind him): console.cloud.google.com → enable "YouTube Data API v3" → Credentials → API key.

## 13. Gemini free-tier reality (learned in testing)

- `gemini-2.0-flash` now has **zero** free-tier quota (429 "limit: 0") — removed. Candidates: `gemini-2.5-flash` → `gemini-2.5-flash-lite`, env-overridable.
- 2.5-flash intermittently returns 503 "high demand" — the client switches models on 503/limit-0 and re-sweeps after 20s.
- Free-tier daily caps reset at midnight Pacific (~12:30 PM IST).
