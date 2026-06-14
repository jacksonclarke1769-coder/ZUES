/* ZEUS god terminal — display & analyse only. No control paths exist here. */
let S = null, ORACLE = null, FILTER = {};
const $ = (q) => document.querySelector(q);
const fmt = (n, d=0) => n == null ? "—" : Number(n).toLocaleString("en-US",{minimumFractionDigits:d, maximumFractionDigits:d});
const usd = (n) => n == null ? "—" : (n<0?"-$":"$")+fmt(Math.abs(n),0);
const cls = (n) => n>0?"pos":n<0?"neg":"dim";
const ago = (ts) => { if(!ts) return "never"; const s=(Date.now()-new Date(ts))/1e3;
  return s<90?`${s.toFixed(0)}s ago`:s<5400?`${(s/60).toFixed(0)}m ago`:`${(s/3600).toFixed(1)}h ago`; };

async function refresh(){
  const t0=performance.now();
  S = await (await fetch("/api/state")).json();
  document.body.dataset.tier = S.header.tier;
  renderHeader(performance.now()-t0); renderAll();
}

function renderHeader(clientMs){
  $("#voice").textContent = S.meta.voice;
  const m=S.meta,h=S.header;
  const tierCls={GREEN:"g",YELLOW:"y",ORANGE:"o",RED:"r",BLACK:"k"}[h.tier]||"";
  $("#chips").innerHTML = [
    [`MODE <b>${m.mode}</b>`, m.mode==="LOCKED"?"k":""],
    [`TRADING <b>${m.trading_allowed?"PERMITTED":"FORBIDDEN"}</b>`, m.trading_allowed?"g":"r"],
    [`ALERT TIER <b>${h.tier}</b>`, tierCls],
    [`SESSION <b>${h.in_entry_window?"ENTRY WINDOW OPEN":"GATES CLOSED"}</b>`, h.in_entry_window?"g":""],
    [`HEARTBEAT <b>${ago(h.heartbeat)}</b>`,""],
    [`BROKER SYNC <b>${ago(h.broker_sync)}</b>`,""],
    [`JOURNAL <b>${ago(h.last_journal)}</b>`,""],
  ].map(([t,c])=>`<span class="chip ${c}">${t}</span>`).join("");
  $("#meta").innerHTML =
    `Last refreshed <b>${new Date(m.refreshed).toLocaleTimeString()}</b> · server ${m.refresh_ms}ms · round-trip ${clientMs.toFixed(0)}ms<br>`+
    `Data health <b>${m.data_health}</b> · Next session <b>${m.next_session}</b>`;
}

function panel(title, body){ return `<div class="panel"><h3>${title}</h3>${body}</div>`; }
function kv(rows){ return `<dl class="kv">`+rows.map(([k,v])=>`<dt>${k}</dt><dd>${v}</dd>`).join("")+`</dl>`; }

function renderAll(){
  renderCommand(); renderAccounts(); renderStrategies(); renderTrades();
  renderJournal(); renderRecon(); renderAlerts(); renderEvidence(); renderSettings();
}

/* Ⅰ COMMAND CENTRE — the bridge: 5 questions in 5 seconds */
function tradeState(){
  const t=S.header.tier, ok=S.meta.trading_allowed;
  if(t==="BLACK") return ["⚫","BLACK LOCKOUT","k"];
  if(!ok||t==="RED") return ["🔴","TRADE BLOCKED","r"];
  if(t==="ORANGE"||t==="YELLOW") return ["🟡","CAUTION","y"];
  return ["🟢","TRADE ALLOWED","g"];
}
function renderCommand(){
  const p=S.portfolio, a=S.strategies, w=S.week_panel||{};
  const [ico,label,c]=tradeState();
  const healthy=S.accounts.filter(x=>x.status==="SAFE").length;
  const edgePct=Math.min(a.A.vs_validation??100, a.B.vs_validation??100);
  const kpi=(top,sub,big)=>`<div class="panel kpi"><div class="big ${big||""}">${top}</div><div class="dim">${sub}</div></div>`;
  const ares = S.ares||{};
  const dep = S.deployment||{};
  const depStrip = dep.d1c_active_eval_filter
    ? `<div class="ares-strip" style="border-color:var(--gold);color:var(--gold-hi)">⚙ ${dep.d1c_banner}</div>` : "";
  const aresStrip = ares.violation && ares.violation.length
    ? `<div class="ares-strip viol">⚔ ARES ON FUNDED ACCOUNT — VIOLATION: ${ares.violation.join(", ")} — DISARM NOW</div>`
    : (ares.active
       ? `<div class="ares-strip">⚔ ARES EVAL ATTACK MODE — ${Object.entries(ares.accounts).map(([k,v])=>k+" @ "+v.size).join(" · ")} · ZEUS funded mode elsewhere</div>`
       : "");
  $("#page-command").innerHTML = `
  ${aresStrip}${depStrip}
  <div class="hero ${c}">
    <div class="hero-status">${ico} ${label}</div>
    <div class="hero-sub">
      Accounts Healthy <b>${healthy}/${S.accounts.length||0}</b> ·
      Active Alerts <b>${S.alerts.length}</b> ·
      Mode <b>${S.meta.mode}</b> ·
      Next Session <b>${S.meta.next_session}</b> ·
      Heartbeat <b>${ago(S.header.heartbeat)}</b> ·
      Refreshed <b>${new Date(S.meta.refreshed).toLocaleTimeString()}</b>
    </div>
    <p class="brief">${S.brief||""}</p>
  </div>

  <div class="grid g4 kpis">
    ${kpi(fmt(w.pts,0)+" pts",`Weekly · plan ${S.plan?.avg.pts_wk}/wk avg · ${S.plan?.strong.pts_wk} strong`,cls(w.usd))}
    ${kpi(usd(p.pnl_month),"Monthly",cls(p.pnl_month))}
    ${kpi(usd(p.pnl_ytd),"Year-to-date",cls(p.pnl_ytd))}
    ${kpi(`${healthy} / ${S.accounts.length||0}`,"Accounts alive")}
    ${kpi(`${p.alloc_a+p.alloc_b} MNQ`,`${((p.alloc_a+p.alloc_b)/10).toFixed(1)} NQ exposure`)}
    ${kpi(p.p3_active>0?`${p.p3_active} PROTECTED`:"SHEATHED","P3 status",p.p3_active?"neg":"")}
    ${kpi(`${fmt(edgePct,0)}%`,a.worst,edgePct>=90?"pos":edgePct>=70?"":"neg")}
    ${kpi(S.meta.next_session.split(" ").slice(-2).join(" "),"Next session")}
  </div>

  <div class="grid g3" style="margin-top:14px">
    ${panel("This Week", kv([
      ["Points", `<b class="${cls(w.pts)}">${fmt(w.pts,0)} pts</b>`],
      ["Dollars", `<b class="${cls(w.usd)}">${usd(w.usd)} gross</b>`],
      ["Trades", w.n??0],["Win rate", w.wr!=null?w.wr+"%":"—"],
      ["Avg R", w.avg_r!=null?fmt(w.avg_r,2)+"R":"—"],
      ["Last week", fmt(w.last,0)+" pts"],["4-week avg", fmt(w.avg4,0)+" pts"],
      ["12-week avg", fmt(w.avg12,0)+" pts"],
      ["Plan — avg regime", `<b>+${S.plan?.avg.pts_wk} pts · ${usd(S.plan?.avg.net_wk)} net</b>`],
      ["Plan — strong year", `+${S.plan?.strong.pts_wk} pts · ${usd(S.plan?.strong.net_wk)} net`]]))}
    ${panel("Portfolio Health", Object.entries(S.lights||{}).map(([k,v])=>
      `<div class="stat light"><span class="lamp ${v}"></span>${k}</div>`).join("")
      +`<div class="note">Click pages Ⅱ–Ⅵ for detail. Green = healthy.</div>`)}
    ${panel("Action Centre", (S.actions&&S.actions.length)
       ? S.actions.map(x=>`<div class="stat action">☐ ${x}</div>`).join("")
       : `<div class="big pos" style="font-size:18px">No action required.</div>`)}
  </div>

  ${challengerRow()}

  <div class="grid g2" style="margin-top:14px">
    ${panel("Accounts", S.accounts.length?`<table><tr><th>Account</th><th>Cushion</th><th>P3</th><th>Status</th></tr>`+
      S.accounts.map(x=>`<tr><td>${x.name}</td><td>${usd(x.cushion)}</td>
        <td>${x.p3_braked?"ON":"OFF"}</td>
        <td><span class="tag ${x.status}">${x.status==="SAFE"?"🟢":x.status==="CAUTION"?"🟡":"🔴"} ${x.status}</span></td></tr>`).join("")
      +`</table><div class="note">Click page Ⅱ for full account detail.</div>`
      : `<span class="dim">No accounts registered — pre-deployment.</span>`)}
    ${panel("Latest Activity", (S.activity||[]).map(e=>
       `<div class="stat"><span class="dim">${new Date(e.ts).toLocaleTimeString()}</span> &nbsp;${e.text}</div>`).join("")
       || `<span class="dim">No events.</span>`)}
  </div>`;
}

/* Challenger & Regime row (PROMETHEUS / ATHENA — display only, nothing here trades) */
function challengerRow(){
  const rm=S.regime_monitor||{}; const rg=rm.regime, sh=rm.d1c_shadow, cd=rm.d1c_candidate;
  const regimeBody = rg ? kv([
      ["Status", `<span class="tag ${rg.status}">${rg.status}</span> <span class="dim">as of ${rg.asof}</span>`],
      ["Median stop distance", `<b>${fmt(rg.median_stop_distance_pts,1)} pt</b> <span class="dim">(RED &lt;15 · YELLOW &lt;25)</span>`],
      ["Cost burden", `<b>${fmt(rg.cost_burden_pct_of_R,1)}%</b> of R <span class="dim">(2014-18 dead era: ~22%)</span>`],
      ["Rolling 252-trade PF", `<b>${fmt(rg.rolling_252_pf,2)}</b> <span class="dim">(RED &lt;1.0 sustained)</span>`],
      ["Rolling expectancy", `${fmt(rg.rolling_126_expectancy_R,3)}R · WR ${fmt(rg.rolling_126_win_rate_pct,1)}%`]])
    : `<span class="dim">regime_status.json absent — run regime_dashboard.py</span>`;
  const trialBody = sh ? kv([
      ["Challenger", `<b>${sh.challenger_status||"—"}</b>`],
      ["Forward clock", `<b>${sh.official_forward_count??0} / 30</b> · next: ${sh.next_official_gate||"—"}`],
      ["Backfilled / Replay", `${sh.backfilled_decision_count??0} diag · ${sh.replay_decision_count??0} rehearsal <span class="dim">(never count)</span>`],
      ["Fail-open events", `<b class="${(sh.fail_open_events||0)>0?'neg':'pos'}">${sh.fail_open_events??0}</b>`],
      ["Production gate", sh.production_gate_enabled
          ? `<span class="tag RED">ON — INCIDENT</span>`
          : `<span class="tag GREEN">OFF (paper only)</span>`],
      ["Verdict", `<span class="dim">${sh.current_athena_verdict||"—"}</span>`]])
    : `<span class="dim">no shadow status yet</span>`;
  const candBody = cd ? kv([
      ["MC net /yr", `$${fmt(cd.mc_net_base/1000,1)}k → <b class="pos">$${fmt(cd.mc_net_d1c/1000,1)}k</b> (+${cd.mc_net_delta_pct}%)`],
      ["Bad-luck p5", `$${fmt(cd.p5_base/1000,1)}k → <b class="pos">$${fmt(cd.p5_d1c/1000,1)}k</b>`],
      ["Real 12-mo replay", `$${fmt(cd.real_12mo_base/1000,1)}k → <b class="pos">$${fmt(cd.real_12mo_d1c/1000,1)}k</b> (+${cd.real_12mo_delta_pct}%)`],
      ["Portfolio all-dead", `${cd.all_dead_base_pct}% → <b class="pos">${cd.all_dead_d1c_pct}%</b>`],
      ["Stream PF split", `keep <b>${cd.keep_pf}</b> / drop ${cd.drop_pf} · keep-rate ~${cd.validated_keep_rate}%`],
      ["Hostile record", `CERBERUS ${cd.cerberus} · VULCAN ${cd.vulcan_readiness}`]])
      +`<div class="note">${cd.note}</div>`
    : "";
  const st=rm.stats_12mo;
  const statsBody = st ? `<table>
      <tr><th></th><th>ZEUS-MAX</th><th>+D1c <span class="dim">(paper)</span></th></tr>
      <tr><td>12-mo net</td><td>${usd(st.base.net_12mo)}</td><td class="pos"><b>${usd(st.d1c.net_12mo)}</b></td></tr>
      <tr><td>Trades / week</td><td>${fmt(st.base.trades_wk,1)}</td><td>${fmt(st.d1c.trades_wk,1)}</td></tr>
      <tr><td>Win rate (book)</td><td>${fmt(st.base.wr_pct,1)}%</td><td class="pos"><b>${fmt(st.d1c.wr_pct,1)}%</b></td></tr>
      <tr><td>Win rate (A only)</td><td>${fmt(st.base.wr_a_pct,1)}%</td><td class="pos"><b>${fmt(st.d1c.wr_a_pct,1)}%</b></td></tr>
      <tr><td>Avg R / trade (A)</td><td>+${fmt(st.base.avg_r_a,3)}R</td><td class="pos"><b>+${fmt(st.d1c.avg_r_a,3)}R</b></td></tr>
      <tr><td>Avg pts / trade</td><td>+${fmt(st.base.avg_pts_trade,1)}</td><td class="pos"><b>+${fmt(st.d1c.avg_pts_trade,1)}</b></td></tr>
      <tr><td>Trades (12 mo)</td><td>${st.base.trades}</td><td>${st.d1c.trades}</td></tr>
    </table><div class="note">${st.window} · ${st.note}</div>` : "";
  return `<div class="grid g2" style="margin-top:14px">
    ${panel("Regime Monitor — PROMETHEUS", regimeBody)}
    ${panel("Challenger D1c — ATHENA Trial", trialBody)}
  </div>
  <div class="grid g2" style="margin-top:14px">
    ${panel("Last 12 Months — Stream Statistics", statsBody)}
    ${panel("If Promoted (validated · PAPER-ONLY)", candBody)}
  </div>`;
}

/* Ⅱ ACCOUNTS */
function renderAccounts(){
  $("#page-accounts").innerHTML = S.accounts.length ? `<div class="grid g3">`+
    S.accounts.map(a=>`<div class="card ${a.status}">
      <h4>${a.name}<span class="tag ${a.status}">${a.status}</span></h4>
      ${kv([["Firm",a.firm],["Size",usd(a.size)],["Phase",a.phase],
        ["Balance",usd(a.balance)],["Floor",usd(a.floor)],
        ["Cushion",`${usd(a.cushion)} (${fmt(a.cushion_frac*100,0)}%)`],
        ["P3",a.p3_braked?`<span class="tag DANGER">SPEAR LOWERED</span>`:"sheathed"],
        ["Daily loss used",usd(a.daily_loss_used)],["Trades today",a.trades_today],
        ["Open position",a.open_position??"flat"],
        ["Working stop",a.working_stop??"—"],["Working target",a.working_target??"—"],
        ["Last recon",a.last_recon],["Last payout",a.last_payout??"—"],
        ["Next payout eligible",a.next_payout_eligible??"—"],
        ["Paid to date",usd(a.paid)]])}
      <div class="bar ${a.cushion_frac<.4?"bad":a.cushion_frac<.6?"warn":""}"><i style="width:${Math.min(100,a.cushion_frac*100)}%"></i></div>
    </div>`).join("")+`</div>`
  : panel("Accounts", `<span class="dim">No accounts registered. They will appear when B1 syncs broker state.</span>`);
}

/* Ⅲ STRATEGIES */
function stratBlock(s){
  const r=(x)=>x?`${x.n} tr · WR ${x.wr}% · PF ${x.pf??"—"} · ${s.baseline.exp_r?x.exp_r+"R":x.exp_pts+"pt"} exp · ${usd(x.avg_usd)}/tr`:"—";
  return panel(s.label+` — <span class="tag ${s.health.split(" ")[0]}">${s.health}</span>`, kv([
    ["All trades", r(s.total)],["Rolling 30", r(s.r30)],["Rolling 60", r(s.r60)],
    ["Rolling 90", r(s.r90)],["Max drawdown", usd(-Math.abs(s.max_dd))],
    ["vs validation", s.vs_validation!=null?`${s.vs_validation}% of baseline`:"insufficient data"],
    ["Baseline", s.baseline.exp_r?`+${s.baseline.exp_r}R/trade · PF ${s.baseline.pf}`:`+${s.baseline.exp_pts}pt/trade · PF ${s.baseline.pf}`]]))
}
function renderStrategies(){
  $("#page-strategies").innerHTML = `<div class="grid g2">${stratBlock(S.strategies.A)}${stratBlock(S.strategies.B)}</div>
   <div style="margin-top:14px">${panel("Weekly Points Tracker", weeklyTable())}</div>
   <div class="note">Edge health per RAGNAROK decay monitor: ≥90% FULL STRENGTH · ≥70% WATCHING · ≥50% DEGRADED (half size) · &lt;50% CRITICAL (halt) · HALTED. The live strategy is frozen — health drives SIZE, never rules.</div>`;
}
function weeklyTable(){
  const w=S.weekly;
  return kv([["Current week", fmt(w.current,1)+" pts"],["Last week", fmt(w.last,1)],
    ["4-week avg", fmt(w.avg4,1)],["12-week avg", fmt(w.avg12,1)],
    ["Best / worst", `${fmt(w.best,1)} / ${fmt(w.worst,1)}`],
    ["Estimate", w.est_note]]) +
  `<table style="margin-top:10px"><tr><th>Week</th><th>A pts</th><th>B pts</th><th>Total</th><th>$</th></tr>`+
  w.weeks.map(x=>`<tr><td>${x.week}</td><td>${fmt(x.A,1)}</td><td>${fmt(x.B,1)}</td><td><b>${fmt(x.total,1)}</b></td><td class="${cls(x.usd)}">${usd(x.usd)}</td></tr>`).join("")+`</table>`;
}

/* Ⅳ TRADES */
const TFILTERS=[["all","All"],["A","Profile A"],["B","Profile B"],["win","Winners"],["loss","Losers"],["p3","P3 trades"],["rejected","Rejected"],["broken","Chain issues"]];
function renderTrades(){
  const f=FILTER.trades||"all";
  let rows=S.trades.filter(t=>
    f==="all"||(f==="A"&&t.strategy==="A")||(f==="B"&&t.strategy==="B")||
    (f==="win"&&t.usd>0)||(f==="loss"&&t.usd<0)||(f==="p3"&&t.p3)||
    (f==="rejected"&&t.status==="rejected")||(f==="broken"&&!t.chain_ok));
  $("#page-trades").innerHTML = panel("Trade Ledger",
   `<div class="filters">${TFILTERS.map(([k,l])=>`<button data-tf="${k}" class="${f===k?"on":""}">${l}</button>`).join("")}</div>
    <table><tr><th>Time</th><th>Strat</th><th>Account</th><th>Side</th><th>Entry</th><th>Stop</th><th>Exit</th><th>R</th><th>Pts</th><th>$</th><th>Slip</th><th>Chain</th><th>Evidence</th></tr>
    ${rows.slice(0,120).map(t=>`<tr>
      <td>${new Date(t.ts).toLocaleString()}</td><td>${t.strategy}</td><td>${t.account}</td>
      <td>${t.side} ${t.qty}</td><td>${fmt(t.entry,2)}</td><td>${fmt(t.stop,2)}</td>
      <td>${fmt(t.exit,2)}</td><td class="${cls(t.r)}">${fmt(t.r,2)}</td>
      <td>${fmt(t.points,2)}</td><td class="${cls(t.usd)}">${usd(t.usd)}</td>
      <td>${fmt(t.slip,2)}</td>
      <td>${t.chain_ok?`<span class="tag ok">✓</span>`:`<span class="tag RED">✗</span>`}</td>
      <td><a href="/api/trade/${t.cl}" target="_blank" style="color:var(--gold-hi)">export</a></td></tr>`).join("")}
    </table><div class="note">${rows.length} trades shown (max 120). Every row is reconstructable from the journal — that is the point.</div>`);
  document.querySelectorAll("[data-tf]").forEach(b=>b.onclick=()=>{FILTER.trades=b.dataset.tf;renderTrades();});
}

/* Ⅴ JOURNAL */
function renderJournal(){
  const jn=S.journal;
  $("#page-journal").innerHTML = `<div class="grid g2">
   ${panel("B0 Journal", kv([
     ["Status", jn.online?`<span class="tag ok">ONLINE</span>`:`<span class="tag RED">OFFLINE</span>`],
     ["Append-only", jn.append_only?`<span class="tag ok">VERIFIED LIVE</span>`:`<span class="tag BLACK">FAILED</span>`],
     ["Events", fmt(jn.events)],["Last INTENT", ago(jn.last.INTENT)],
     ["Last ACK", ago(jn.last.ACK)],["Last FILL", ago(jn.last.FILL)],
     ["Last RECON_ALERT", ago(jn.last.RECON_ALERT)],
     ["Duplicates blocked", fmt(jn.dup_blocked)],
     ["Unknown orders", jn.unknown_orders],["Unknown fills", jn.unknown_fills]]))}
   ${panel("Evidence Locker Chain", kv([
     ["Hash-chain", jn.locker_ok?`<span class="tag ok">INTACT</span>`:`<span class="tag BLACK">TAMPER DETECTED</span>`],
     ...(jn.locker_problems||[]).map((p,i)=>[`Problem ${i+1}`,p])])
     +`<div class="note">${jn.append_only&&jn.locker_ok?"The journal can be trusted. ZEUS does not trust his memory — he trusts this.":"DO NOT TRADE until the journal is trustworthy."}</div>`)}
  </div>`;
}

/* Ⅵ RECONCILIATION */
function renderRecon(){
  const r=S.recon;
  $("#page-recon").innerHTML = panel("Reconciliation Center",
   kv([["Last run", ago(r.last_run)],["Naked-position alerts (total)", r.naked],
       ["Unknown fills", S.journal.unknown_fills],["Unknown orders", S.journal.unknown_orders]])
   +`<h3 style="margin-top:14px">Recent RECON_ALERTS</h3>`
   +(r.alerts.length?`<table><tr><th>Time</th><th>Account</th><th>Check</th><th>Tier</th><th>Detail</th></tr>`+
     r.alerts.map(a=>`<tr><td>${new Date(a.ts).toLocaleString()}</td><td>${a.account}</td>
       <td>${a.payload?.check??"—"}</td><td><span class="tag ${a.payload?.tier??"YELLOW"}">${a.payload?.tier??"?"}</span></td>
       <td>${JSON.stringify(a.payload?.detail??a.payload?.note??"").slice(0,80)}</td></tr>`).join("")+`</table>`
    :`<span class="dim">No discrepancies on record. Broker and ledger agree.</span>`)
   +`<div class="note">Broker is truth. Any confirmed mismatch escalates the terminal to RED or BLACK automatically — this page cannot suppress it.</div>`);
}

/* Ⅶ ALERTS */
function alertTable(rows){
  return `<table><tr><th>Tier</th><th>Alert</th><th>Detail</th><th>Required action</th><th>Ack</th></tr>`+
   rows.map(a=>`<tr><td><span class="tag ${a.tier}">${a.tier}</span></td><td>${a.name}</td>
     <td>${a.detail}</td><td>${a.action}</td>
     <td>${a.acked?`<span class="dim">acked</span>`:`<button class="ackbtn" data-ack="${a.name}">ack</button>`}</td></tr>`).join("")+`</table>`;
}
function renderAlerts(){
  $("#page-alerts").innerHTML = panel("HEIMDALL Alerts",
    (S.alerts.length?alertTable(S.alerts):`<span class="dim">No alerts. The watchman sees nothing.</span>`)
    +`<div class="note">Acknowledgement is a journaled record of awareness — it never dismisses an alert. Alerts clear only when their condition clears. No alert can be hidden from this terminal.</div>`);
  document.querySelectorAll(".ackbtn").forEach(b=>b.onclick=async()=>{
    await fetch("/api/ack",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({name:b.dataset.ack,note:"acknowledged via terminal"})});
    refresh();
  });
}

/* Ⅷ EVIDENCE */
function renderEvidence(){
  const e=S.evidence;
  $("#page-evidence").innerHTML = panel("Evidence Locker",
   `<div class="grid g3">`+Object.entries(e).map(([k,v])=>
     `<div class="stat"><div class="big">${v}</div><div class="dim">${k}</div></div>`).join("")+`</div>
    <div class="note">Purpose: if a firm questions the account, ZEUS proves every trade was generated by the system — signal → intent → fill → exit, hash-chained. Export any trade from the Trades page; verify the chain with <code>python3 locker.py verify</code>.</div>`);
}

/* Ⅸ ORACLE */
async function renderOracle(){
  if(!ORACLE) ORACLE = await (await fetch("/api/oracle")).json();
  const o=ORACLE;
  $("#page-oracle").innerHTML = panel(`Weekly Oracle Review — ${o.window}`,
    Object.entries(o.sections).map(([k,v])=>`<div class="stat"><b style="color:var(--gold-hi)">${k}</b><pre>${v}</pre></div>`).join("")
    +`<h3 style="margin-top:12px">Recommendations</h3>`
    +o.recommendations.map(r=>`<div class="stat"><span class="label">${r.label}</span> ${r.text}</div>`).join("")
    +`<div class="note">The oracle reviews, analyses, recommends. It cannot deploy. Any change walks the full gauntlet: hypothesis → backtest → OOS → Monte Carlo → slippage stress → funded sim → paper → HUMAN APPROVAL. Until then the live strategy is frozen.</div>`);
}

/* Ⅹ SETTINGS */
function renderSettings(){
  const iv=localStorage.getItem("zeus_iv")||"30";
  $("#page-settings").innerHTML = `<div class="grid g2">
   ${panel("Display Settings", `
     <div class="stat">Refresh interval
       <select id="set-iv">${[10,30,60,300].map(v=>`<option ${v==iv?"selected":""}>${v}</option>`).join("")}</select> seconds</div>
     <div class="stat">Theme <b>OLYMPUS DARK</b> <span class="dim">(there is no other theme on the mountain)</span></div>
     <div class="stat">Account visibility / strategy visibility — <span class="dim">all visible (display-only build)</span></div>`)}
   ${panel("Welded Controls", `
     <div class="stat lockrow"><input type="checkbox" disabled> Enable LIVE trading
       <div class="dim">Requires: SAFETY.enabled=True AND paper=False in code + config, THOR battery green, Gate-6 sign-off. Not available from any dashboard, by design.</div></div>
     <div class="stat lockrow"><input type="checkbox" disabled> Modify strategy rules / sizing / P3
       <div class="dim">Frozen. Changes walk the Oracle gauntlet to HUMAN APPROVAL.</div></div>
     <div class="stat lockrow"><input type="checkbox" disabled> Clear BLACK lockout
       <div class="dim">Only <code>flatten.operator_clear()</code> with a written root-cause note — deliberately NOT exposed here.</div></div>
     <div class="stat">Emergency lockout status: ${S.header.lockout?`<span class="tag BLACK">LOCKED — ${S.header.lockout}</span>`:`<span class="tag ok">CLEAR</span>`}</div>`)}
  </div>`;
  $("#set-iv").onchange=(e)=>{localStorage.setItem("zeus_iv",e.target.value);startTimer();};
}

/* nav + refresh loop */
document.querySelectorAll("#rail button").forEach(b=>b.onclick=()=>{
  document.querySelectorAll("#rail button").forEach(x=>x.classList.remove("on"));
  document.querySelectorAll(".page").forEach(x=>x.classList.remove("on"));
  b.classList.add("on");
  $("#page-"+b.dataset.page).classList.add("on");
  if(b.dataset.page==="oracle") renderOracle();
});
let TIMER=null;
function startTimer(){ clearInterval(TIMER);
  TIMER=setInterval(refresh, 1000*(parseInt(localStorage.getItem("zeus_iv")||"30"))); }
refresh(); startTimer();
