# MentorOS — Interaction Phases (27 July 2026)

Follow-on to `COUNCIL-2026-07-27-REDESIGN.md`. That doc covers the visual redesign
(slices 1-6, of which 1-3 shipped). This one covers four interaction phases mined from
21st.dev and Magic UI, filtered against this app's real constraints.

Spec lives at the repo root to match `PHASE5.md` / `COUNCIL-*.md`, not under
`docs/superpowers/specs/` — this repo keeps its docs flat.

---

## 0. Where the ideas came from, and what was thrown away

Faiz asked for ideas from **21st.dev** and **Magic UI**.

**21st.dev is not usable as a library here.** It is a React + Tailwind + shadcn/ui
registry — copy-paste source for Cursor-style tools. This app is vanilla JS and plain
CSS with **no Node and no build step**. It is an idea catalogue, nothing more.

**Roughly 45 of Magic UI's ~60 components are rejected**, not on taste but on this app's
own history. Recorded here so nobody re-proposes them:

| Rejected | Reason |
|---|---|
| Border Beam, Shine Border, Shimmer Button, Rainbow Button, Animated Shiny Text | Animated gradients = `background-position` animation. The exact class of effect that lagged the phone and was deleted in `d4685e1`. A skeleton *shimmer* is this same technique under a new name — the most likely accidental violation. |
| Meteors, Particles, Confetti, Sparkles Text, Flickering Grid, Ripple background, Light Rays, Warp Background, Aurora Text | Continuous canvas/repaint. The starfield was deleted for this (`2bd83ae`), and the Batch 4 council rejected confetti by name. |
| Progressive Blur, Magic Card, Glare Hover, Backlight | `filter: blur()` and mouse-follow radial gradients — full-page readback per frame. `backdrop-filter` is banned in a load-bearing comment at `style.css` `.topbar`. |
| Scroll Progress, Text Reveal, Dia Text Reveal, Scroll Based Velocity | Scroll-linked. `window.scrollTo(0,0)` fires on every view change AND every lesson step, so these would snap 30+ times a session. |
| Smooth Cursor, Pointer, Lens, Dock, Magic Card | Desktop hover concepts. This is a touch-first TWA; `:hover` is already gated behind `@media (hover: hover)` because it sticks after a tap on Android. |
| Globe, Icon Cloud, Orbiting Circles, Marquee | Continuous decoration, and heavy. Violates "no continuous decoration" regardless of cost. |
| Number Ticker, Word Rotate | **Already built** — `countUp`, `animateXpChip`, and the rotating loader messages. |

---

## 1. Inherited constraints (every phase)

These come from `COUNCIL-2026-07-27-REDESIGN.md` §5-§7 and are not negotiable here.

1. `transform` and `opacity` only. Never continuously animate `box-shadow`,
   `background-position`, `filter`, or `backdrop-filter`.
2. No `transform` / `filter` / `perspective` / `will-change` / `contain: paint` on
   `body`, `#app`, `.view`, or any new wrapper — it creates a containing block and
   breaks all seven `position: fixed` layers.
3. Never rename a class, change an element's tag, or add a wrapper without checking
   §5 of the council doc. If it appears there, both files move in the same commit.
4. `prefers-reduced-motion` is honoured, and stays `1ms` rather than `none` — JS awaits
   `animationend`/`transitionend` in places.
5. One accent (`--brand`) + `--gold` for earned state. No second accent.
6. Anything that MEASURES rendered content runs inside `show(view, after)`.
7. Verify by computed style — **pixel screenshots time out in this environment**, and
   "it rendered" is not proof a measurement ran.

---

## 2. Phase 1 — Tap ripple  *(BUILD NOW — approved 27 Jul)*

**Why this one first.** It is the only idea of the five that is pure win: isolated,
cheap, cannot touch the DOM contract, and it is the strongest remaining "this is a native
app, not a website" signal. The app already has asymmetric press physics
(`:active { transform: translateY(1px) scale(0.994) }`, press 0.05s / release eased) —
a ripple originating at the touch point is the other half of that story.

### Mechanism

- **ONE delegated `pointerdown` listener** on `document`. Not per-element: `renderStep`,
  `renderDashboard` and friends rebuild markup via `innerHTML` constantly, so per-element
  listeners would leak and die.
- On a qualifying target: append `<span class="ripple">`, positioned at the pointer
  offset, animate `transform: scale(0 -> 1)` + `opacity: 0.35 -> 0`, remove on
  `animationend`.
- Duration ~450ms, `--ease-out`. Transform + opacity only.

### Which elements — and the trap

Ripple hosts need `position: relative; overflow: hidden`.

> **`overflow: hidden` CLIPS NEGATIVE MARGINS.** `.bookmark-btn` and `.weekly-x` both use
> negative margins to absorb a 44px touch target without growing visually (a deliberate
> fix in `b4a2e93`). Putting a ripple on any element that CONTAINS those silently shrinks
> the tap area back to what was already fixed once.

So ripple goes on **leaf controls only**:

`.btn` · `.day-row` · `.opt` · `.iopt` · `.class-card` · `.wager-chip` · `.dur-chip` ·
`.seg-item` · `.skillmap-card`

**Never `.card`**, never `.lesson-section`, never any container.

This list is deliberately the same enumeration as the existing tap layer at
`style.css` (`-webkit-tap-highlight-color: transparent; touch-action: manipulation`) —
keep the two in step; anything that suppresses the native highlight should provide its
own feedback.

### Guards

- Skip when `matchMedia("(prefers-reduced-motion: reduce)").matches`.
- Skip `:disabled` elements — `.opt` buttons are disabled once a wager is committed, and
  a ripple there would imply the tap did something.
- Skip if the target already has an unfinished ripple (rapid double-tap).
- `pointerdown`, not `click` — feedback must be immediate, and `click` fires after
  release.

### Risks

| Risk | Handling |
|---|---|
| `overflow: hidden` clipping a 44px target | Leaf controls only (above). Verify `.bookmark-btn` height after. |
| Ripple span surviving an `innerHTML` rewrite | It cannot — the rewrite removes it. Transient by design. |
| `.opt` index-sensitive grading | The span is not `.opt`, so `querySelectorAll('.opt')` is unaffected. **Verify anyway.** |
| Radius clipping on `--r-full` chips | `overflow: hidden` respects `border-radius`; verify on `.wager-chip`. |

### Verification

- `.bookmark-btn` still measures >= 44px, and `#savedCard` still appears after a tap.
- `[...$("quizOptions").querySelectorAll(".opt")].length === q.options.length` and all are
  `BUTTON`.
- A ripple element exists during a press and is gone within ~600ms (no accumulation after
  20 taps).
- Under emulated reduced motion, zero ripple nodes are created.
- Standard checks 1/3/4/5 from the council doc.

---

## 3. Phase 2 — Verdict word reveal  *(after the 1 Aug visual check)*

The negotiate screen is the app's best moment — the mentor delivering an honest
assessment, including what will NOT fit. It currently just appears.

**Mechanism.** One-shot per-word fade-up on `.mentor-msg`. Total <= 300ms for the whole
message, ~12ms stagger, `transform: translateY(4px)` + `opacity`.

**The real constraint.** The message runs through `fmt()` and can contain `**bold**` and
`` `code` ``. Splitting `innerHTML` on spaces would shred the tags. The implementation
must **walk text nodes only** (`TreeWalker`, `NodeFilter.SHOW_TEXT`) and wrap words in
place, leaving element structure intact.

**Guards.** Reduced motion renders instantly. Never blocks reading — if the message is
long, cap the stagger so the last word still lands within 300ms.

**Honest flag.** Voice A killed narration and reassurance copy, and this is adjacent to
that. The argument for it: it reads as the mentor *speaking*, not the app *performing*.
That is a taste call and it must be judged on the phone, not asserted here. If it reads
as theatre, cut it — the cost of removal is one commit.

---

## 4. Phase 3 — Level ring on the account avatar  *(BLOCKED on slice 4)*

Slice 4 (`COUNCIL-2026-07-26.md` §6) adds a topbar avatar opening an Account sheet. A
thin XP-to-next-level ring around that avatar puts the game layer permanently on screen
at **zero added vertical space** — which matters, because the fold at 360x640 currently
has ~11px of headroom.

**Mechanism.** An inline `<svg>` circle using `stroke-dasharray` / `stroke-dashoffset`,
set **once per render**. Not animated continuously. Gold (`--gold`), since it represents
earned state.

**Two hard constraints:**

1. The avatar (and its ring) must be a **SIBLING of `#topbarStatus`, never a child** —
   `renderDashboard` owns that element's `innerHTML` and would wipe it. Give it
   `flex: none` so the existing `.streak-chip { flex: 0 1 auto; text-overflow: ellipsis }`
   remains the thing that degrades at 360px.
2. **Purely additive.** It must not replace any of the six `style.width`-driven meters
   (`progressFill`, `xpFill`, `stepBarFill`, `studyBarFill`, `resultLvFill`,
   `.skill-fill`). Re-modelling any of those as an SVG ring makes six JS writes silent
   no-ops with no error.

**Verify at 360x640** with the widest realistic status text (`LV 12 · 4120 XP` +
`11-day streak`) that the wordmark, avatar and chips do not collide.

---

## 5. Phase 4 — Skills view rebuild  *(PLANNED — build only when real data exists)*

Merges two ideas because **both rebuild the same view**, and building the constellation
on the current list then re-doing it as a bento grid means constructing that view twice.

**Approved 27 Jul: plan now, build after ~a week of real bootcamp use.** The dev account
holds 2 topics, both `"new"`. A constellation of two unlinked dots looks broken, not
premium, and a bento grid sized by mastery is meaningless when everything is one band.

### 5a. `dna.links` — the data work

`dna.topics` is a flat dict; **no relationship graph exists**. But the raw material does:
`state["quizzes"][day]["answers"][].topic`. Topics tested in the **same checkpoint**
genuinely co-occur — "these were tested together on day 7" is a real relation a learner
recognises, not an invented one.

Add to `dna.compute()`:

```
dna["links"] = [ {"a": topicKey, "b": topicKey, "n": timesCoOccurred}, ... ]
```

- Built from the same loop that already walks every quiz answer.
- Normalised through `norm_topic()` exactly like `topics` keys, so they join.
- Pairs sorted so `(a, b)` is stable; self-pairs dropped.
- Cap the list (e.g. top ~40 by `n`) — `state` is rewritten whole on every request and
  `bookmarks`/`awarded` already grow unbounded (council M7).

**No migration needed.** DNA is recomputed from scratch on every quiz submit, so the
field self-heals. **But** existing docs have no `links` until the learner's next
checkpoint, so the view MUST render correctly when `links` is absent or empty.

### 5b. Constellation

Faint SVG lines between linked topics, drawn **one-shot** on view open via
`stroke-dashoffset`. Never looping. Line opacity scales with `n` so a strong relation
reads stronger — structure encoding real information, which is the test that separates
this from decoration.

Must run inside `show(view, after)` if it measures node positions.

### 5c. Bento grid

Tiles sized by attempts and mastery so **weak topics are physically bigger** — the thing
you should work on takes up the most space. Replaces a uniform list where every topic
looks equally important.

### Risks — this is the high-risk phase

| Risk | Handling |
|---|---|
| `.skill-fill` receives an inline `style="width:N%"` from `app.js` | If the bar changes shape, that write moves in the **same commit**. |
| Band classes are interpolated: `skill-band ${r.band}`, `skill-fill ${r.band}`, `sdot ${r.band}` — four values (`weak`/`developing`/`mastered`/`new`) | Any rename touches both files together. `--brand-dim` currently carries `weak`. |
| Thin data | Honest empty/low-data state. `band()` returns `"new"` under 3 attempts by design — never fake a percentage. |
| `links` absent on older docs | Render the grid with no lines; never throw. |
| Constellation reading as decoration | If lines cannot be grounded in `dna.links`, do not draw them. |

---

## 6. Sequence

| # | Phase | Gate |
|---|---|---|
| 1 | Tap ripple | none — **approved to build 27 Jul** |
| — | *Verify slices 1-3 on the real phone* | **~1 Aug, blocks everything below** |
| 2 | Verdict word reveal | after the visual check |
| 3 | Level ring | after **slice 4** ships the avatar |
| 4 | Skills rebuild (`dna.links` + constellation + bento) | after ~a week of real quiz data |

Phases 2-4 are each one commit, independently revertible. None of them may be bundled
with a slice from the visual redesign.
