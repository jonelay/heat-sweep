// heat-sweep dashboard: results list, one result detail (stat strip +
// loss-breakdown chart), and a synchronous run form. All chrome, theme,
// widgets, and providers come from view-sweep; this file only knows the
// heat-sweep REST shapes.

import { initTheme, loadPalette, bindThemeToggle } from "/view-sweep/js/theme.js";
import { createPlot, loadPlotSpec } from "/view-sweep/js/plot.js";
import { statStrip, badge, emptyHint, provenance, NULL_VALUE } from "/view-sweep/js/widgets.js";
import { mountPanel, mountStatusBar, bindConnectionBanner, toast } from "/view-sweep/js/chrome.js";
import { FetchProvider } from "/view-sweep/js/providers/fetch.js";
import { WebSocketProvider } from "/view-sweep/js/providers/websocket.js";

const $ = (id) => document.getElementById(id);
const fmt = (v, digits = 3) => (typeof v === "number" && Number.isFinite(v) ? v.toPrecision(digits) : NULL_VALUE);

// -- data ------------------------------------------------------------------------

const api = new FetchProvider();
const state = { results: [], selected: null, models: [], devices: [] };

async function refreshResults() {
  state.results = await api.fetch("/api/results");
  state.results.sort((a, b) => (b.timestamp ?? "").localeCompare(a.timestamp ?? ""));
  renderResults();
}

// -- table helper (view-sweep ships no table widget; plain DOM here) ------------

function table(host, columns, rows, {
  onSelect = null, selectedKey = null, key = null, empty = "no results yet — run a model from the sidebar",
} = {}) {
  const t = document.createElement("table");
  t.className = "hs-table";
  const thead = t.createTHead().insertRow();
  for (const c of columns) thead.insertCell().outerHTML = `<th>${c.label}</th>`;
  const body = t.createTBody();
  for (const r of rows) {
    const tr = body.insertRow();
    if (onSelect) {
      tr.classList.add("selectable");
      tr.addEventListener("click", () => onSelect(r));
    }
    if (key && selectedKey != null && key(r) === selectedKey) tr.classList.add("selected");
    for (const c of columns) {
      const td = tr.insertCell();
      const v = c.render ? c.render(r) : r[c.field];
      if (v instanceof Node) td.append(v); else td.textContent = v ?? NULL_VALUE;
      if (c.num) td.classList.add("num");
    }
  }
  host.replaceChildren(rows.length ? t : emptyHint(empty));
}

// -- panels ------------------------------------------------------------------------

const panes = $("panes");
const resultsPanel = mountPanel({ id: "results", title: "Results", collapsible: false });
const detailPanel = mountPanel({ id: "detail", title: "Result", collapsible: false });
panes.append(resultsPanel.card, detailPanel.card);

const strip = document.createElement("div");
const prov = document.createElement("div");
const chartHost = document.createElement("div");
const chartEl = document.createElement("div");
chartEl.className = "vs-plot";
const chartHint = emptyHint("select a result to see its loss breakdown");
const chartCaption = document.createElement("p");
chartCaption.className = "vs-caption";
const fallbackHost = document.createElement("div");
chartHost.append(chartEl, chartHint, chartCaption, fallbackHost);
detailPanel.body.append(strip, prov, chartHost);

function renderResults() {
  const columns = [
    { label: "id", render: (r) => r.config_id.slice(0, 8) },
    { label: "model", field: "model" },
    { label: "assembly", field: "assembly_name" },
    { label: "status", render: (r) => badge(r.status === "OK" ? "completed" : "failed", r.status) },
    { label: "p_total (W)", num: true, render: (r) => fmt(r.metrics?.p_total_W, 4) },
    { label: "when", render: (r) => (r.timestamp ?? "").slice(0, 19).replace("T", " ") },
  ];
  table(resultsPanel.body, columns, state.results, {
    onSelect: select, key: (r) => r.config_id, selectedKey: state.selected?.config_id,
  });
}

// Top-level loss keys (no position prefix) are the assembly totals.
const LOSS_KEYS = ["p_cond_W", "p_sw_on_W", "p_sw_off_W", "p_diode_cond_W", "p_rr_W"];

let plot = null;
function renderDetail() {
  const r = state.selected;
  if (!r) return;
  const m = r.metrics ?? {};
  statStrip(strip, [
    { label: "p_total", value: m.p_total_W != null ? `${fmt(m.p_total_W, 4)} W` : null },
    { label: "T_sink", value: m.T_sink_C != null ? `${fmt(m.T_sink_C, 4)} °C` : null },
    { label: "converged", value: m.converged != null ? String(m.converged) : null },
    { label: "status", value: r.status },
  ]);
  provenance(prov, { model: r.model, model_version: r.model_version, timestamp: r.timestamp, result_id: r.config_id });

  const { title, unit, x, y } = chartSeries(m);
  if (plot && globalThis.Plotly) {
    chartCaption.textContent = title;
    chartHint.textContent = "no chartable metrics in this result";
    plot.redraw(chartEl, x.length ? [{
      type: "bar", x, y, marker: { color: x.map((_, i) => plot.token(`series-${(i % 8) + 1}`)) },
    }] : [], { yaxis: plot.axisStyle(unit), xaxis: plot.axisStyle("") }, chartHint);
  } else {
    chartEl.style.display = "none";
    chartHint.style.display = "none";
    chartCaption.textContent = `${title} — Plotly not loaded (CDN unreachable), showing a table`;
    table(fallbackHost, [
      { label: "", render: (i) => x[i] },
      { label: unit, num: true, render: (i) => fmt(y[i], 4) },
    ], x.map((_, i) => i), { empty: "no chartable metrics in this result" });
  }
}

// What to chart for a result: the assembly loss breakdown when the model
// reports one (semiconductor_loss), else per-position Tj (thermal).
function chartSeries(m) {
  const losses = LOSS_KEYS.filter((k) => m[k] != null);
  if (losses.length) {
    return { title: "assembly loss breakdown", unit: "W",
             x: losses.map((k) => k.replace(/^p_|_W$/g, "")), y: losses.map((k) => m[k]) };
  }
  const tj = Object.keys(m).filter((k) => k.endsWith("_Tj_C"));
  return { title: "junction temperature by position", unit: "°C",
           x: tj.map((k) => k.slice(0, -5)), y: tj.map((k) => m[k]) };
}

async function select(r) {
  state.selected = r;
  renderResults();
  renderDetail();
  // the list is slim; the full record carries model_version for provenance
  try {
    const full = await api.fetch(`/api/results/${r.config_id}`);
    if (state.selected === r) { state.selected = { ...r, model_version: full.model_version }; renderDetail(); }
  } catch { /* stale id: list refresh will drop it */ }
}

// -- run form ----------------------------------------------------------------------

let ws = null;
// Jobs whose outcome the UI has already shown. The POST response is the
// source of truth (the run is synchronous); the WS job_complete frame is
// an optimisation that may arrive first, never, or after a reconnect, so
// both paths consult this set to avoid selecting/toasting twice.
const seenJobs = new Set();

async function showJobResult(jobId, resultId, msg) {
  if (seenJobs.has(jobId)) return;
  seenJobs.add(jobId);
  await refreshResults();
  const hit = state.results.find((r) => r.config_id === resultId);
  if (hit) select(hit);
  toast(msg);
}

$("run-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = new FormData(ev.target);
  const num = (k) => Number(f.get(k));
  const jobId = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  // subscribeJobs returns false while the socket is connecting/reconnecting;
  // the POST path below covers that case, so the result is not needed.
  ws?.subscribeJobs([jobId]);
  $("run-btn").disabled = true;
  try {
    const job = await api.post("/api/jobs", {
      job_id: jobId, device: f.get("device"), model: f.get("model"), topology: f.get("topology"),
      Rth_cs: num("Rth_cs"), T_amb_C: num("T_amb_C"),
      op: { f_sw_Hz: num("f_sw_Hz"), V_dc: num("V_dc"), I_phase_rms: num("I_phase_rms"), f_out_Hz: num("f_out_Hz"),
            pf: num("pf"), m_index: num("m_index"), T_amb_C: num("T_amb_C") },
    });
    await showJobResult(jobId, job.result_id,
      job.status === "completed" ? `job ${jobId} complete` : `run failed: ${job.error}`);
  } catch (e) {
    toast(`run rejected: ${e.message}`);
  } finally {
    $("run-btn").disabled = false;
  }
});

function fill(selectEl, items, { value = (x) => x, label = (x) => x } = {}) {
  selectEl.replaceChildren();
  for (const it of items) {
    const o = document.createElement("option");
    o.value = value(it);
    o.textContent = label(it);
    selectEl.append(o);
  }
}

// -- boot --------------------------------------------------------------------------

async function main() {
  const palette = await loadPalette("/view-sweep/spec/palettes/engineering.json");
  const theme = initTheme({ palette, storageKey: "hs-theme" });
  bindThemeToggle($("theme-toggle"), theme);
  const statusBar = mountStatusBar($("statusbar"));
  bindConnectionBanner($("conn-banner"));

  if (globalThis.Plotly) {
    const spec = await loadPlotSpec("/view-sweep/spec/plot.json");
    plot = createPlot({ spec, theme });
    document.addEventListener("vs:theme-change", renderDetail);
  }

  [state.models, state.devices] = await Promise.all([api.fetch("/api/models"), api.fetch("/api/assemblies")]);
  fill($("f-model"), state.models.filter((m) => m.source === "computed"), { value: (m) => m.name, label: (m) => `${m.name} v${m.version}` });
  fill($("f-device"), state.devices, { value: (d) => d.name, label: (d) => `${d.name} (${d.device.device_type})` });
  fill($("f-topology"), state.devices[0]?.topologies ?? ["half_bridge"]);
  $("f-topology").value = "half_bridge";
  table($("model-list"), [
    { label: "model", field: "name" },
    { label: "cost", field: "cost" },
    { label: "v", field: "version", num: true },
  ], state.models, { empty: "no models registered" });

  ws = new WebSocketProvider().connect();
  ws.subscribe("job_complete", (msg) => {
    statusBar.stampResult();
    showJobResult(msg.job_id, msg.result_ids[0], `job ${msg.job_id} complete`);
  });
  ws.subscribe("job_failed", (msg) => showJobResult(msg.job_id, null, `job ${msg.job_id} failed: ${msg.error}`));
  ws.onReconnect(refreshResults);

  await refreshResults();
  if (state.results.length) select(state.results[0]);
}

main().catch((e) => {
  console.error(e);
  toast(`dashboard failed to start: ${e.message}`, { duration: 8000 });
});
