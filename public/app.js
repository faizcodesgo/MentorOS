/* MentorOS frontend — plain JS, no framework. */

const $ = (id) => document.getElementById(id);
const views = ["onboarding", "negotiate", "generating", "dashboard", "lesson", "quiz", "skills", "recap", "viva"];

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

/* "~2h 30m" from estimated minutes */
function fmtTime(min) {
  if (!min || min < 1) return "";
  const h = Math.floor(min / 60), m = Math.round(min / 5) * 5 % 60;
  if (h && m) return `~${h}h ${m}m`;
  if (h) return `~${h}h`;
  return `~${min}m`;
}

let lastShownXp = null;

/* count the XP number upward in the level chip, with a gold glow */
function animateXpChip(el, from, to, lv) {
  const dur = 700, t0 = performance.now();
  el.classList.remove("bump");
  void el.offsetWidth;
  el.classList.add("bump");
  let done = false;
  const finish = () => { if (!done) { done = true; el.textContent = `LV ${lv} · ${to} XP`; } };
  (function step(t) {
    if (done) return;
    const p = Math.min(1, (t - t0) / dur);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = `LV ${lv} · ${Math.round(from + (to - from) * eased)} XP`;
    if (p < 1) requestAnimationFrame(step); else finish();
  })(t0);
  setTimeout(finish, dur + 120);   // guarantee the final value even if rAF is throttled
}

/* ---------- helpers ---------- */

function show(view) {
  views.forEach((v) => $("view-" + v).classList.toggle("hidden", v !== view));
  $("askFab").classList.toggle("hidden", view !== "lesson");   // floating Ask only in a lesson
  $("askSheet").classList.add("hidden");
  window.scrollTo(0, 0);
}

function toast(msg, ms = 4000) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), ms);
}

let loadingRotator = null;
function loading(on, text) {
  $("loading").classList.toggle("hidden", !on);
  if (loadingRotator) { clearInterval(loadingRotator); loadingRotator = null; }
  if (text) $("loadingText").textContent = text;
}

/* on the long generation steps, rotate encouraging lines so it feels alive */
function loadingCycle(messages) {
  $("loading").classList.remove("hidden");
  let i = 0;
  $("loadingText").textContent = messages[0];
  if (loadingRotator) clearInterval(loadingRotator);
  loadingRotator = setInterval(() => {
    i = (i + 1) % messages.length;
    $("loadingText").textContent = messages[i];
  }, 2800);
}

/* quiet reward pill — replaces the old full-screen victory banner */
function rewardPill(label, amount) {
  return new Promise((resolve) => {
    const el = document.createElement("div");
    el.className = "reward-pill";
    el.innerHTML = amount ? `${esc(label)} <span class="amt">${esc(amount)}</span>` : esc(label);
    document.body.appendChild(el);
    setTimeout(() => { el.remove(); resolve(); }, 1500);
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
    name: $("inName").value.trim(),
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
  const estTxt = entry && entry.est_minutes ? ` · ${fmtTime(entry.est_minutes)} today` : "";
  $("todayReward").textContent = entry ? `+${questReward(entry)} XP${estTxt}` : "";
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

  renderGreeting();
  renderWeeklyReport();
  renderSkillMapCard();
  renderSavedCard();
  loadWarmup();

  $("dayList").querySelectorAll(".day-row").forEach((row) => {
    row.addEventListener("click", () => {
      if (row.classList.contains("locked")) {
        toast("One quest at a time — finish this one first.");
        return;
      }
      const day = parseInt(row.dataset.day, 10);
      if (row.classList.contains("done")) openRecap(day);  // done days open their recap
      else openLesson(day);
    });
  });
}

/* time-of-day + name + one continuity thread — built client-side, no AI */
function renderGreeting() {
  const name = (state.profile && state.profile.name) ? state.profile.name : "";
  const h = new Date().getHours();
  const part = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : h < 22 ? "Good evening" : "Late one";
  let line = name ? `${part}, ${name}.` : `${part}.`;

  // one honest continuity thread from real data
  const dna = state.dna;
  const s = state.streak || {};
  const doneReal = orderedCurriculum().filter((d) => d.kind !== "revision" && isDone(d.day)).length;
  let thread = "";
  if (new Date().getDay() === 1 && doneReal > 0)   // fresh-start effect: Monday = clean slate
    thread = "New week, clean slate — let's make it count.";
  else if (doneReal === 0) thread = "Let's get your first quest done.";
  else if (dna && dna.weakest && dna.topics && dna.topics[dna.weakest] && dna.topics[dna.weakest].band !== "mastered")
    thread = `We'll keep chipping at ${dna.weakest} today.`;
  else if (s.count >= 3) thread = `${s.count} days running — nice rhythm.`;
  else if (dna && dna.strongest) thread = `${dna.strongest} is clicking for you.`;
  $("greeting").textContent = line + (thread ? " " + thread : "");
}

/* weekly progress report — a card that appears only after ~7 more quests done */
function renderWeeklyReport() {
  const card = $("weeklyCard");
  const w = state.weekly || { last_shown: 0, snap_xp: 0, snap_mastered: [] };
  const doneReal = orderedCurriculum().filter((d) => d.kind !== "revision" && isDone(d.day)).length;
  if (doneReal - (w.last_shown || 0) < 7) { card.classList.add("hidden"); return; }

  const xpGain = (state.xp || 0) - (w.snap_xp || 0);
  const dna = state.dna || {};
  const masteredNow = Object.entries(dna.topics || {}).filter(([, r]) => r.band === "mastered").map(([t]) => t);
  const newlyMastered = masteredNow.filter((t) => !(w.snap_mastered || []).includes(t));
  const questsThisWeek = doneReal - (w.last_shown || 0);

  const rows = [
    `<div class="wk-stat"><span class="wk-num">${questsThisWeek}</span><span class="wk-lbl">quests done</span></div>`,
    `<div class="wk-stat"><span class="wk-num">+${xpGain}</span><span class="wk-lbl">XP earned</span></div>`,
    `<div class="wk-stat"><span class="wk-num">${newlyMastered.length}</span><span class="wk-lbl">topics mastered</span></div>`,
  ].join("");
  let notes = "";
  if (newlyMastered.length) notes += `<p class="wk-note">You locked in: <b>${newlyMastered.slice(0, 4).map(esc).join(", ")}</b>.</p>`;
  if (dna.weakest && dna.topics[dna.weakest] && dna.topics[dna.weakest].band !== "mastered")
    notes += `<p class="wk-note">Next week's focus: <b>${esc(dna.weakest)}</b>.</p>`;
  else notes += `<p class="wk-note">Strong week — keep the rhythm going.</p>`;

  $("weeklyBody").innerHTML = `<div class="wk-stats">${rows}</div>${notes}`;
  card.classList.remove("hidden");
}

$("weeklyDismiss").addEventListener("click", async () => {
  $("weeklyCard").classList.add("hidden");
  try { await api("/api/weekly/seen", { method: "POST" }); state = await api("/api/state"); }
  catch {}
});

/* NOTE: the habit-stacking "study cue" was removed — a static reminder can't
   fire at the anchor moment. It returns as a notification in the notifications
   phase (needs PWA/native). The study_anchor field + /api/anchor stay dormant. */

function renderSavedCard() {
  const marks = state.bookmarks || [];
  const card = $("savedCard");
  if (!marks.length) { card.classList.add("hidden"); return; }
  card.classList.remove("hidden");
  $("savedList").innerHTML = marks.map((m) =>
    `<button class="saved-row" data-day="${m.day}"><span class="saved-h">${esc(m.heading)}</span><span class="saved-day mono">Day ${m.day}</span></button>`).join("");
  $("savedList").querySelectorAll(".saved-row").forEach((row) => {
    row.addEventListener("click", () => openLesson(parseInt(row.dataset.day, 10)));
  });
}

function renderStreakChip() {
  const s = state.streak || { count: 0, shields: 0 };
  if (!s.count) return "";
  const shields = s.shields ? ` · ${s.shields} shield${s.shields > 1 ? "s" : ""}` : "";
  return `<span class="streak-chip"><b>${s.count}</b>-day streak${shields}</span>`;
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
  loading(true, "Opening your skill map…");
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

/* ---------- day / chapter recap ---------- */

/* which phase (chapter) a real quest-day belongs to, by its day number */
function phaseOfDay(day) {
  const phases = state.plan.phases || [];
  let cum = 0;
  for (let i = 0; i < phases.length; i++) {
    cum += phases[i].days;
    if (day <= cum) return { index: i, phase: phases[i], startDay: cum - phases[i].days + 1, endDay: cum };
  }
  return phases.length ? { index: phases.length - 1, phase: phases[phases.length - 1], startDay: 1, endDay: state.plan.days } : null;
}

/* is this real quest the last one of its chapter? (chapter just completed) */
function isChapterEnd(day) {
  const p = phaseOfDay(day);
  if (!p) return false;
  // the highest-day real quest at or below endDay
  const real = state.plan.curriculum.filter((d) => d.kind !== "revision" && d.day <= p.endDay);
  const lastDay = Math.max(...real.map((d) => d.day));
  return day === lastDay;
}

async function openRecap(day, opts = {}) {
  loading(true, "Putting today together…");
  let lesson;
  try { lesson = await api("/api/lesson/" + day); } catch { loading(false); return; }
  loading(false);

  const entry = state.plan.curriculum.find((d) => d.day === day) || {};
  const quiz = (state.quizzes || {})[String(day)];
  const dna = state.dna || {};

  $("recapKicker").textContent = entry.kind === "revision" ? "Revision recap" : `Day ${day} recap`;
  $("recapTitle").textContent = lesson.title || entry.title || "";
  $("recapSummary").textContent = stripMd(lesson.summary || "");

  const xpToday = questReward(entry) + (quiz ? quiz.xp_earned : 0);
  const stats = [`+${xpToday} XP earned`];
  if (quiz) stats.push(`Checkpoint ${quiz.score}/${quiz.total}`);
  stats.push(`${(entry.topics || []).length} topic${(entry.topics || []).length === 1 ? "" : "s"}`);
  $("recapStats").innerHTML = stats.map((s) => `<span class="recap-stat">${esc(s)}</span>`).join("");

  // one thing to carry forward — a weak topic, tied to spaced review
  const carry = dna.weakest && dna.topics && dna.topics[dna.weakest] && dna.topics[dna.weakest].band !== "mastered"
    ? dna.weakest : ((entry.topics || [])[0] || "");
  if (carry) {
    $("recapCarryLabel").style.display = "";
    $("recapCarry").textContent = `${carry} — it'll come back in a warm-up soon, so it stays fresh.`;
  } else {
    $("recapCarryLabel").style.display = "none";
    $("recapCarry").textContent = "";
  }

  // "say it back" — pick a concept from today to self-explain
  const concept = (entry.topics || [])[0] || entry.title || "today's idea";
  explainConcept = { day, concept };
  $("explainPrompt").textContent = `In your own words, what is “${concept}” and why does it matter?`;
  $("explainInput").value = "";
  $("explainFeedback").className = "explain-feedback hidden";
  $("btnExplain").disabled = false;
  $("explainCard").style.display = entry.kind === "revision" ? "none" : "";

  // chapter block only when a chapter just wrapped
  const chap = opts.chapterEnd ? phaseOfDay(day) : null;
  if (chap) {
    vivaChapter = chap.index;
    $("btnStartViva").onclick = () => startViva(chap.index);
    $("chapterBlock").classList.remove("hidden");
    $("chapterTitle").textContent = chap.phase.name;
    $("chapterBody").textContent = `Chapter ${chap.index + 1} done — days ${chap.startDay}–${chap.endDay}. ${chap.phase.focus || ""}`;
    const solid = Object.entries(dna.topics || {})
      .filter(([, r]) => r.band === "mastered").map(([t]) => t).slice(0, 6);
    $("chapterSolid").innerHTML = solid.length
      ? `<p class="label">Solid now</p>` + solid.map((t) => `<span class="recap-chip">${esc(t)}</span>`).join("")
      : "";
    const next = (state.plan.phases || [])[chap.index + 1];
    $("chapterNext").textContent = next ? `Next chapter: ${next.name} — ${next.focus || ""}` : "Final chapter — you're almost there.";
  } else {
    $("chapterBlock").classList.add("hidden");
  }

  show("recap");
}

$("btnRecapBack").addEventListener("click", () => { renderDashboard(); show("dashboard"); });

/* ---------- mock interview (viva) ---------- */

let vivaChapter = 0;
let vivaRun = null; // {questions, idx, answers}

async function startViva(chapter) {
  loadingCycle(["Setting up your interview…", "Thinking up good questions…"]);
  try {
    const r = await api("/api/interview/start", { method: "POST", body: JSON.stringify({ chapter }) });
    loading(false);
    if (!r.questions || !r.questions.length) { toast("Couldn't set up the interview — try again."); return; }
    vivaRun = { chapter, questions: r.questions, idx: 0, answers: [] };
    $("vivaAsk").classList.remove("hidden");
    $("vivaResults").classList.add("hidden");
    show("viva");
    renderVivaQ();
  } catch (err) { loading(false); toast(err.message, 6000); }
}

function renderVivaQ() {
  const { questions, idx } = vivaRun;
  const q = questions[idx];
  $("vivaDots").textContent = questions.map((_, i) => i < idx ? "●" : i === idx ? "◉" : "○").join(" ");
  $("vivaKind").textContent = (q.kind === "applied" ? "Applied" : "Theory") + ` · Question ${idx + 1} of ${questions.length}`;
  $("vivaQ").innerHTML = fmt(q.q);
  $("vivaInput").value = "";
  $("btnVivaNext").textContent = idx === questions.length - 1 ? "Finish & get feedback" : "Next question";
  $("vivaInput").focus();
}

$("btnVivaNext").addEventListener("click", async () => {
  const q = vivaRun.questions[vivaRun.idx];
  vivaRun.answers.push({ id: q.id, text: $("vivaInput").value.trim() });
  if (vivaRun.idx < vivaRun.questions.length - 1) {
    vivaRun.idx++;
    renderVivaQ();
    return;
  }
  loadingCycle(["Reviewing your interview…", "Weighing each answer…", "Writing your feedback…"]);
  try {
    const r = await api("/api/interview/submit", {
      method: "POST",
      body: JSON.stringify({ chapter: vivaRun.chapter, answers: vivaRun.answers }),
    });
    state = await api("/api/state");
    loading(false);
    renderVivaResults(r);
  } catch (err) { loading(false); toast(err.message, 6000); }
});

$("btnVivaQuit").addEventListener("click", () => {
  if (!confirm("Leave the interview? Your answers won't be saved.")) return;
  vivaRun = null; renderDashboard(); show("dashboard");
});

function renderVivaResults(r) {
  $("vivaAsk").classList.add("hidden");
  $("vivaResults").classList.remove("hidden");
  $("vivaDots").textContent = "";
  $("vivaOverall").innerHTML = `<p class="label">How you did</p><p class="viva-overall-text">${fmt(r.overall || "")}</p>`;
  const qById = {};
  vivaRun.questions.forEach((q) => (qById[q.id] = q.q));
  $("vivaResultList").innerHTML = (r.results || []).map((res) => `
    <div class="card viva-result ${esc(res.verdict || "okay")}">
      <p class="viva-rq">${fmt(qById[res.id] || "")}</p>
      <p class="vr-good">✓ ${esc(res.whats_good || "")}</p>
      ${res.tighten ? `<p class="vr-tighten">→ ${esc(res.tighten)}</p>` : ""}
      ${res.model_answer ? `<details class="vr-model"><summary>Model answer</summary><p>${fmt(res.model_answer)}</p></details>` : ""}
    </div>`).join("");
  rewardPill("Mock interview complete", `+${r.xp_gained} XP`);
}

$("btnVivaDone").addEventListener("click", () => { vivaRun = null; renderDashboard(); show("dashboard"); });

/* floating ask button → bottom sheet */
$("askFab").addEventListener("click", () => {
  $("askSheet").classList.remove("hidden");
  $("askInput").focus();
});
$("askClose").addEventListener("click", () => $("askSheet").classList.add("hidden"));
$("askSheet").addEventListener("click", (e) => { if (e.target === $("askSheet")) $("askSheet").classList.add("hidden"); });

let explainConcept = null;
$("btnExplain").addEventListener("click", async () => {
  const text = $("explainInput").value.trim();
  if (!text) { toast("Write your explanation first."); return; }
  if (!explainConcept) return;
  $("btnExplain").disabled = true;
  loadingCycle(["Reading your explanation…", "Checking it against the lesson…"]);
  try {
    const r = await api("/api/explain", {
      method: "POST",
      body: JSON.stringify({ day: explainConcept.day, concept: explainConcept.concept, text }),
    });
    state = await api("/api/state");
    loading(false);
    const fb = $("explainFeedback");
    fb.className = "explain-feedback";
    fb.innerHTML =
      `<p class="ef-good">✓ ${esc(r.whats_good)}</p>` +
      (r.whats_missing ? `<p class="ef-add">+ ${esc(r.whats_missing)}</p>` : "");
    await rewardPill("Nice — you said it back", `+${r.xp_gained} XP`);
  } catch (err) {
    loading(false);
    $("btnExplain").disabled = false;
    toast(err.message, 6000);
  }
});

/* ---------- morning warm-up (spaced review) ---------- */

let warmupRun = null;

async function loadWarmup() {
  $("warmupCard").classList.add("hidden");
  $("warmupDone").classList.add("hidden");
  let data;
  try { data = await api("/api/warmup"); } catch { return; }   // cheap check, no AI
  if (data.done) {
    $("warmupDone").innerHTML = `<span class="check">✓</span> Warm-up done`;
    $("warmupDone").classList.remove("hidden");
    return;
  }
  if (!data.available) return;  // nothing due yet
  // tiny-habits framing: if today's quest isn't done yet, sell it as a "minimum day"
  const questDone = isDone(currentEntry().day);
  $("warmupSub").textContent = questDone
    ? `${data.count} quick recall${data.count > 1 ? "s" : ""} on earlier topics · +15 XP`
    : `Short on time? A 2-minute warm-up keeps your streak alive.`;
  $("warmupCard").classList.remove("hidden");
  $("btnWarmup").onclick = startWarmup;
}

async function startWarmup() {
  loadingCycle(["Setting up your warm-up…", "Fresh questions, not repeats…"]);
  let data;
  try { data = await api("/api/warmup/start", { method: "POST" }); }
  catch (err) { loading(false); toast(err.message); return; }
  loading(false);
  if (!data.questions || !data.questions.length) { toast("No warm-up due right now."); return; }
  warmupRun = { questions: data.questions, idx: 0, results: [], picked: null };
  $("quizDay").textContent = "warm-up";
  document.querySelector("#view-quiz .kicker").textContent = "Warm-up · quick recall";
  show("quiz");
  renderWarmupQ();
}

function renderWarmupQ() {
  const { questions, idx } = warmupRun;
  const q = questions[idx];
  warmupRun.picked = null;
  $("quizDots").textContent = questions.map((_, i) => i < idx ? "●" : i === idx ? "◉" : "○").join(" ");
  $("quizQ").innerHTML = fmt(q.q);
  $("quizFeedback").className = "quiz-feedback hidden";
  $("btnNextQ").classList.add("hidden");
  $("wagerRow").classList.add("hidden");   // warm-ups skip the confidence wager
  $("quizOptions").innerHTML = q.options.map((o, i) => `<button class="opt" data-i="${i}">${fmt(o)}</button>`).join("");
  $("quizOptions").querySelectorAll(".opt").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (warmupRun.picked !== null) return;
      warmupRun.picked = parseInt(btn.dataset.i, 10);
      const correct = warmupRun.picked === q.answer;
      const opts = $("quizOptions").querySelectorAll(".opt");
      opts[q.answer].classList.add("correct");
      if (!correct) opts[warmupRun.picked].classList.add("wrong");
      opts.forEach((b) => (b.disabled = true));
      warmupRun.results.push({ ref: q.ref, topic: q.topic, correct });
      const fb = $("quizFeedback");
      fb.className = correct ? "quiz-feedback win" : "quiz-feedback lose";
      fb.textContent = correct ? "Still got it." : "Worth another look — the answer's highlighted.";
      $("btnNextQ").textContent = idx === questions.length - 1 ? "Done" : "Next";
      $("btnNextQ").classList.remove("hidden");
    });
  });
}

async function finishWarmup() {
  loading(true, "Saving your warm-up…");
  try {
    const r = await api("/api/warmup/submit", { method: "POST", body: JSON.stringify({ results: warmupRun.results }) });
    state = await api("/api/state");
    loading(false);
    renderDashboard();
    show("dashboard");
    loadWarmup();
    await rewardPill(`Warm-up · ${r.score}/${r.total}`, `+${r.xp_gained} XP`);
  } catch (err) {
    loading(false);
    toast(err.message);
  } finally {
    warmupRun = null;
  }
}

/* ---------- focus session ---------- */

let focus = null;

$("btnFocus") && $("btnFocus").addEventListener("click", () => {
  const entry = currentEntry();
  $("focusQuestName").textContent = entry ? entry.title : "Today's quest";
  $("focusIntent").value = "";
  $("focusSheet").classList.remove("hidden");
});
$("btnFocusCancel").addEventListener("click", () => $("focusSheet").classList.add("hidden"));
document.querySelectorAll(".dur-chip").forEach((c) => c.addEventListener("click", () => {
  document.querySelectorAll(".dur-chip").forEach((x) => x.classList.remove("selected"));
  c.classList.add("selected");
}));

$("btnFocusStart").addEventListener("click", async () => {
  const mins = parseInt(document.querySelector(".dur-chip.selected").dataset.min, 10);
  const intent = $("focusIntent").value.trim();
  $("focusSheet").classList.add("hidden");
  focus = { total: mins * 60, left: mins * 60, left_room: false, timer: null };
  $("focusIntentShow").textContent = intent ? `Goal: ${intent}` : "";
  $("focusStatus").textContent = "";
  $("focusRun").classList.remove("hidden");
  tickFocus();
  try { await document.getElementById("focusRun").requestFullscreen(); } catch {}
  requestWakeLock();
  focus.timer = setInterval(() => {
    focus.left--;
    tickFocus();
    if (focus.left <= 0) endFocus(true);
  }, 1000);
});

function tickFocus() {
  const m = Math.floor(focus.left / 60), s = focus.left % 60;
  $("focusTime").textContent = `${m}:${String(s).padStart(2, "0")}`;
  $("focusBarFill").style.width = `${100 * (1 - focus.left / focus.total)}%`;
}

let wakeLock = null;
async function requestWakeLock() {
  try { wakeLock = await navigator.wakeLock.request("screen"); } catch {}
}
document.addEventListener("visibilitychange", () => {
  if (!focus) return;
  if (document.hidden) {
    focus.left_room = true;
    $("focusStatus").textContent = "";
  } else {
    requestWakeLock();  // wake lock drops when hidden — re-acquire
    if (focus.left_room) $("focusStatus").textContent = "Welcome back — you left the room.";
  }
});

$("btnFocusEnd").addEventListener("click", () => endFocus(false));

async function endFocus(completed) {
  if (!focus) return;
  clearInterval(focus.timer);
  const unbroken = completed && !focus.left_room;
  focus = null;
  try { if (wakeLock) { wakeLock.release(); wakeLock = null; } } catch {}
  try { if (document.fullscreenElement) await document.exitFullscreen(); } catch {}
  $("focusRun").classList.add("hidden");
  if (completed) {
    try {
      const r = await api("/api/focus/done", { method: "POST", body: JSON.stringify({ unbroken }) });
      state = await api("/api/state");
      renderDashboard();
      await rewardPill("Focus complete", `+${r.xp_gained} XP`);
    } catch (err) { toast(err.message); }
  } else {
    toast("Paused — pick up anytime.");
  }
}

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
          flowchart: { nodeSpacing: 45, rankSpacing: 50, padding: 14, useMaxWidth: true, htmlLabels: false },
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

/* ---------- interactive lesson widgets ---------- */

/* drop anything malformed so a bad widget never breaks a lesson (mirrors the SVG guard) */
function validInteraction(it) {
  if (!it || (it.type !== "mcq" && it.type !== "predict")) return false;
  if (!Array.isArray(it.options) || it.options.length < 2 || it.options.length > 5) return false;
  if (!it.options.every((o) => typeof o === "string" && o.length)) return false;
  if (typeof it.answer !== "number" || it.answer < 0 || it.answer >= it.options.length) return false;
  if (it.type === "predict" && (typeof it.code !== "string" || !it.code.length)) return false;
  return true;
}

/* build the widget DOM (with handlers) — commit-before-reveal, rewards-only */
function buildInteraction(it) {
  const wrap = document.createElement("div");
  wrap.className = "interaction";
  const label = it.type === "predict" ? "Predict the output" : "Quick check";
  const codeHtml = it.type === "predict"
    ? `<pre class="interaction-code"><code>${esc(it.code)}</code></pre>` : "";
  wrap.innerHTML = `
    <p class="label">${label}</p>
    ${it.prompt ? `<p class="interaction-q">${fmt(it.prompt)}</p>` : ""}
    ${codeHtml}
    <div class="interaction-opts">${it.options.map((o, i) => `<button class="iopt" data-i="${i}">${fmt(o)}</button>`).join("")}</div>
    <p class="interaction-feedback hidden"></p>`;

  let answered = false;
  wrap.querySelectorAll(".iopt").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (answered) return;                    // commit-before-reveal, one shot to think
      answered = true;
      const picked = parseInt(btn.dataset.i, 10);
      const correct = picked === it.answer;
      const opts = wrap.querySelectorAll(".iopt");
      opts[it.answer].classList.add("correct");
      if (!correct) opts[picked].classList.add("wrong");
      opts.forEach((b) => (b.disabled = true));
      const fb = wrap.querySelector(".interaction-feedback");
      fb.className = "interaction-feedback " + (correct ? "good" : "off");
      const why = it.explanation ? " " + stripMd(it.explanation) : "";
      fb.textContent = (correct ? "Right." : "Not quite.") + why;
    });
  });
  return wrap;
}

let lessonSteps = [];
let stepIdx = 0;

function renderLesson(l) {
  currentLesson = l;

  // header (rendered once, fixed across steps)
  const lessonEntry = state.plan.curriculum.find((d) => d.day === l.day) || {};
  const headKicker = lessonEntry.kind === "revision" ? "REVISION"
    : `DAY ${l.day}${l.is_checkpoint ? " · CHECKPOINT" : ""}`;
  $("lessonHead").innerHTML = `<p class="mono kicker">${headKicker}</p><h1>${esc(l.title)}</h1>`;

  // videos / watch links
  const direct = (l.videos || [])
    .map((v) => `<a class="resource-link" target="_blank" rel="noopener" href="${esc(v.url)}">▶ ${esc(v.title)} <span class="channel">· ${esc(v.channel)}</span></a>`)
    .join("");
  const resources = direct || (l.resource_queries || [])
    .map((q) => `<a class="resource-link" target="_blank" rel="noopener"
        href="https://www.youtube.com/results?search_query=${encodeURIComponent(q)}">▶ ${esc(q)}</a>`)
    .join("");

  // at most 2 sections carry an interactive widget
  const widgetSlots = {};
  let widgetCount = 0;
  (l.sections || []).forEach((s, i) => {
    if (widgetCount < 2 && validInteraction(s.interaction)) { widgetSlots[i] = s.interaction; widgetCount++; }
  });

  // build the step list: intro(+watch) → each section → practice bundle → summary
  lessonSteps = [];
  lessonSteps.push({ kind: "intro", html:
    `<p class="lesson-intro">${fmt(l.intro)}</p>` +
    (resources ? `<div class="card"><p class="label mono">WATCH</p>${l.resources_note ? `<p class="resources-note">${fmt(l.resources_note)}</p>` : ""}${resources}</div>` : "")
  });
  (l.sections || []).forEach((s, i) => lessonSteps.push({ kind: "section", i, s, widget: widgetSlots[i], html: sectionHtml(l, s, i) }));
  lessonSteps.push({ kind: "practice", html:
    `<div class="card">
      <p class="label mono">PRACTICE</p>
      <ul class="plain-list">${(l.practice || []).map((p) => `<li>${fmt(p)}</li>`).join("")}</ul>
      <p class="label mono" style="margin-top:14px">HOMEWORK</p>
      <ul class="plain-list">${(l.homework || []).map((h) => `<li>${fmt(h)}</li>`).join("")}</ul>
      <p class="label mono" style="margin-top:14px">COMMON MISTAKES</p>
      <ul class="plain-list">${(l.common_mistakes || []).map((m) => `<li>${fmt(m)}</li>`).join("")}</ul>
    </div>`
  });
  lessonSteps.push({ kind: "summary", html: `<div class="card"><p class="label mono">SUMMARY</p><p>${fmt(l.summary)}</p></div>` });

  const done = state.progress[String(l.day)] && state.progress[String(l.day)].completed;
  $("completeReward").textContent = `REWARD: +${l.is_checkpoint ? 150 : 100} XP`;
  $("askInput").value = "";
  $("explorations").innerHTML = (l.explorations || []).map(explorationHtml).join("");

  stepIdx = 0;
  renderStep();
}

function sectionHtml(l, s, i) {
  const marked = (state.bookmarks || []).some((m) => m.day === l.day && m.sectionIndex === i);
  return `<div class="card lesson-section">
      <div class="section-head">
        <h3>${esc(s.heading)}</h3>
        <button class="bookmark-btn ${marked ? "on" : ""}" data-sec="${i}" data-heading="${escAttr(s.heading)}" aria-label="Save section">
          <svg viewBox="0 0 24 24" fill="${marked ? "currentColor" : "none"}" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
        </button>
      </div>
      ${s.probe ? `<div class="probe">${fmt(s.probe)}</div>` : ""}
      <div class="analogy">${fmt(s.analogy)}</div>
      ${s.visual ? visualHolder(s.visual)
        : (s.diagram ? `<div class="diagram" data-type="mermaid" data-code="${escAttr(s.diagram)}"></div>` : "")}
      <div class="explanation">${fmt(s.explanation)}</div>
      ${s.worked_example ? `<div class="worked"><p class="label">Worked example</p><div class="worked-body">${fmt(s.worked_example)}</div></div>` : ""}
      <ul class="keypoints">${(s.key_points || []).map((k) => `<li>${fmt(k)}</li>`).join("")}</ul>
      <div class="tryit">${fmt(s.try_it)}</div>
      ${s.interaction && validInteraction(s.interaction) ? `<div class="interaction-slot" data-slot="${i}"></div>` : ""}
    </div>`;
}

function renderStep() {
  const l = currentLesson;
  const step = lessonSteps[stepIdx];
  const last = stepIdx === lessonSteps.length - 1;
  const done = state.progress[String(l.day)] && state.progress[String(l.day)].completed;

  const cont = $("stepContent");
  cont.innerHTML = step.html;
  cont.classList.remove("step-in"); void cont.offsetWidth; cont.classList.add("step-in");

  // progress
  $("stepBarFill").style.width = `${((stepIdx + 1) / lessonSteps.length) * 100}%`;
  $("stepCount").textContent = `${stepIdx + 1} / ${lessonSteps.length}`;

  // nav
  $("btnStepBack").style.visibility = stepIdx === 0 ? "hidden" : "visible";
  $("btnStepNext").style.display = last ? "none" : "";
  $("completeCard").style.display = last && !done ? "" : "none";

  // wire this step's dynamic bits
  if (step.kind === "section") {
    if (step.widget) {
      const slot = cont.querySelector(`.interaction-slot[data-slot="${step.i}"]`);
      if (slot) slot.appendChild(buildInteraction(step.widget));
    }
    const btn = cont.querySelector(".bookmark-btn");
    if (btn) btn.addEventListener("click", async () => {
      try {
        const r = await api("/api/bookmark/toggle", { method: "POST",
          body: JSON.stringify({ day: l.day, sectionIndex: step.i, heading: btn.dataset.heading }) });
        btn.classList.toggle("on", r.saved);
        btn.querySelector("svg").setAttribute("fill", r.saved ? "currentColor" : "none");
        state = await api("/api/state");
      } catch (err) { toast(err.message); }
    });
    renderDiagrams(cont);   // render on reveal (offscreen diagrams render blank)
  }

  // checkpoint offer lives on the last step
  if (last) renderBossCard(l, done); else $("bossCard").classList.add("hidden");

  window.scrollTo(0, 0);
}

$("btnStepNext").addEventListener("click", () => { if (stepIdx < lessonSteps.length - 1) { stepIdx++; renderStep(); } });
$("btnStepBack").addEventListener("click", () => { if (stepIdx > 0) { stepIdx--; renderStep(); } });

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
  loadingCycle(["Thinking about your question…", "Pulling the threads together…", "Almost there…"]);
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

    const finishedDay = openDay;
    if (quizWaiting) {
      // stay on the lesson — reveal the Boss Check right where the user is
      $("completeCard").style.display = "none";
      renderBossCard(lesson, true);
    }

    if (r.xp_gained > 0) {
      const oldLv = levelFromXp(r.xp - r.xp_gained);
      const newLv = levelFromXp(r.xp);
      await rewardPill("Quest complete", `+${r.xp_gained} XP`);
      if (newLv > oldLv) {
        await rewardPill(`Level ${newLv} · ${rankFromLevel(newLv)}`, "");
      }
    }
    if (quizWaiting) {
      $("bossCard").scrollIntoView({ block: "center", behavior: "smooth" });
    } else {
      // no checkpoint on this day — go straight to the day recap
      openRecap(finishedDay, { chapterEnd: isChapterEnd(finishedDay) });
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

  // optional one-hint "Stuck?" reveal (pre-generated, no AI call)
  const hintWrap = $("quizHintWrap");
  if (q.hint) {
    hintWrap.style.display = "";
    $("quizHint").textContent = q.hint;
    $("quizHint").classList.add("hidden");
    $("quizHintBtn").style.display = "";
    $("quizHintBtn").onclick = () => {
      $("quizHint").classList.remove("hidden");
      $("quizHintBtn").style.display = "none";
    };
  } else {
    hintWrap.style.display = "none";
  }

  $("quizOptions").innerHTML = q.options.map((o, i) =>
    `<button class="opt" data-i="${i}">${fmt(o)}</button>`).join("");
  const opts = $("quizOptions").querySelectorAll(".opt");
  opts.forEach((btn) => {
    btn.addEventListener("click", () => {
      // you can freely change your answer until you commit a confidence wager
      opts.forEach((b) => b.classList.remove("picked"));
      btn.classList.add("picked");
      quizRun.picked = parseInt(btn.dataset.i, 10);
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
  opts.forEach((b) => (b.disabled = true));   // now locked — wager committed
  opts[q.answer].classList.add("correct");
  if (!correct) opts[picked].classList.add("wrong");

  const wager = { safe: 1, confident: 1.5, allin: 2 }[confidence];
  let gained, cls, msg;
  if (correct) {
    quizRun.combo++;
    const comboMult = quizRun.combo === 1 ? 1 : quizRun.combo === 2 ? 1.5 : 2;
    gained = Math.round(10 * wager * comboMult);
    const sure = confidence === "allin";        // "Certain" and right
    cls = sure ? "quiz-feedback gold" : "quiz-feedback win";
    const combo = quizRun.combo >= 2 ? ` · ${quizRun.combo} in a row` : "";
    msg = `${sure ? "Sure and correct" : "Correct"} · +${gained} XP${combo}`;
  } else {
    quizRun.combo = 0;
    gained = 2;
    cls = "quiz-feedback lose";
    msg = `Not quite — the right answer's highlighted.`;
  }
  quizRun.xp += gained;
  quizRun.answers.push({ chosen: picked, confidence });

  const fb = $("quizFeedback");
  fb.className = cls;
  fb.textContent = msg;

  const last = idx === lesson.quiz.length - 1;
  $("btnNextQ").textContent = last ? "See results" : "Next";
  $("btnNextQ").classList.remove("hidden");
}

$("btnNextQ").addEventListener("click", async () => {
  if (warmupRun) {   // warm-up mode reuses the quiz view
    warmupRun.idx++;
    if (warmupRun.idx < warmupRun.questions.length) renderWarmupQ();
    else finishWarmup();
    return;
  }
  quizRun.idx++;
  if (quizRun.idx < quizRun.lesson.quiz.length) {
    renderQuestion();
    return;
  }
  // finished — server grades authoritatively and awards the XP
  const finishedDay = quizRun.lesson.day;
  loading(true, "Scoring your answers…");
  try {
    const r = await api(`/api/quiz/${finishedDay}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers: quizRun.answers }),
    });
    state = await api("/api/state");
    loading(false);
    const oldLv = levelFromXp(r.xp - r.xp_gained);
    const newLv = levelFromXp(r.xp);
    await rewardPill(r.perfect ? `Perfect run · ${r.score}/${r.total}` : `Checkpoint · ${r.score}/${r.total}`, `+${r.xp_gained} XP`);
    if (newLv > oldLv) {
      await rewardPill(`Level ${newLv} · ${rankFromLevel(newLv)}`, "");
    }
    for (const topic of r.mastered || []) {
      await rewardPill("Topic mastered", topic);
    }
    if (r.revision) {
      toast(`Your mentor added a revision on ${r.revision.topics.join(", ")} — we'll go over it together.`, 6000);
    }
    openRecap(finishedDay, { chapterEnd: isChapterEnd(finishedDay) });
  } catch (err) {
    loading(false);
    toast(err.message, 6000);
  } finally {
    quizRun = null;
  }
});

boot();
