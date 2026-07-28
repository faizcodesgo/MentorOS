# MentorOS — Redesign Council, 27 July 2026

Four agents, run before a full visual redesign: **design direction**, **UX/IA**,
**mobile red team**, **continuity auditor**. Companion to `COUNCIL-2026-07-26.md`
(the bug/auth/dashboard council) and `handoff.md` (setup + history).

Faiz's ask: *"let's redesign MentorOS"* → clarified to **full visual redesign of the
app**, not a dashboard tweak and not a backend fix.

Status when this ran: production **suspended** (Render free hours exhausted, back
~1 Aug), **9 commits queued and unverified live** through `2639b19`, working tree clean.

---

## 0. The finding that outranks the redesign

**The `.locked` CSS class is the only thing sequencing the 40-day plan.**

Verified server-side: `GET /api/lesson/<day>` (`app.py:580`) validates only that the
day exists in the curriculum. `POST /api/day/<day>/complete` validates **nothing**.
The client check at `app.js:801` — `classList.contains("locked")` — is the entire gate.

Consequences, today, with no redesign at all:
- Any rename of `.locked` unlocks the whole bootcamp.
- A tap on day 40 fires a 15–60s Gemini generation and awards 100 XP.
- Ordering damage is silent and unrecoverable.

**This should be fixed server-side regardless of what happens to the design.**

---

## 1. What the current design actually is

### Verified good — do not touch (design agent, cross-checked)

| Thing | Where | Why |
|---|---|---|
| Asymmetric press physics | `style.css:145-149` — press 0.05s, release eased | How physical buttons behave; almost nobody implements it |
| Native-tap layer | `:58-64` | The single biggest "not a website" signal in the file |
| `@media (hover: hover)` gating | `:297-303, :863-865, :1073` | Stuck hover after tap is the #1 PWA tell |
| `overscroll-behavior-y: contain` | `:53` | Kills pull-to-refresh mid-quiz |
| Direction-aware step transition | `:342-343`, `--step-dx` | The lesson reads as a physical strip |
| Result-screen sequencing | `:1093-1098` | Correct reward-screen instinct |
| Reduced-motion via `1ms` not `none` | `:1140-1148` | `none` silently breaks JS awaiting `transitionend` |
| 44px targets absorbed by negative margin | `.weekly-x:534`, `.bookmark-btn:750-755` | Pro move |
| Opacity-only skeleton | `:448-452` | The right lesson from the jank regression |

### The actual diagnosis

> It is not the hue. It is that **sixteen components are the same 10px outlined box**,
> and the **entire game layer renders smaller than the body text**.

- `1px solid var(--line)` × **38**. `var(--r2)` (10px) × **27**. `.card`, `.day-row`,
  `.opt`, `.iopt`, `.class-card`, `.scope-opt`, `.rev-item`, `.recap-stat`,
  `.wager-chip`, `.dur-chip`, `.resource-link`, `.material-box`, `.analogy`, `.worked`,
  `.interaction-code`, `.plan-goal-raw`, `.seg` are all the same object.
- `--shadow-1` on `#12161f` over `#0b0e14` is a sub-1% luminance change — invisible.
  AUDIT Batch C's "add real elevation" was declared executed; the elevation half never
  landed.
- XP = 13.6px chip. Streak = 12px grey. Skill map = five 11px dots. The dial-back from
  Destiny went one notch past *restrained* into *absent*.
- `border-left: 3px solid` × **12** — the most-copied device in AI-generated dark
  dashboards. **Four of them are `solid var(--line)`** — a 3px stripe the same colour as
  the 1px border, encoding nothing.

### Real defects found (not style opinions)

1. **`.skill-fill.weak` and `.skill-fill.developing` are both `var(--brand)`**
   (`style.css:837-844`). The skill map physically cannot distinguish "shaky" from
   "getting there". Same for `.skill-band`. **Information loss, shipping now.**
2. **`--faint #626b7a` on `--bg` = 3.55:1 — fails WCAG AA.** It is the colour of
   `.label`, i.e. every form label in the app, at 12px.
3. **`prompts.py:280` hard-codes the diagram palette off-system:**
   `#8b5cf6` (the purple the audit killed — still in the app, in every diagram),
   `#facc15` (a different gold from `--gold #f5c542`), `#e6edf3` (a different ink from
   `--ink #eaeef5`), `#1c2330`/`#283042` (surfaces outside the ramp).
4. **55 `.mono` classes in `index.html` set no mono family** — `.mono, .tnum` is
   `font-variant-numeric: tabular-nums` only. Dead vocabulary on prose.
5. **`index.html:17` downloads three weights of IBM Plex Mono** for two `code` rules,
   on the critical path of the cold-open that `116bf5d` spent a session optimising.
6. Off-token hex scattered: `#0f141b` ×2, `#b8c2ff` ×2, `#3a2f2f`,
   `rgba(239,68,68,…)` (that's `#ef4444`, not `--bad #f85149`).

---

## 2. The three directions

### A — SIGNAL *(recommended)*
Surfaces defined by **light, not outlines**. `border: 1px solid` drops from 38 uses to
four (topbar edge, list dividers, input, modal edge). Everything else becomes a fill
ramp `--bg / --s1 / --s2 / --s3` plus `0 1px 0 rgba(255,255,255,0.05) inset` — the
top-highlight that makes a dark surface read as raised without an outline. One `--s3`
surface per view, and it is always the thing to touch next.

Signature: **the segmented step rail** — one segment per real lesson step, filled via
`scaleX`, checkpoint segment gold. Replaces an anonymous width-animated bar and tells
you how many steps remain.

**The bet:** if the fill ramp is even slightly wrong, the app collapses into mush.

### B — READING ROOM *(strongest idea, disqualified)*
App stays dark; the **lesson becomes paper**. The argument is real: 40 days × 3–4h of
light-on-dark prose is the least premium thing in the build, and every product whose
job is sustained reading defaults to paper. Scoped to `#view-lesson` only — ~12 token
overrides, no theme toggle, no second polish surface.

**Why it dies:** `prompts.py:280` hard-codes the diagram palette as dark-only. On cream,
every diagram's labels go invisible and every box becomes a dark blob. Fixing the prompt
fixes only *future* lessons — every already-generated lesson is cached in Mongo with the
old palette. You would need a runtime hex-remap that inverts an arbitrary model-authored
palette. That is a correctness problem on the app's best asset.

Also: `theme-color` is one value (black notch over a cream page unless `show()` swaps it),
and a View Transitions crossfade between `#0b0e14` and `#f5f1e8` at 11pm is a flashbang.

### C — SEASON *(partially harvested)*
40 days = a season with acts. Chamfered `clip-path` geometry, five-step rank ramp,
act headers grouping the plan list.

**Why not whole:** chamfers on top of an outline-first system read as a Valorant fan
site — precisely the failure Faiz already diagnosed. Also `clip-path` clips `box-shadow`,
so chamfered and elevated are mutually exclusive.

**Harvested:** act/chapter headers for the plan list (structure encoding real content).
**NOT harvested:** the rank ramp — see §3.

---

## 3. Where the agents CONFLICT (read this before building)

The design agent proposed four things the continuity auditor flags as overturning
locked decisions. **These are Faiz's calls, not the builder's.**

| Proposed | Conflicts with | Status |
|---|---|---|
| Replace Space Grotesk with **Archivo** | Locked 1.8 — Space Grotesk + Inter since `1445e95` | **ASK** |
| **5-colour rank ramp** incl. teal `#7ee0d0` | Locked 1.1 — one accent + gold only. 26 Jul council: "NOT to do: a second accent colour" | **REJECT as proposed** — the skill-map bug is real but must be fixed within one accent (luminance/saturation steps of `--brand`, or gold-only for mastered) |
| **Delete `.greeting`**, reorder dashboard | Locked 1.18 + "NOT to do: reordering anything above the Today card" | **REJECT** |
| Delete all 12 left-border stripes | O1 — the remaining blue ones were deliberately left *for Faiz's eye* | **ASK** — the 4 `solid var(--line)` ones are safe to delete now |

The UX agent also disagrees with council §6 on one line: it wants `#xpToNext`/`#xpFill`
moved out of `.plan-strip` (arguing the level meter renders in three places — topbar
chip, plan strip, result screen — so moving it removes a *duplicate*, which is the
owner's own "thin don't delete" rule). **Faiz's call.**

---

## 4. Structure — the UX agent's findings

### A live crash, present in shipped code
Back-button from `#view-result` lands on the last quiz question with "See results"
visible. `startQuiz()` pushes an entry, `renderResult()` pushes another, and the submit
handler's `finally` sets `quizRun = null` (`app.js:2519`). Tap → `quizRun.idx++` →
**TypeError, dead screen**. Same shape for `warmupRun`.

### Root cause of five bugs: `popstate` re-renders one view
`app.js:161` — `if (st.v === "dashboard") renderDashboard();`. The other twelve get
re-shown with stale DOM. Downstream:
- **Every "are you sure?" is bypassed by the hardware back button.** `#btnQuizQuit` and
  `#btnVivaQuit` confirm; the back gesture doesn't — runs die silently. In a TWA the
  hardware button is the *primary* affordance, so the guard is on the wrong control.
- **Four sheets have no history entry** (`#remindersSheet`, `#focusSheet`,
  `#studyOptSheet`, `#welcomeBack`). Back → the view underneath navigates while the sheet
  stays on screen. Only `#askSheet` pushes (`:1441`), and the handler hardcodes
  `st.overlay !== "ask"` (`:154`). **§6's account sheet inherits this bug unless the
  primitive is generalised first.**
- **`#loading` ignores navigation** — a `position: fixed; inset: 0` scrim with no cancel.
  Back during a 15–60s generation → dashboard with "Reading your skill map…" on top for
  up to a minute.

### Data loss
- **`#projInput` has no draft persistence** and `renderProject()` clears it
  unconditionally (`app.js:2209`). Longest text the user ever types, hours of work.
- **`vivaRun.answers` is memory-only** — a back press, a call, or an OS kill destroys a
  6-question free-text interview with no warning and no draft.
- **`mos_resume` is a single global key** — opening any other day overwrites today's
  position.

### The lesson is the app, and it has no orientation
Max day = `1 intro + 12 sections + 4 breaks + 1 practice + 1 summary` = **19 steps**
(`prompts.py:518` caps sections at 12, `:541` caps blocks at 5). Six hours in:
`#stepCount` says "7 / 19" over a denominator nobody thinks in; `#lessonHead` and
`.step-progress` both scroll away on the first swipe; there is no index and no jump.

**Highest-leverage single change in the whole redesign:** make `.step-progress` sticky
and named — `Block 2 of 3 · Section 5 of 12 — "Hash collisions"`, counted over
*sections* not steps (`s.block` already exists in the data) — and make it tappable into
a step-index sheet. That one component fixes five things, including finishing the
half-built bookmark feature (`#savedList` discards `sectionIndex` at `app.js:883`).

### Composition verdict: one merge, zero removals
`#view-result` → `#view-recap` as a third `.seg` segment. Today the per-question review
is reachable **exactly once, ever**. The merge also deletes the crash above by removing
that history entry.

### The completed plan contradicts itself
`allDone` is computed at `app.js:642` and used in three places — it **never reaches
`#todayCard`**. So after the last day: `#dashDayTitle` says "Plan complete. Well done."
while directly below it the Today card shows the last day's title, its already-earned
XP, and a live "Start today" that opens a finished lesson in non-review mode.

### Also confirmed
Three safe-area misses: `#app` bottom (`style.css:119`), `.ask-fab` bottom (`:971`),
and `.study-bar` **top** (`:569`) — which replaces `.topbar`, so study mode currently
slides the timer under the notch. Five `confirm()` + one `prompt()` render Chrome's
origin-prefixed dialog in the TWA (§6 only named two of them). Six back-links, three
labels, one destination, two naming a *different existing view*.

---

## 5. The DOM contract — what a visual redesign must not touch

**Every item is read, written, toggled or queried by `app.js`. Renaming any of them
breaks the app with no build error, no type error, and usually no console error.**

### The fatal five — JS reaching into hand-written markup by class

| `app.js` | Selector | Breaks |
|---|---|---|
| `1485`, `2382` | `#view-quiz .kicker` | `startWarmup` + `startQuiz`. It *contains* `#quizDay`, which `startQuiz` recreates via `innerHTML`. Rename `.kicker` (an editorial class used 14×) or restructure `.quiz-head` → **both checkpoints and warm-ups throw on entry** |
| `1582` | `.dur-chip.selected` → `.dataset.min` | No null guard. Rename `.selected` → "Start studying" throws, study mode dead |
| `453`, `455` | `.class-card` + `dataset.class` | Picker unbinds; every learner silently gets `allrounder` forever |
| `2432` | `.wager-chip` + `dataset.w` | A checkpoint answer can never be committed |
| `674` | `#topbarStatus .xp-chip` | **The §6 avatar must sit BESIDE `#topbarStatus`, not inside it** — `renderDashboard` owns that `innerHTML` |

### Classes that are STATE, not style
`.locked` (§0) · `.done` · `.day-row` · `.chapter-row` · `.seg-item`/`.active` ·
`.opt` + `.picked`/`.correct`/`.wrong` · `.iopt` + same · `.selected` · `.on` (bookmark
truth value read off the DOM) · `.hidden` · `.out` · `.bump` · `.step-in` · `.vt` ·
`.study-mode` · `.timer-hidden`

### Six `className =` sites that WIPE designer-added classes
`app.js:231, 548, 1267, 1350, 1496, 1512, 1933, 1956, 2397, 2473` — any class added in
`index.html` to `#verdictBadge`, `#explainFeedback` or `#quizFeedback` is destroyed on
first render.

### Index-sensitive grading
`opts[q.answer].classList.add("correct")` is a flat `querySelectorAll(".opt")`. Render
options as `<li class="opt"><span class="opt-letter">` and if the letter also carries
`.opt`, **the wrong answer is marked correct** — the server still grades right, so the
app disagrees with itself, silently.
`opts.forEach(b => b.disabled = true)` only works because they are `<button>`. Convert
to `<div role="button">` and `disabled` becomes an inert expando — the user keeps
clicking after committing, re-firing `revealAnswer` and inflating `quizRun.combo`.

### Two visibility systems — never "normalise" them
`.hidden` class on ~45 elements; inline `style.display` on 20. They are mutually
exclusive (`display:""` cannot beat `display:none !important`). Elements that must
**never** carry `.hidden` in markup: `#authNote`, `#scopeOutWrap`, `#genSub`,
`#btnReminders`, `#planAssessCard`, `#noteDot`, `#notesCard`, `#recapCarryLabel`,
`#explainCard`, `#completeCard`, `#projSubmitCard`, `#btnBoss`, `#quizHintWrap`,
`#quizHintBtn`, `#btnStepNext`.
`style.visibility` deliberately reserves layout space on `#stepNav`, `#btnStepBack`,
`.study-time` — converting these to `display:none` makes lesson content jump.

### Element-type dependencies
Options/chips stay `<button>` · `#planGoalRaw` stays `<pre>` · `#inGoal` stays
`<textarea>` · `.rev-item`/`.vr-model`/`.scope-advanced`/`.focus-block` stay `<details>` ·
`.scope-opt` keeps **real radios** (`chosenScope()` reads `input[name="scope"]:checked`;
buttons → uploaded material is silently scoped to nothing) ·
**`.bookmark-btn` must contain a literal inline `<svg>`** — `app.js:2158` does
`.querySelector("svg").setAttribute(...)`; an icon font or sprite `<use>` throws a
TypeError before the `try` block and bookmarks stop saving as an unhandled rejection.

### Geometry the JS writes
Six meters driven by `style.width = "N%"`: `.progress-fill` (`app.js:686, 1044, 2552`),
`.xp-fill` (`694`), `.step-bar-fill` (`1740, 2115`), `.study-bar-fill` (`1608, 1614`),
`.skill-fill` (`1192`), `#resultLvFill`. **Re-model any as an SVG ring, `scaleX`, conic
gradient or `<progress>` and all six become silent no-ops.**

Also: `body.study-mode #app { padding-top: 60px }` is a magic number hand-matched to the
study bar's rendered height. `.sheet` + `#explorations` both need `min-height: 0` (that
pair is the entire fix for "the composer scrolls away"). `.toast` 80px/z52 vs
`.reward-pill` 22px/z51 is the fix for them overlapping after a checkpoint.

---

## 6. Performance — what is banned on this device

Standing rule confirmed, not softened: **transform + opacity only; never continuously
animate `box-shadow`, `background-position`, or `filter`.**

### BANNED at any size
1. **`backdrop-filter`** on topbar or study bar — already tried, already caused the lag
   (`d4685e1`). Full-page readback + blur on every scroll frame, with no devtools on the
   phone to diagnose it.
2. **Blurred glows / gradient meshes / "aurora"** — same readback cost permanently, and
   it inflates every View Transition snapshot (which rasterises the page twice per nav).
3. **Animated or conic-gradient borders** — `background-position` animation wearing a hat.
4. **Scroll-linked effects** — `window.scrollTo(0,0)` fires on every view change *and*
   every lesson step (`app.js:114, 2177`), so a scroll-linked header snaps 30+ times a
   session.
5. **Any `transform`/`filter`/`perspective`/`will-change`/`contain: paint` on `body`,
   `#app`, `.view` or a new wrapper.** Not a perf ban — a **correctness** ban: it creates
   a containing block for `position: fixed` and instantly breaks all seven fixed layers
   (`.toast`, `.reward-pill`, `.ask-fab`, `.sheet-scrim`, `.modal-scrim`, `.study-bar`,
   `.loading`). A "springy page transition" does exactly this.
6. **Springy layout animation / FLIP on the day list** — the chapter toggle re-renders the
   whole dashboard via `innerHTML`; there is no stable node identity to FLIP against.

### Safe if constrained
Large shadows (static only, never on the 50 `.day-row`s) · oversized display type
(static; **animate `transform: scale()`, never `font-size`**) · gradients (static, small
elements only) · View Transitions (**do not add a second `view-transition-name`** — a
duplicate makes Chrome skip the transition, and with it the `after`-callback timing
`fitSvgText` depends on) · colour transitions ≤0.2s · the existing three haptic moments.

**The trap most likely to be hit by accident: a skeleton *shimmer*.** That is a
`background-position` animation with a new name. Opacity pulse only.

### `fitSvgText` — one latent bug worth fixing during the redesign
SVG `<text>` inherits Inter from `body`, loaded with `&display=swap`. If a diagram is
measured before the webfont lands, labels are fitted to `system-ui` metrics and the swap
reflows them — the exact overflow bug `4f3dc91` exists to kill. **Add
`document.fonts.ready.then(() => fitSvgText(svg))` alongside the immediate call.**
And **never style SVG text from the stylesheet** — a CSS `font-size` overrides the
presentation attribute `fitSvgText` writes, defeating the whole mechanism.

---

## 7. The DO-NOT-BREAK contract

**Colour**
1. Exactly one accent (`--brand`). No second accent, no purple, no violet. `--gold` on XP,
   mastery and milestones only.
2. Blue means actionable or moving. Structure is `--line`/`--muted`.
3. Dark only. No light theme, no `prefers-color-scheme`, no toggle.

**Decoration & motion**
4. No continuous background decoration — no starfield, glow, particles, orb, shine, pulse.
   Only functional loaders may loop, on opacity/transform.
5. Never continuously animate `box-shadow`/`background-position`/`filter`/`backdrop-filter`.
   The topbar stays solid.
6. Overshoot easing is for rewards only; navigation uses ease-out.
7. Every reveal respects `prefers-reduced-motion` — and it stays `1ms`, not `none`.

**Type & iconography**
8. Space Grotesk headings + Inter body **unless Faiz approves a change** (§3). No Orbitron,
   no sci-fi face.
9. Line-icon SVG, never emoji.
10. Sentence case. No uppercase-mono label on every field.
11. Prose ~62–65ch, `:focus-visible` on every control, 44px minimum targets.

**Game feel — the twice-asked list**
12. **The visible combo counter stays**: "Correct / Sure and correct · +N XP · N in a row",
    gold on confident-correct, gold "Perfect run N/N". **Asked for twice. Do not quiet it
    a third time.** It has no element of its own — it is interpolated into
    `#quizFeedback.textContent` at `app.js:2459-2460`, so swapping that for structured
    markup is a fourth way to break it.
13. XP, levels, streak, shields, ranks, classes and the wager all stay. No full-screen
    victory banners, no CAPS-LOCK crit language, no casino framing. Wager labels stay
    Guessing / Fairly sure / Certain with visible odds.
14. `PAYOFF` stays in step across `app.py`, `app.js` and the `index.html` odds text.
15. **"Balanced" stays the default-selected class.**
16. Rewards only. No XP ever subtracted, no hint penalty, no guilt copy, no surveillance,
    no streak that visibly zeroes.

**Structure**
17. One hub. No bottom nav, no settings view, no permanent chrome. *(All three agents
    independently upheld this. The real problem it would have fixed — no consistent way
    home — is solved by one back-affordance contract, not by a nav.)*
18. Above-the-fold order unchanged: greeting → goal line → plan strip → Today card, with
    "Start today" above the fold at 360×640.
19. One "do something now" card visible at a time.
20. Explain-it-back, the career chip, the warm-up row and the weekly row all stay. **Thin,
    never delete.** Only cut what another surface already fully delivers.
21. The goal line is one muted, truncated, tappable line. The full goal is never truncated
    in storage.

**Voice**
22. Voice A, one term per concept: Today / Your plan / Checkpoint / the goal name.
23. State, don't reassure, apologise or narrate. No "AI" in the tagline.

**Technical invariants**
24. `fitSvgText()` stays. Anything measuring rendered content runs inside `show(view, after)`.
25. Diagrams are sanitized inline SVG only. No Mermaid, no CDN scripts.
26. All state refetches go through `refreshState()`. Never a bare `state = await api(...)`.
27. The View Transition wraps the DOM swap only — the history push stays synchronous.
28. `env(safe-area-inset-*)` survives on topbar, toast, reward pill, FAB — **and gets
    added to `.study-bar` top and `.ask-fab` bottom, which are missing it today.**
29. `overscroll-behavior-y: contain`, `-webkit-tap-highlight-color`, `touch-action` stay.

**Process**
30. Verify via `read_page` + computed styles — **pixel screenshots time out in this
    environment**, and "it rendered" is not proof a measurement ran.
31. Anything on the open-questions list gets **asked**, not decided.
32. Record decisions in `DESIGN-DECISIONS.md`, not only in commit messages. Regressions
    R3 and R4 happened because a decision existed only in a commit body.

---

## 8. Document hygiene — landmines for anyone briefed off this repo

**The owner's design decisions are not in the repo.** They live in the assistant's memory
file. The repo docs either omit them or contradict them.

| Problem | Severity |
|---|---|
| **`AUDIT.md` Batch D still reads as live instructions** to cut All-Rounder, explain-it-back, the combo counter and the career chip. **All four were reversed on 5 Jul (`5f34644`).** Its status header still asserts the muted-combo state. | **HIGHEST** — this is the historical regression loaded and pointed at the redesign |
| `AUDIT.md` is dated "4 October 2026". It is from **4 July** (`95f3b05`). A reader infers it is the newest document; it is one of the oldest. | High |
| `handoff.md` was rewritten 16 Jul (`0e562b3`) and contains **zero record of the 3–5 Jul design era** — no premium pass, no combo restoration, no F1/F2/F3 reversals | High |
| `mentor-app-plan.md` §11 specifies "indigo/purple accents"; §143 proposes a **5-item bottom nav**; the §13-family describes "Boss Check", 5-question quizzes, the old 1×/1.5×/2× wager, purple skill dots, Mermaid, and "fullscreen the lesson" — all superseded | High |
| `handoff.md` §5 numbers are wrong: claims `SCHEMA = 13` (actual **16**), `app.py` ~1100 lines (actual **1632**), `app.js` ~1750 (actual **2609**) | Medium |
| `handoff.md` §9 says Faiz's live plan is `_id: "default"`, 365 XP. `COUNCIL-2026-07-26.md` §5 says `default` is orphaned at schema 12 with **577 XP** and the live account is `faiz ahmed` with **40 days / 0 XP / 0 done**. Two docs, two XP figures — **the record is genuinely ambiguous; trust neither number** | Medium |
| `2bd83ae` claims IBM Plex Mono was "dropped everywhere" and `style.css:78` comments "no separate mono typeface" — but `index.html:17` still downloads three weights | Medium |

**Three fixes before any redesign code:**
1. `SUPERSEDED BY 5f34644 (5 Jul)` banner on `AUDIT.md` Batch D, listing the four restored features.
2. Create `DESIGN-DECISIONS.md` — fold §7 out of memory into the repo.
3. Mark `mentor-app-plan.md` §11 and the §13-family historical.

---

## 9. The regression ledger — what history says will go wrong

| # | What happened | The pattern |
|---|---|---|
| R1 | Decoration added (`1445e95`) → lag fix (`d4685e1`) → "deleted" (`2bd83ae`) → **still found live** by the audit → actually deleted (`0b6ac67`) | A commit message asserting deletion is not evidence of deletion. Verify in computed CSS |
| R2 | `showBanner` deleted, a call site survived → ReferenceError at the highest-XP moment, undetected for a day | Removing a celebration primitive breaks the rarest, highest-value moment — the one least likely to be tested |
| R3 | **Combo feedback removed and restored twice** (`2bd83ae`→`a7fc965`→`e12a1a6`→`5f34644`) | The deleting pass had no visibility into the earlier restoration, because it lived only in a commit message |
| R4 | Batch D over-cut four distinct features; all four restored next day | **"Declutter duplicates and chrome; THIN distinct things, never delete them"** |
| R5 | Focus mode shipped as a blank fullscreen countdown that hid the lesson | Specs describing a takeover get built as takeovers |
| R6 | The smoothness pass broke two things it had just built (resume never resumed; `fitSvgText` measured `display:none`) | **"Headless 'it rendered' checks aren't enough — assert the measurement actually RAN"** |

---

## 10. Recommended order of work

**Slice 0 is a precondition, not a step.** The red team's position, which I endorse:
nine commits are queued unverified, H1 (concurrent-write clobber) is still open and
silently un-completes days, and Faiz is about to start a 40-day bootcamp where a silent
regression is lost study time, not a bug report.

| Slice | Contents | Why independently shippable | Why revertible |
|---|---|---|---|
| **0** *(blocking ship, not build)* | Verify the 9 queued commits live (~1 Aug). Fix the UptimeRobot schedule. Dogfood 5–7 days. | Only way to know the baseline is what you think it is | Nothing new to revert |
| **0b** *(do now, independent of design)* | Server-side day-sequence validation (§0). The `#view-result` crash (§4). Three safe-area fixes. `document.fonts.ready` for `fitSvgText`. | All bug fixes, no design coupling | Small, surgical |
| **1** | **Tokens only** — `:root`, `style.css:3-47`. New colour ramp, spacing, radius, elevation. **Zero selector changes, zero markup, zero JS.** | Every surface changes at once → the new look becomes judgeable **on the phone**, which is the one thing that can't be judged headlessly | One block in one file |
| **2** | **Type + rhythm** — families in `index.html:17`, the scale, line-height, `ch` measures | Reading a lesson *is* the product | One commit. Re-check `fitSvgText`; **do not add font weights** — each is another blocking request in the cold-open path |
| **3** | **Cards, buttons, inputs** — restyle `.card`, `.btn`, `.day-row`, `.opt`, `.iopt`, chips. **No renames, no element-type changes, no new wrappers.** | 80% of the visible surface | DOM contract intact ⇒ §5 can't fire |
| **4** | Dashboard + account sheet (`COUNCIL-2026-07-26` §6) + the `allDone` Today card + **generalise the overlay history primitive first** | Already specified; reuses `.sheet` verbatim | One view |
| **5** | Motion tuning — VT durations, pill queue, haptics | Explicitly on the "needs Faiz's eyes live" list | Numbers, not mechanisms |
| **6** | **Anything requiring markup changes** — sticky step bar, step-index sheet, result→recap merge, day list → `view-plan` | **It isn't independently safe.** Assume dangerous by default | Full §11 checklist every time |

**Two hard rules for every slice:**
1. No slice renames a class, changes a tag, or adds a wrapper without checking §5 first.
   If it appears in §5, it is a **code** change, not a design change, and both files move
   in the same commit.
2. Run checks 1, 3, 4, 5 from §11 after **every** slice. Under two minutes, and they cover
   the four failure modes that produce no error at all.

---

## 11. Verification checks — runnable locally, no production needed

| # | Risk | Check |
|---|---|---|
| 1 | `.locked` renamed → whole plan unsequenced | `document.querySelectorAll('#dayList .day-row.locked').length > 0` on a fresh plan. Then tap the last day — assert a toast, not a lesson. **Run first, after every slice** |
| 2 | `#view-quiz .kicker` gone → checkpoints + warm-ups throw on entry | `!!document.querySelector("#view-quiz .kicker")`, then actually open a checkpoint |
| 3 | Progress meters dead | `$("progressFill").style.width` is a non-empty `%` **and** computed width ≠ `0px`. Repeat for `xpFill`, `stepBarFill`, `studyBarFill`, `resultLvFill`, `.skill-fill` |
| 4 | `.hidden` softened | `getComputedStyle($("view-quiz")).display === "none"` while on the dashboard |
| 5 | Containing block created on `#app`/`body` | Scroll a long lesson to the bottom, `toast("x")` — it must appear at the bottom of the **viewport** |
| 6 | Bookmark svg replaced | `!!document.querySelector(".bookmark-btn svg")`, then tap → reload → still gold |
| 7 | Options non-`<button>` or index-shifted | `[...$("quizOptions").querySelectorAll(".opt")].every(o => o.tagName === "BUTTON")` and `.length === q.options.length`. After committing a wager, clicking again must do nothing |
| 8 | App-shell scroller → `scrollTo(0,0)` no-ops | Scroll a lesson to the bottom, Back, re-enter → `window.scrollY === 0`. Pull-to-refresh at the top of a quiz must not reload |
| 9 | Banned technique reintroduced | `grep -n "background-position\|backdrop-filter\|filter:\s*blur" public/style.css` → nothing but the comments at `:100` and `:447` |
| 10 | Combo counter broken a third time | Answer 2 correctly with any wager → `$("quizFeedback").textContent` contains `"2 in a row"` |

**Bonus:** if the app boots blank with **no console error**, check `refreshState`
(`app.js:302-306`) first — a `replace_all` once rewrote the line inside it into infinite
recursion. The redesign equivalent is a `replace_all` over `classList.add("hidden")` or
`"selected"`.

---

## 12. Open questions for Faiz

Design-blocking (answer before slice 1–3):
- **Q1** Keep Space Grotesk, or move to a different display face?
- **Q2** The skill map genuinely cannot show weak vs developing. Fix within one accent
  (luminance steps of blue), or overturn the one-accent rule for earned state only?
- **Q3** The 4 stripes that are `border-left: 3px solid var(--line)` encode nothing —
  delete? And the blue ones left "for your eye" (O1) — keep as structure or neutralise?
- **Q4** Move the XP meter off the dashboard into the account sheet (UX agent) or leave it
  (council §6)?

Standing, still unanswered (some since 5 Jul):
- **O2** Do the view transitions feel premium or sluggish on your phone?
- **O3** Does the reward-pill sequence after a big day read as celebration or a parade?
- **O6** Do you want **more** animation anywhere specific — level-up, checkpoint, streak?
- **O10** Honest lesson-time estimate ("core vs +optional video"), and chaptering the step
  bar by block instead of a raw "N / 21"?
- **O14** A 3-day phase draws both a checkpoint and a project, leaving SQL one new-content
  day out of three — widen SQL or drop that project?

**Settled — do not re-raise:** the app logo (done, `6b66a6b`); Google sign-in (dropped
26 Jul); app-blocking (physically impossible in a TWA, asked and answered three times).

---

# POSTSCRIPT — 28 Jul 2026: BUILT. Status of everything above.

The council ran 27 Jul; by 28 Jul **every slice was built, verified locally, and pushed**
(16 commits, `c03ac05` → `1ce8609`; the narrative session log is `handoff.md` §14).
Production stayed suspended throughout — **nothing has been seen on a real screen**, and
the §11 checks are what stands between these commits and the owner's phone on ~1 Aug.

## How the owner answered §12

- **Q1 typeface → Archivo.** A deliberate owner decision overturning the Space Grotesk
  lock — recorded as such, not as drift. The wordmark is finally set in the display face.
- **Q2 skill colours → fix within one accent.** `--brand-dim #5580ad`, a luminance step
  of the same blue. The one-accent rule survives its third challenge. (First value tried
  measured 3.23:1 — that band is 12px TEXT; shipped at 4.79:1.)
- **Q3 stripes** — the four `solid var(--line)` stripes died with the border pass; the
  blue ones await his eye on-device (still open).
- **Q4 XP meter placement** — NOT moved; §6's "don't reorder above the Today card" held.
  Revisit only if his on-device pass says the plan strip feels crowded.
- Sequencing: he chose **bugs first**, then slices; slice 5's taste questions
  (O2/O3/O4) stay deliberately untuned — every knob is now a one-line token
  (`--vt-out`/`--vt-in`, `MOTION` in app.js).

## Where reality diverged from this document

1. **§0 is fixed** — `_day_unlocked()` gates both endpoints server-side (403), gate
   before the cache read, prefetch unaffected.
2. **Slice 1's proposed token names were a trap this doc set.** The design agent's
   `--s1/--s2/--s3` surface tokens collide with the EXISTING spacing scale (30 uses).
   Distinct names used. A council can hand you a loaded gun politely.
3. **The ramp bet fired exactly as §2-A warned.** First fill ramp measured 1.084 bg→card
   — invisible. Shipped only after measuring: 1.24 / 1.19 / 1.29.
4. **§1's own contrast fix was wrong once.** `--faint` at 4.63:1 was measured against
   `--bg`, but `.label` sits on CARDS (2.55:1 there). Labels now use `--muted`. Rule:
   measure against the surface the colour actually sits on.
5. **Borders: 26 → 17, not → 4.** The rest are sheets/badges/dividers left deliberately;
   sweeping them blind is how §9's regressions happened. Revisit after the device pass.
6. **§4's crash is doubly dead** — the `RUN_EXPIRED` guard (c03ac05) AND the result
   view's deletion (6c) removed the entry at the source. popstate also redirects entries
   naming views that no longer exist.
7. **§5 (DOM contract) proved its worth nine times** — the verification passes caught
   nine real bugs reading missed (ramp mush, wrong-surface contrast, a CSS parse
   near-miss, the ripple leak, the ghost overlay entry, the fresh-result staleness, a
   stale step label, plus two tester-side errors). Keep running §11 after every change.
8. **Slice 6 shipped as three commits** (6a sticky step bar + step index + M6 bookmark
   fix; 6b day list → plan view; 6c result → recap Checkpoint segment). One merge, zero
   removals, exactly as §4 recommended.
9. **Beyond this doc's scope, same session:** tap ripple + `REDESIGN-PHASES.md` (and ~45
   Magic UI rejections recorded); the claude.ai/design "MentorOS" gallery generated FROM
   `style.css` (`tools/build_design_gallery.py`) — the only pre-deploy way to SEE any of
   this; the diagram palette fix + runtime migration (`ab6f509`/`bdb5397` — delete
   `DIAGRAM_PALETTE_MIGRATION` after the Aug-1 plan restart); `RESOURCES-SPEC.md`.

## §8 doc hygiene — status

`AUDIT.md` now carries the SUPERSEDED banner (done alongside this postscript).
`DESIGN-DECISIONS.md` and the `mentor-app-plan.md` §11/§13 historical markers remain
**undone** — the owner chose bugs-first; do them before any session that reads those docs
as instructions.
