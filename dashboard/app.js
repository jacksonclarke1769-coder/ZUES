// Profile A dashboard — pulls from the live store API; auto-refreshes every 15s.
const $ = (id) => document.getElementById(id);
const fmt = (n, d = 0) => (n == null ? "—" : Number(n).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }));
const money = (n) => (n == null ? "—" : (n < 0 ? "-$" : "$") + Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 0 }));
const cls = (n) => (n > 0 ? "pos" : n < 0 ? "neg" : "");
let charts = {};

async function j(u) { const r = await fetch(u); return r.json(); }

function kpi(label, val, sub, good) {
  return `<div class="kpi"><div class="k-lab">${label}</div><div class="k-val ${good || ""}">${val}</div><div class="k-sub">${sub || ""}</div></div>`;
}

async function render() {
  const o = await j("/api/overview");
  $("stratName").textContent = o.strategy_name;
  $("cfg").textContent = o.config;
  $("dnote").textContent = o.data_note;
  const sb = $("statusBadge"); sb.textContent = o.status;
  sb.className = "badge " + (o.status.includes("VALIDATED") ? "ok" : "warn");

  // live bar
  const lv = o.live || {};
  $("lvMode").textContent = lv.paper ? "PAPER" : "LIVE $";
  $("lvAcct").textContent = lv.account || "—";
  $("lvBal").textContent = money(lv.balance);
  const dp = $("lvDay"); dp.textContent = money(lv.today_pnl); dp.className = cls(lv.today_pnl);
  $("lvPos").textContent = lv.open_position ? lv.open_position : "flat";
  $("lvSig").textContent = lv.last_signal || "—";
  $("lvLive").textContent = lv.connected ? "online" : "offline";
  $("liveInd").classList.toggle("on", !!lv.connected);

  // KPIs
  const s = o.summary || {}, v = o.validation || {}, e = o.edge || {};
  $("kpis").innerHTML = [
    kpi("Profit Factor", fmt(s.pf, 2), `${s.trades} trades`, s.pf >= 1.2 ? "pos" : ""),
    kpi("Win Rate", fmt(s.wr, 1) + "%", "Exit #3 (50%@1R+2R)", ""),
    kpi("Expectancy", "+" + fmt(s.exp_r, 3) + "R", `avg win +${fmt(s.avg_win, 2)}R`, "pos"),
    kpi("Total", "+" + fmt(s.total_r, 0) + "R", "2019–2026", "pos"),
    kpi("Max Drawdown", fmt(s.maxdd_r, 1) + "R", `streak ${s.streak}`, ""),
    kpi("CME-validated PF", fmt(v.cme_pf, 2), `real NQ=F ${fmt(v.real_futures_pf, 2)}`, v.cme_pf >= 1.2 ? "pos" : ""),
    kpi("Funded score", fmt(s.funded, 0) + "/100", "MyFundedFutures-ready", ""),
    kpi("Frequency", "~12/mo", "~1 / 1.8 days", ""),
  ].join("");
  $("valNote").innerHTML = v.verdict || "";

  // edge box
  $("edgeBox").innerHTML = `<b>Source:</b> ${e.source || ""}<br><br><b>Cadence:</b> ${e.freq || ""}<br>
    <b>Avg stop:</b> ${fmt(e.stop_mean_pt)}pt lifetime · ${fmt(e.stop_recent_pt)}pt recent (price-scaled).`;

  // funded sizing
  const fu = o.funded || {};
  $("fundProg").textContent = "— " + (fu.program || "");
  $("sizing").innerHTML = (fu.sizing || []).map(r =>
    `<tr class="${(r.role || '').includes('FUNDED') ? 'hi' : ''}"><td><b>${r.size}</b></td><td>${r.risk}</td><td>${r.role}</td><td>${r.pass90}</td><td class="mut">${r.note}</td></tr>`).join("");
  $("fundMeta").innerHTML = "<b>Strategy:</b> " + (fu.meta || "");
  $("fundBlow").innerHTML = "<b>Survival:</b> " + (fu.blow_rate || "");

  // risk
  const r = o.risk || {};
  $("riskTbl").innerHTML = [
    ["P(drawdown ≥10R)", r.dd10], ["P(drawdown ≥15R)", r.dd15], ["P(drawdown ≥20R)", r.dd20],
    ["95th-pct losing streak", r.streak95], ["99th-pct max drawdown", (r.cap99_r || "") + "R"],
  ].map(x => `<tr><td>${x[0]}</td><td style="text-align:right"><b>${x[1]}</b></td></tr>`).join("");
  $("riskNote").textContent = r.note || "";

  await drawEquity(); await drawMonthly(); drawYears(o.walkforward || []);
  drawSizingMatrix(o.sizing_matrix || {}, o.sizing_matrix_notes || {}, o.sizing_matrix_note || "");
  await drawTrades();
  await drawPaper();
}

let _sizingSel = "50K", _sizingPeriod = "2019+";
function drawSizingMatrix(periods, notes, note) {
  const card = $("sizingCard");
  const pers = periods ? Object.keys(periods) : [];
  if (!pers.length) { card.style.display = "none"; return; }
  card.style.display = "";
  if (!periods[_sizingPeriod]) _sizingPeriod = pers[0];
  const matrix = periods[_sizingPeriod] || {};
  const accts = Object.keys(matrix);
  if (!matrix[_sizingSel]) _sizingSel = accts[0];
  const plabel = { "2019+": "Full 2019+", "12mo": "Last 12 months" };
  $("sizingHdr").textContent = "— " + (note || "") + " · " + ((notes && notes[_sizingPeriod]) || _sizingPeriod);
  $("sizingPeriod").innerHTML = pers.map(p => `<button class="szTab ${p === _sizingPeriod ? 'on' : ''}" data-per="${p}">${plabel[p] || p}</button>`).join("");
  document.querySelectorAll("#sizingPeriod .szTab").forEach(b => b.onclick = () => { _sizingPeriod = b.dataset.per; drawSizingMatrix(periods, notes, note); });
  $("sizingTabs").innerHTML = accts.map(a => `<button class="szTab ${a === _sizingSel ? 'on' : ''}" data-acc="${a}">${a}</button>`).join("");
  document.querySelectorAll("#sizingTabs .szTab").forEach(b => b.onclick = () => { _sizingSel = b.dataset.acc; drawSizingMatrix(periods, notes, note); });
  const rows = matrix[_sizingSel] || [];
  const net = rows.map(r => r.net), passed = rows.map(r => r.passed);
  mk("sizingChart", "bar", {
    labels: rows.map(r => r.size), datasets: [
      { label: "net $ (" + plabel[_sizingPeriod] + ")", data: net, yAxisID: "y", order: 2, backgroundColor: net.map(v => v >= 0 ? "#3ddc97" : "#ff5c7c") },
      { type: "line", label: "accounts passed", data: passed, yAxisID: "y1", order: 1, borderColor: "#e8b84b", backgroundColor: "#e8b84b", pointRadius: 4, borderWidth: 2, tension: .2 },
    ]
  }, {
    plugins: { legend: { display: true, labels: { color: "#9aa3b5", boxWidth: 12 } } },
    scales: {
      x: { ticks: { color: "#7c8499" }, grid: { display: false } },
      y: { position: "left", ticks: { callback: v => "$" + (v / 1000).toFixed(0) + "k", color: "#7c8499" }, grid: { color: "#1b2030" } },
      y1: { position: "right", beginAtZero: true, ticks: { color: "#e8b84b", precision: 0 }, grid: { display: false }, title: { display: true, text: "accts passed", color: "#e8b84b" } },
    }
  });
  $("sizingTbl").innerHTML = rows.map(r => `<tr>
    <td><b>${r.size}</b></td>
    <td style="text-align:right">${r.pass_pct == null ? '—' : r.pass_pct + '%'}</td>
    <td style="text-align:right">${r.passed}</td>
    <td style="text-align:right" class="${r.failed > 0 ? 'neg' : 'mut'}">${r.failed}</td>
    <td style="text-align:right">${r.avg_pass_days == null ? '—' : '~' + r.avg_pass_days + 'd'}</td>
    <td style="text-align:right">${money(r.per_account)}</td>
    <td style="text-align:right" class="${r.funded_blows > 0 ? 'neg' : 'pos'}">${r.funded_blows}</td>
    <td style="text-align:right">${money(r.net_yr)}</td></tr>`).join("");
  const sust = rows.filter(r => r.failed <= 1 && r.passed > 0).sort((a, b) => b.net_yr - a.net_yr)[0];
  $("sizingNote").innerHTML = `<b>${_sizingSel}</b> · ${plabel[_sizingPeriod]} · EOD DD $${(rows[0].dd || 0).toLocaleString()} · eval ~$${rows[0].fee}. ` +
    `Bars = total net; line = accounts passed; table "net/yr" = annualised income. ` +
    (sust ? `<b>Sustainable: ${sust.size}</b> (${sust.pass_pct}% pass · ~${sust.avg_pass_days}d to pass · ${money(sust.net_yr)}/yr · only ${sust.failed} failed evals). ` : "") +
    `<span class="mut">Bigger than that = eval-fee churn. 2019+ is conservative; 12mo is the recent (stronger) regime.</span>`;
}

async function drawPaper() {
  let p; try { p = await j("/api/paper"); } catch { return; }
  const m = (p && p.panel) || {};
  const card = $("paperCard");
  if (!m || !m.total_paper_signals) { card.style.display = "none"; return; }
  card.style.display = "";
  $("paperKpis").innerHTML = [
    kpi("Paper signals", fmt(m.total_paper_signals), `${fmt(m.filled_paper_trades)} filled · ${fmt(m.missed_paper_trades)} missed`, ""),
    kpi("TP1 hit", fmt(m.tp1_hit_pct, 1) + "%", "of filled", ""),
    kpi("TP2 hit", fmt(m.tp2_hit_pct, 1) + "%", "full target", ""),
    kpi("Stop hit", fmt(m.stop_hit_pct, 1) + "%", "of filled", ""),
    kpi("Est. PF", fmt(m.est_PF, 2), "paper realized", m.est_PF >= 1.2 ? "pos" : ""),
    kpi("Est. expectancy", (m.est_expectancy_R > 0 ? "+" : "") + fmt(m.est_expectancy_R, 3) + "R", "per filled", cls(m.est_expectancy_R)),
    kpi("Avg stop", fmt(m.avg_stop_size_pts, 1) + "pt", "size", ""),
    kpi("Avg slippage", fmt(m.avg_slippage_est_pts, 2) + "pt", "stop fills (est)", ""),
  ].join("");
  const hm = (t) => (t ? String(t).slice(11, 16) : "—");
  $("paperTbl").querySelector("tbody").innerHTML = (p.log || []).slice(-200).reverse().map(x => {
    const R = (x.result_R === "" || x.result_R == null) ? null : Number(x.result_R);
    return `<tr><td>${x.date}</td><td>${x.direction}</td><td>${fmt(x.entry, 2)}</td>
      <td>${hm(x.fill_time)}</td><td>${hm(x.tp1_time)}</td><td>${hm(x.tp2_time)}</td><td>${hm(x.stop_time)}</td>
      <td class="${cls(R)}">${R == null ? "—" : (R > 0 ? "+" : "") + R.toFixed(3)}</td>
      <td class="mut">${x.fill_quality || ""}</td><td class="mut">${x.notes || ""}</td></tr>`;
  }).join("");
  $("paperNote").textContent = `— realtime fill-assumption check (data-only) · ${fmt(m.late_signals || 0)} late · ${fmt(m.mffu_rejected || 0)} sim-rejected · ${fmt(m.touch_only_fills || 0)} touch-only`;
}

async function drawEquity() {
  const eq = await j("/api/equity");
  mk("equityChart", "line", { labels: eq.map(e => e.ts.slice(0, 10)), datasets: [{ data: eq.map(e => e.balance), borderColor: "#3ddc97", backgroundColor: "rgba(61,220,151,.08)", fill: true, pointRadius: 0, borderWidth: 2, tension: .1 }] },
    { scales: { x: { display: false }, y: { ticks: { callback: v => "$" + (v / 1000).toFixed(0) + "k", color: "#7c8499" }, grid: { color: "#1b2030" } } } });
}

async function drawMonthly() {
  let m = (await j("/api/monthly")).slice(-12);
  const pnl = m.map(x => x.pnl);
  mk("monthlyChart", "bar", { labels: m.map(x => x.month.slice(2)), datasets: [{ data: pnl, backgroundColor: pnl.map(v => v >= 0 ? "#3ddc97" : "#ff5c7c") }] },
    { scales: { x: { ticks: { color: "#7c8499" }, grid: { display: false } }, y: { ticks: { callback: v => "$" + (v / 1000).toFixed(0) + "k", color: "#7c8499" }, grid: { color: "#1b2030" } } } });
}

function drawYears(wf) {
  const pf = wf.map(x => x.pf);
  mk("yearChart", "bar", { labels: wf.map(x => x.year), datasets: [{ data: pf, backgroundColor: pf.map(v => v >= 1.2 ? "#3ddc97" : v >= 1 ? "#e8b84b" : "#ff5c7c") }] },
    { scales: { x: { ticks: { color: "#7c8499" }, grid: { display: false } }, y: { suggestedMin: 0.8, ticks: { color: "#7c8499" }, grid: { color: "#1b2030" } } } });
}

async function drawTrades() {
  const t = await j("/api/trades");
  $("tradesTbl").querySelector("tbody").innerHTML = t.slice(-200).reverse().map(x =>
    `<tr><td>${(x.ts_entry || "").slice(0, 16)}</td><td class="mut">${x.phase}</td><td>${x.direction}</td>
     <td>${fmt(x.entry_px, 2)}</td><td>${fmt(x.stop_px, 2)}</td><td>${fmt(x.exit_px, 2)}</td>
     <td>${fmt(x.pnl_pts, 1)}</td><td class="${cls(x.pnl_usd)}">${money(x.pnl_usd)}</td>
     <td class="${x.reason === 'win' ? 'pos' : x.reason === 'loss' ? 'neg' : 'mut'}">${x.reason}</td></tr>`).join("");
  $("tradeNote").textContent = `— ${t.length} trades (showing last 200)`;
}

function mk(id, type, data, opts) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($(id), { type, data, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, ...opts } });
}

render();
setInterval(render, 15000);   // auto-refresh — picks up new live trades as the bot fills
