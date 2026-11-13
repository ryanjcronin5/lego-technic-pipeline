"use strict";

const $ = (sel) => document.querySelector(sel);
const fmt = new Intl.NumberFormat();

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

async function api(path) {
  const res = await fetch(path);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

function showError(err) {
  const box = $("#error");
  box.textContent = err.message;
  box.hidden = false;
}

function img(url) {
  return url ? `<img src="${esc(url)}" alt="" loading="lazy" onerror="this.remove()">` : "";
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function renderKpis(s) {
  const items = [
    [fmt.format(s.technic_sets), "Technic sets"],
    [fmt.format(s.total_sets), "Sets in catalogue"],
    [fmt.format(s.distinct_technic_parts), "Distinct Technic parts"],
    [`${s.first_technic_year ?? "–"}–${s.latest_technic_year ?? "–"}`, "Years covered"],
  ];
  $("#kpis").innerHTML = items
    .map(([v, l]) => `<div class="kpi"><div class="value">${esc(v)}</div><div class="label">${esc(l)}</div></div>`)
    .join("");
  if (s.last_refreshed) {
    $("#refreshed").textContent = `Last refreshed ${new Date(s.last_refreshed).toLocaleString()}.`;
  }
}

function renderCharts(trends) {
  const text = cssVar("--muted");
  const grid = cssVar("--border");
  Chart.defaults.color = text;
  Chart.defaults.borderColor = grid;
  const years = trends.map((t) => t.year);

  new Chart($("#avgChart"), {
    type: "line",
    data: {
      labels: years,
      datasets: [
        { label: "Technic", data: trends.map((t) => t.technic_avg_parts), borderColor: cssVar("--accent"),
          backgroundColor: cssVar("--accent"), spanGaps: true, pointRadius: 0, tension: 0.25 },
        { label: "All LEGO", data: trends.map((t) => t.all_avg_parts), borderColor: cssVar("--accent-2"),
          backgroundColor: cssVar("--accent-2"), pointRadius: 0, tension: 0.25 },
      ],
    },
    options: { maintainAspectRatio: false, interaction: { mode: "index", intersect: false } },
  });

  new Chart($("#countChart"), {
    type: "bar",
    data: { labels: years, datasets: [{ label: "Technic sets", data: trends.map((t) => t.technic_sets),
      backgroundColor: cssVar("--accent") }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } } },
  });
}

function renderBiggest(rows) {
  $("#biggest tbody").innerHTML = rows.map((r) => `
    <tr><td>${img(r.img_url)}</td>
      <td>${esc(r.name)}<div class="muted">${esc(r.set_num)}</div></td>
      <td>${r.year}</td><td class="num">${fmt.format(r.num_parts)}</td></tr>`).join("");
}

function renderParts(rows) {
  $("#parts tbody").innerHTML = rows.map((r) => `
    <tr><td>${esc(r.name || r.part_num)}<div class="muted">${esc(r.part_num)} · ${esc(r.category || "")}</div></td>
      <td class="num">${fmt.format(r.total_quantity)}</td><td class="num">${fmt.format(r.set_count)}</td></tr>`).join("");
}

async function selectSet(setNum) {
  $("#results").innerHTML = "";
  const target = $("#selected");
  target.innerHTML = "<p class='hint'>Loading…</p>";
  try {
    const [set, similar] = await Promise.all([
      api(`/api/sets/${encodeURIComponent(setNum)}`),
      api(`/api/sets/${encodeURIComponent(setNum)}/similar?limit=10`),
    ]);
    target.innerHTML = `
      <div class="selected-head">${img(set.img_url)}
        <div><h2>${esc(set.name)}</h2>
        <div class="muted">${esc(set.set_num)} · ${set.year} · ${fmt.format(set.num_parts)} parts ·
          ${fmt.format(set.distinct_parts)} distinct part types</div></div></div>
      ${similar.length ? `<table><thead><tr><th></th><th>Similar set</th><th class="num">Shared types</th><th style="width:30%">Similarity</th></tr></thead><tbody>
        ${similar.map((s) => `<tr><td>${img(s.img_url)}</td>
          <td>${esc(s.name)}<div class="muted">${esc(s.set_num)} · ${s.year}</div></td>
          <td class="num">${fmt.format(s.shared_parts)}</td>
          <td><div class="bar" style="width:${Math.round(s.similarity * 100)}%"></div>
            <div class="muted">${Math.round(s.similarity * 100)}%</div></td></tr>`).join("")}
      </tbody></table>` : "<p class='hint'>No part inventory for this set.</p>"}`;
  } catch (err) {
    target.innerHTML = "";
    showError(err);
  }
}

let searchTimer;
function onSearch(event) {
  clearTimeout(searchTimer);
  const q = event.target.value.trim();
  if (q.length < 2) { $("#results").innerHTML = ""; return; }
  searchTimer = setTimeout(async () => {
    try {
      const rows = await api(`/api/sets/search?q=${encodeURIComponent(q)}&limit=8`);
      $("#results").innerHTML = rows.length
        ? rows.map((r) => `<li><button data-set="${esc(r.set_num)}">${esc(r.name)}
            <span class="muted">${esc(r.set_num)} · ${r.year}</span></button></li>`).join("")
        : "<li class='hint'>No matching Technic sets.</li>";
    } catch (err) { showError(err); }
  }, 200);
}

async function init() {
  $("#search").addEventListener("input", onSearch);
  $("#results").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-set]");
    if (btn) selectSet(btn.dataset.set);
  });
  try {
    const [summary, trends, biggest, parts] = await Promise.all([
      api("/api/summary"), api("/api/trends"), api("/api/sets/biggest?limit=10"), api("/api/parts/top?limit=10"),
    ]);
    renderKpis(summary);
    renderCharts(trends);
    renderBiggest(biggest);
    renderParts(parts);
  } catch (err) {
    showError(err);
  }
}

init();
