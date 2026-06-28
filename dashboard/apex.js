/* ===== ZEUS · terminal logic ===== */
const $ = id => document.getElementById(id);
let S = {}, CAL = null, RW = null, VIEW = "overview", CALV = null;
const money = (n,dp=0) => { n=+n||0; const s=n<0?"−":n>0?"+":""; return s+"$"+Math.abs(n).toLocaleString(undefined,{maximumFractionDigits:dp}); };
const cls = n => (+n>0?"pos":+n<0?"neg":"");
const k = n => "$"+(Math.round(n/100)/10)+"k";
const M = ["January","February","March","April","May","June","July","August","September","October","November","December"];

/* splash: once per session, skippable (click / any key) */
(function(){
  const sp=$("splash"); if(!sp) return;
  const reveal=()=>{ sp.style.animation="none"; sp.style.opacity="0"; sp.style.visibility="hidden"; document.body.classList.add("ready"); };
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if(reduce || sessionStorage.getItem("zeus_seen")){ sessionStorage.setItem("zeus_seen","1"); reveal(); return; }
  sessionStorage.setItem("zeus_seen","1");
  setTimeout(()=>document.body.classList.add("ready"), 5700);
  const skip=()=>{ reveal(); sp.removeEventListener("click",skip); removeEventListener("keydown",skip); };
  sp.addEventListener("click",skip); addEventListener("keydown",skip);
})();

/* clock + data-freshness ('fail loud': stale data must look stale) */
let lastOk=0;
function syncStatus(){
  const el=$("sync"); if(!el) return;
  const age=lastOk?(Date.now()-lastOk)/1000:1e9, stale=age>60;
  el.className="pill"+(stale?" stale":"");
  el.innerHTML=`<span class="dot ${stale?'r':'p'}"></span>${stale?'STALE':'SYNCED'} <b>${lastOk?new Date(lastOk).toLocaleTimeString('en-GB',{hour12:false}):'—'}</b>`;
}
function clock(){ $("clock").textContent=new Date().toLocaleTimeString("en-GB",{hour12:false}); syncStatus(); }
setInterval(clock,1000); clock();

function barStat(){
  const d=S.deployment||{}, h=S.header||{};
  const bot = d.status==="RED"?["r","HALTED"]:d.green?["p","LIVE"]:["a","ARMED"];
  const feed = d.data_state==="GREEN"?["p","GREEN"]:d.data_state==="YELLOW"?["a","YELLOW"]:["r","RED"];
  const exec = d.webhook_mode==="LIVE"?["p","LIVE"]:["a", d.webhook_mode||"DRY-RUN"];
  // weekly strategy-fidelity verdict (mirrors the Trades/Home review panel)
  const rv = !RW ? ["a","…"] : RW.fidelity_ok===true?["p","GREEN-LIGHT"]
                  : RW.fidelity_ok===false?["r","HOLD"]:["a","—"];
  const pill=(l,[c,v])=>`<span class="pill"><span class="dot ${c}"></span>${l} <b>${v}</b></span>`;
  $("barstat").innerHTML = `<span class="pill" id="sync"></span>`+pill("BOT",bot)+pill("FEED",feed)+pill("EXEC",exec)
    +`<span class="pill">TIER <b class="gold">${h.tier||"—"}</b></span>`
    +`<span class="pill rvpill ${rv[0]}" title="weekly strategy-fidelity review — click for detail"><span class="dot ${rv[0]}"></span>REVIEW <b>${rv[1]}</b></span>`;
  const rp=$("barstat").querySelector(".rvpill"); if(rp) rp.onclick=()=>{ const t=document.querySelector('.nv[data-view="trades"]'); if(t) t.click(); };
  syncStatus();
}

/* a day's total trade P&L = realised (fill-backed) + modeled/paper */
const eff = e => (e.pnl||0)+(e.hypothetical_pnl||0);
const isLive = e => (e.pnl||0)!==0;            // fill-backed/realised vs paper-modeled
function totals(){
  let all=0, today=0, week=0, month=0, real=0, tdays=0;
  const now=new Date(), tk=now.toISOString().slice(0,10), mk=tk.slice(0,7);
  const w=new Date(now); w.setDate(now.getDate()-6); const wk=w.toISOString().slice(0,10);
  if(CAL) for(const [d,e] of Object.entries(CAL)){ const v=eff(e); all+=v; real+=(e.pnl||0); tdays++;
    if(d===tk)today=v; if(d>=wk)week+=v; if(d.slice(0,7)===mk)month+=v; }
  return {all, today, week, month, real, tdays};
}

/* ---------- TOPSTEP CALENDAR (shared: home embeds it, tab adds nav) ---------- */
function topstep(nav){
  if(!CAL) return `<div class="note">loading calendar…</div>`;
  const keys=Object.keys(CAL).sort(); const base=keys.length?new Date(keys[keys.length-1]+"T12:00"):new Date();
  if(!CALV) CALV={y:base.getFullYear(),m:base.getMonth()};
  const {y,m}=CALV, p2=n=>String(n).padStart(2,"0"), key=d=>`${y}-${p2(m+1)}-${p2(d)}`;
  const nd=new Date(y,m+1,0).getDate(), sd=new Date(y,m,1).getDay();
  let slots=[]; for(let i=0;i<sd;i++) slots.push(null); for(let d=1;d<=nd;d++) slots.push(d); while(slots.length%7) slots.push(null);
  let cells="", monTot=0, monTr=0, td=0, wn=0;
  for(let w=0; w<slots.length; w+=7){
    let wTot=0;
    for(let i=0;i<7;i++){ const d=slots[w+i];
      if(d==null){ cells+=`<div class="cell pad"></div>`; continue; }
      const e=CAL[key(d)];
      if(e){ const v=eff(e); monTot+=v; monTr+=e.trades; td++; if(v>0)wn++; wTot+=v;
        const c=v>0?"up":v<0?"dn":"";
        const tg=isLive(e)?`<span class="tg live">LIVE</span>`:`<span class="tg ppr">PPR</span>`;
        cells+=`<div class="cell ${c}"><span class="dm">${d}</span>${tg}<span class="pl">${money(v)}</span><span class="tr">${e.trades} trade${e.trades==1?'':'s'}</span></div>`;
      } else cells+=`<div class="cell"><span class="dm">${d}</span></div>`;
    }
    cells+=`<div class="wkcell"><div class="l">Week</div><div class="v mono ${cls(wTot)}">${wTot?money(wTot):'·'}</div></div>`;
  }
  if(nav) setTimeout(()=>{ const pv=$("cprev"),nx=$("cnext");
    if(pv) pv.onclick=()=>{CALV.m--;if(CALV.m<0){CALV.m=11;CALV.y--}renderView();};
    if(nx) nx.onclick=()=>{CALV.m++;if(CALV.m>11){CALV.m=0;CALV.y++}renderView();}; },0);
  return `<div class="cal-head"><div class="cal-title">${M[m]} ${y}</div>
    <div class="cal-sum">
      <span class="it">NET <b class="mono ${cls(monTot)}">${money(monTot)}</b></span>
      <span class="it">DAYS <b class="mono">${td}</b></span>
      <span class="it">TRADES <b class="mono">${monTr}</b></span>
      <span class="it">GREEN <b class="mono">${td?Math.round(100*wn/td):0}%</b></span>
    </div>${nav?`<div class="cal-nav"><button id="cprev">‹ prev</button><button id="cnext">next ›</button></div>`:''}</div>
    <div class="cal rise">${["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map(d=>`<div class="dow">${d}</div>`).join("")}<div class="dow wk">Wk</div>${cells}</div>`;
}

/* ---------- campaign (shared) ---------- */
function campaign(compact){
  const p=S.playbook; if(!p||p.error) return "";
  const ev=p.eval,f=p.funded,ec=p.economics;
  const arr=`<div class="arr"><svg viewBox="0 0 24 24" width="22" height="22"><path d="M3 12h15M13 5.5 19.5 12 13 18.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg></div>`;
  const step=(d,kk,t,c,n,u,s)=>`<div class="step" style="animation-delay:${d}s"><div class="k">${kk}</div><div class="t">${t}</div><div class="c">${c}</div><div class="n">${n}<s>${u}</s></div><div class="s">${s}</div></div>`;
  const flow = step(0,"Phase I · The Trial",ev.tier,`${ev.size} · $${ev.stop} stop`,ev.pass_pct+"%","pass",`median ${ev.median_days}d · spray ~$19/try`)+arr
    + step(.22,"Phase II · The Ascent","Funded · scale at the lock",`${f.phase1} → +$2k lock → ${f.phase2}`,money(f.income_mo),"/mo",`~5wk to lock · ${f.lock_pct}% reach it · ${f.busts}`)+arr
    + step(.44,"The Legion","20 × 50K fleet","scaled · near-unbustable",k(ec.fleet20_mo),"/mo",`~${ec.eval_to_mature_wk}wk eval→mature`);
  const live=((S.portfolio||{}).funded||0)+((S.portfolio||{}).evals||0)>0;
  return `<div class="camp rise"><div class="camp-h"><div class="ttl">APEX CAMPAIGN<small>PATH&nbsp;TO&nbsp;THE&nbsp;THRONE</small></div><div class="seal${live?'':' proj'}">${live?p.status:'PROJECTED'}</div></div>
    <div class="flow">${flow}</div>${compact?"":`<div class="camp-rules"><span class="rh">The Laws of Apex</span>${p.rules.map(r=>`<span class="law">${r}</span>`).join("")}</div>`}</div>`;
}

const head=(ix,t,sub)=>`<div class="head"><h2><span class="ix">${ix}</span>${t}</h2><div class="sub">${sub}</div></div>`;

/* ---------- HOME ---------- */
function vOverview(){
  const pf=S.portfolio||{}, p=S.playbook||{}, ec=p.economics||{}, d=S.deployment||{};
  const T=totals();
  const open=(pf.evals||0)+(pf.funded||0);
  const offline = d.status==="RED" || !d.green || open===0;
  const banner = offline ? `<div class="banner rise">SYSTEM NOT LIVE${d.status==="RED"?" · bot halted":""}${d.data_state==="RED"?" · feed red":""} : the P&L below is paper/test and the campaign figures are projections, not realised money</div>` : "";
  // ledger
  const ledger = `<div class="ledger rise">
    <div class="total"><div class="l">Total P&L</div><div class="v mono ${cls(T.all)}">${money(T.all)}<small>net · ${T.tdays}d · incl. paper</small></div></div>
    <div class="periods">
      <div class="per"><div class="l">Today</div><div class="v mono ${cls(T.today)}">${money(T.today)}</div></div>
      <div class="per"><div class="l">This week</div><div class="v mono ${cls(T.week)}">${money(T.week)}</div></div>
      <div class="per"><div class="l">This month</div><div class="v mono ${cls(T.month)}">${money(T.month)}</div></div>
      <div class="per"><div class="l">Realised <span style="color:var(--faint)">· broker-proven</span></div><div class="v mono ${cls(T.real)}">${money(T.real)}</div></div>
    </div></div>`;
  // stages pipeline (open accounts + current stage)
  const stg=(ph,ct,nm,cur,act,arr)=>`<div class="stg ${cur?'cur':''}"><div class="ph">${ph}</div><div class="ct mono ${act?'act':''}">${ct}</div><div class="nm">${nm}</div>${arr?`<div class="ar">${arr}</div>`:''}</div>`;
  const ar=`<svg viewBox="0 0 24 24" width="16" height="16"><path d="M5 12h13M14 7l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>`;
  const pipe = `<div class="panel rise" style="padding:0;border:0">
    <div style="display:flex;align-items:center;justify-content:space-between;padding:0 2px 12px">
      <div style="font:600 10px var(--mono);letter-spacing:.18em;color:var(--dim);text-transform:uppercase">Fleet stages · what's running</div>
      <div style="font:600 11px var(--mono);color:var(--dim)">OPEN <b class="gold" style="font-size:14px">${open}</b> / 20</div></div>
    <div class="pipe">
      ${stg("Stage 1 · Spray", pf.evals||0, "Evals in progress", open===0, (pf.evals||0)>0, ar)}
      ${stg("Stage 2 · Ascent", pf.funded||0, "Funded · grinding to +$2k lock", false, (pf.funded||0)>0, ar)}
      ${stg("Stage 3 · Legion", 0, "Scaled A6/B3 · near-unbustable", false, false, "")}
    </div>
    ${open===0?`<div class="note">Pre-deployment · no accounts live yet. <b>Next move:</b> buy a 50K EOD eval and spray Stage 1 (~${p.eval?.pass_pct||57}% pass, median ${p.eval?.median_days||7}d).</div>`:''}</div>`;
  // home calendar (current month, no nav)
  const cal = `<div class="panel rise" style="margin-top:18px">${topstep(false)}<div class="note">Daily P&L &amp; trade count, Topstep-style. <b>PPR</b> = paper/modeled test trades; <b>LIVE</b> = broker-proven fills. NET is the month; the right column totals each week.</div></div>`;
  return head("01","Home", `${new Date().toDateString()}<br>APEX 50K · EOD trail · strategy frozen`)
    + banner
    + ledger
    + `<div style="margin:18px 0">${weekReview(true)}</div>`
    + `<div style="margin:18px 0">${pipe}</div>`
    + campaign(true)
    + cal;
}

/* ---------- PLAYBOOK ---------- */
function vPlaybook(){
  const p=S.playbook||{}, ev=p.eval||{}, f=p.funded||{}, ec=p.economics||{};
  const tl=[["Days 0–7",`median ${ev.median_days||7}d`,`pass the eval (~${ev.pass_pct||57}%)`,"act"],["Weeks 1–7","~7 weeks",`grind ${ev.size?f.phase1:'A4/B2'} → lock (~${f.lock_pct||68}%)`,"act"],["Post-lock","mature",`${f.phase2||'A6/B3'} · floor locked`,""]];
  return head("02","Playbook", "the Apex campaign · frozen &amp; validated<br>real Databento · spray eval / scale funded")
    + campaign(false)
    + `<div class="grid g3" style="margin-top:18px">
        <div class="panel rise"><div class="l">Eval · spray</div><div style="font:700 34px var(--mono);color:var(--gold)">${ev.pass_pct}%</div><div class="note" style="margin-top:6px">pass · ${ev.bust_pct}% bust · ${ev.expire_pct}% expire<br>${ev.size} @ $${ev.stop} stop · median ${ev.median_days}d<br>${ev.note}</div></div>
        <div class="panel rise" style="animation-delay:.06s"><div class="l">Funded · scale</div><div style="font:700 34px var(--mono);color:var(--gold)">${money(f.income_mo)}</div><div class="note" style="margin-top:6px">/mo blended · ${f.busts}<br>${f.phase1} → +$2k lock → ${f.phase2}<br>~${f.lock_days}d to lock · ${f.lock_pct}% reach it</div></div>
        <div class="panel rise" style="animation-delay:.12s"><div class="l">Momentum</div><div style="font:700 34px var(--mono)">PF 1.67</div><div class="note" style="margin-top:6px">${ec.momentum}</div></div>
      </div>
      <div class="panel rise" style="margin-top:16px"><div class="l">Account lifecycle · eval → lock → mature</div>
        <div style="display:flex;gap:0;margin-top:4px">${tl.map(s=>`<div style="flex:1;padding:16px 16px 0;border-top:2px solid ${s[3]?'var(--gold)':'var(--line2)'}"><div style="font:600 9px var(--mono);letter-spacing:.14em;color:var(--gold-d);text-transform:uppercase">${s[0]}</div><div style="font:600 18px var(--mono);margin-top:6px">${s[1]}</div><div style="font:500 10px var(--mono);color:var(--dim);margin-top:3px">${s[2]}</div></div>`).join("")}</div>
        <div class="note">~<b>7-8 weeks</b> from buying an eval to a floor-locked A6/B3 account (for the ~${Math.round((ev.pass_pct||57)*(f.lock_pct||68)/100)}% that clear eval + lock).</div></div>`;
}

/* ---------- FLEET ---------- */
function vFleet(){
  const pf=S.portfolio||{}, perMo=(S.playbook?.economics?.per_acct_mo)||1924;
  let rows="";
  for(let w=3;w<=26;w+=(w<22?1:4)){ const funded=Math.min(20,w-2);
    rows+=`<tr><td>wk ${w}</td><td>${funded}</td><td style="color:var(--faint)">${funded<20?Math.min(2,20-funded):0}</td><td class="pos">${money(funded*perMo)}</td><td>${funded>=20?'<span class="tag p">FULL</span>':'<span class="tag g">RAMPING</span>'}</td></tr>`; }
  return head("03","Fleet", `${pf.funded||0} funded · ${pf.evals||0} in eval<br>target: 20 × 50K accounts`)
    + (pf.total_accounts? "" : `<div class="panel rise" style="margin-bottom:16px;border-color:var(--gold-deep);box-shadow:inset 0 0 20px var(--glow)"><div class="l">Pre-deployment</div><div style="font:700 30px var(--mono)">0 live</div><div class="note">No Apex accounts running yet. Below is the <b>projected</b> fleet build at 1 funded account / week.</div></div>`)
    + `<div class="panel rise"><div class="l">Projected fleet ramp &amp; run-rate</div><table style="margin-top:8px"><tr><th>Week</th><th>Funded</th><th>In eval</th><th>Run-rate /mo</th><th>State</th></tr>${rows}</table><div class="note">5-yr-average basis · partial monthly payouts to the $52,100 safety net · expect materially less live (correlated fleet).</div></div>`;
}

/* ---------- WEEKLY REVIEW (live trades + strategy-fidelity verdict) ---------- */
function weekReview(compact){
  const r=RW;
  if(!r) return `<div class="panel rise"><div class="l">This week · live trades</div><div class="note">loading weekly review…</div></div>`;
  const tr=r.trades||[], ok=r.fidelity_ok;
  const vc = ok===true?"g":ok===false?"r":"n", vt = ok===true?"GREEN-LIGHT":ok===false?"HOLD":"NO VERDICT";
  const verdict = `<div class="rvb ${vc}"><span class="tag ${vc}">${vt}</span><div class="rvt">${r.verdict||""}</div><div class="rvm">${r.since||""} → ${r.until||""} · win/lose-blind</div></div>`;
  const chip=(l,v,c)=>`<div class="rvc"><div class="l">${l}</div><div class="v mono ${c||''}">${v}</div></div>`;
  const summary = `<div class="rvs">
      ${chip("Live trades", r.n_trades||0)}
      ${chip("Modeled P&L", money(r.modeled_pnl||0), cls(r.modeled_pnl))}
      ${chip("Pending confirm", r.pending_confirm||0, (r.pending_confirm||0)>0?"gold":"")}
      ${chip("Engine signals", r.engine_signals_live??"—")}
      ${chip("No-trade blocks", r.n_blocks||0)}</div>`;
  const off = (r.off_strategy&&r.off_strategy.length)
    ? `<div class="banner rise" style="border-color:var(--neg);color:var(--neg);background:var(--neg-bg);margin:14px 0 0">⚠ ${r.off_strategy.length} OFF-STRATEGY trade(s): a live fill with no matching engine signal. Investigate before buying the next account.</div>` : "";
  if(compact) return `<div class="panel rise">${verdict}${summary}${off}</div>`;
  const clean=s=>(s||"").replace(/^(fill-backed|HYPOTHETICAL)\s*·\s*/i,"").slice(0,72);
  const rows = tr.length ? tr.map(x=>`<tr><td>${x.date}</td><td>${x.strategy}</td><td>${x.direction} ×${x.contracts}</td><td class="${cls(x.pnl)}">${money(x.pnl)}</td><td>${x.confirmed?'<span class="tag p">CONFIRMED</span>':'<span class="tag n">PENDING</span>'}</td><td style="color:var(--faint)">${clean(x.note)}</td></tr>`).join("")
    : `<tr><td colspan="6" style="text-align:center;color:var(--faint);padding:18px">No live trades in the last 7 days.</td></tr>`;
  return `<div class="panel rise">${verdict}${summary}${off}
      <table style="margin-top:16px"><tr><th>Date</th><th>Strat</th><th>Side</th><th>$ modeled</th><th>Status</th><th>Why / note</th></tr>${rows}</table>
      <div class="note"><b>Fidelity</b> is win/lose-blind: it only checks every live trade was a rule-based engine signal. P&L is <b>modeled</b> until you eye-confirm the fill in Tradovate (then it flips to CONFIRMED). <b>review_week.py</b> gives the full terminal report incl. block reasons.</div></div>`;
}

/* ---------- TRADES ---------- */
function vTrades(){
  const t=S.trades||[];
  const chain = t.length
    ? `<div class="panel rise" style="margin-top:18px;padding:4px 0"><div class="l" style="padding:13px 20px 0">Execution-chain detail · journal-reconstructed</div><table><tr><th>Time</th><th>Strat</th><th>Account</th><th>Side</th><th>Entry</th><th>Exit</th><th>R</th><th>$</th><th>Chain</th></tr>${t.slice(0,100).map(x=>`<tr><td>${new Date(x.ts).toLocaleString()}</td><td>${x.strategy}</td><td>${x.account}</td><td>${x.side} ${x.qty}</td><td>${(+x.entry||0).toFixed(2)}</td><td>${(+x.exit||0).toFixed(2)}</td><td class="${cls(x.r)}">${(+x.r||0).toFixed(2)}</td><td class="${cls(x.usd)}">${money(x.usd)}</td><td>${x.chain_ok?'<span class="tag p">✓</span>':'<span class="tag r">✗</span>'}</td></tr>`).join("")}</table></div>`
    : `<div class="panel rise" style="margin-top:18px"><div class="l">Execution-chain detail</div><div class="note">No journal-confirmed chains yet. Every routed fill lands here, hash-chained and reconstructable.</div></div>`;
  const n = (RW&&RW.n_trades)||0;
  return head("04","Trades",`this week · ${n} live trade${n==1?'':'s'} · fidelity review`)+weekReview(false)+chain;
}

/* ---------- CALENDAR (full, Topstep + nav) ---------- */
function vCalendar(){ return head("05","Calendar","daily P&L · trade count · weekly totals")+`<div class="panel rise">${topstep(true)}<div class="note"><b>PPR</b> = paper/modeled test trades; <b>LIVE</b> = broker-proven fills. Last 2 weeks: Jun 16 A +$1,400 (paper), Jun 22 B −$229, Jun 24 B −$249, Jun 25 B +$369 (operator-confirmed live win). Jun 26 (Fri) flat: both profiles live, no qualifying setup (A: 50 evals, 0 candidates; B/ORB: no breakout trigger); feed GREEN through the close.</div></div>`; }

/* ---------- HEALTH ---------- */
function statusRows(){
  const d=S.deployment||{}, h=S.header||{}, j=S.journal||{};
  const row=(nm,[c,v],ds)=>`<div class="srow"><span class="dot ${c}"></span><span class="nm">${nm}</span><span class="ds">${ds}</span><span class="tag ${c}">${v}</span></div>`;
  return [
    row("Data feed", d.data_state==="GREEN"?["p","GREEN"]:d.data_state==="YELLOW"?["a","YELLOW"]:["r","RED"], `CME NQ 1m via Chrome · last bar age ${Math.round(d.last_bar_age_s||0)}s`),
    row("Bot / deployment", d.status==="RED"?["r","RED"]:d.green?["p","GREEN"]:["a","ARMED"], `${d.status||"—"} · ${d.data_ready?"data ready":"data not ready"}`),
    row("Execution route", d.traderspost_proven?["p","PROVEN"]:["a","UNPROVEN"], `${d.execution_route||"none"} · webhook ${d.webhook_mode||"—"}`),
    row("Heartbeat", h.heartbeat?["p","ALIVE"]:["r","ABSENT"], h.heartbeat?`last beat ${new Date(h.heartbeat).toLocaleString()}`:"no process heartbeat"),
    row("Journal", j.online?["p","ONLINE"]:["a","IDLE"], `last event ${h.last_journal?new Date(h.last_journal).toLocaleString():"—"}`),
    row("Lockout", h.lockout?["r","LOCKED"]:["p","CLEAR"], h.lockout||"no emergency lockout")
  ];
}
function vHealth(){ return head("06","Health","integrity &amp; ops · broker is truth")+`<div class="rise">${statusRows().join("")}</div><div class="note">Fail-closed by design: a stale/RED feed places no trades. No control here can arm trading, modify sizing, or clear a lockout · display only.</div>`; }

/* ---------- render + nav ---------- */
const VIEWS={overview:vOverview,playbook:vPlaybook,fleet:vFleet,trades:vTrades,calendar:vCalendar,health:vHealth};
function renderView(){ $("v-"+VIEW).innerHTML = VIEWS[VIEW](); }
async function refresh(){
  let ok=true;
  try{ S=await (await fetch("/api/state",{cache:"no-store"})).json(); lastOk=Date.now(); }catch(e){ ok=false; }
  if(ok){ try{ CAL=await (await fetch("/api/calendar",{cache:"no-store"})).json(); }catch(e){ CAL=CAL||{}; } }
  if(ok){ try{ RW=await (await fetch("/api/review_week",{cache:"no-store"})).json(); }catch(e){ RW=RW||null; } }
  const d=S.deployment||{}, pf=S.portfolio||{};
  document.body.classList.toggle("offline", d.status==="RED" || !d.green || ((pf.funded||0)+(pf.evals||0))===0);
  barStat(); renderView();
}
/* re-pull fresh when the dashboard is re-opened / re-focused */
document.addEventListener("visibilitychange", ()=>{ if(!document.hidden) refresh(); });
window.addEventListener("focus", refresh);
document.querySelectorAll(".nv").forEach(b=>{
  b.tabIndex=0; b.setAttribute("role","button"); b.setAttribute("aria-label",b.dataset.view);
  const go=()=>{
    document.querySelectorAll(".nv").forEach(x=>{x.classList.remove("on");x.removeAttribute("aria-current");});
    document.querySelectorAll(".view").forEach(x=>x.classList.remove("on"));
    b.classList.add("on"); b.setAttribute("aria-current","page"); VIEW=b.dataset.view; $("v-"+VIEW).classList.add("on"); renderView(); location.hash=VIEW;
  };
  b.onclick=go;
  b.addEventListener("keydown",e=>{ if(e.key==="Enter"||e.key===" "){ e.preventDefault(); go(); } });
});
/* keyboard: 1-6 jump views · ←/→ step calendar months · T = latest month */
const NAV=["overview","playbook","fleet","trades","calendar","health"];
addEventListener("keydown", e=>{
  if(!document.body.classList.contains("ready")) return;
  if(e.key>="1"&&e.key<="6"){ const t=document.querySelector(`.nv[data-view="${NAV[+e.key-1]}"]`); if(t)t.click(); }
  else if(VIEW==="calendar"&&CALV&&(e.key==="ArrowLeft"||e.key==="ArrowRight")){ CALV.m+=e.key==="ArrowRight"?1:-1; if(CALV.m<0){CALV.m=11;CALV.y--} if(CALV.m>11){CALV.m=0;CALV.y++} renderView(); }
  else if((e.key==="t"||e.key==="T")&&VIEW==="calendar"){ CALV=null; renderView(); }
});
refresh().then(()=>{ if(location.hash){ const t=document.querySelector(`.nv[data-view="${location.hash.slice(1)}"]`); if(t) t.click(); } });
setInterval(refresh, 30000);
