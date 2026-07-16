/* MentorOS frontend — plain JS, no framework. */

const $ = (id) => document.getElementById(id);
const views = ["auth", "onboarding", "negotiate", "generating", "dashboard", "lesson", "quiz", "result", "skills", "recap", "viva", "project", "plan"];

let state = null;          // slim server state (plan + progress + profile + xp)
let negotiation = null;    // last /api/negotiate result
let pendingInput = null;   // goal/days/hours the user submitted
let chosenClass = "allrounder";   // default "Balanced"; scholar|builder|consistent|challenger override

/* ---------- XP / levels ---------- */

const RANKS = [[16, "PLATINUM"], [10, "GOLD"], [5, "SILVER"], [0, "BRONZE"]];

/* Confidence payoffs: [XP if right, XP if wrong]. MUST match PAYOFF in app.py —
   the server is authoritative; this only previews the number. See the comment
   there for why saying "guessing" honestly still pays. */
const PAYOFF = { safe: [14, 12], confident: [16, 8], allin: [18, 0] };

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

/* Total XP required to REACH level `lv` — the exact inverse of levelFromXp
   above, so the "XP to next level" meter can never disagree with the level. */
function xpForLevel(lv) {
  let total = 0, cost = 100;
  for (let l = 1; l < lv; l++) {
    total += cost;
    cost = 50 * (l + 2);
  }
  return total;
}

function rankFromLevel(lv) {
  for (const [min, name] of RANKS) if (lv >= min) return name;
  return "BRONZE";
}

/* "GOLD" -> "Gold" for display (quiet progress, not shouting) */
function rankLabel(lv) {
  const r = rankFromLevel(lv);
  return r.charAt(0) + r.slice(1).toLowerCase();
}

function questReward(entry) {
  if (entry && entry.kind === "project") return 300;   // milestones are worth ~4-6 lessons
  return entry && entry.is_checkpoint ? 150 : 100;
}

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

/* ---------- navigation + history ----------

   The app had NO History API use at all: one entry for the whole session, so
   Android's back gesture went straight past it and CLOSED the app — mid-quiz,
   mid-lesson, or with the Ask sheet open. Two layers get an entry, and only two:
   the view, and an open overlay (the Ask sheet). Lesson steps deliberately do
   NOT — nine steps would mean nine back-presses to escape one lesson, and the
   on-screen Back button already walks them.                                    */

let currentView = null;
let suppressHistory = false;   // set while WE are reacting to a popstate

function show(view) {
  views.forEach((v) => $("view-" + v).classList.toggle("hidden", v !== view));
  $("askFab").classList.toggle("hidden", view !== "lesson");   // floating Ask only in a lesson
  $("askSheet").classList.add("hidden");
  if (study && view !== "lesson") endStudy(false);   // leaving the lesson ends the session
  window.scrollTo(0, 0);

  if (!suppressHistory && view !== currentView) {
    // replace (not push) for the very first view, so there's a base entry to
    // land on rather than an empty one that exits the app
    if (currentView === null) history.replaceState({ v: view }, "");
    else history.pushState({ v: view }, "");
  }
  currentView = view;
}

function isAskOpen() { return !$("askSheet").classList.contains("hidden"); }
function hideAsk() { $("askSheet").classList.add("hidden"); }

/* Close the sheet THROUGH history, so the ✕ and the back gesture take the same
   path and can't leave a stale entry behind either way. */
function closeAsk() {
  if (history.state && history.state.overlay === "ask") history.back();
  else hideAsk();
}

window.addEventListener("popstate", (e) => {
  const st = e.state || {};
  // an open overlay always eats the first back press
  if (isAskOpen() && st.overlay !== "ask") {
    hideAsk();
    if (!st.v || st.v === currentView) return;
  }
  if (st.v && st.v !== currentView) {
    suppressHistory = true;
    try {
      if (st.v === "dashboard") renderDashboard();
      show(st.v);
    } finally {
      suppressHistory = false;
    }
  }
});

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
    // the custom header marks requests as coming from the app itself —
    // guarded endpoints (like reset) require it
    headers: { "Content-Type": "application/json", "X-Requested-With": "MentorOS" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // Session gone mid-session (cleared cookies, signed out elsewhere): bounce
    // to sign-in rather than leave them tapping a dead screen. The auth routes
    // are excluded — a wrong password is a legitimate 401 the form handles.
    if (res.status === 401 && !path.startsWith("/api/auth/")) renderAuth(true);
    const err = new Error(data.error || `Request failed (${res.status})`);
    err.status = res.status;   // callers branch on 401 -> show the sign-in screen
    throw err;
  }
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

/* ---------- accounts ---------- */

let authMode = "signup";

function renderAuth(anyAccounts) {
  // First run on a fresh install: offer signup. Once accounts exist, the common
  // case is someone coming back, so lead with login.
  authMode = anyAccounts ? "login" : "signup";
  paintAuth();
  show("auth");
}

function paintAuth() {
  const signup = authMode === "signup";
  $("authTitle").textContent = signup ? "Make your account" : "Welcome back";
  $("authSub").textContent = signup
    ? "Your plan, your progress, your streak — kept to you."
    : "Sign in to pick up where you left off.";
  $("btnAuth").textContent = signup ? "Create account" : "Sign in";
  $("authNote").style.display = signup ? "" : "none";
  $("btnAuthSwitch").textContent = signup ? "I already have an account" : "Make a new account";
  $("authPass").setAttribute("autocomplete", signup ? "new-password" : "current-password");
}

$("btnAuthSwitch").addEventListener("click", () => {
  authMode = authMode === "signup" ? "login" : "signup";
  paintAuth();
});

$("btnSignOut").addEventListener("click", async () => {
  try { await api("/api/auth/logout", { method: "POST" }); } catch {}
  state = null;
  lastShownXp = null;              // don't animate the next person's XP from yours
  currentView = null;              // reset the history base
  renderAuth(true);
});

$("authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("authName").value.trim();
  const password = $("authPass").value;
  if (!name || !password) return;
  const btn = $("btnAuth");
  btn.disabled = true;
  btn.textContent = authMode === "signup" ? "Creating…" : "Signing in…";
  try {
    const r = await api(`/api/auth/${authMode}`, {
      method: "POST",
      body: JSON.stringify({ name, password }),
    });
    $("authPass").value = "";
    if (r.claimed_existing_plan) toast("Found your existing plan — it's all here.", 5000);
    await boot();
  } catch (err) {
    toast(err.message, 5000);
    paintAuth();
  } finally {
    btn.disabled = false;
  }
});

async function boot() {
  try {
    state = await api("/api/state");
  } catch (e) {
    // 401 isn't an error worth shouting about — it just means "sign in first"
    if (e.status === 401) {
      let any = false;
      try { any = (await api("/api/auth/me")).any_accounts; } catch {}
      return renderAuth(any);
    }
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

/* ---- study material upload ---- */
let materialUploaded = false;

$("btnPasteToggle").addEventListener("click", () => {
  $("inMaterialText").classList.toggle("hidden");
  $("inMaterialText").focus();
});

$("inMaterialText").addEventListener("input", () => {
  $("scopeOptions").classList.toggle("hidden", !$("inMaterialText").value.trim());
});

$("inMaterialFile").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  $("materialStatus").textContent = "Reading your file…";
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch("/api/material", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");
    materialUploaded = true;
    $("materialStatus").textContent = `${data.name} — ${data.chars.toLocaleString()} characters ready`;
    $("scopeOptions").classList.remove("hidden");
  } catch (err) {
    $("materialStatus").textContent = err.message;
  }
});

/* upload pasted text (called on submit if present) */
async function uploadPastedMaterial() {
  const text = $("inMaterialText").value.trim();
  if (!text || materialUploaded) return;
  const res = await fetch("/api/material", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, name: "pasted notes" }),
  });
  const data = await res.json();
  if (res.ok) { materialUploaded = true; $("scopeOptions").classList.remove("hidden"); }
}

function chosenScope() {
  const hasMaterial = materialUploaded || $("inMaterialText").value.trim();
  if (!hasMaterial) return "";
  const r = document.querySelector('input[name="scope"]:checked');
  return r ? r.value : "essentials";
}

$("goalForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!chosenClass) {
    toast("Pick a teaching style first.");
    return;
  }
  pendingInput = {
    name: $("inName").value.trim(),
    goal: $("inGoal").value.trim().slice(0, 2000),
    days: parseInt($("inDays").value, 10),
    hours_per_day: parseFloat($("inHours").value),
    level_notes: $("inLevel").value.trim(),
    learner_class: chosenClass,
  };
  const btn = $("btnNegotiate");
  btn.disabled = true;
  loading(true, "Assessing your goal…");
  try {
    await uploadPastedMaterial();              // upload pasted notes if any
    pendingInput.material_scope = chosenScope();
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
        short_title: negotiation.short_title,
        // the negotiation rendered these once and dropped them — keep the
        // receipt for what's in and what got cut
        achievable_scope: negotiation.achievable_scope || [],
        dropped_scope: negotiation.dropped_scope || [],
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

let genAborted = false;

function setGenState(mode) {
  const err = mode === "error";
  $("genSpinner").classList.toggle("hidden", err);          // stop the spinner on error
  $("genTitle").textContent = err ? "Couldn't finish building your plan" : "Building your curriculum";
  $("genProgress").textContent = err ? "It didn't finish — try again, or start over." : "Planning every day of your plan…";
  $("genSub").style.display = err ? "none" : "";
  $("btnGenRetry").classList.toggle("hidden", !err);
}

async function generatePhases() {
  genAborted = false;
  setGenState("loading");
  try {
    // one request builds ALL phases in parallel — no slow per-phase loop
    await api("/api/plan/generate-all", { method: "POST" });
    if (genAborted) return;                                 // user hit Start over mid-build
    state = await api("/api/state");
    renderDashboard();
    show("dashboard");
    toast("Your plan is ready. Day 1 starts now.");
  } catch (err) {
    if (genAborted) return;
    setGenState("error");
  }
}
$("btnGenRetry").addEventListener("click", generatePhases);

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

  // A pasted syllabus is not its own title, and its first 40 chars are actively
  // misleading (they can be the subjects the student asked to SKIP). Blank
  // short_title means "unnamed" — say so plainly and let them name it.
  $("dashGoal").textContent = plan.short_title || "Your plan";
  $("dashGoal").title = plan.goal || "";
  $("dashDayTitle").textContent = allDone
    ? "Plan complete. Well done."
    : entry.kind === "revision" ? "Revision day"
    : entry.kind === "project" ? "Milestone project"
    : `Day ${entry.day} of ${plan.days}`;
  $("dashCount").textContent = `${doneReal}/${plan.days} days done`;

  // Topbar FIRST: LV/XP lives there, on every view. The dashboard used to print
  // a byte-identical copy 200px below it. Build the chip before animating it —
  // rewriting this innerHTML afterwards would wipe the count-up mid-flight.
  $("topbarStatus").innerHTML =
    `<span class="xp-chip">LV ${lv} · ${xp} XP</span>${renderStreakChip()}`;
  const topChip = document.querySelector("#topbarStatus .xp-chip");
  if (lastShownXp !== null && xp > lastShownXp && topChip) {
    animateXpChip(topChip, lastShownXp, xp, lv);
  }
  lastShownXp = xp;

  // career chip only appears once a prior season's XP exists (2nd+ plan) — on a
  // first plan lifetime_xp is 0, so it stays hidden (no duplicate of current XP)
  const career = state.lifetime_xp || 0;
  $("careerChip").innerHTML = career > 0 ? `Career <b>${career + xp} XP</b>` : "";
  // the streak's full story lives here, where there's width for it
  $("streakChip").textContent = streakDetail();
  $("progressFill").style.width = `${(doneReal / plan.days) * 100}%`;

  $("todayTitle").textContent = entry ? entry.title : "";
  $("todayObjectives").innerHTML = entry
    ? (entry.objectives || []).map((o) => `<li>${esc(o)}</li>`).join("")
    : "";
  const estTxt = entry && entry.est_minutes ? ` · ${fmtTime(entry.est_minutes)} today` : "";
  $("todayReward").textContent = entry ? `+${questReward(entry)} XP${estTxt}` : "";
  $("btnStartToday").textContent = entry && entry.kind === "revision" ? "Start revision" : "Start today";
  $("btnStartToday").onclick = () => openLesson(entry.day);

  const currentId = entry.day;
  const currentOrder = entry.order ?? entry.day;
  $("dayList").innerHTML = ord
    .map((d) => {
      const done = isDone(d.day);
      const isToday = d.day === currentId && !done;
      const locked = (d.order ?? d.day) > currentOrder && !done;
      const revision = d.kind === "revision";
      const project = d.kind === "project";
      const cls = ["day-row", done ? "done" : "", isToday ? "today-row" : "", locked ? "locked" : "", d.is_checkpoint && !project ? "checkpoint" : "", revision ? "revision" : "", project ? "project" : ""].join(" ");
      const stateTxt = done ? `+${questReward(d)} XP` : isToday ? "Today" : locked ? "Locked" : "";
      const label = revision ? "Revision" : project ? "Milestone" : `Day ${d.day}`;
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

  // reminders entry only where it can actually work (installed app) or is
  // already on — a desktop-browser tab doesn't need the button. Match any
  // installed display mode so the TWA on Android reliably shows it.
  const installed = ["standalone", "fullscreen", "minimal-ui"]
    .some((m) => window.matchMedia(`(display-mode: ${m})`).matches) || navigator.standalone === true;
  const pushRelevant = installed || (state.notifications || {}).enabled;
  $("btnReminders").style.display = pushRelevant ? "" : "none";

  $("dayList").querySelectorAll(".day-row").forEach((row) => {
    row.addEventListener("click", () => {
      if (row.classList.contains("locked")) {
        toast("Finish the current day first.");
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
  else if (doneReal === 0) thread = "Let's get Day 1 done.";
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

  // one thin line — the recap and skill map carry the detail
  const bits = [`This week: ${questsThisWeek} days`, `+${xpGain} XP`];
  if (newlyMastered.length) bits.push(`${newlyMastered.length} topic${newlyMastered.length > 1 ? "s" : ""} mastered`);
  $("weeklyBody").textContent = bits.join(" · ");
  card.classList.remove("hidden");
}

$("weeklyDismiss").addEventListener("click", async () => {
  $("weeklyCard").classList.add("hidden");
  try { await api("/api/weekly/seen", { method: "POST" }); state = await api("/api/state"); }
  catch {}
});

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

/* The topbar is 320px wide on a small phone next to the logo — it gets the
   headline only. Shields and the best run are detail, and detail belongs on the
   dashboard where there's room, not ellipsised into "3-day streak · 2 sh…". */
function renderStreakChip() {
  const s = state.streak || { count: 0, shields: 0, best: 0 };
  if (!s.count) return "";
  return `<span class="streak-chip"><b>${s.count}</b>-day streak</span>`;
}

/* The full picture, for the dashboard. `best` never resets — the current run
   can break, but what you actually achieved survives it, which is the whole
   reason a break is survivable instead of a reason to stop. */
function streakDetail() {
  const s = state.streak || { count: 0, shields: 0, best: 0 };
  const bits = [];
  if (s.count) bits.push(`${s.count}-day streak`);
  else if (s.best > 1) bits.push("Streak restarts today");
  if (s.best > Math.max(s.count, 1)) bits.push(`best ${s.best}`);
  if (s.shields) bits.push(`${s.shields} shield${s.shields > 1 ? "s" : ""}`);
  return bits.join(" · ");
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

  // Honest copy. This used to claim the plan had been "re-paced" (nothing was
  // ever re-paced) and hand out a return bonus for being away — which quietly
  // made skipping the most XP-efficient thing you could do.
  const d = r.days_away;
  $("wbBody").textContent =
    `It's been ${d} day${d === 1 ? "" : "s"}. Nothing's lost — your plan, your XP and every ` +
    `lesson are exactly where you left them. Pick up from the next day whenever you're ready.`;
  $("wbRewards").innerHTML = "";
  $("welcomeBack").classList.remove("hidden");
}

$("wbResume").addEventListener("click", () => {
  $("welcomeBack").classList.add("hidden");
  const entry = currentEntry();
  if (entry) openLesson(entry.day);
});

async function resetAll(msg) {
  if (!confirm(msg)) return;
  await api("/api/reset", { method: "POST", body: JSON.stringify({ confirm: true }) });
  state = await api("/api/state");
  show("onboarding");
}

$("btnReset").addEventListener("click", () =>
  resetAll("This permanently deletes your plan and progress. Continue?"));

$("btnAbandonGen").addEventListener("click", async () => {
  if (!confirm("This permanently deletes your plan and progress. Continue?")) return;
  genAborted = true;   // ignore any in-flight generation result
  try {
    await api("/api/reset", { method: "POST", body: JSON.stringify({ confirm: true }) });
    state = await api("/api/state");
  } catch {}
  show("onboarding");
});

/* ---------- study reminders (push notifications) ---------- */

function urlB64ToUint8(base64) {
  const pad = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + pad).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

$("btnReminders").addEventListener("click", () => {
  const n = state.notifications || {};
  $("remTime").value = n.daily_time || "19:00";
  $("remQuietStart").value = (n.quiet_hours || {}).start || "22:00";
  $("remQuietEnd").value = (n.quiet_hours || {}).end || "08:00";
  const on = n.enabled && (n.subscriptions_count || (n.subscriptions || []).length);
  $("remStatus").textContent = n.enabled ? "Reminders are on." : "";
  $("btnEnableReminders").textContent = n.enabled ? "Update reminders" : "Enable reminders";
  $("btnDisableReminders").classList.toggle("hidden", !n.enabled);
  $("remindersSheet").classList.remove("hidden");
});
$("remindersClose").addEventListener("click", () => $("remindersSheet").classList.add("hidden"));

$("btnEnableReminders").addEventListener("click", async () => {
  const btn = $("btnEnableReminders");
  btn.disabled = true;
  const prefs = {
    daily_time: $("remTime").value || "19:00",
    quiet_hours: { start: $("remQuietStart").value || "22:00", end: $("remQuietEnd").value || "08:00" },
    tz_offset: new Date().getTimezoneOffset(),   // so the chosen time is in the user's own timezone
  };
  try {
    if (!("serviceWorker" in navigator) || !("PushManager" in window))
      throw new Error("This browser can't do reminders. On Android Chrome, install the app first.");
    const perm = await Notification.requestPermission();
    if (perm !== "granted") throw new Error("Reminders need notification permission.");
    const reg = await navigator.serviceWorker.register("/sw.js");
    await navigator.serviceWorker.ready;
    const { key } = await api("/api/vapid-public-key");
    if (!key) throw new Error("Reminders aren't configured on the server yet.");
    let sub = await reg.pushManager.getSubscription();
    if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8(key) });
    await api("/api/push/subscribe", { method: "POST", body: JSON.stringify({ subscription: sub, ...prefs }) });
    await api("/api/push/settings", { method: "POST", body: JSON.stringify({ enabled: true, ...prefs }) });
    state = await api("/api/state");
    $("remStatus").textContent = "Reminders are on.";
    $("btnDisableReminders").classList.remove("hidden");
    toast("Study reminders enabled.");
  } catch (err) {
    $("remStatus").textContent = err.message;
  } finally {
    btn.disabled = false;
  }
});

$("btnDisableReminders").addEventListener("click", async () => {
  try {
    await api("/api/push/settings", { method: "POST", body: JSON.stringify({ enabled: false }) });
    state = await api("/api/state");
    $("remStatus").textContent = "Reminders are off.";
    $("btnDisableReminders").classList.add("hidden");
  } catch (err) { toast(err.message); }
});

/* ---------- plan detail ---------- */

function renderPlan() {
  const plan = state.plan || {};
  const ord = orderedCurriculum();
  const doneReal = ord.filter((d) => d.kind !== "revision" && isDone(d.day)).length;

  $("planTitle").textContent = plan.short_title || "Your plan";
  const started = plan.created_at
    ? new Date(plan.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })
    : "";
  $("planMeta").textContent = [
    started && `Started ${started}`,
    `${plan.days} days`,
    `${plan.hours_per_day}h a day`,
    `${doneReal}/${plan.days} done`,
  ].filter(Boolean).join(" · ");
  requestAnimationFrame(() => {
    $("planProgress").style.width = `${(doneReal / (plan.days || 1)) * 100}%`;
  });

  const msg = plan.mentor_message || "";
  $("planAssessCard").style.display = msg ? "" : "none";
  $("planAssess").textContent = stripMd(msg);

  // phase i spans days sum(days before it)+1 .. +its own — same arithmetic the
  // curriculum prompt uses to slice the plan
  let start = 1;
  $("planPhases").innerHTML = (plan.phases || []).map((p) => {
    const len = parseInt(p.days, 10) || 0;
    const end = start + len - 1;
    const doneHere = ord.filter((d) => d.kind !== "revision" && d.day >= start && d.day <= end && isDone(d.day)).length;
    const stateTxt = doneHere >= len ? "done" : doneHere > 0 ? `day ${doneHere} of ${len}` : `${len} days`;
    const cls = doneHere >= len ? "done" : doneHere > 0 ? "current" : "";
    const row = `<div class="plan-phase ${cls}">
        <span class="pp-dot"></span>
        <span class="pp-name">${esc(p.name || "")}</span>
        <span class="pp-state mono">${esc(stateTxt)}</span>
        ${p.focus ? `<span class="pp-focus">${esc(p.focus)}</span>` : ""}
      </div>`;
    start = end + 1;
    return row;
  }).join("");

  // the receipt: what the mentor agreed to cover, and what it told you it cut
  const inScope = plan.achievable_scope || [];
  const cut = plan.dropped_scope || [];
  $("planScope").innerHTML = (inScope.length || cut.length)
    ? `${inScope.length ? `<p class="label mono list-label">What this covers</p>
         <ul class="plain-list">${inScope.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>` : ""}
       ${cut.length ? `<p class="label mono list-label">What I left out</p>
         <ul class="plain-list muted-list">${cut.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>` : ""}`
    : "";

  const raw = plan.goal || "";
  $("planGoalSummary").textContent = `Show the full text you gave me (${raw.length.toLocaleString()} characters)`;
  $("planGoalRaw").textContent = raw;
}

/* Long goals are WELCOME — pasting a syllabus produces a better plan, not a
   worse one. The counter only appears near the cap, and it says so, because
   silently swallowing 500 characters of someone's syllabus is the worst
   possible failure here. */
$("inGoal").addEventListener("input", (e) => {
  const n = e.target.value.length;
  $("goalCount").textContent = n > 1200
    ? `${n.toLocaleString()} / 2000 — long goals are fine, I read all of it.` : "";
});
$("inGoal").addEventListener("paste", () => {
  setTimeout(() => {
    if ($("inGoal").value.length >= 2000) {
      toast("That's over 2000 characters, so I kept the first 2000 — check the end of the box.", 7000);
    }
  }, 0);
});

$("dashGoal").addEventListener("click", () => { renderPlan(); show("plan"); });
$("btnPlanBack").addEventListener("click", () => { renderDashboard(); show("dashboard"); });

/* Name it yourself. A pasted syllabus can't be auto-titled — its first words are
   often the subjects you asked to skip — and five of your words beat a model's
   guess, for free. */
$("btnRenamePlan").addEventListener("click", async () => {
  const current = (state.plan && state.plan.short_title) || "";
  const next = prompt("Name this plan (a few words):", current);
  if (next === null) return;
  const title = next.trim().slice(0, 40);
  if (!title) return;
  try {
    await api("/api/plan/title", { method: "POST", body: JSON.stringify({ short_title: title }) });
    state.plan.short_title = title;
    renderPlan();
    toast("Renamed.");
  } catch (err) { toast(err.message); }
});

/* ---------- skill map ---------- */

function renderSkillMapCard() {
  const dna = state.dna;
  // The mentor's note used to be its own blue italic line on the dashboard,
  // directly under the blue goal — two blue blocks sandwiching the title, in an
  // app whose CSS calls blue "THE one accent". It says the same thing as this
  // card's subtitle, which was a hardcoded placeholder. One home, no colour.
  const topics = dna ? Object.entries(dna.topics || {}) : [];
  const note = dna && dna.notes && dna.total_answered >= 3
    ? stripMd(dna.notes.split(".")[0]) + "."
    : "";
  $("skillMapSub").textContent = note || (topics.length
    ? `${topics.length} topic${topics.length > 1 ? "s" : ""} tracked · ${Math.round((dna.overall_mastery || 0) * 100)}% overall`
    : "Finish a checkpoint and your skill map appears here.");

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
    notes.innerHTML = `<p class="label mono">Mentor's notes</p><p class="notes-body">${fmt(dna.notes)}</p>`;
    notes.style.display = "";
  } else {
    notes.style.display = "none";
  }

  const topics = dna ? Object.entries(dna.topics || {}) : [];
  if (!topics.length) {
    $("skillsList").innerHTML = `<div class="card"><p class="sub">No skills tracked yet. Finish a checkpoint and your topics appear here.</p></div>`;
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

let recapDay = null;

async function openRecap(day, opts = {}) {
  recapDay = day;
  loading(true, "Loading your recap…");
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

  // "say it back" — pick a concept from today to self-explain (daily retrieval;
  // hidden on revision days, which are already recall)
  const concept = (entry.topics || [])[0] || entry.title || "today's idea";
  explainConcept = { day, concept };
  $("explainPrompt").textContent = `In your own words: what is “${concept}”, and why does it matter?`;
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

  // the segmented control always lands back on Recap when the view opens
  $("recapSeg").querySelectorAll(".seg-item").forEach((b) =>
    b.classList.toggle("active", b.dataset.mode === "recap"));
  show("recap");
}

$("btnRecapBack").addEventListener("click", () => { renderDashboard(); show("dashboard"); });

/* Recap <-> Full session. A completed day used to open its recap with no way to
   reach the lesson again — the only route back in was if you happened to have
   bookmarked a section. */
$("recapSeg").addEventListener("click", (e) => {
  const btn = e.target.closest(".seg-item");
  if (!btn || btn.classList.contains("active")) return;
  if (btn.dataset.mode === "lesson") openLesson(recapDay, { review: true });
});

/* The checkpoint was the only view with no exit. Answers are only POSTed at the
   end, so leaving really does discard the run — say so plainly, then let them go. */
$("btnQuizQuit").addEventListener("click", () => {
  const answered = (quizRun && quizRun.answers.length) || (warmupRun && warmupRun.results.length) || 0;
  if (answered && !confirm("Leave the checkpoint? Your answers so far won't be saved.")) return;
  quizRun = null; warmupRun = null;
  renderDashboard();
  show("dashboard");
});

/* explain-it-back — one light daily self-explanation in the recap */
let explainConcept = null;
$("btnExplain").addEventListener("click", async () => {
  const text = $("explainInput").value.trim();
  if (!text) { toast("Write your explanation first."); return; }
  if (!explainConcept) return;
  $("btnExplain").disabled = true;
  loadingCycle(["Checking your explanation…"]);
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
      `<p class="ef-good">${esc(r.whats_good)}</p>` +
      (r.whats_missing ? `<p class="ef-add">${esc(r.whats_missing)}</p>` : "");
    await rewardPill("Nice — you said it back", `+${r.xp_gained} XP`);
  } catch (err) {
    loading(false);
    $("btnExplain").disabled = false;
    toast(err.message, 6000);
  }
});

/* ---------- mock interview (viva) ---------- */

let vivaChapter = 0;
let vivaRun = null; // {questions, idx, answers}

async function startViva(chapter) {
  loadingCycle(["Setting up your interview…", "Preparing questions…"]);
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
  loadingCycle(["Reviewing your answers…", "Preparing your feedback…"]);
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
      <p class="vr-good">${esc(res.whats_good || "")}</p>
      ${res.tighten ? `<p class="vr-tighten">${esc(res.tighten)}</p>` : ""}
      ${res.model_answer ? `<details class="vr-model"><summary>Model answer</summary><p>${fmt(res.model_answer)}</p></details>` : ""}
    </div>`).join("");
  rewardPill("Mock interview complete", `+${r.xp_gained} XP`);
}

$("btnVivaDone").addEventListener("click", () => { vivaRun = null; renderDashboard(); show("dashboard"); });

/* floating ask button → bottom sheet */
$("askFab").addEventListener("click", () => {
  $("askSheet").classList.remove("hidden");
  // give the sheet its own history entry so the back gesture closes IT, not the app
  history.pushState({ v: currentView, overlay: "ask" }, "");
  $("askInput").focus();
});
$("askClose").addEventListener("click", () => closeAsk());
$("askSheet").addEventListener("click", (e) => { if (e.target === $("askSheet")) closeAsk(); });

/* ---------- morning warm-up (spaced review) ---------- */

let warmupRun = null;

async function loadWarmup() {
  $("warmupCard").classList.add("hidden");
  $("warmupDone").classList.add("hidden");
  let data;
  try { data = await api("/api/warmup"); } catch { return; }   // cheap check, no AI
  if (data.done) {
    $("warmupDone").textContent = "Warm-up done";
    $("warmupDone").classList.remove("hidden");
    return;
  }
  if (!data.available) return;  // nothing due yet
  $("warmupSub").textContent =
    `${data.count} quick recall${data.count > 1 ? "s" : ""} on earlier topics · +15 XP`;
  $("warmupCard").classList.remove("hidden");
  $("btnWarmup").onclick = startWarmup;
}

async function startWarmup() {
  loadingCycle(["Preparing your questions…"]);
  let data;
  try { data = await api("/api/warmup/start", { method: "POST" }); }
  catch (err) { loading(false); toast(err.message); return; }
  loading(false);
  if (!data.questions || !data.questions.length) { toast("No warm-up due right now."); return; }
  warmupRun = { questions: data.questions, idx: 0, results: [], picked: null };
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
      // send what was PICKED — the server grades it against what it served
      warmupRun.results.push({ ref: q.ref, chosen: warmupRun.picked });
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

/* ---------- study mode (a focus timer that rides ON TOP of the live lesson,
   never a blank takeover) ---------- */

let study = null;      // { total, left, elapsed, timer, goal }
let wakeLock = null;

$("btnFocus") && $("btnFocus").addEventListener("click", () => {
  const entry = currentEntry();
  $("focusQuestName").textContent = entry ? entry.title : "Today's lesson";
  $("focusIntent").value = "";
  $("focusSheet").classList.remove("hidden");
});
$("btnFocusCancel").addEventListener("click", () => $("focusSheet").classList.add("hidden"));
document.querySelectorAll(".dur-chip").forEach((c) => c.addEventListener("click", () => {
  document.querySelectorAll(".dur-chip").forEach((x) => x.classList.remove("selected"));
  c.classList.add("selected");
}));

/* best-effort: open the phone's Digital Wellbeing (where Focus mode lives).
   No stable cross-OEM intent exists, so the manual steps stay visible as the
   reliable path. Only meaningful inside the installed Android app. */
$("btnOpenFocusMode") && $("btnOpenFocusMode").addEventListener("click", () => {
  try {
    window.location.href =
      "intent://#Intent;action=android.intent.action.MAIN;package=com.google.android.apps.wellbeing;end";
  } catch {}
});

function startStudyTick() {
  study.timer = setInterval(() => {
    study.left--; study.elapsed++;
    tickStudy();
    if (study.left <= 0) reachedZero();
  }, 1000);
}

$("btnFocusStart").addEventListener("click", async () => {
  const mins = parseInt(document.querySelector(".dur-chip.selected").dataset.min, 10);
  const goal = $("focusIntent").value.trim();
  $("focusSheet").classList.add("hidden");

  // study mode studies the CURRENT lesson — make sure it's on screen first
  const entry = currentEntry();
  if (entry && openDay !== entry.day) await openLesson(entry.day);
  if ($("view-lesson").classList.contains("hidden")) return;  // no lesson to study — bail quietly

  study = { total: mins * 60, left: mins * 60, elapsed: 0, timer: null, goal };
  $("studyGoal").textContent = goal || "";
  $("studyDone").classList.add("hidden");
  $("studyBar").classList.remove("hidden");
  document.body.classList.add("study-mode");
  tickStudy();
  requestWakeLock();
  startStudyTick();
});

function tickStudy() {
  const left = Math.max(0, study.left);
  const m = Math.floor(left / 60), s = left % 60;
  $("studyTime").textContent = `${m}:${String(s).padStart(2, "0")}`;
  $("studyBarFill").style.width = `${100 * (1 - study.left / study.total)}%`;
}

function reachedZero() {
  clearInterval(study.timer); study.timer = null;
  $("studyDoneText").textContent = `${Math.round(study.total / 60)} minutes done — nice.`;
  $("studyDone").classList.remove("hidden");
}

$("btnStudyMore") && $("btnStudyMore").addEventListener("click", () => {
  if (!study) return;
  study.total = 10 * 60; study.left = 10 * 60;
  $("studyDone").classList.add("hidden");
  tickStudy();
  startStudyTick();
});
$("btnStudyWrap") && $("btnStudyWrap").addEventListener("click", () => endStudy(true));
$("btnStudyEnd") && $("btnStudyEnd").addEventListener("click", () => endStudy(false));
$("btnStudyToggle") && $("btnStudyToggle").addEventListener("click", () => {
  const hidden = document.body.classList.toggle("timer-hidden");
  $("btnStudyToggle").textContent = hidden ? "Show timer" : "Hide timer";
});

async function requestWakeLock() {
  try { wakeLock = await navigator.wakeLock.request("screen"); } catch {}
}
document.addEventListener("visibilitychange", () => {
  if (study && !document.hidden) requestWakeLock();   // re-acquire; no guilt for leaving
});

async function endStudy(completed) {
  if (!study) return;
  const elapsed = study.elapsed;
  if (study.timer) clearInterval(study.timer);
  study = null;
  document.body.classList.remove("study-mode", "timer-hidden");
  $("studyBar").classList.add("hidden");
  $("studyDone").classList.add("hidden");
  $("btnStudyToggle").textContent = "Hide timer";
  try { if (wakeLock) { wakeLock.release(); wakeLock = null; } } catch {}
  // rewards-only: a wrapped/finished session pays a bit more; a quick bail is
  // silent. The server decides the XP from real elapsed time and caps the day.
  if (completed || elapsed >= 300) {
    try {
      const r = await api("/api/focus/done", {
        method: "POST",
        body: JSON.stringify({ completed: !!completed, elapsed_seconds: elapsed }),
      });
      if (r.xp_gained > 0) {
        state.xp = r.xp;
        await rewardPill("Studied", `+${r.xp_gained} XP`);
      }
    } catch {}
  }
}

/* ---------- lesson ---------- */

let openDay = null;
let currentLesson = null;

let lessonReviewMode = false;   // reopened a finished day from its recap

async function openLesson(day, opts = {}) {
  openDay = day;
  lessonReviewMode = !!opts.review;
  const entry = (state.plan.curriculum || []).find((d) => d.day === day) || {};
  if (entry.kind === "project") return openProject(entry);
  const label = entry.kind === "revision" ? "Preparing your revision…"
    : entry.is_checkpoint ? "Preparing your checkpoint…"
    : "Preparing Day " + day + "…";
  loading(true, label);
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

/* Make every label fit the box it's in.

   The model writes these diagrams blind — it cannot measure rendered text, so it
   guesses a box width and long labels spill over their box and collide with the
   next one ("Control Unit (CU" printed across "Arithmetic Logic Unit"). The
   prompt now gives it the width arithmetic, but the prompt can't be trusted to
   be right every time. The BROWSER can measure, so it gets the final say.

   For each <text>: find the smallest <rect> that contains it, and if the text is
   wider, step the font down; if it still won't fit, squeeze it with textLength.
   Slightly condensed type is always better than two labels on top of each other. */
function fitSvgText(svg) {
  const rects = [...svg.querySelectorAll("rect")].map((r) => {
    try { return { el: r, box: r.getBBox() }; } catch { return null; }
  }).filter(Boolean);

  for (const t of svg.querySelectorAll("text")) {
    let len;
    try { len = t.getComputedTextLength(); } catch { continue; }
    if (!len) continue;
    let bx;
    try { bx = t.getBBox(); } catch { continue; }
    const cx = bx.x + bx.width / 2, cy = bx.y + bx.height / 2;

    // the tightest rect this label sits inside
    let host = null;
    for (const { box } of rects) {
      if (cx >= box.x && cx <= box.x + box.width && cy >= box.y && cy <= box.y + box.height) {
        if (!host || box.width < host.width) host = box;
      }
    }
    const limit = (host ? host.width : (svg.viewBox.baseVal.width || 600)) - 12;
    if (limit <= 0 || len <= limit) continue;

    // step the font down before resorting to squeezing
    let size = parseFloat(getComputedStyle(t).fontSize) || 14;
    while (size > 9 && len > limit) {
      size -= 1;
      t.setAttribute("font-size", size);
      try { len = t.getComputedTextLength(); } catch { break; }
    }
    if (len > limit) {
      t.setAttribute("textLength", Math.max(10, limit));
      t.setAttribute("lengthAdjust", "spacingAndGlyphs");
    }
  }
}

function renderDiagrams(root) {
  // SVG-only — the prompts forbid mermaid, so nothing else ever renders
  for (const h of (root || document).querySelectorAll(".diagram[data-code]")) {
    const clean = sanitizeSvg(h.dataset.code);
    if (clean) h.innerHTML = clean; else h.remove();
    h.removeAttribute("data-code");
    // must run AFTER insertion — text can only be measured once it's in the DOM
    const svg = h.querySelector && h.querySelector("svg");
    if (svg) { try { fitSvgText(svg); } catch {} }
  }
}

function visualHolder(visual) {
  if (!visual || !visual.code || visual.type !== "svg") return "";
  return `<div class="diagram" data-type="svg" data-code="${escAttr(visual.code)}"></div>`;
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
  const headKicker = lessonEntry.kind === "revision" ? "Revision"
    : `Day ${l.day}${l.is_checkpoint ? " · Checkpoint" : ""}`;
  $("lessonHead").innerHTML = `<p class="mono kicker">${headKicker}</p><h1>${esc(l.title)}</h1>`;

  // videos / watch links
  const direct = (l.videos || [])
    .map((v) => `<a class="resource-link" target="_blank" rel="noopener" href="${esc(v.url)}">▶ ${esc(v.title)} <span class="channel">· ${esc(v.channel)}${v.duration ? " · " + esc(v.duration) : ""}</span></a>`)
    .join("");
  const resources = direct || (l.resource_queries || [])
    .map((q) => `<a class="resource-link" target="_blank" rel="noopener"
        href="https://www.youtube.com/results?search_query=${encodeURIComponent(q)}">▶ ${esc(q)}</a>`)
    .join("");

  // at most 1 section carries an interactive widget — the quiz and warm-up
  // already test; a third mechanic per lesson is clutter
  const widgetSlots = {};
  let widgetCount = 0;
  (l.sections || []).forEach((s, i) => {
    if (widgetCount < 1 && validInteraction(s.interaction)) { widgetSlots[i] = s.interaction; widgetCount++; }
  });

  // build the step list: intro(+watch) → each section → practice bundle → summary
  lessonSteps = [];
  lessonSteps.push({ kind: "intro", html:
    `<p class="lesson-intro">${fmt(l.intro)}</p>` +
    (resources ? `<div class="card"><p class="label mono">Watch</p>${l.resources_note ? `<p class="resources-note">${fmt(l.resources_note)}</p>` : ""}${resources}</div>` : "")
  });
  // Long days are split into blocks with a real break between them. A 6-hour
  // sitting is attendance, not learning — the break IS the feature.
  let lastBlock = null;
  (l.sections || []).forEach((s, i) => {
    const block = s.block || null;
    if (block && lastBlock !== null && block !== lastBlock) {
      lessonSteps.push({ kind: "break", block, html: breakHtml(l, block) });
    }
    lastBlock = block;
    lessonSteps.push({ kind: "section", i, s, widget: widgetSlots[i], html: sectionHtml(l, s, i) });
  });
  lessonSteps.push({ kind: "practice", html:
    `<div class="card">
      <p class="label mono">Practice</p>
      <ul class="plain-list">${(l.practice || []).map((p) => `<li>${fmt(p)}</li>`).join("")}</ul>
      <p class="label mono" style="margin-top:14px">Homework</p>
      <ul class="plain-list">${(l.homework || []).map((h) => `<li>${fmt(h)}</li>`).join("")}</ul>
      <p class="label mono" style="margin-top:14px">Common mistakes</p>
      <ul class="plain-list">${(l.common_mistakes || []).map((m) => `<li>${fmt(m)}</li>`).join("")}</ul>
    </div>`
  });
  lessonSteps.push({ kind: "summary", html: `<div class="card"><p class="label mono">Summary</p><p>${fmt(l.summary)}</p></div>` });

  const done = state.progress[String(l.day)] && state.progress[String(l.day)].completed;
  $("completeReward").textContent = `+${l.is_checkpoint ? 150 : 100} XP`;
  $("askInput").value = "";
  // newest first, matching where new answers land (see the ask handler)
  $("explorations").innerHTML = [...(l.explorations || [])].reverse().map(explorationHtml).join("");

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
      ${visualHolder(s.visual)}
      <div class="explanation">${fmt(s.explanation)}</div>
      ${s.worked_example ? `<div class="worked"><p class="label">Worked example</p><div class="worked-body">${fmt(s.worked_example)}</div></div>` : ""}
      <ul class="keypoints">${(s.key_points || []).map((k) => `<li>${fmt(k)}</li>`).join("")}</ul>
      ${sectionVideoHtml(s)}
      <div class="tryit">${fmt(s.try_it)}</div>
      ${s.interaction && validInteraction(s.interaction) ? `<div class="interaction-slot" data-slot="${i}"></div>` : ""}
    </div>`;
}

/* This topic's video, ON this topic's step — after the explanation, so you meet
   it having already read the idea rather than as a wall of links on step 1.
   Falls back to a search link when the API is unavailable or out of quota, so a
   section that wanted a video always offers one. */
function sectionVideoHtml(s) {
  if (s.video && s.video.url) {
    const v = s.video;
    return `<a class="resource-link section-video" target="_blank" rel="noopener" href="${esc(v.url)}">
      ▶ ${esc(v.title)}<span class="channel"> · ${esc(v.channel)}${v.duration ? " · " + esc(v.duration) : ""}</span></a>`;
  }
  if (s.resource_query) {
    return `<a class="resource-link section-video" target="_blank" rel="noopener"
      href="https://www.youtube.com/results?search_query=${encodeURIComponent(s.resource_query)}">▶ ${esc(s.resource_query)}</a>`;
  }
  return "";
}

/* The break between blocks. Not decoration — spacing the work is what makes a
   long day stick, so it gets its own step rather than a line of small print. */
function breakHtml(l, nextBlock) {
  const total = Math.max(...(l.sections || []).map((s) => s.block || 1));
  return `<div class="card break-card">
      <p class="label mono">Break</p>
      <h3>Stop here for a bit</h3>
      <p class="break-body">You've finished block ${nextBlock - 1} of ${total}. Get up, look at something
      that isn't a screen for 10 minutes, then come back for block ${nextBlock}.
      The pause is doing real work — it's when what you just read settles.</p>
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
  $("btnBack").innerHTML = lessonReviewMode ? "&larr; Back to recap" : "&larr; Back to plan";

  // wire this step's dynamic bits
  if (step.kind === "section") {
    if (step.widget) {
      const slot = cont.querySelector(`.interaction-slot[data-slot="${step.i}"]`);
      if (slot) slot.appendChild(buildInteraction(step.widget));
    }
    const btn = cont.querySelector(".bookmark-btn");
    if (btn) btn.addEventListener("click", async () => {
      // Optimistic: flip it NOW, reconcile after. This used to await the POST and
      // THEN await a full /api/state refetch before turning gold — two serial
      // round-trips, each queued behind whatever else the server was doing, so a
      // star took 4-5 seconds to light up. Nothing here is destructive: the worst
      // case is a star that un-stars itself with a message.
      const want = !btn.classList.contains("on");
      const paint = (on) => {
        btn.classList.toggle("on", on);
        btn.querySelector("svg").setAttribute("fill", on ? "currentColor" : "none");
      };
      paint(want);
      try {
        const r = await api("/api/bookmark/toggle", { method: "POST",
          body: JSON.stringify({ day: l.day, sectionIndex: step.i, heading: btn.dataset.heading }) });
        paint(r.saved);                       // reconcile with the truth
        state.bookmarks = r.bookmarks || state.bookmarks;
      } catch (err) {
        paint(!want);                         // revert — the save didn't happen
        toast("Couldn't save that bookmark: " + err.message);
      }
    });
    renderDiagrams(cont);   // render on reveal (offscreen diagrams render blank)
  }

  // checkpoint offer lives on the last step
  if (last) renderBossCard(l, done); else $("bossCard").classList.add("hidden");

  window.scrollTo(0, 0);
}

$("btnStepNext").addEventListener("click", () => { if (stepIdx < lessonSteps.length - 1) { stepIdx++; renderStep(); } });
$("btnStepBack").addEventListener("click", () => { if (stepIdx > 0) { stepIdx--; renderStep(); } });

/* ---------- projects (build-it milestones) ---------- */

let currentProject = null;

async function openProject(entry) {
  currentProject = entry;
  loadingCycle(["Preparing your project…"]);
  let proj;
  try { proj = await api("/api/project/" + entry.project_id); }
  catch (err) { loading(false); toast(err.message, 6000); return; }
  loading(false);
  renderProject(entry, proj);
  show("project");
}

function renderProject(entry, proj) {
  $("projTitle").textContent = proj.title || entry.title;
  $("projBrief").innerHTML = fmt(proj.brief || "");
  $("projReqs").innerHTML = (proj.requirements || []).map((r) => `<li>${fmt(r)}</li>`).join("");
  $("projStarter").innerHTML = proj.starter
    ? `<p class="label mono" style="margin-top:12px">Start from</p><div class="worked-body">${fmt(proj.starter)}</div>` : "";

  const reviewed = proj.status === "reviewed" && proj.review;
  $("projSubmitCard").style.display = reviewed ? "none" : "";
  if (reviewed) renderProjectReview(proj.review); else $("projReviewCard").classList.add("hidden");
  $("projInput").value = "";
  $("btnProjSubmit").disabled = false;
}

function renderProjectReview(r) {
  $("projReviewCard").innerHTML = `
    <p class="label mono">Mentor review</p>
    ${r.opener ? `<p class="review-opener">${fmt(r.opener)}</p>` : ""}
    <p class="review-h good">What's strong</p>
    <ul class="plain-list">${(r.whats_good || []).map((x) => `<li>${fmt(x)}</li>`).join("")}</ul>
    <p class="review-h sharpen">One thing to sharpen</p>
    <ul class="plain-list">${(r.whats_missing || []).map((x) => `<li>${fmt(x)}</li>`).join("")}</ul>
    ${r.next_focus ? `<p class="review-h next">Do this next</p><p class="review-next">${fmt(r.next_focus)}</p>` : ""}`;
  $("projReviewCard").classList.remove("hidden");
}

$("btnProjectBack").addEventListener("click", () => { renderDashboard(); show("dashboard"); });

$("btnProjSubmit").addEventListener("click", async () => {
  const content = $("projInput").value.trim();
  if (!content) { toast("Add your work first."); return; }
  $("btnProjSubmit").disabled = true;
  loadingCycle(["Reviewing your work…"]);
  try {
    const r = await api("/api/project/" + currentProject.project_id + "/submit", {
      method: "POST", body: JSON.stringify({ content, type: "submit" }) });
    state = await api("/api/state");
    loading(false);
    $("projSubmitCard").style.display = "none";
    renderProjectReview(r.review);
    if (r.xp_gained) await rewardPill("Milestone built", `+${r.xp_gained} XP`);
  } catch (err) {
    loading(false); $("btnProjSubmit").disabled = false; toast(err.message, 6000);
  }
});

/* Checkpoint offer/result card at the bottom of a lesson */
function renderBossCard(l, done) {
  const card = $("bossCard");
  const result = (state.quizzes || {})[String(l.day)];
  if (!l.quiz || !l.quiz.length || (!done && !result)) {
    card.classList.add("hidden");
    return;
  }
  card.classList.remove("hidden");
  if (result) {
    $("bossSub").innerHTML = `<span class="cleared">Done</span> · ${result.score}/${result.total} correct · +${result.xp_earned} XP`;
    $("btnBoss").style.display = "none";
  } else {
    $("bossSub").textContent = `${l.quiz.length} questions on today's lesson — bonus XP only.`;
    $("btnBoss").style.display = "";
    $("btnBoss").onclick = () => startQuiz(l);
  }
}

function explorationHtml(x) {
  return `<div class="exploration">
    <p class="exp-q"><span class="mono">You asked</span> ${esc(x.q)}</p>
    <div class="exp-a">${fmt(x.a)}</div>
    ${visualHolder(x.visual)}
  </div>`;
}

$("btnAsk").addEventListener("click", async () => {
  const question = $("askInput").value.trim();
  if (!question) { toast("Type your question first."); return; }
  $("btnAsk").disabled = true;
  loadingCycle(["Working on your answer…"]);
  try {
    const item = await api("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question, day: openDay }),
    });
    // newest FIRST — it sits directly under the composer, so the answer you
    // just asked for is the one you're looking at, with no scrolling
    $("explorations").insertAdjacentHTML("afterbegin", explorationHtml(item));
    $("askInput").value = "";
    renderDiagrams($("explorations"));
    $("explorations").scrollTop = 0;
  } catch (err) {
    toast(err.message, 6000);
  } finally {
    $("btnAsk").disabled = false;
    loading(false);
  }
});

$("btnBack").addEventListener("click", () => {
  // arrived here from a finished day's recap → go back to it, not past it
  if (lessonReviewMode) return openRecap(openDay);
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
      // stay on the lesson — reveal the checkpoint right where the user is
      $("completeCard").style.display = "none";
      renderBossCard(lesson, true);
    }

    if (r.xp_gained > 0) {
      const oldLv = levelFromXp(r.xp - r.xp_gained);
      const newLv = levelFromXp(r.xp);
      await rewardPill("Day complete", `+${r.xp_gained} XP`);
      if (newLv > oldLv) {
        await rewardPill(`Level ${newLv} · ${rankLabel(newLv)}`, "");
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

/* ---------- checkpoint quiz engine ---------- */

let quizRun = null; // {lesson, idx, answers, combo, xp, picked}

function startQuiz(lesson) {
  quizRun = { lesson, idx: 0, answers: [], combo: 0, xp: 0, picked: null };
  // restore the kicker — a warm-up run replaces it (and removes #quizDay)
  document.querySelector("#view-quiz .kicker").innerHTML =
    'Checkpoint · Day <span id="quizDay"></span>';
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
      quizRun.hintUsed = true;   // costs no XP; it half-credits mastery so the topic comes back
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

  // mirrors PAYOFF in app.py — keep the two tables in step
  const gained = PAYOFF[confidence][correct ? 0 : 1];
  let cls, msg;
  if (correct) {
    quizRun.combo++;
    const sure = confidence === "allin";        // "Certain" and right
    cls = sure ? "quiz-feedback gold" : "quiz-feedback win";
    const combo = quizRun.combo >= 2 ? ` · ${quizRun.combo} in a row` : "";
    msg = `${sure ? "Sure and correct" : "Correct"} · +${gained} XP${combo}`;
  } else {
    quizRun.combo = 0;
    cls = "quiz-feedback lose";
    msg = confidence === "allin"
      ? `Not quite — and you were certain. Worth a second look.`
      : `Not quite · +${gained} XP for an honest call`;
  }
  quizRun.xp += gained;
  quizRun.answers.push({ i: idx, chosen: picked, confidence, hint_used: !!quizRun.hintUsed });
  quizRun.hintUsed = false;

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
  const btn = $("btnNextQ");
  btn.disabled = true;
  btn.textContent = "Scoring…";
  try {
    const r = await api(`/api/quiz/${finishedDay}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers: quizRun.answers }),
    });
    state = await api("/api/state");
    renderResult(finishedDay, r);
  } catch (err) {
    toast(err.message, 6000);
    btn.disabled = false;
    btn.textContent = "See results";
  } finally {
    quizRun = null;
  }
});

/* ---------- checkpoint result ---------- */

function renderResult(day, r) {
  $("resultDay").textContent = day;
  $("resultScore").textContent = `${r.score}/${r.total}`;
  $("resultLine").textContent = r.perfect
    ? "Clean run — every one."
    : r.score / r.total >= 0.6
      ? "Solid — a couple worth a second look."
      : "Worth going over. The ones you missed come back in a warm-up.";

  const b = r.breakdown || {};
  const rows = [["Questions", b.questions || 0]];
  if (b.perfect) rows.push(["Perfect run", b.perfect]);
  if (b.combo) rows.push([`Best run of ${b.best_combo}`, b.combo]);
  $("resultBreakdown").innerHTML = rows
    .map(([k, v]) => `<div class="ledger-row"><span>${esc(k)}</span><span class="tnum">+${v}</span></div>`)
    .join("");
  $("resultTotal").textContent = `+${r.xp_gained}`;

  // level meter — where this run left you
  const lv = levelFromXp(r.xp);
  const floor = xpForLevel(lv), ceil = xpForLevel(lv + 1);
  $("resultLvFrom").textContent = `LV ${lv}`;
  $("resultLvTo").textContent = `LV ${lv + 1}`;
  $("resultLvXp").textContent = `${r.xp - floor} / ${ceil - floor} XP`;
  requestAnimationFrame(() => {
    $("resultLvFill").style.width = `${((r.xp - floor) / (ceil - floor)) * 100}%`;
  });

  $("resultMastered").innerHTML = (r.mastered || []).length
    ? `<p class="label">Mastered</p>` +
      r.mastered.map((t) => `<span class="recap-chip gold-chip">${esc(t)}</span>`).join("")
    : "";

  const rev = $("resultRevision");
  if (r.revision) {
    rev.classList.remove("hidden");
    rev.innerHTML = `<p class="thin-text">Your mentor added a revision on ${esc(r.revision.topics.join(", "))}. ` +
                    `It's in your plan — we'll go over it together.</p>`;
  } else {
    rev.classList.add("hidden");
  }

  // The review: what you picked, what was right, and why. Wrong ones open by
  // default — those are the ones worth reading.
  $("resultReview").innerHTML = (r.review || []).map((q, i) => {
    const yours = q.chosen >= 0 && q.options[q.chosen] !== undefined ? q.options[q.chosen] : "—";
    return `<details class="rev-item${q.correct ? "" : " wrong"}"${q.correct ? "" : " open"}>
      <summary>
        <span class="rev-n mono">Q${i + 1}</span>
        <span class="rev-q">${fmt(q.q)}</span>
        <span class="rev-mark ${q.correct ? "ok" : "no"}">${q.correct ? "Correct" : "Missed"}</span>
      </summary>
      <div class="rev-body">
        ${q.correct ? "" : `<p class="rev-line"><span class="label">You said</span> ${fmt(yours)}</p>`}
        <p class="rev-line"><span class="label">Answer</span> ${fmt(q.options[q.answer] ?? "")}</p>
        ${q.why ? `<p class="rev-why">${fmt(q.why)}</p>` : ""}
        ${q.hint_used ? `<p class="rev-note">You used the hint here — it'll come back in a warm-up.</p>` : ""}
      </div>
    </details>`;
  }).join("");

  resultDay = day;
  show("result");
  // level-up is the one thing that still deserves a moment of its own, and it
  // lands ON this screen instead of blocking the road to it
  const oldLv = levelFromXp(r.xp - r.xp_gained);
  if (lv > oldLv) rewardPill(`Level ${lv} · ${rankLabel(lv)}`, "");
}

let resultDay = null;
$("btnResultBack").addEventListener("click", () => { renderDashboard(); show("dashboard"); });
$("btnResultRecap").addEventListener("click", () => {
  openRecap(resultDay, { chapterEnd: isChapterEnd(resultDay) });
});

/* register the service worker on load so the offline fallback + push work in
   the installed app (the reminders flow also registers it — register is
   idempotent, so this just makes it happen sooner for everyone) */
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

boot();
