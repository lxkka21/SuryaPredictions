"use strict";

const $ = (sel, el) => (el || document).querySelector(sel);
const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
const fmt = (n, d = 1) => {
  const v = Number(n);
  return isNaN(v) ? "—" : v.toFixed(d);
};
const compName = (c) => ({
  PL: "Premier League", LALIGA: "La Liga", BL1: "Bundesliga", SA: "Serie A",
  FL1: "Ligue 1", UCL: "UEFA CL", UEL: "UEFA EL", UECL: "UEFA Conf.",
  FAC: "FA Cup", CDR: "Copa del Rey", DFB: "DFB-Pokal",
  CI: "Coppa Italia", CDF: "Coupe de France", CS: "Super Cup",
  LC: "Carabao Cup",
}[c] || c);

const kickoffValue = (f) => {
  if (f.kickoff_utc) {
    const value = Date.parse(f.kickoff_utc);
    if (!Number.isNaN(value)) return value;
  }
  return Date.parse(`${f.date || "9999-12-31"}T23:59:59`);
};

const formatMatchday = (date) => {
  if (!date) return "Date TBC";
  const value = new Date(`${date}T12:00:00`);
  return Number.isNaN(value.getTime()) ? date : value.toLocaleDateString(undefined, {
    weekday: "long", day: "numeric", month: "short", year: "numeric"
  });
};

const formatKickoff = (f) => {
  if (!f.kickoff_utc) return "TBC";
  const value = new Date(f.kickoff_utc);
  if (Number.isNaN(value.getTime())) return "TBC";
  return value.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

const LATE_MIN = 85;
const lateGoals = (m) => (m.goals || []).filter(g => g.min > LATE_MIN);
const isLate = (m) => lateGoals(m).length > 0;
const lateMattered = (m) => {
  const lg = lateGoals(m);
  if (!lg.length) return false;
  return lg.some(g => {
    const preH = m.hg - (g.side === "H" ? 1 : 0);
    const preA = m.ag - (g.side === "A" ? 1 : 0);
    return Math.sign(m.hg - m.ag) !== Math.sign(preH - preA);
  });
};

let S = { summary: {}, matches: [], teams: [], rankings: [], fixtures: [] };

async function load() {
  const [summary, matches, teams, rankings, fixtures] = await Promise.all([
    fetch("data/summary.json").then(r => r.json()).catch(() => ({})),
    fetch("data/matches.json").then(r => r.json()).catch(() => []),
    fetch("data/teams.json").then(r => r.json()).catch(() => []),
    fetch("data/rankings.json").then(r => r.json()).catch(() => []),
    fetch("data/fixtures.json").then(r => r.json()).catch(() => []),
  ]);
  S = { summary, matches, teams, rankings, fixtures };
  init();
}

function init() {
  $("#updated").textContent = S.summary.generated_at
    ? `Last updated: ${S.summary.generated_at} · ${S.summary.match_count} matches · ${S.summary.teams_seen} clubs`
    : "No data yet — add results to data/results.csv and run run_week.py";
  renderStats();
  renderLatest();
  renderUpcoming();
  renderWeekMoments();
  renderCompFilter();
  renderMatches();
  renderFixtures();
  renderLeagues();
  renderTeamSelect();
  renderTop();
  renderLateGoals();
}

/* ---------------- tabs ---------------- */
$$("#tabs button").forEach(btn => {
  btn.addEventListener("click", () => {
    $$("#tabs button").forEach(b => b.classList.remove("active"));
    $$(".tab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
  });
});

/* ---------------- overview ---------------- */
function renderStats() {
  const s = S.summary;
  const topTeam = S.teams.find(t => (t.form || []).length) || S.teams[0];
  const topMoment = S.rankings[0];
  const allComps = s.competitions || Object.keys(s.leagues || {});
  const stats = [
    ["Matches played", s.match_count ?? 0, ""],
    ["Clubs tracked", s.teams_seen ?? 0, ""],
    ["Competitions", allComps.length, ""],
    ["Top team", topTeam ? topTeam.team : "—", "gold"],
  ];
  $("#stats").innerHTML = stats.map(([l, n, c]) =>
    `<div class="stat"><div class="num ${c}">${n}</div><div class="lbl">${l}</div></div>`).join("");
}

function resultClass(r) { return "result-" + (r || "draw"); }

function renderLatest() {
  const el = $("#latest-results");
  const ms = [...S.matches].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 10);
  if (!ms.length) { el.innerHTML = `<div class="empty">No results yet.</div>`; return; }
  el.innerHTML = ms.map(m => {
    const hr = m.home_rec, ar = m.away_rec;
    return `<div class="match-line">
      <span class="match-date">${m.date} · ${compName(m.comp)}</span><br>
      <span class="team-link" data-team="${hr.team}">${hr.team}</span>
      <b> ${m.hg}${m.pen_h != null ? ` (${m.pen_h})` : ""}–${m.ag}${m.pen_a != null ? ` (${m.pen_a})` : ""} </b>
      <span class="team-link" data-team="${ar.team}">${ar.team}</span>
      <span class="muted"> · EO ${fmt(Math.max(Math.abs(hr.EO), Math.abs(ar.EO)))}</span>
    </div>`;
  }).join("");
  bindTeamLinks(el);
}

function renderUpcoming() {
  const el = $("#upcoming");
  const fx = [...S.fixtures].sort((a, b) => kickoffValue(a) - kickoffValue(b)).slice(0, 15);
  if (!fx.length) { el.innerHTML = `<div class="empty">No fixtures added yet (optional).</div>`; return; }
  el.innerHTML = fx.map(f => `<div class="match-line">
      <span class="match-date">${f.date} · ${formatKickoff(f)} · ${compName(f.comp)}${f.stage ? " · " + f.stage : ""}</span><br>
      <span class="team-link" data-team="${f.home}">${f.home}</span>
      <span class="fx-eo-badge" style="${eoColor(f.home_avg2 || 0)}">${fmt(f.home_avg2 || 0)}</span>
      <span class="muted">v</span>
      <span class="team-link" data-team="${f.away}">${f.away}</span>
      <span class="fx-eo-badge" style="${eoColor(f.away_avg2 || 0)}">${fmt(f.away_avg2 || 0)}</span>
    </div>`).join("");
  bindTeamLinks(el);
}

function renderWeekMoments() {
  const el = $("#week-moments");
  const top = S.rankings.slice(0, 8);
  if (!top.length) { el.innerHTML = `<div class="empty">Nothing yet.</div>`; return; }
  el.innerHTML = top.map(r => `<div class="match-line">
      <span class="match-date">${r.date} · ${compName(r.comp)}</span><br>
      <span class="team-link" data-team="${r.team}">${r.team}</span>
      <b class="${resultClass(r.result)}"> ${r.result} </b>
      ${r.gf}–${r.ga} vs <span class="team-link" data-team="${r.opp}">${r.opp}</span>
      <span class="muted"> · EO ${fmt(r.EO)} (EX ${fmt(r.EX)}, SI ${fmt(r.SI)}, CI ${fmt(r.CI, 1)})</span>
    </div>`).join("");
  bindTeamLinks(el);
}

/* ---------------- matches tab ---------------- */
function renderCompFilter() {
  const sel = $("#m-comp");
  const comps = [...new Set(S.matches.map(m => m.comp))].sort();
  sel.innerHTML = `<option value="">all competitions</option>` +
    comps.map(c => `<option value="${c}">${compName(c)}</option>`).join("");
}

let sortBy = "date";
function renderMatches() {
  const q = $("#m-search").value.toLowerCase();
  const comp = $("#m-comp").value;
  let ms = S.matches.filter(m =>
    (!comp || m.comp === comp) &&
    (!q || m.home.toLowerCase().includes(q) || m.away.toLowerCase().includes(q)));
  ms.sort((a, b) => sortBy === "date"
    ? b.date.localeCompare(a.date)
    : Math.max(Math.abs(b.home_rec.EO), Math.abs(b.away_rec.EO)) -
      Math.max(Math.abs(a.home_rec.EO), Math.abs(a.away_rec.EO)));
  const body = $("#matches-table tbody");
  if (!ms.length) { body.innerHTML = `<tr><td colspan="5" class="empty">No matches.</td></tr>`; return; }
  body.innerHTML = ms.map(m => {
    const mx = Math.max(Math.abs(m.home_rec.EO), Math.abs(m.away_rec.EO));
    const flag = lateMattered(m) ? `<span class="late-flag" title="Late goal after ${LATE_MIN}&#39; changed the result">LATE</span>` : "";
    return `<tr class="clickable" data-id="${m.id}">
      <td class="muted">${m.date}${flag}</td>
      <td><span class="comp">${compName(m.comp)}</span></td>
      <td><span class="team-link" data-team="${m.home}">${m.home}</span>
          <span class="muted"> v </span>
          <span class="team-link" data-team="${m.away}">${m.away}</span></td>
      <td><b>${m.hg}${m.pen_h != null ? ` (${m.pen_h})` : ""}–${m.ag}${m.pen_a != null ? ` (${m.pen_a})` : ""}</b></td>
      <td class="num">${fmt(mx)}</td>
    </tr>`;
  }).join("");
  bindTeamLinks(body);
  $$("#matches-table tbody tr.clickable").forEach(tr =>
    tr.addEventListener("click", () => showMatchDetail(tr.dataset.id)));
}

function showMatchDetail(id) {
  const m = S.matches.find(x => x.id === id);
  if (!m) return;
  const d = $("#match-detail");
  const rows = [m.home_rec, m.away_rec].map(r => `<tr>
    <td><b>${r.team}</b> <span class="muted">(${r.venue})</span></td>
    <td class="${resultClass(r.result)}">${r.result}</td>
    <td class="num">${fmt(r.EO)}</td>
    <td class="num">${fmt(r.EX)}</td>
    <td class="num">${fmt(r.SI)}</td>
    <td class="num">${fmt(r.CI, 1)}</td>
    <td class="num">${fmt(r.MOT, 1)}</td>
    <td class="num">${fmt(r.PJI)}</td>
    <td class="num">${fmt(r.IMP, 1)}</td>
    <td class="num">${fmt(r.HUM)}</td>
    <td class="num">${fmt(r.ES)}</td>
    <td class="num">${fmt(r.RP)}</td>
    <td class="num">${fmt(r.TEAM_SCORE)}</td>
  </tr>`).join("");
  d.innerHTML = `<h3>${m.home} ${m.hg}${m.pen_h != null ? ` (${m.pen_h})` : ""}–${m.ag}${m.pen_a != null ? ` (${m.pen_a})` : ""} ${m.away}
      <span class="muted">· ${m.date} · ${compName(m.comp)}${m.stage ? " · " + m.stage : ""}</span></h3>
    <div class="table-wrap"><table>
      <thead><tr><th>Team</th><th>Res</th><th>EO</th><th>EX</th><th>SI</th><th>CI</th>
        <th>MOT</th><th>PJI</th><th>IMP</th><th>HUM</th><th>ES</th><th>RP</th><th>TS</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  d.style.display = "block";
}

$("#m-search").addEventListener("input", renderMatches);
$("#m-comp").addEventListener("change", renderMatches);
$("#m-sort").addEventListener("click", () => {
  sortBy = sortBy === "date" ? "eo" : "date";
  $("#m-sort").textContent = sortBy === "date" ? "sort: |EO|" : "sort: date";
  renderMatches();
});

/* ---------------- fixtures tab ---------------- */
let fxCompFilter = "";
function renderFixtures() {
  const comps = [...new Set(S.fixtures.map(f => f.comp))].sort();
  const sel = $("#fx-comp");
  sel.innerHTML = `<option value="">all competitions</option>` +
    comps.map(c => `<option value="${c}">${compName(c)}</option>`).join("");
  sel.addEventListener("change", () => { fxCompFilter = sel.value; renderFixturesList(); });
  renderFixturesList();
}

function renderFixturesList() {
  const el = $("#fixtures-list");
  const filtered = fxCompFilter
    ? S.fixtures.filter(f => f.comp === fxCompFilter)
    : S.fixtures;
  if (!filtered.length) {
    el.innerHTML = `<div class="empty">No upcoming fixtures.</div>`;
    return;
  }
  // Group by local matchday, then sort every fixture by kickoff across all
  // competitions. This keeps the list useful when comparing betting windows.
  const grouped = {};
  filtered.forEach(f => {
    const day = f.date || "unknown";
    if (!grouped[day]) grouped[day] = [];
    grouped[day].push(f);
  });
  const days = Object.keys(grouped).sort((a, b) => a.localeCompare(b));
  for (const day of days) {
    grouped[day].sort((a, b) => kickoffValue(a) - kickoffValue(b) ||
      a.comp.localeCompare(b.comp) || a.home.localeCompare(b.home));
  }

  let html = '';
  for (const day of days) {
    const fx = grouped[day];
    html += `<div class="card">
      <h2 class="fixture-day-heading">${formatMatchday(day)} <span class="muted">${fx.length} match${fx.length === 1 ? "" : "es"}</span></h2>`;
    fx.forEach(f => {
      const hAvg = f.home_avg2 || 0;
      const aAvg = f.away_avg2 || 0;
      const hEs = f.home_es || 0;
      const aEs = f.away_es || 0;
      const hTs = f.home_ts || 0;
      const aTs = f.away_ts || 0;
      html += `<div class="fixture-line">
        <span class="fx-date"><strong>${formatKickoff(f)}</strong><small>${compName(f.comp)}</small></span>
        <span class="fx-team" data-team="${f.home}">
          <span class="fx-name">${f.home}</span>
          <span class="fx-eo-badge" style="${eoColor(hAvg)}" title="Avg of last 2 EOs: ${fmt(hAvg)}">${fmt(hAvg)}</span>
          <span class="fx-ts" title="TEAM_SCORE: ${fmt(hTs)}">TS ${fmt(hTs)}</span>
        </span>
        <span class="fx-vs">vs</span>
        <span class="fx-team" data-team="${f.away}">
          <span class="fx-name">${f.away}</span>
          <span class="fx-eo-badge" style="${eoColor(aAvg)}" title="Avg of last 2 EOs: ${fmt(aAvg)}">${fmt(aAvg)}</span>
          <span class="fx-ts" title="TEAM_SCORE: ${fmt(aTs)}">TS ${fmt(aTs)}</span>
        </span>
      </div>`;
    });
    html += `</div>`;
  }
  el.innerHTML = html;
  bindTeamLinks(el);
}

/* ---------------- leagues/competitions tab: week-by-week EO grid ---------------- */
let leagueFilter = "";
function renderLeagues() {
  // Show all competitions that have matches (leagues + cups + Europe)
  const leagueComps = Object.keys(S.summary.leagues || {});
  const cupComps = Object.keys(S.summary.cups || {});
  const comps = leagueComps.length || cupComps.length
    ? [...leagueComps, ...cupComps]
    : ["PL", "LALIGA", "BL1", "SA", "FL1"];
  if (!comps.includes(leagueFilter)) leagueFilter = comps[0];
  const chips = $("#league-chips");
  chips.innerHTML = comps.map(c =>
    `<button data-comp="${c}" class="${c === leagueFilter ? "active" : ""}">${compName(c)}</button>`).join("");
  $$("#league-chips button").forEach(b => b.addEventListener("click", () => {
    leagueFilter = b.dataset.comp;
    renderLeagues();
  }));
  renderEoGrid();
}

/* EO -> cell style.  Negative (bad) EO = red, positive = green.
   Lightness scales with magnitude: small values are light, large values dark.
   Foreground flips to dark when the background gets too light to read. */
function eoColor(v, mid = 0) {
  if (v == null || isNaN(v)) return "";
  const m = Math.min(1, Math.abs(v) / 10);
  const light = 87 - m * 62;
  if (v > mid) {
    const bg = `hsl(135,70%,${light}%)`;
    return `background:${bg};color:${light > 62 ? "#0e1116" : "#eef2f7"}`;
  }
  if (v < mid) {
    const bg = `hsl(0,70%,${light}%)`;
    return `background:${bg};color:${light > 62 ? "#0e1116" : "#eef2f7"}`;
  }
  return "background:rgba(139,150,165,0.14);color:#d7dee8";
}

function renderEoGrid() {
  const el = $("#league-grid");
  const isLeague = ["PL", "LALIGA", "BL1", "SA", "FL1"].includes(leagueFilter);
  const leagueTeams = S.teams.filter(t => t.league === compName(leagueFilter));
  if (!leagueTeams.length && isLeague) {
    el.innerHTML = `<div class="empty">No teams yet.</div>`;
    return;
  }

  // For cups, collect all teams that have played in this competition
  const cupTeams = isLeague ? [] : S.teams.filter(t =>
    (t.form || []).some(f => f.comp === leagueFilter));
  const teamsToShow = isLeague ? leagueTeams : cupTeams;

  if (!teamsToShow.length) {
    el.innerHTML = `<div class="empty">No matches yet for this competition.</div>`;
    return;
  }

  if (isLeague) {
    // League view: week-by-week grid (unchanged)
    const maxMW = leagueTeams.reduce((mx, t) => {
      (t.form || []).forEach(f => { if (f.comp === leagueFilter) mx = Math.max(mx, f.MW || 0); });
      return mx;
    }, 0);
    if (!maxMW) {
      el.innerHTML = `<div class="empty">No league matches played yet for this competition.</div>`;
      return;
    }

    const rows = leagueTeams.map(t => {
      const byMw = {};
      (t.form || []).forEach(f => { if (f.comp === leagueFilter) byMw[f.MW] = f; });
      let cells = "";
      for (let gw = 1; gw <= maxMW; gw++) {
        const f = byMw[gw];
        if (!f) { cells += `<td class="eo-cell none"></td>`; continue; }
        const tip = `${f.date} · ${t.team} ${f.score || ""} ${f.opp} · ${f.result} · EO ${fmt(f.EO)}`;
        cells += `<td class="eo-cell" style="${eoColor(f.EO)}"
          title="${tip}">${fmt(f.EO)}</td>`;
      }
      return `<tr>
        <td class="team-name" title="${t.team}">${t.team}</td>
        ${cells}
      </tr>`;
    }).join("");

    const gwHead = Array.from({ length: maxMW }, (_, i) =>
      `<th class="gw">GW${i + 1}</th>`).join("");

    el.innerHTML = `
      <div class="toolbar">
        <span class="muted">GW = each club's own league matchweek · EO colour-coded (green + / red −)</span>
      </div>
      <div class="table-wrap eo-wrap">
        <table class="eo-grid">
          <thead><tr><th class="team-name">Team</th>${gwHead}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div class="legend">
        <span class="lg" style="background:hsl(135,70%,25%);color:#eef2f7">+10</span>
        <span class="lg" style="background:hsl(135,70%,56%);color:#0e1116">+5</span>
        <span class="lg" style="background:rgba(139,150,165,0.14);color:#d7dee8">0</span>
        <span class="lg" style="background:hsl(0,70%,56%);color:#0e1116">−5</span>
        <span class="lg" style="background:hsl(0,70%,25%);color:#eef2f7">−10</span>
        <span class="muted">hover a cell for details · empty = no league match that week (cups excluded)</span>
      </div>`;
  } else {
    // Cup/European view: chronological list with stage labels
    const allMatches = [];
    teamsToShow.forEach(t => {
      (t.form || []).forEach(f => {
        if (f.comp === leagueFilter) allMatches.push({ ...f, team: t.team });
      });
    });
    // Deduplicate: each match appears twice (home + away team), keep once
    const seen = new Set();
    const unique = allMatches.filter(m => {
      const key = [m.date, m.team, m.opp].sort().join('_');
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    unique.sort((a, b) => a.date.localeCompare(b.date));

    if (!unique.length) {
      el.innerHTML = `<div class="empty">No matches played yet for this competition.</div>`;
      return;
    }

    const rows = unique.map(m => {
      const stageLabel = m.MW ? ` · ${m.MW}` : "";
      return `<tr>
        <td class="muted">${m.date}</td>
        <td><span class="team-link" data-team="${m.team}">${m.team}</span></td>
        <td class="${resultClass(m.result)}">${m.result}</td>
        <td>${m.score || ""}</td>
        <td><span class="team-link" data-team="${m.opp}">${m.opp}</span></td>
        <td class="num">${fmt(m.EO)}</td>
        <td class="muted">${compName(m.comp)}${stageLabel}</td>
      </tr>`;
    }).join("");

    el.innerHTML = `
      <div class="toolbar">
        <span class="muted">Cup / European matches · EO colour-coded (green + / red −)</span>
      </div>
      <div class="table-wrap">
        <table class="eo-grid">
          <thead><tr><th>Date</th><th>Team</th><th>Res</th><th>Score</th><th>Opp</th><th>EO</th><th>Stage</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div class="legend">
        <span class="lg" style="background:hsl(135,70%,25%);color:#eef2f7">+10</span>
        <span class="lg" style="background:hsl(135,70%,56%);color:#0e1116">+5</span>
        <span class="lg" style="background:rgba(139,150,165,0.14);color:#d7dee8">0</span>
        <span class="lg" style="background:hsl(0,70%,56%);color:#0e1116">−5</span>
        <span class="lg" style="background:hsl(0,70%,25%);color:#eef2f7">−10</span>
      </div>`;
  }
  bindTeamLinks(el);
}

function formDots(form) {
  if (!form || !form.length) return `<span class="muted">—</span>`;
  return `<span>${form.map(f => `<span class="${f.result}">${f.result[0].toUpperCase()}</span>`).join(" ")}</span>`;
}

/* ---------------- teams tab ---------------- */
function renderTeamSelect() {
  const sel = $("#team-select");
  const opts = S.teams.map(t => `<option value="${t.team}">${t.team} (${t.league})</option>`).join("");
  sel.innerHTML = opts || `<option value="">— no teams —</option>`;
  sel.addEventListener("change", () => renderTeamDetail(sel.value));
  if (S.teams.length) renderTeamDetail(sel.value);
}

function renderTeamDetail(name) {
  const t = S.teams.find(x => x.team === name);
  const detail = $("#team-title");
  const statsEl = $("#team-stats");
  const hist = $("#team-matches tbody");
  if (!t) {
    detail.textContent = "No team selected";
    $("#team-chart").innerHTML = `<div class="empty">No data yet.</div>`;
    statsEl.innerHTML = "";
    hist.innerHTML = "";
    return;
  }
  detail.innerHTML = `${t.team} · ${t.league} <span class="muted" style="font-size:12px;font-weight:400">(xG not available — PJI is Elo proxy)</span>`;
  statsEl.innerHTML = [
    ["ELO", fmt(t.elo, 0)], ["TEAM_SCORE", fmt(t.TEAM_SCORE)],
    ["ES", fmt(t.ES)], ["RP", fmt(t.RP)], ["Pts", t.P],
  ].map(([l, v]) => `<div class="stat"><div class="num">${v}</div><div class="lbl">${l}</div></div>`).join("");
  const form = t.form || [];
  hist.innerHTML = form.map(f => {
    const match = S.matches.find(m => m.date === f.date && m.comp === f.comp &&
      ((m.home === f.team && m.away === f.opp) || (m.away === f.team && m.home === f.opp)));
    const goals = match?.goals || [];
    const isHome = match?.home === f.team;
    const teamGoals = goals.filter(g => g.side === (isHome ? 'H' : 'A')).map(g => g.min).join(', ');
    const oppGoals = goals.filter(g => g.side !== (isHome ? 'H' : 'A')).map(g => g.min).join(', ');
    const goalsHtml = goals.length
      ? `<div class="goals-line">⚽ ${f.team}: ${teamGoals || '—'} | ${f.opp}: ${oppGoals || '—'}</div>`
      : '';
    return `<tr>
        <td class="muted">${f.date}</td>
        <td><span class="comp">${compName(f.comp)}</span></td>
        <td>${f.opp}</td>
        <td class="${resultClass(f.result)}">${f.result}</td>
        <td class="num score-col">${f.score}</td>
        <td class="num">${fmt(f.EO)}</td>
        <td class="num">${fmt(f.ES)}</td>
        <td class="num">${fmt(f.RP)}</td>
        <td class="num">${fmt(f.PJI)}</td>
      </tr><tr class="goal-row"><td colspan="9">${goalsHtml}</td></tr>`;
  }).join("") || `<tr><td colspan="9" class="empty">No matches.</td></tr>`;
  drawTeamChart(form);
}

function drawTeamChart(form) {
  const el = $("#team-chart");
  if (!form || form.length < 2) {
    el.innerHTML = `<div class="empty">Need at least 2 matches for a chart.</div>`;
    return;
  }
  const W = 900, H = 280, pad = { l: 34, r: 10, t: 16, b: 26 };
  const pts = form.map((f, i) => [i, f.EO]);
  const ts = form.map((f, i) => [i, f.ES]);
  const all = [...pts, ...ts];
  const xmin = 0, xmax = Math.max(1, form.length - 1);
  const ymin = Math.min(...all.map(p => p[1]), 0), ymax = Math.max(...all.map(p => p[1]), 1);
  const X = i => pad.l + (i - xmin) / (xmax - xmin) * (W - pad.l - pad.r);
  const Y = v => pad.t + (ymax - v) / (ymax - ymin) * (H - pad.t - pad.b);
  const line = d => d.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(" ");
  const grid = [0];
  for (let i = Math.ceil(ymin); i <= ymax; i++) grid.push(i);
  const xs = [...new Set(Array.from({ length: Math.min(10, form.length) }, (_, i) =>
    Math.round(i * (form.length - 1) / 9)))];
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}">
    ${grid.map(v => `<line x1="${pad.l}" x2="${W - pad.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#2a3441"/>
      <text x="${pad.l - 6}" y="${Y(v) + 4}" font-size="10" fill="#8b96a5" text-anchor="end">${v}</text>`).join("")}
    ${xs.map(i => `<text x="${X(i)}" y="${H - 8}" font-size="10" fill="#8b96a5" text-anchor="middle">${form[i].date.slice(5)}</text>`).join("")}
    <path d="${line(ts)}" fill="none" stroke="#d4a017" stroke-width="2"/>
    <path d="${line(pts)}" fill="none" stroke="#e63946" stroke-width="2"/>
    <circle cx="${X(pts[pts.length - 1][0])}" cy="${Y(pts[pts.length - 1][1])}" r="3.5" fill="#e63946"/>
    <circle cx="${X(ts[ts.length - 1][0])}" cy="${Y(ts[ts.length - 1][1])}" r="3.5" fill="#d4a017"/>
  </svg>
  <div class="muted" style="font-size:12px">— red: EO · gold: ES (momentum) —</div>`;
}

/* ---------------- top moments ---------------- */
function renderTop() {
  const body = $("#top-table tbody");
  if (!S.rankings.length) { body.innerHTML = `<tr><td colspan="13" class="empty">Nothing yet.</td></tr>`; return; }
  body.innerHTML = S.rankings.map((r, i) => `<tr>
    <td>${i + 1}</td>
    <td class="muted">${r.date}</td>
    <td><span class="team-link" data-team="${r.team}">${r.team}</span></td>
    <td><span class="team-link" data-team="${r.opp}">${r.opp}</span></td>
    <td><span class="comp">${compName(r.comp)}</span></td>
    <td class="${resultClass(r.result)}">${r.result}</td>
    <td class="num">${fmt(r.EO)}</td>
    <td class="num">${fmt(r.EX)}</td>
    <td class="num">${fmt(r.SI)}</td>
    <td class="num">${fmt(r.CI, 1)}</td>
    <td class="num">${fmt(r.PJI)}</td>
    <td class="num">${fmt(r.ES)}</td>
    <td class="num">${fmt(r.RP)}</td>
  </tr>`).join("");
  bindTeamLinks(body);
}

/* ---------------- late goals ---------------- */
function renderLateGoals() {
  const body = $("#late-table tbody");
  const late = S.matches.filter(lateMattered);
  renderLateSummary(late);
  if (!late.length) {
    body.innerHTML = `<tr><td colspan="9" class="empty">No games where a late goal (after the ${LATE_MIN}th minute) changed the result.</td></tr>`;
    return;
  }
  const rows = late.sort((a, b) => b.date.localeCompare(a.date)).map(m => {
    const lg = lateGoals(m);
    const mins = lg.map(g => g.min).join(", ");
    const team = lg.map(g => g.side === "H" ? m.home : m.away).join(", ");
    const mx = Math.max(Math.abs(m.home_rec.EO), Math.abs(m.away_rec.EO));
    const kind = Math.sign(m.hg - m.ag) === 0 ? "saved a point" : "won the game";
    return `<tr class="clickable" data-id="${m.id}">
      <td class="muted">${m.date}</td>
      <td><span class="comp">${compName(m.comp)}</span></td>
      <td><span class="team-link" data-team="${m.home}">${m.home}</span>
          <span class="muted"> v </span>
          <span class="team-link" data-team="${m.away}">${m.away}</span></td>
      <td><b>${m.hg}${m.pen_h != null ? ` (${m.pen_h})` : ""}–${m.ag}${m.pen_a != null ? ` (${m.pen_a})` : ""}</b></td>
      <td><span class="late-flag">LATE</span> ${lg.length}</td>
      <td class="num">${mins}</td>
      <td><span class="team-link" data-team="${team}">${team}</span></td>
      <td class="num">${fmt(mx)}</td>
      <td class="muted">${kind}</td>
    </tr>`;
  }).join("");
  body.innerHTML = rows;
  bindTeamLinks(body);
  $$("#late-table tbody tr.clickable").forEach(tr =>
    tr.addEventListener("click", () => showMatchDetail(tr.dataset.id)));
}

function renderLateSummary(late) {
  const el = $("#late-summary");
  const winners = late.filter(m => Math.sign(m.hg - m.ag) !== 0).length;
  const savers = late.length - winners;
  el.innerHTML = `<div class="stats small">
      <div class="stat"><div class="num">${late.length}</div><div class="lbl">Games decided by a late goal</div></div>
      <div class="stat"><div class="num">${winners}</div><div class="lbl">Won it late</div></div>
      <div class="stat"><div class="num">${savers}</div><div class="lbl">Saved a point late</div></div>
      <div class="stat"><div class="num">${late.reduce((n, m) => n + lateGoals(m).length, 0)}</div><div class="lbl">Result-changing late goals</div></div>
    </div>`;
}

/* ---------------- shared ---------------- */
function bindTeamLinks(root) {
  $$(".team-link", root).forEach(a => a.addEventListener("click", (e) => {
    e.stopPropagation();
    const name = a.dataset.team;
    const opt = $("#team-select");
    if ([...opt.options].some(o => o.value === name)) {
      opt.value = name;
      renderTeamDetail(name);
      selectTab("teams");
      window.scrollTo(0, 0);
    }
  }));
}

function selectTab(name) {
  $$("#tabs button").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  $$(".tab").forEach(t => t.classList.toggle("active", t.id === "tab-" + name));
}

load();
