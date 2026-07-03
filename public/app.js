/* MentorOS frontend — plain JS, no framework. */

const $ = (id) => document.getElementById(id);
const views = ["onboarding", "negotiate", "generating", "dashboard", "lesson", "quiz", "skills"];

let state = null;          // slim server state (plan + progress + profile + xp)
let negotiation = null;    // last /api/negotiate result
let pendingInput = null;   // goal/days/hours the user submitted
let chosenClass = "";      // scholar | builder | consistent | challenger

/* ---------- XP / levels ---------- */

const RANKS = [[16, "PLATINUM"], [10, "GOLD"], [5, "SILVER"], [0, "BRONZE"]];

/* triangular curve: level N costs 50×N XP — fast levels early, slower later */
function levelFromXp(xp) {
  let lv = 1, total = 0, cost = 100;
  while ((xp || 0) >= total + cost) {
    total += cost;
    lv++;
    cost = 50 * (lv + 1);
  }
  return lv;
}

function rankFromLevel(lv) {
  for (const [min, name] of RANKS) if (lv >= min) return name;
  return "BRONZE";
}

function questReward(entry) { return entry && entry.is_checkpoint ? 150 : 100; }

let lastShownXp = null;

/* count the XP number upward in the level chip, with a gold glow */
function animateXpChip(el, from, to, lv) {
  const dur = 700, t0 = performance.now();
  el.classList.remove("bump");
  void el.offsetWidth;
  el.classList.add("bump");
  (function step(t) {
    const p = Math.min(1, (t - t0) / dur);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = `LV ${lv} · ${Math.round(from + (to - from) * eased)} XP`;
    if (p < 1) requestAnimationFrame(step);
  })(t0);
}

/* ---------- helpers ---------- */

function show(view) {
  views.forEach((v) => $("view-" + v).classList.toggle("hidden", v !== view));
  window.scrollTo(0, 0);
}

function toast(msg, ms = 4000) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), ms);
}

function loading(on, text) {
  $("loading").classList.toggle("hidden", !on);
  if (text) $("loadingText").textContent = text;
}

/* achievement banner (quest complete / level up) — returns after it finishes */
function showBanner(title, sub, levelup = false) {
  return new Promise((resolve) => {
    const b = $("banner");
    $("bannerTitle").textContent = title;
    $("bannerSub").textContent = sub;
    b.classList.toggle("levelup", levelup);
    b.classList.remove("hidden");
    void b.offsetWidth; // restart the CSS animation
    setTimeout(() => { b.classList.add("hidden"); resolve(); }, 1950);
  });
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

/* escape first, then allow ONLY **bold** and `code` from the model */
function fmt(s) {
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

/* attribute-safe escaping (quotes matter inside data-* attributes) */
function escAttr(s) {
  return esc(s).replace(/"/g, "&quot;");
}

/* ---------- boot ---------- */

async function boot() {
  try {
    state = await api("/api/state");
  } catch (e) {
    toast("Can't reach the server: " + e.message);
    return;
  }
  const plan = state.plan;
  if (plan && plan.curriculum.length > 0 &&
      plan.phases_generated >= plan.phases.length) {
    renderDashboard();
    show("dashboard");
    checkPace();
  } else if (plan && (plan.phases || []).length > 0) {
    // plan exists but curriculum unfinished — resume generation
    show("generating");
    generatePhases();
  } else {
    // no plan, or a broken plan shell with no phases — start fresh
    show("onboarding");
  }
}

/* ---------- onboarding & negotiation ---------- */

document.querySelectorAll(".class-card").forEach((card) => {
  card.addEventListener("click", () => {
    document.querySelectorAll(".class-card").forEach((c) => c.classList.remove("selected"));
    card.classList.add("selected");
    chosenClass = card.dataset.class;
  });
});

$("goalForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!chosenClass) {
    toast("Choose your class first — it shapes how the mentor teaches you.");
    return;
  }
  pendingInput = {
    goal: $("inGoal").value.trim(),
    days: parseInt($("inDays").value, 10),
    hours_per_day: parseFloat($("inHours").value),
    level_notes: $("inLevel").value.trim(),
    learner_class: chosenClass,
  };
  const btn = $("btnNegotiate");
  btn.disabled = true;
  loading(true, "The mentor is thinking about your goal…");
  try {
    negotiation = await api("/api/negotiate", {
      method: "POST",
      body: JSON.stringify(pendingInput),
    });
    renderNegotiation();
    show("negotiate");
  } catch (err) {
    toast(err.message, 6000);
  } finally {
    btn.disabled = false;
    loading(false);
  }
});

function renderNegotiation() {
  const n = negotiation;
  const badge = $("verdictBadge");
  badge.textContent = n.verdict.toUpperCase();
  badge.className = "badge mono " + n.verdict;
  $("mentorMessage").textContent = n.mentor_message;

  $("scopeIn").innerHTML = (n.achievable_scope || [])
    .map((s) => `<li>${esc(s)}</li>`).join("");
  const out = n.dropped_scope || [];
  $("scopeOutWrap").style.display = out.length ? "" : "none";
  $("scopeOut").innerHTML = out.map((s) => `<li>${esc(s)}</li>`).join("");

  $("phaseList").innerHTML = (n.phases || [])
    .map((p) => `<li><strong>${esc(p.name)}</strong> <span class="days mono">${p.days}d</span><br><span class="days">${esc(p.focus)}</span></li>`)
    .join("");
}

$("btnAdjust").addEventListener("click", () => show("onboarding"));

$("btnAccept").addEventListener("click", async () => {
  if (!negotiation || !(negotiation.phases || []).length) {
    toast("The mentor couldn't build phases for this goal — adjust it and ask again.");
    return;
  }
  loading(true, "Setting up your plan…");
  try {
    await api("/api/plan/init", {
      method: "POST",
      body: JSON.stringify({
        ...pendingInput,
        phases: negotiation.phases,
        mentor_message: negotiation.mentor_message,
      }),
    });
    loading(false);
    show("generating");
    await generatePhases();
  } catch (err) {
    loading(false);
    toast(err.message, 6000);
  }
});

async function generatePhases() {
  try {
    let done = false;
    while (!done) {
      const r = await api("/api/plan/generate-phase", { method: "POST" });
      done = r.done;
      $("genProgress").textContent =
        `Phase ${Math.min(r.phases_generated + 1, r.total_phases || r.phases_generated)} of ${r.total_phases || "?"}…`;
    }
    state = await api("/api/state");
    renderDashboard();
    show("dashboard");
    toast("Your plan is ready. Day 1 starts now.");
  } catch (err) {
    toast("Curriculum generation hit a snag: " + err.message + " — retrying may help.", 8000);
    // leave the user on the generating screen with a retry
    $("genProgress").innerHTML = `<button class="btn ghost small" onclick="generatePhases()">Retry</button>`;
  }
}

/* ---------- dashboard ---------- */

const isDone = (dayId) => !!(state.progress[String(dayId)] && state.progress[String(dayId)].completed);

/* curriculum in display order (day is the stable id; order is the sequence) */
function orderedCurriculum() {
  return state.plan.curriculum.slice().sort((a, b) => (a.order ?? a.day) - (b.order ?? b.day));
}

/* the next quest to do — first not-completed in display order */
function currentEntry() {
  const ord = orderedCurriculum();
  return ord.find((d) => !isDone(d.day)) || ord[ord.length - 1];
}

function renderDashboard() {
  const plan = state.plan;
  const ord = orderedCurriculum();
  const realQuests = ord.filter((d) => d.kind !== "revision");
  const doneReal = realQuests.filter((d) => isDone(d.day)).length;
  const allDone = ord.every((d) => isDone(d.day));
  const entry = currentEntry();
  const xp = state.xp || 0;
  const lv = levelFromXp(xp);

  $("dashGoal").textContent = "MAIN QUEST · " + plan.goal.toUpperCase();
  $("dashDayTitle").textContent = allDone
    ? "Main quest complete. Well done."
    : entry.kind === "revision" ? "Revision Quest" : `Day ${entry.day} of ${plan.days}`;
  $("dashCount").textContent = `${doneReal}/${plan.days} QUESTS DONE`;
  if (lastShownXp !== null && xp > lastShownXp) {
    animateXpChip($("levelChip"), lastShownXp, xp, lv);
  } else {
    $("levelChip").textContent = `LV ${lv} · ${xp} XP`;
  }
  lastShownXp = xp;
  $("rankChip").textContent = rankFromLevel(lv) + " RANK";
  const career = state.lifetime_xp || 0;
  $("careerChip").innerHTML = career > 0 ? `CAREER <b>${career + xp} XP</b>` : "";
  $("progressFill").style.width = `${(doneReal / plan.days) * 100}%`;
  $("topbarStatus").innerHTML =
    `<span class="xp-chip">LV ${lv} · ${xp} XP</span>${renderStreakChip()}`;

  $("todayTitle").textContent = entry ? entry.title : "";
  $("todayObjectives").innerHTML = entry
    ? (entry.objectives || []).map((o) => `<li>${esc(o)}</li>`).join("")
    : "";
  $("todayReward").textContent = entry ? `REWARD: +${questReward(entry)} XP` : "";
  $("btnStartToday").textContent = entry && entry.kind === "revision" ? "Start revision" : "Start the quest";
  $("btnStartToday").onclick = () => openLesson(entry.day);

  const currentId = entry.day;
  const currentOrder = entry.order ?? entry.day;
  $("dayList").innerHTML = ord
    .map((d) => {
      const done = isDone(d.day);
      const isToday = d.day === currentId && !done;
      const locked = (d.order ?? d.day) > currentOrder && !done;
      const revision = d.kind === "revision";
      const cls = ["day-row", done ? "done" : "", isToday ? "today-row" : "", locked ? "locked" : "", d.is_checkpoint ? "checkpoint" : "", revision ? "revision" : ""].join(" ");
      const stateTxt = done ? `✓ +${questReward(d)} XP` : isToday ? "TODAY" : locked ? "LOCKED" : "";
      const label = revision ? "◆ REVISION" : `${d.is_checkpoint ? "◈" : ""} DAY ${d.day}`;
      return `<button class="${cls}" data-day="${d.day}">
        <span class="num mono">${label}</span>
        <span class="t">${esc(d.title)}</span>
        <span class="state mono">${stateTxt}</span>
      </button>`;
    })
    .join("");

  renderSkillMapCard();

  $("dayList").querySelectorAll(".day-row").forEach((row) => {
    row.addEventListener("click", () => {
      if (row.classList.contains("locked")) {
        toast("One quest at a time — finish this one first.");
        return;
      }
      openLesson(parseInt(row.dataset.day, 10));
    });
  });
}

function renderStreakChip() {
  const s = state.streak || { count: 0, shields: 0 };
  if (!s.count) return "";
  const shields = "◈".repeat(Math.min(s.shields || 0, 3));
  return `<span class="streak-chip">🔥 ${s.count}${shields ? " " + shields : ""}</span>`;
}

/* ---------- schedule awareness (welcome back) ---------- */

async function checkPace() {
  let r;
  try {
    r = await api("/api/pace-check", { method: "POST" });
  } catch { return; }
  if (!r.behind) return;

  state = await api("/api/state");
  renderDashboard();

  $("wbBody").textContent =
    `You stepped away for ${r.days_away} days — no problem. I've re-paced your roadmap so you pick up right where it makes sense. Nothing lost, goal still on track.`;
  const rewards = [`+${r.bonus_xp} XP return bonus`];
  rewards.push(r.shield_used ? "streak shield spent to keep your streak" : "+1 streak shield, on the house");
  $("wbRewards").innerHTML = rewards.map((t) => `<span class="wb-reward">✦ ${esc(t)}</span>`).join("");
  $("welcomeBack").classList.remove("hidden");
}

$("wbResume").addEventListener("click", () => {
  $("welcomeBack").classList.add("hidden");
  const entry = currentEntry();
  if (entry) openLesson(entry.day);
});

async function resetAll(msg) {
  if (!confirm(msg)) return;
  await api("/api/reset", { method: "POST" });
  state = await api("/api/state");
  show("onboarding");
}

$("btnReset").addEventListener("click", () =>
  resetAll("This wipes your whole plan and progress. Sure?"));

$("btnAbandonGen").addEventListener("click", () =>
  resetAll("Abandon this plan and start over from the goal screen?"));

/* ---------- skill map ---------- */

function renderSkillMapCard() {
  const dna = state.dna;
  const dashNote = $("dashNote");
  if (dna && dna.notes && dna.total_answered >= 3) {
    dashNote.textContent = "Mentor's note: " + stripMd(dna.notes.split(".")[0]) + ".";
    dashNote.style.display = "";
  } else {
    dashNote.style.display = "none";
  }

  const topics = dna ? Object.entries(dna.topics || {}) : [];
  $("skillMapSub").textContent = topics.length
    ? `${topics.length} topic${topics.length > 1 ? "s" : ""} tracked · ${Math.round((dna.overall_mastery || 0) * 100)}% overall`
    : "Take a Boss Check and your skill map appears here.";

  const top = topics.slice().sort((a, b) => b[1].attempts - a[1].attempts).slice(0, 3);
  $("skillMapDots").innerHTML = top.map(([, r]) => `<span class="sdot ${r.band}"></span>`).join("");
  $("noteDot").style.display = state.notes_seen === false ? "inline-block" : "none";
}

$("skillMapCard").addEventListener("click", openSkills);

async function openSkills() {
  loading(true, "✨ Opening your skill map…");
  try {
    const data = await api("/api/skills");
    state.notes_seen = true;
    renderSkills(data.dna);
    show("skills");
  } catch (err) {
    toast(err.message);
  } finally {
    loading(false);
  }
}

$("btnSkillsBack").addEventListener("click", () => {
  renderDashboard();
  show("dashboard");
});

const BAND_LABEL = { mastered: "Mastered", developing: "Developing", weak: "Not yet mastered", new: "Just started" };

function renderSkills(dna) {
  const notes = $("notesCard");
  if (dna && dna.notes) {
    notes.innerHTML = `<p class="label mono">MENTOR'S NOTES</p><p class="notes-body">${fmt(dna.notes)}</p>`;
    notes.style.display = "";
  } else {
    notes.style.display = "none";
  }

  const topics = dna ? Object.entries(dna.topics || {}) : [];
  if (!topics.length) {
    $("skillsList").innerHTML = `<div class="card"><p class="sub">No skills tracked yet. Clear a Boss Check and your topics start appearing here.</p></div>`;
    return;
  }

  const order = { mastered: 3, developing: 2, weak: 1, new: 0 };
  topics.sort((a, b) => (order[b[1].band] - order[a[1].band]) || (b[1].mastery - a[1].mastery));

  $("skillsList").innerHTML = topics.map(([name, r]) => {
    const pct = Math.round(r.mastery * 100);
    const thin = r.attempts < 3;
    const barW = thin ? Math.min(pct, 35) : pct;
    return `<div class="skill-row">
      <span class="sdot ${r.band}"></span>
      <div class="skill-main">
        <div class="skill-top">
          <span class="skill-name">${esc(name)}</span>
          <span class="skill-band ${r.band}">${thin ? "New" : BAND_LABEL[r.band]}</span>
        </div>
        <div class="skill-bar"><div class="skill-fill ${r.band}" style="width:${barW}%"></div></div>
        <p class="skill-meta mono">${r.attempts} question${r.attempts > 1 ? "s" : ""}${thin ? " · low confidence" : ""}</p>
      </div>
    </div>`;
  }).join("");
}

function stripMd(s) { return String(s).replace(/\*\*/g, ""); }

/* ---------- lesson ---------- */

let openDay = null;
let currentLesson = null;

async function openLesson(day) {
  openDay = day;
  loading(true, "Preparing Day " + day + "…");
  try {
    const lesson = await api("/api/lesson/" + day);
    renderLesson(lesson);
    show("lesson");
  } catch (err) {
    toast(err.message, 6000);
  } finally {
    loading(false);
  }
}

/* lazy-load mermaid only when a lesson actually has a mermaid diagram */
let mermaidReady = null;
function ensureMermaid() {
  if (!mermaidReady) {
    mermaidReady = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js";
      s.onload = () => {
        mermaid.initialize({
          startOnLoad: false, securityLevel: "strict", suppressErrorRendering: true,
          theme: "base",
          themeVariables: {
            darkMode: true, background: "#161b22",
            primaryColor: "#1c2330", primaryTextColor: "#e6edf3", primaryBorderColor: "#4f8cff",
            secondaryColor: "#231c33", secondaryBorderColor: "#8b5cf6",
            tertiaryColor: "#1a2030", tertiaryBorderColor: "#283042",
            lineColor: "#8b949e", textColor: "#e6edf3",
            fontFamily: "Inter, sans-serif", fontSize: "14px",
            edgeLabelBackground: "#161b22", clusterBkg: "#12161f",
          },
        });
        resolve();
      };
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }
  return mermaidReady;
}

/* allow only safe, self-contained SVG from the model */
function sanitizeSvg(code) {
  const doc = new DOMParser().parseFromString(code, "image/svg+xml");
  const svg = doc.documentElement;
  if (svg.nodeName.toLowerCase() !== "svg" || doc.querySelector("parsererror")) return null;
  svg.querySelectorAll("script, foreignObject, iframe, image, use, animate, set")
    .forEach((el) => el.remove());
  for (const el of [svg, ...svg.querySelectorAll("*")]) {
    for (const attr of [...el.attributes]) {
      if (/^on/i.test(attr.name) || /javascript:/i.test(attr.value) ||
          attr.name === "href" || attr.name === "xlink:href") {
        el.removeAttribute(attr.name);
      }
    }
  }
  if (!svg.getAttribute("viewBox")) return null;
  svg.removeAttribute("height");
  svg.setAttribute("width", "100%");
  return new XMLSerializer().serializeToString(svg);
}

async function renderDiagrams(root) {
  const holders = (root || document).querySelectorAll(".diagram[data-code]");
  if (!holders.length) return;

  for (const h of holders) {
    if (h.dataset.type === "svg") {
      const clean = sanitizeSvg(h.dataset.code);
      if (clean) h.innerHTML = clean; else h.remove();
      h.removeAttribute("data-code");
    }
  }

  const mmd = [...(root || document).querySelectorAll('.diagram[data-code]')]
    .filter((h) => h.dataset.type !== "svg");
  if (!mmd.length) return;
  try { await ensureMermaid(); } catch { mmd.forEach((h) => h.remove()); return; }
  for (const h of mmd) {
    try {
      const { svg } = await mermaid.render("mmd" + Math.random().toString(36).slice(2, 8), h.dataset.code);
      h.innerHTML = svg;
    } catch {
      h.remove(); // invalid diagram from the model — hide, never show garbage
    }
    h.removeAttribute("data-code");
  }
}

function visualHolder(visual) {
  if (!visual || !visual.code || !visual.type) return "";
  return `<div class="diagram" data-type="${escAttr(visual.type)}" data-code="${escAttr(visual.code)}"></div>`;
}

function renderLesson(l) {
  currentLesson = l;
  const direct = (l.videos || [])
    .map((v) => `<a class="resource-link" target="_blank" rel="noopener" href="${esc(v.url)}">▶ ${esc(v.title)} <span class="channel">· ${esc(v.channel)}</span></a>`)
    .join("");
  const resources = direct || (l.resource_queries || [])
    .map((q) => `<a class="resource-link" target="_blank" rel="noopener"
        href="https://www.youtube.com/results?search_query=${encodeURIComponent(q)}">▶ ${esc(q)}</a>`)
    .join("");

  const sections = (l.sections || []).map((s) => `
    <div class="card lesson-section">
      <h3>${esc(s.heading)}</h3>
      <div class="analogy">${fmt(s.analogy)}</div>
      ${s.visual ? visualHolder(s.visual)
        : (s.diagram ? `<div class="diagram" data-type="mermaid" data-code="${escAttr(s.diagram)}"></div>` : "")}
      <div class="explanation">${fmt(s.explanation)}</div>
      <ul class="keypoints">${(s.key_points || []).map((k) => `<li>${fmt(k)}</li>`).join("")}</ul>
      <div class="tryit">${fmt(s.try_it)}</div>
    </div>`).join("");

  $("lessonBody").innerHTML = `
    <div class="lesson-head">
      <p class="mono kicker">DAY ${l.day}${l.is_checkpoint ? " · CHECKPOINT" : ""}</p>
      <h1>${esc(l.title)}</h1>
    </div>
    <p class="lesson-intro">${fmt(l.intro)}</p>
    ${resources ? `<div class="card"><p class="label mono">WATCH (best matches on YouTube)</p>${resources}</div>` : ""}
    ${sections}
    <div class="card">
      <p class="label mono">PRACTICE</p>
      <ul class="plain-list">${(l.practice || []).map((p) => `<li>${fmt(p)}</li>`).join("")}</ul>
      <p class="label mono" style="margin-top:14px">HOMEWORK</p>
      <ul class="plain-list">${(l.homework || []).map((h) => `<li>${fmt(h)}</li>`).join("")}</ul>
      <p class="label mono" style="margin-top:14px">COMMON MISTAKES</p>
      <ul class="plain-list">${(l.common_mistakes || []).map((m) => `<li>${fmt(m)}</li>`).join("")}</ul>
    </div>
    <div class="card"><p class="label mono">SUMMARY</p><p>${fmt(l.summary)}</p></div>
  `;

  const done = state.progress[String(l.day)] && state.progress[String(l.day)].completed;
  $("completeCard").style.display = done ? "none" : "";
  $("completeReward").textContent = `REWARD: +${l.is_checkpoint ? 150 : 100} XP`;

  $("askInput").value = "";
  $("explorations").innerHTML = (l.explorations || []).map(explorationHtml).join("");
  renderBossCard(l, done);
  renderDiagrams();
}

/* Boss Check offer/result card at the bottom of a lesson */
function renderBossCard(l, done) {
  const card = $("bossCard");
  const result = (state.quizzes || {})[String(l.day)];
  if (!l.quiz || !l.quiz.length || (!done && !result)) {
    card.classList.add("hidden");
    return;
  }
  card.classList.remove("hidden");
  if (result) {
    $("bossSub").innerHTML = `<span class="cleared">CLEARED</span> · ${result.score}/${result.total} correct · +${result.xp_earned} XP earned`;
    $("btnBoss").style.display = "none";
  } else {
    $("bossSub").textContent = `${l.quiz.length} questions on today's quest. Bonus XP only — you can't lose anything you've earned.`;
    $("btnBoss").style.display = "";
    $("btnBoss").onclick = () => startQuiz(l);
  }
}

function explorationHtml(x) {
  return `<div class="exploration">
    <p class="exp-q"><span class="mono">YOU ASKED</span> ${esc(x.q)}</p>
    <div class="exp-a">${fmt(x.a)}</div>
    ${visualHolder(x.visual)}
  </div>`;
}

$("btnAsk").addEventListener("click", async () => {
  const question = $("askInput").value.trim();
  if (!question) { toast("Type your question first."); return; }
  $("btnAsk").disabled = true;
  loading(true, "✨ Thinking…");
  try {
    const item = await api("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question, day: openDay }),
    });
    $("explorations").insertAdjacentHTML("beforeend", explorationHtml(item));
    $("askInput").value = "";
    renderDiagrams($("explorations"));
    $("explorations").lastElementChild.scrollIntoView({ block: "center", behavior: "smooth" });
  } catch (err) {
    toast(err.message, 6000);
  } finally {
    $("btnAsk").disabled = false;
    loading(false);
  }
});

$("btnBack").addEventListener("click", () => {
  renderDashboard();
  show("dashboard");
});

$("btnComplete").addEventListener("click", async () => {
  try {
    const r = await api(`/api/day/${openDay}/complete`, { method: "POST" });
    state = await api("/api/state");
    const lesson = currentLesson;
    const quizWaiting = lesson && lesson.quiz && lesson.quiz.length &&
      !(state.quizzes || {})[String(openDay)];

    if (quizWaiting) {
      // stay on the lesson — reveal the Boss Check right where the user is
      $("completeCard").style.display = "none";
      renderBossCard(lesson, true);
    } else {
      renderDashboard();
      show("dashboard");
    }

    if (r.xp_gained > 0) {
      const oldLv = levelFromXp(r.xp - r.xp_gained);
      const newLv = levelFromXp(r.xp);
      await showBanner("QUEST COMPLETE", `+${r.xp_gained} XP`);
      if (newLv > oldLv) {
        $("app").classList.add("shake");
        setTimeout(() => $("app").classList.remove("shake"), 500);
        await showBanner("LEVEL UP", `LV ${newLv} · ${rankFromLevel(newLv)} RANK`, true);
      }
      if (quizWaiting) {
        $("bossCard").scrollIntoView({ block: "center", behavior: "smooth" });
      }
    } else {
      toast(`Day ${openDay} complete.`);
    }
  } catch (err) {
    toast(err.message);
  }
});

/* ---------- Boss Check engine ---------- */

let quizRun = null; // {lesson, idx, answers, combo, xp, picked}

function startQuiz(lesson) {
  quizRun = { lesson, idx: 0, answers: [], combo: 0, xp: 0, picked: null };
  $("quizDay").textContent = lesson.day;
  show("quiz");
  renderQuestion();
}

function renderQuestion() {
  const { lesson, idx } = quizRun;
  const q = lesson.quiz[idx];
  quizRun.picked = null;

  $("quizDots").textContent = lesson.quiz.map((_, i) =>
    i < idx ? "●" : i === idx ? "◉" : "○").join(" ");
  $("quizQ").innerHTML = fmt(q.q);
  $("quizFeedback").className = "quiz-feedback hidden";
  $("btnNextQ").classList.add("hidden");
  $("wagerRow").classList.add("hidden");
  $("comboChip").textContent = quizRun.combo >= 2 ? `COMBO ×${quizRun.combo === 2 ? "1.5" : "2"}` : "";

  $("quizOptions").innerHTML = q.options.map((o, i) =>
    `<button class="opt" data-i="${i}">${fmt(o)}</button>`).join("");
  $("quizOptions").querySelectorAll(".opt").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (quizRun.picked !== null) return;
      quizRun.picked = parseInt(btn.dataset.i, 10);
      btn.classList.add("picked");
      $("quizOptions").querySelectorAll(".opt").forEach((b) => (b.disabled = true));
      $("wagerRow").classList.remove("hidden");
      $("wagerRow").scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  });
}

document.querySelectorAll(".wager-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    if (!quizRun || quizRun.picked === null) return;
    if ($("wagerRow").classList.contains("hidden")) return;
    revealAnswer(chip.dataset.w);
  });
});

function revealAnswer(confidence) {
  const { lesson, idx, picked } = quizRun;
  const q = lesson.quiz[idx];
  const correct = picked === q.answer;
  $("wagerRow").classList.add("hidden");

  const opts = $("quizOptions").querySelectorAll(".opt");
  opts[q.answer].classList.add("correct");
  if (!correct) opts[picked].classList.add("wrong");

  const wager = { safe: 1, confident: 1.5, allin: 2 }[confidence];
  let gained, cls, msg;
  if (correct) {
    quizRun.combo++;
    const comboMult = quizRun.combo === 1 ? 1 : quizRun.combo === 2 ? 1.5 : 2;
    gained = Math.round(10 * wager * comboMult);
    const crit = confidence === "allin";
    cls = crit ? "quiz-feedback crit" : "quiz-feedback win";
    msg = `${crit ? "⚡ CRITICAL HIT — " : ""}+${gained} XP${quizRun.combo >= 2 ? ` · COMBO ×${comboMult}` : ""}`;
  } else {
    quizRun.combo = 0;
    gained = 2;
    cls = "quiz-feedback lose";
    msg = `Weak point revealed: ${q.topic || "this topic"} · +2 XP for scouting it`;
  }
  quizRun.xp += gained;
  quizRun.answers.push({ chosen: picked, confidence });

  const fb = $("quizFeedback");
  fb.className = cls;
  fb.textContent = msg;
  $("comboChip").textContent = quizRun.combo >= 2 ? `COMBO ×${quizRun.combo === 2 ? "1.5" : "2"}` : "";

  const last = idx === lesson.quiz.length - 1;
  $("btnNextQ").textContent = last ? "Finish" : "Next";
  $("btnNextQ").classList.remove("hidden");
}

$("btnNextQ").addEventListener("click", async () => {
  quizRun.idx++;
  if (quizRun.idx < quizRun.lesson.quiz.length) {
    renderQuestion();
    return;
  }
  // finished — server grades authoritatively and awards the XP
  loading(true, "✨ Judging your run…");
  try {
    const r = await api(`/api/quiz/${quizRun.lesson.day}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers: quizRun.answers }),
    });
    state = await api("/api/state");
    loading(false);
    renderDashboard();
    show("dashboard");
    const oldLv = levelFromXp(r.xp - r.xp_gained);
    const newLv = levelFromXp(r.xp);
    await showBanner(
      r.perfect ? "FLAWLESS VICTORY" : "BOSS CHECK CLEARED",
      `${r.score}/${r.total} · +${r.xp_gained} XP${r.crits ? ` · ${r.crits} CRIT${r.crits > 1 ? "S" : ""}` : ""}`
    );
    if (newLv > oldLv) {
      $("app").classList.add("shake");
      setTimeout(() => $("app").classList.remove("shake"), 500);
      await showBanner("LEVEL UP", `LV ${newLv} · ${rankFromLevel(newLv)} RANK`, true);
    }
    for (const topic of r.mastered || []) {
      await showBanner("TOPIC MASTERED", topic.toUpperCase(), true);
    }
    if (r.revision) {
      toast(`Your mentor added a revision quest on ${r.revision.topics.join(", ")} — no worries, we'll re-nail it.`, 6000);
    }
  } catch (err) {
    loading(false);
    toast(err.message, 6000);
  } finally {
    quizRun = null;
  }
});

boot();
