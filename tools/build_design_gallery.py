"""Build the MentorOS design-system gallery for claude.ai/design.

Every card INLINES the real public/style.css rather than restating any value, so
the gallery cannot drift from the app. If a token changes, re-run this and the
gallery is correct again. Never hand-copy a hex or a size into this file.

    python tools/build_design_gallery.py [outdir]

Default outdir is the session scratchpad; nothing is written into the repo.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(ROOT, "public", "style.css")

DEFAULT_OUT = os.path.join(
    os.environ.get("TEMP", "/tmp"), "mentoros-design-gallery"
)


def token(css, name):
    """Read a :root token's value straight out of the stylesheet."""
    m = re.search(r"^\s*--" + re.escape(name) + r":\s*([^;]+);", css, re.M)
    return m.group(1).strip() if m else "?"


def page(css, group, name, subtitle, body, script="", width=390):
    return f"""<!-- @dsCard group="{group}" name="{name}" subtitle="{subtitle}" -->
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400&display=swap" rel="stylesheet">
<style>
{css}
/* preview chrome only — not part of the app */
body {{ padding: 20px; margin: 0; }}
.dsWrap {{ max-width: {width}px; margin: 0 auto; }}
.dsNote {{ font-size: 12px; color: var(--faint); margin: 18px 0 6px;
  text-transform: uppercase; letter-spacing: .08em; font-weight: 600; }}
.dsRow {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }}
.dsSwatch {{ height: 60px; border-radius: var(--r1); display: flex; align-items: flex-end;
  padding: 6px; font-size: 11px; font-family: "IBM Plex Mono", monospace; flex: 1; min-width: 84px; }}
</style>
</head>
<body>
<div class="dsWrap">
{body}
</div>
{script}
</body>
</html>
"""


def build(css):
    """Return [(filename, group, name, subtitle, html)]."""
    out = []

    def add(fn, group, name, subtitle, body, script="", width=390):
        out.append((fn, group, name, subtitle,
                    page(css, group, name, subtitle, body, script, width)))

    # ---------- Foundations ----------
    surfaces = [("--bg", "page"), ("--panel", "card"),
                ("--panel-2", "plate"), ("--panel-3", "primary")]
    sw = "".join(
        f'<div class="dsSwatch" style="background:var({t});'
        f'{"border:1px solid var(--line);" if t == "--bg" else ""}">{t}<br>{token(css, t[2:])}</div>'
        for t, _ in surfaces)
    inks = "".join(
        f'<p style="color:var({t});margin:4px 0;font-size:15px">{t} — {token(css, t[2:])} — '
        f'The quick brown fox jumps</p>' for t in ["--ink", "--muted", "--faint"])
    accents = "".join(
        f'<div class="dsSwatch" style="background:var({t});color:#08111f">{t}<br>{token(css, t[2:])}</div>'
        for t in ["--brand", "--brand-dim", "--gold", "--good", "--bad"])
    add("foundations-color.html", "Foundations", "Colour",
        "Surface ramp, text tones, accent + earned state",
        f"""<h2>Colour</h2>
<p class="dsNote">Surface ramp — hierarchy is luminance, not outlines</p>
<div class="dsRow">{sw}</div>
<p class="sub" style="font-size:13px;margin-top:8px">Steps measured 1.24 bg→card, 1.19 card→plate, 1.29 card→primary. Under ~1.10 a card reads as flat.</p>
<p class="dsNote">Text</p>{inks}
<p class="dsNote">One accent + earned state</p>
<div class="dsRow">{accents}</div>
<p class="sub" style="font-size:13px;margin-top:8px">--brand-dim is a luminance step of the SAME blue, not a second accent. It exists so the skill map can tell "shaky" from "getting there".</p>""")

    steps = [("--text-xs", "Micro label"), ("--text-sm", "Caption / meta"),
             ("--text-md", "Secondary body"), ("--text-lg", "Reading size — lesson prose"),
             ("--text-xl", "Section heading")]
    scale = "".join(
        f'<p style="font-size:var({t});margin:10px 0">{label} <span class="mono" '
        f'style="color:var(--faint);font-size:var(--text-xs)">{t} · {token(css, t[2:])}</span></p>'
        for t, label in steps)
    add("foundations-type.html", "Foundations", "Type",
        "Archivo display + Inter body + Plex Mono figures",
        f"""<h1>Archivo h1</h1><h2>Archivo h2</h2><h3>Archivo h3</h3>
<p class="dsNote">Scale</p>{scale}
<p class="dsNote">Figures — tabular, because they animate</p>
<p class="mono" style="font-size:var(--text-lg)">LV 12 · 4,120 XP · 11-day streak</p>
<p class="sub" style="font-size:13px">countUp and animateXpChip rewrite these ~60×/sec; without tabular figures the topbar reflows every frame.</p>""")

    add("foundations-elevation.html", "Foundations", "Elevation & radius",
        "Inset highlight, three shadows, three radii",
        f"""<p class="dsNote">Elevation — each leads with an inset top-highlight</p>
<div class="card" style="box-shadow:var(--shadow-1)">--shadow-1 · resting card</div>
<div class="card" style="box-shadow:var(--shadow-2)">--shadow-2 · primary / sheet</div>
<div class="card" style="box-shadow:var(--shadow-3)">--shadow-3 · floating</div>
<p class="sub" style="font-size:13px">The inset highlight is what reads as "raised" on a dark surface. It lives in the shadow tokens, so every card picked it up with zero selector changes.</p>
<p class="dsNote">Radius</p>
<div class="dsRow">
  <div class="dsSwatch" style="background:var(--panel-2);border-radius:var(--r1)">--r1 {token(css,'r1')}</div>
  <div class="dsSwatch" style="background:var(--panel-2);border-radius:var(--r2)">--r2 {token(css,'r2')}</div>
  <div class="dsSwatch" style="background:var(--panel-2);border-radius:var(--r3)">--r3 {token(css,'r3')}</div>
</div>""")

    # ---------- Controls ----------
    add("controls-buttons.html", "Controls", "Buttons",
        "Primary, ghost, small, danger, disabled",
        """<div class="dsRow"><button class="btn primary">Start today</button>
<button class="btn ghost">Back to dashboard</button></div>
<p class="dsNote">Small — every back link, 44px minimum</p>
<div class="dsRow"><button class="btn ghost small">Back to dashboard</button>
<button class="btn small danger">Start a new plan</button></div>
<p class="dsNote">Disabled</p>
<div class="dsRow"><button class="btn primary" disabled>Working…</button></div>
<p class="sub" style="font-size:13px">Press physics: down lands in 0.05s, release eases. Tap anywhere to see the ripple.</p>""",
        script=RIPPLE_JS)

    add("controls-chips.html", "Controls", "Chips & segmented",
        "Confidence wager, duration, segmented control",
        """<p class="dsNote">Confidence wager — visible odds, 44px targets</p>
<div class="wager-chips">
  <button class="wager-chip">Guessing<span class="mono" style="font-size:var(--text-xs);color:var(--muted)">14 / 12</span></button>
  <button class="wager-chip">Fairly sure<span class="mono" style="font-size:var(--text-xs);color:var(--muted)">16 / 8</span></button>
  <button class="wager-chip">Certain<span class="mono" style="font-size:var(--text-xs);color:var(--muted)">18 / 0</span></button>
</div>
<p class="dsNote">Duration</p>
<div class="dsRow"><button class="dur-chip">15 min</button><button class="dur-chip selected">25 min</button><button class="dur-chip">45 min</button></div>
<p class="dsNote">Segmented</p>
<div class="seg"><button class="seg-item active">Recap</button><button class="seg-item">Full session</button></div>""",
        script=RIPPLE_JS)

    # ---------- Content ----------
    add("content-cards.html", "Content", "Cards",
        "Standard vs the one primary surface per view",
        """<div class="card"><p class="label mono">Skill map</p>
<h3>Standard card</h3><p class="sub">Fill plus an inset highlight. No outline.</p></div>
<div class="card card-primary"><p class="label mono">Today</p>
<h3>The one primary surface</h3><p class="sub">Lighter fill, bigger radius, real elevation — never a second colour.</p>
<button class="btn primary" style="width:100%;margin-top:12px">Start today</button></div>""",
        script=RIPPLE_JS)

    add("content-dayrows.html", "Content", "Plan rows",
        "Done, today, up next, locked, checkpoint, project",
        """<div class="day-row done"><span class="num mono">1</span><span class="t">Variables and types</span><span class="amt mono">+100</span></div>
<div class="day-row today-row"><span class="num mono">4</span><span class="t">From code to execution</span><span class="amt mono">+100</span></div>
<div class="day-row locked upnext"><span class="num mono">5</span><span class="t">Memory and pointers</span></div>
<div class="day-row locked"><span class="num mono">6</span><span class="t">Arrays</span></div>
<div class="day-row locked checkpoint"><span class="num mono">7</span><span class="t">Checkpoint</span></div>
<div class="day-row locked project"><span class="num mono">8</span><span class="t">Milestone: build a parser</span></div>
<p class="sub" style="font-size:13px;margin-top:10px">.locked is load-bearing — it was the ONLY thing sequencing the plan until the server-side gate landed.</p>""",
        script=RIPPLE_JS)

    add("content-prose.html", "Content", "Lesson prose",
        "One reading size across every block",
        """<div class="card lesson-section">
<div class="section-head"><h3>Hash collisions</h3></div>
<p class="probe">what happens when two keys land in the same bucket?</p>
<p class="explanation">A hash function maps a key to a bucket. Two different keys can map to the same one — that is a collision, and it is not a bug. Every real hash table has a strategy for it.</p>
<div class="analogy">Two people with the same locker number. You do not rebuild the gym — you agree who stacks on top.</div>
<div class="tryit">Given buckets of size 8 and hash(k) = k % 8, which keys collide with 17?</div>
</div>
<p class="sub" style="font-size:13px">Explanation, analogy, probe and try-it all share one 18px reading size. They used to be four different sizes across seven blocks.</p>""")

    add("content-diagram.html", "Content", "Diagram plate",
        "The signature asset, on its own surface",
        """<div class="card lesson-section"><div class="section-head"><h3>Process states</h3></div>
<div class="diagram"><svg viewBox="0 0 320 120" width="100%" xmlns="http://www.w3.org/2000/svg">
<rect x="8" y="40" width="86" height="40" rx="6" fill="#1c2330" stroke="#283042"></rect>
<text x="51" y="64" font-size="12" text-anchor="middle" fill="#e6edf3">Ready</text>
<rect x="117" y="40" width="86" height="40" rx="6" fill="#1c2330" stroke="#283042"></rect>
<text x="160" y="64" font-size="12" text-anchor="middle" fill="#e6edf3">Running</text>
<rect x="226" y="40" width="86" height="40" rx="6" fill="#1c2330" stroke="#283042"></rect>
<text x="269" y="64" font-size="12" text-anchor="middle" fill="#e6edf3">Blocked</text>
<path d="M94 60 L117 60" stroke="#4f8cff" stroke-width="2"></path>
<path d="M203 60 L226 60" stroke="#4f8cff" stroke-width="2"></path>
</svg></div></div>
<p class="sub" style="font-size:13px">Diagram SVG is authored by the model against a palette hard-coded in prompts.py — still off-system, including a purple the audit thought it had deleted. Bringing it onto tokens is outstanding work.</p>""")

    # ---------- Checkpoint ----------
    add("checkpoint-options.html", "Checkpoint", "Options",
        "Resting, picked, correct, wrong",
        """<p class="quiz-q">Which structure gives O(1) average lookup?</p>
<div class="quiz-options">
  <button class="opt">Linked list</button>
  <button class="opt picked">Hash table</button>
  <button class="opt correct">Hash table — correct</button>
  <button class="opt wrong">Binary tree — wrong</button>
</div>
<p class="sub" style="font-size:13px;margin-top:12px">Resting state carries a TRANSPARENT border, so every state rule that sets border-color still works and no box shifts.</p>""",
        script=RIPPLE_JS)

    add("checkpoint-result.html", "Checkpoint", "Result",
        "Score, ledger, level meter",
        """<p class="label mono">Checkpoint</p>
<p class="result-score">18 / 20</p>
<div class="result-ledger">
  <div class="ledger-row"><span>Correct × 8</span><span class="mono">+112</span></div>
  <div class="ledger-row"><span>Sure and correct</span><span class="mono gold-chip">+32</span></div>
  <div class="ledger-row"><span>Perfect run</span><span class="mono gold-chip">+25</span></div>
</div>
<div class="xp-track"><div class="xp-fill" style="width:62%"></div></div>
<p class="sub" style="font-size:13px">The combo counter has been removed and restored twice at Faiz's request. It is interpolated into #quizFeedback textContent — it has no element of its own.</p>""")

    # ---------- Skills ----------
    bands = ""
    for band, word, pct in [("mastered", "Mastered", 88), ("developing", "Getting there", 64),
                            ("weak", "Shaky", 38), ("new", "Not enough data yet", 20)]:
        bands += f"""<div class="skill-row"><span class="sdot {band}"></span><div class="skill-main">
<div class="skill-top"><span class="skill-name">{word.lower()} topic</span><span class="skill-band {band}">{word}</span></div>
<div class="skill-bar"><div class="skill-fill {band}" style="width:{pct}%"></div></div>
</div></div>"""
    add("skills-bands.html", "Skills", "Skill bands",
        "Four states — the bug this fixed",
        f"""{bands}
<p class="sub" style="font-size:13px;margin-top:12px">"Shaky" and "Getting there" were BOTH var(--brand) in the bar and the label — the skill map could not distinguish them at all. Fixed with a luminance step, not a second colour.</p>""")

    add("skills-notes.html", "Skills", "Mentor's notes",
        "Template-assembled, never AI, always anchored to data",
        """<div class="card notes-card"><p class="label mono">Mentor's notes</p>
<p class="notes-body">You've genuinely got <b>recursion</b> down — it shows in your quizzes. Watch <b>pointers</b>: you answered confidently but got it wrong, so let's re-nail it — those stick best once fixed.</p></div>
<p class="sub" style="font-size:13px">Assembled from the numbers in dna.py. Under three attempts it says so rather than inventing a percentage.</p>""")

    return out


RIPPLE_JS = """<script>
const RIPPLE_HOSTS = ".btn, .day-row, .opt, .iopt, .class-card, .wager-chip, .dur-chip, .seg-item, .skillmap-card";
document.addEventListener("pointerdown", (e) => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const host = e.target.closest && e.target.closest(RIPPLE_HOSTS);
  if (!host || host.disabled) return;
  if (host.querySelector(":scope > .ripple")) return;
  const box = host.getBoundingClientRect();
  const size = Math.max(box.width, box.height) * 2;
  const span = document.createElement("span");
  span.className = "ripple";
  span.style.width = span.style.height = size + "px";
  span.style.left = e.clientX - box.left - size / 2 + "px";
  span.style.top = e.clientY - box.top - size / 2 + "px";
  const drop = () => span.remove();
  span.addEventListener("animationend", drop, { once: true });
  setTimeout(drop, 700);
  host.appendChild(span);
}, { passive: true });
</script>"""


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    with open(CSS, encoding="utf-8") as f:
        css = f.read()
    os.makedirs(outdir, exist_ok=True)
    cards = build(css)
    for fn, group, name, subtitle, html in cards:
        with open(os.path.join(outdir, fn), "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  {group:12} {name:22} {fn}")
    print(f"\n{len(cards)} cards -> {outdir}")
    print(f"stylesheet inlined from {CSS} ({len(css)} bytes)")


if __name__ == "__main__":
    main()
