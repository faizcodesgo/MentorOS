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
