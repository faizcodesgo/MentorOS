/* MentorOS frontend — plain JS, no framework. */

const $ = (id) => document.getElementById(id);
const views = ["onboarding", "negotiate", "generating", "dashboard", "lesson"];

let state = null;          // slim server state (plan + progress + profile)
let negotiation = null;    // last /api/negotiate result
let pendingInput = null;   // goal/days/hours the user submitted

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

/* ---------- boot ---------- */

async function boot() {
  try {
    state = await api("/api/state");
  } catch (e) {
    toast("Can't reach the server: " + e.message);
    return;
  }
  if (state.plan && state.plan.curriculum.length > 0 &&
      state.plan.phases_generated >= state.plan.phases.length) {
    renderDashboard();
    show("dashboard");
  } else if (state.plan) {
    // plan exists but curriculum unfinished — resume generation
    show("generating");
    generatePhases();
  } else {
    show("onboarding");
  }
}

/* ---------- onboarding & negotiation ---------- */

$("goalForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  pendingInput = {
    goal: $("inGoal").value.trim(),
    days: parseInt($("inDays").value, 10),
    hours_per_day: parseFloat($("inHours").value),
    level_notes: $("inLevel").value.trim(),
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

function currentDay() {
  // first not-completed day in the curriculum
  const days = state.plan.curriculum.map((d) => d.day).sort((a, b) => a - b);
  for (const d of days) {
    if (!(state.progress[String(d)] && state.progress[String(d)].completed)) return d;
  }
  return days[days.length - 1]; // everything done
}

function renderDashboard() {
  const plan = state.plan;
  const doneCount = Object.values(state.progress).filter((p) => p.completed).length;
  const today = currentDay();

  $("dashGoal").textContent = plan.goal.toUpperCase();
  $("dashDayTitle").textContent = doneCount >= plan.curriculum.length
    ? "Plan complete. Well done."
    : `Day ${today} of ${plan.days}`;
  $("dashCount").textContent = `${doneCount}/${plan.curriculum.length} DAYS DONE`;
  $("progressFill").style.width = `${(doneCount / plan.curriculum.length) * 100}%`;
  $("topbarStatus").textContent = `DAY ${today}/${plan.days}`;

  const entry = plan.curriculum.find((d) => d.day === today);
  $("todayTitle").textContent = entry ? entry.title : "";
  $("todayObjectives").innerHTML = entry
    ? entry.objectives.map((o) => `<li>${esc(o)}</li>`).join("")
    : "";
  $("btnStartToday").onclick = () => openLesson(today);

  $("dayList").innerHTML = plan.curriculum
    .slice().sort((a, b) => a.day - b.day)
    .map((d) => {
      const done = state.progress[String(d.day)] && state.progress[String(d.day)].completed;
      const isToday = d.day === today && !done;
      const locked = d.day > today;
      const cls = ["day-row", done ? "done" : "", isToday ? "today-row" : "", locked ? "locked" : "", d.is_checkpoint ? "checkpoint" : ""].join(" ");
      const stateTxt = done ? "DONE" : isToday ? "TODAY" : "";
      return `<button class="${cls}" data-day="${d.day}">
        <span class="num mono">DAY ${d.day}</span>
        <span class="t">${esc(d.title)}</span>
        <span class="state mono">${stateTxt}</span>
      </button>`;
    })
    .join("");

  $("dayList").querySelectorAll(".day-row").forEach((row) => {
    row.addEventListener("click", () => {
      const day = parseInt(row.dataset.day, 10);
      if (day > currentDay()) {
        toast("One day at a time — finish today first.");
        return;
      }
      openLesson(day);
    });
  });
}

$("btnReset").addEventListener("click", async () => {
  if (!confirm("This wipes your whole plan and progress. Sure?")) return;
  await api("/api/reset", { method: "POST" });
  state = await api("/api/state");
  show("onboarding");
});

/* ---------- lesson ---------- */

let openDay = null;

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

function renderLesson(l) {
  const resources = (l.resource_queries || [])
    .map((q) => `<a class="resource-link" target="_blank" rel="noopener"
        href="https://www.youtube.com/results?search_query=${encodeURIComponent(q)}">▶ ${esc(q)}</a>`)
    .join("");

  const sections = (l.sections || []).map((s) => `
    <div class="card lesson-section">
      <h3>${esc(s.heading)}</h3>
      <div class="analogy">${fmt(s.analogy)}</div>
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
}

$("btnBack").addEventListener("click", () => {
  renderDashboard();
  show("dashboard");
});

$("btnComplete").addEventListener("click", async () => {
  try {
    await api(`/api/day/${openDay}/complete`, { method: "POST" });
    state = await api("/api/state");
    toast(`Day ${openDay} complete. See you tomorrow.`);
    renderDashboard();
    show("dashboard");
  } catch (err) {
    toast(err.message);
  }
});

boot();
