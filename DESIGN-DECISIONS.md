# MentorOS — Design Decisions (standing rules)

**What this is:** the owner's design decisions, in the repo, where a briefed session will
actually look. It exists because the two worst regression cycles in this project's
history (the combo counter cut-and-restored twice; Batch D's four over-cuts, all reversed
next day) happened when a decision lived only in a commit message or an assistant's
memory, invisible to the next pass.

**The protocol:** when Faiz changes a decision, update THIS file in the same commit —
never only the commit message. Each rule notes where it came from. "Owner, reaffirmed ×N"
means he has actively defended it against N separate proposals — treat those as load-
bearing walls, not preferences.

Companion docs: `COUNCIL-2026-07-27-REDESIGN.md` §5 is the DOM contract (classes/ids/
element types JS depends on — a *code* boundary, not taste) and §11 the re-runnable
checks. `handoff.md` is history. This file is only the rules.

---

## Colour

1. **Exactly one accent: `--brand` blue.** Gold (`--gold`) is for XP, mastery and
   milestone moments ONLY. No second hue — no purple, no violet, no teal. *(Owner,
   reaffirmed ×3: the 3 Jul premium pass, the 26 Jul council's "NOT to do" list, and
   27 Jul when a 5-colour rank ramp was proposed and rejected.)* Where a second signal is
   genuinely needed, use a **luminance step of the same blue** — `--brand-dim` (the
   skill-map weak band) is the precedent.
2. **Blue means actionable or moving.** Structure and eyebrow labels are `--muted`/
   `--line`, never the accent.
3. **Dark only.** Light mode was CUT (Batch 4 council, 3 Jul: "breaks one-blue dark
   identity, doubles polish"). No `prefers-color-scheme`, no toggle. *(This decision
   previously existed in no repo document — that gap is why this file exists.)*
4. **Surfaces are fills, not outlines.** Hierarchy comes from the measured luminance ramp
   (`--bg → --panel → --panel-2 → --panel-3`, steps ≥ ~1.15) plus the inset top-highlight
   in the shadow tokens. Borders stay *declared but transparent* where state rules set
   `border-color`. The two exceptions that must be SEEN: input edges and ghost buttons
   (`--line-strong`).
5. **Measure a colour against the surface it actually sits on** — not against `--bg`.
   (`--faint` passed on the background and failed at 2.55:1 on cards; labels use
   `--muted` for exactly this reason.) Text ≥ 4.5:1 where it renders.

## Decoration & motion

6. **No continuous decoration.** No starfield, glow, particles, orb, shine, pulse,
   gradient mesh, aurora. Only functional loaders may loop, on opacity/transform.
   *(Owner: "screams AI-generated"; also a measured phone-lag fix, d4685e1.)*
7. **Transform + opacity only. Never continuously animate `box-shadow`,
   `background-position`, `filter`, or `backdrop-filter`.** The topbar stays solid.
   A skeleton *shimmer* is `background-position` animation wearing a hat — the ban's
   most likely accidental violation.
8. **Overshoot easing (`--ease-pop`) is for reward moments only.** Navigation eases out.
9. **Reduced motion stays `1ms`, never `none`** — JS awaits animation events, and `none`
   silently breaks them. Any animation-gated JS needs a timeout fallback regardless
   (toast, reward pill and the ripple all hedge this way).
10. **Rejected outright, do not re-propose:** Orbitron ("sci-fi cheese"), three.js/real
    3D, sound FX, confetti, scroll-linked effects, motion libraries, autoplay-next, fake
    urgency, glassmorphism/blur, animated gradient borders, mouse-follow effects. The
    full annotated rejection list (~45 Magic UI components) is in `REDESIGN-PHASES.md`.

## Type & iconography

11. **Archivo display + Inter body.** *(Owner decision, 27 Jul — a deliberate
    overturning of the earlier Space Grotesk lock, recorded as such.)* Archivo carries
    h1–h3, the wordmark, quiz questions, the result score. IBM Plex Mono exists at ONE
    weight, for `code` only. `.mono`/`.tnum` mean tabular figures — numbers that animate
    must keep them or the chrome reflows every frame.
12. **One reading size for lesson prose** — 18px/1.7, every prose block in a section
    (explanation, analogy, worked example, probe, try-it). Smaller steps are for chrome.
    Prose measures ~62–65ch.
13. **Line-icon SVG, never emoji.** Sentence case. No uppercase-mono micro-label walls.
14. **44px minimum touch targets** (negative-margin absorption is the house pattern) and
    `:focus-visible` on every control.

## Game feel — the twice-asked list

15. **The visible combo counter STAYS**: "Correct / Sure and correct · +N XP · N in a
    row", gold on confident-correct, gold "Perfect run N/N". **Cut and restored twice
    (a7fc965, 5f34644). Do not quiet it a third time.** It has no element of its own —
    it is interpolated into `#quizFeedback`'s textContent, so "restructuring" that
    element is the third way to break it.
16. **XP, levels, streak, shields, ranks, classes and the confidence wager all stay.**
    No full-screen victory banners, no CAPS-LOCK crit language, no casino framing.
    Wager labels: Guessing / Fairly sure / Certain, odds visible. `PAYOFF` stays in
    step across app.py, app.js and the index.html odds text; combo is a flat end-of-run
    bonus, NEVER a multiplier inside the wager maths (it would destroy the CBM
    calibration thresholds).
17. **"Balanced" (allrounder) is the default-selected class.** *(Cut once, restored at
    owner request — a beginner shouldn't be forced to over-commit on screen one.)*
18. **Rewards only, never punish.** No XP subtracted, hints cost nothing, streaks freeze
    rather than zero (best is permanent), no guilt copy, no attention surveillance, no
    fullscreen takeover that hides the lesson. The founding pillar; it outranks every
    other rule here.
19. **The reward pane exists once.** A reward is shown at the moment it is earned;
    revisits get the sober stored view. Re-animating an old reward is a lie.
20. **Deepen, never skip.** Mastery unlocks optional depth; it never skips required
    days (26 Jul council: skip-ahead is Dunning-Kruger bait for a beginner).

## Structure

21. **One hub.** No bottom nav, no settings view, no permanent chrome. New capability
    slots into an existing screen or appears conditionally. *(Upheld independently by
    three councils; the real problem a nav would have solved — no consistent way home —
    is solved by the back-affordance contract instead.)*
22. **Above-the-fold order is fixed:** greeting → goal line → plan strip → Today card,
    "Start today" above the fold at 360×640. One "do something now" card at a time;
    the dashboard shows a 3-row plan window, the full list lives in Your plan.
23. **Thin, don't delete.** Only cut what another surface already fully delivers
    (the owner cuts true duplicates himself — study cue, undo-complete). Explain-it-back,
    the career chip, the warm-up row and the weekly row exist in thinned form by design.
24. **The goal line is one muted, truncated, tappable line** — and the stored goal text
    is NEVER truncated (its first 40 chars can be the subjects he asked to SKIP).
25. **Honest > flattering, everywhere.** "Not enough data yet" beats a fake percentage;
    est_minutes reports real time; timestamps only from real chapter data, attributed
    ("per the video's own chapters") — never model-invented precision.

## Voice

26. **Voice A: confident mentor. One term per concept** — Today / Checkpoint / Your
    plan / the goal name. No Quest/Boss/Arena/Dungeon. State, don't reassure, apologise
    or narrate. No "AI" in the tagline.

## Technical invariants a design pass can silently break

27. `fitSvgText()` stays; anything measuring rendered content runs inside
    `show(view, after)`; never style diagram `<text>` from the stylesheet (a CSS
    font-size overrides the fitted presentation attribute).
28. Diagrams are sanitized inline SVG only; their palette is the token palette
    (prompts.py names it; `DIAGRAM_PALETTE_MIGRATION` in app.js remaps pre-token cached
    lessons — delete it once the Aug-1 restart regenerates everything).
29. All state refetches go through `refreshState()`; the localStorage snapshot clears on
    401/sign-out/reset. History pushes stay synchronous outside view-transition
    callbacks; one overlay on screen = one overlay history entry (`openSheet` replaces).
30. Six meters are driven by JS writing `style.width` — re-modelling any as SVG
    rings/`scaleX` silently kills all six. `.hidden` means `display:none !important`;
    never soften it. No `transform`/`filter`/`will-change` on `body`/`#app`/`.view`
    (breaks all seven fixed layers). `env(safe-area-inset-*)` on every fixed bar.
31. Feel-tuning knobs live in ONE place: `--vt-out`/`--vt-in` in `:root`, `MOTION` in
    app.js. Tune there, nothing else moves.

## Open — deliberately undecided (needs the owner's device, ~1 Aug)

VT durations (premium or sluggish?) · reward-pill sequence (celebration or parade? cut
the streak pill first if parade) · haptic strength · the remaining blue left-border
stripes (kept "for his eye") · the 17 remaining full-box borders vs the council's ~4
target · whether the plan strip should lose the XP meter (proposed, held).

## Settled forever — do not re-raise

Google/Gmail sign-in (dropped 26 Jul; `reset_password.py` solves the real problem) ·
app-blocking (physically impossible in a TWA — asked and answered three times) · the
app logo (done, 6b66a6b).
