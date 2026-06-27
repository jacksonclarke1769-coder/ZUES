/* ===== APEX // BLACKBOX — terminal logic ===== */
const $ = id => document.getElementById(id);
let S = {}, CAL = null, VIEW = "overview", CALV = null;

const money = (n, dp=0) => { n=+n||0; const s=n<0?"-":n>0?"+":""; return s+"$"+Math.abs(n).toLocaleString(undefined,{maximumFractionDigits:dp}); };
const cls = n => (+n>0?"pos":+n<0?"neg":"dimt");
const k = n => "$"+(Math.round(n/100)/10)+"k";

/* ---------- top bar ---------- */
function clock(){ const d=new Date(); $("clock").textContent=d.toLocaleTimeString("en-GB",{hour12:false}); }
setInterval(clock,1000); clock();

function barStat(){
  const d=S.deployment||{}, h=S.header||{};
  const bot = d.status==="RED"?["r","HALTED"]:d.green?["g","LIVE"]:["a","ARMED"];
  const feed = d.data_state==="GREEN"?["g","GREEN"]:d.data_state==="YELLOW"?["a","YELLOW"]:["r","RED"];
  const exec = (d.webhook_mode==="LIVE")?["g","LIVE"]:["a", d.webhook_mode||"DRY-RUN"];
  const pill=(label,[c,v])=>`<span class="pill"><span class="dot ${c}"></span>${label} <b>${v}</b></span>`;
  $("barstat").innerHTML = pill("BOT",bot)+pill("FEED",feed)+pill("EXEC",exec)
    + `<span class="pill">TIER <b style="color:var(--acc)">${h.tier||"—"}</b></span>`;
}

/* ---------- the APEX campaign (shared) ---------- */
function campaign(compact){
  const p=S.playbook; if(!p||p.error) return "";
  const ev=p.eval,f=p.funded,ec=p.economics;
  const arr=`<div class="arr"><svg viewBox="0 0 24 24" width="24" height="24"><path d="M3 12h15M13 5.5 19.5 12 13 18.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg></div>`;
  const step=(d,kk,t,c,n,u,s)=>`<div class="step" style="animation-delay:${d}s"><div class="k">${kk}</div><div class="t">${t}</div><div class="c">${c}</div><div class="n">${n}<s>${u}</s></div><div class="s">${s}</div></div>`;
  const flow = step(0,"Phase I · The Trial",ev.tier,`${ev.size} · $${ev.stop} stop`,ev.pass_pct+"%","pass",`median ${ev.median_days}d · spray ~$19/try`)
    + arr
    + step(.26,"Phase II · The Ascent","Funded — scale at the lock",`${f.phase1} → +$2k lock → ${f.phase2}`,money(f.income_mo),"/mo",`~5wk to lock · ${f.lock_pct}% reach it · ${f.busts}`)
    + arr
    + step(.52,"The Legion","20 × 50K fleet","scaled · near-unbustable",k(ec.fleet20_mo),"/mo",`~${ec.eval_to_mature_wk}wk eval→mature`);
  return `<div class="camp rise">
    <div class="camp-h"><div class="ttl">APEX CAMPAIGN<small>PATH&nbsp;TO&nbsp;THE&nbsp;THRONE</small></div><div class="seal">${p.status}</div></div>
    <div class="flow">${flow}</div>
    ${compact?"":`<div class="camp-rules"><span class="rh">The Laws of Apex</span>${p.rules.map(r=>`<span class="law">${r}</span>`).join("")}</div>`}
  </div>`;
}

/* ---------- ramp projection (computed) ---------- */
function rampBars(){
  const perMo=(S.playbook?.economics?.per_acct_mo)||1585, W=26;
  let bars="", labels="";
  for(let w=1;w<=W;w++){
    const funded=Math.max(0,Math.min(20,w-2));            // 1 funded/week from wk3
    const h=Math.round(funded/20*100);
    bars+=`<div class="b future" style="height:${Math.max(3,h)}%;animation-delay:${w*.02}s" title="wk ${w}: ${funded} funded · ~${money(Math.round(funded*perMo))}/mo"></div>`;
  }
  return `<div class="ramp">${bars}</div>
    <div class="ramp-x"><span>WK 1</span><span>1st funded ~wk3</span><span>20 funded ~wk22</span><span>WK 26</span></div>`;
}

/* ---------- VIEWS ---------- */
const head=(ix,title,sub)=>`<div class="head"><h2><span class="ix">${ix}</span>${title}</h2><div class="sub">${sub}</div></div>`;

function vOverview(){
  const pf=S.portfolio||{}, p=S.playbook||{}, ec=p.economics||{};
  const kpis=[
    ["Today",     money(today()),               cls(today()), "realised P&L"],
    ["This week", money(pf.pnl_week),            cls(pf.pnl_week), "running"],
    ["This month",money(pf.pnl_month),           cls(pf.pnl_month), "running"],
    ["Fleet",     `${pf.funded||0}<span style="font-size:13px;color:var(--faint)"> / 20</span>`, "", `${pf.evals||0} in eval · target ~${k(ec.fleet20_mo||31700)}/mo`]
  ];
  return head("01","Overview", `${new Date().toDateString()}<br>APEX 50K · EOD trail · strategy frozen`)
   + `<div class="grid g4" style="margin-bottom:20px">`
   + kpis.map((x,i)=>`<div class="card kpi rise ${i===3&&pf.funded? 'hot':''}" style="animation-delay:${i*.06}s"><div class="lbl">${x[0]}</div><div class="big mono ${x[2]}">${x[1]}</div><div class="meta">${x[3]}</div></div>`).join("")
   + `</div>`
   + campaign(true)
   + `<div class="grid g2" style="margin-top:20px">
        <div class="card rise"><div class="lbl">Projected ramp — 1 funded / week → 20</div>${rampBars()}
          <div class="note">Each new account grinds ~5wk at A4/B2 to the +$2k lock, then scales to A6/B3. Run-rate builds to <b>${k(ec.fleet20_mo||31700)}/mo</b> at full fleet (5-yr avg basis).</div></div>
        <div class="card rise" style="animation-delay:.1s"><div class="lbl">Live status</div>${statusRows().slice(0,4).join("")}
          <div class="note">Full integrity view in <b>Health</b> (06). The bot is fail-closed — a RED feed places no trades.</div></div>
      </div>`;
}
function today(){ if(!CAL) return 0; const t=new Date().toISOString().slice(0,10); return CAL[t]?.pnl||0; }

function vPlaybook(){
  const p=S.playbook||{}, ev=p.eval||{}, f=p.funded||{}, ec=p.economics||{};
  const tl = [["Weeks 0–2","~8 days","pass the eval (~86%)","act"],
              ["Weeks 2–7","~5 weeks","grind A4/B2 → +$2k lock (87%)","act"],
              ["Week 7+","mature","A6/B3 · near-unbustable",""]];
  return head("02","Playbook", "the Apex campaign — frozen & validated<br>real Databento · spray eval / scale funded")
   + campaign(false)
   + `<div class="grid g3" style="margin-top:20px">
        <div class="card rise"><div class="lbl">Eval · spray</div>
          <div class="big mono pos">${ev.pass_pct}%</div><div class="meta">pass · ${ev.bust_pct}% bust · ${ev.expire_pct}% expire</div>
          <div class="note">${ev.size} @ $${ev.stop} stop · median ${ev.median_days}d<br>${ev.note}</div></div>
        <div class="card rise" style="animation-delay:.07s"><div class="lbl">Funded · scale</div>
          <div class="big mono pos">${money(f.income_mo)}</div><div class="meta">/mo blended · ${f.busts}</div>
          <div class="note">${f.phase1} → +$2k floor-lock → ${f.phase2}<br>~${f.lock_days}d to lock · ${f.lock_pct}% reach it</div></div>
        <div class="card rise" style="animation-delay:.14s"><div class="lbl">Momentum</div>
          <div class="big mono">PF 1.83</div><div class="meta">upgraded continuation edge</div>
          <div class="note">${ec.momentum}</div></div>
      </div>
      <div class="card rise" style="margin-top:14px"><div class="lbl">Account lifecycle — eval → lock → mature</div>
        <div class="tl">${tl.map(s=>`<div class="seg ${s[3]}"><div class="w">${s[0]}</div><div class="d">${s[1]}</div><div class="l">${s[2]}</div></div>`).join("")}</div>
        <div class="note">~<b>7 weeks</b> from buying an eval to a mature, near-unbustable A6/B3 account (for the ~87% that clear both stages).</div></div>`;
}

function vFleet(){
  const pf=S.portfolio||{}, perMo=(S.playbook?.economics?.per_acct_mo)||1585;
  let rows="";
  for(let w=3;w<=26;w+=(w<22?1:4)){
    const funded=Math.min(20,w-2), evals=Math.min(2, 20-(funded));
    rows+=`<tr><td>wk ${w}</td><td>${funded}</td><td class="dimt">${funded<20?Math.min(2,20-funded):0}</td><td class="pos">${money(funded*perMo)}</td><td>${funded>=20?'<span class="tag g">FULL</span>':'<span class="tag a">RAMPING</span>'}</td></tr>`;
  }
  return head("03","Fleet", `${pf.funded||0} funded · ${pf.evals||0} in eval<br>target: 20 × 50K accounts`)
   + (pf.total_accounts? "" : `<div class="card rise" style="margin-bottom:16px;border-color:var(--acc-d);box-shadow:inset 0 0 22px var(--acc-glow)">
        <div class="lbl">Pre-deployment</div><div class="big mono">0 live</div>
        <div class="note">No Apex accounts running yet — the eval phase starts the ramp. Below is the <b>projected</b> fleet build at 1 funded account / week.</div></div>`)
   + `<div class="card rise"><div class="lbl">Projected fleet ramp & run-rate</div>
        <table style="margin-top:10px"><tr><th>Week</th><th>Funded</th><th>In eval</th><th>Run-rate /mo</th><th>State</th></tr>${rows}</table>
        <div class="note">5-yr-average basis · partial monthly payouts to the $52,100 safety net · expect materially less live (correlated fleet).</div></div>`;
}

function vTrades(){
  const t=S.trades||[];
  const body = t.length ? `<table><tr><th>Time</th><th>Strat</th><th>Account</th><th>Side</th><th>Entry</th><th>Exit</th><th>R</th><th>$</th><th>Chain</th></tr>`
    + t.slice(0,100).map(x=>`<tr><td>${new Date(x.ts).toLocaleString()}</td><td>${x.strategy}</td><td>${x.account}</td><td>${x.side} ${x.qty}</td><td>${(+x.entry||0).toFixed(2)}</td><td>${(+x.exit||0).toFixed(2)}</td><td class="${cls(x.r)}">${(+x.r||0).toFixed(2)}</td><td class="${cls(x.usd)}">${money(x.usd)}</td><td>${x.chain_ok?'<span class="tag g">✓</span>':'<span class="tag r">✗</span>'}</td></tr>`).join("")+`</table>`
    : `<div class="card rise"><div class="lbl">Ledger empty</div><div class="big mono">0 trades</div><div class="note">No routed Apex trades yet. Every fill will land here, hash-chained and reconstructable from the journal.</div></div>`;
  return head("04","Trades", `${t.length} on record`) + (t.length? `<div class="card rise" style="padding:6px 0">${body}</div>`:body);
}

async function vCalendar(){
  if(!CAL){ try{ CAL=await (await fetch("/api/calendar")).json(); }catch(e){ CAL={}; } }
  const keys=Object.keys(CAL).sort(); const base=keys.length?new Date(keys[keys.length-1]+"T12:00"):new Date();
  if(!CALV) CALV={y:base.getFullYear(),m:base.getMonth()};
  const {y,m}=CALV, p2=n=>String(n).padStart(2,"0"), key=d=>`${y}-${p2(m+1)}-${p2(d)}`;
  const nd=new Date(y,m+1,0).getDate(), sd=new Date(y,m,1).getDay(); let tot=0,tr=0,wn=0;
  let cells="";
  for(let i=0;i<sd;i++) cells+=`<div class="cell pad"></div>`;
  for(let d=1;d<=nd;d++){ const e=CAL[key(d)];
    if(!e){ cells+=`<div class="cell"><span class="dm">${d}</span></div>`; continue; }
    tot+=e.pnl;tr++; if(e.pnl>0)wn++;
    const c=e.pnl>0?"up":e.pnl<0?"dn":"";
    cells+=`<div class="cell ${c}"><span class="dm">${d}</span><span class="tg ${e.mode==='live'?'live':'paper'}">${e.mode==='live'?'LIVE':'PPR'}</span><span class="pl">${money(e.pnl)}</span></div>`;
  }
  const M=["January","February","March","April","May","June","July","August","September","October","November","December"];
  setTimeout(()=>{ $("cprev")&&($("cprev").onclick=()=>{CALV.m--;if(CALV.m<0){CALV.m=11;CALV.y--}renderView();}); $("cnext")&&($("cnext").onclick=()=>{CALV.m++;if(CALV.m>11){CALV.m=0;CALV.y++}renderView();}); },0);
  return head("05",`Calendar`, `${M[m]} ${y}`)
   + `<div class="grid g4" style="margin-bottom:18px">
       <div class="card kpi"><div class="lbl">Month net</div><div class="big mono ${cls(tot)}">${money(tot)}</div></div>
       <div class="card kpi"><div class="lbl">Trading days</div><div class="big mono">${tr}</div></div>
       <div class="card kpi"><div class="lbl">Green days</div><div class="big mono">${tr?Math.round(100*wn/tr):0}%</div></div>
       <div class="card kpi"><div class="lbl">Nav</div><div style="display:flex;gap:8px;margin-top:10px"><button id="cprev" class="pill" style="cursor:pointer">‹ prev</button><button id="cnext" class="pill" style="cursor:pointer">next ›</button></div></div>
      </div>
      <div class="cal" style="margin-bottom:5px">${["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map(d=>`<div class="dow">${d}</div>`).join("")}</div>
      <div class="cal rise">${cells}</div>
      <div class="note">Daily realised P&L · <b>PPR</b> = paper (simulated fills), <b>LIVE</b> = routed orders.</div>`;
}

function statusRows(){
  const d=S.deployment||{}, h=S.header||{}, j=S.journal||{};
  const row=(nm,[c,v],ds)=>`<div class="srow"><span class="dot ${c}"></span><span class="nm">${nm}</span><span class="ds">${ds}</span><span class="tag ${c}">${v}</span></div>`;
  return [
    row("Data feed", d.data_state==="GREEN"?["g","GREEN"]:d.data_state==="YELLOW"?["a","YELLOW"]:["r","RED"], `CME NQ 1m via Chrome · last bar age ${Math.round((d.last_bar_age_s||0))}s`),
    row("Bot / deployment", d.status==="RED"?["r","RED"]:d.green?["g","GREEN"]:["a","ARMED"], d.status_note||`${d.status||"—"} · ${d.data_ready?"data ready":"data not ready"}`),
    row("Execution route", d.traderspost_proven?["g","PROVEN"]:["a","UNPROVEN"], `${d.execution_route||"none"} · webhook ${d.webhook_mode||"—"}`),
    row("Heartbeat", h.heartbeat?["g","ALIVE"]:["r","ABSENT"], h.heartbeat? `last beat ${new Date(h.heartbeat).toLocaleString()}`:"no process heartbeat"),
    row("Journal", j.online?["g","ONLINE"]:["a","IDLE"], `last event ${h.last_journal? new Date(h.last_journal).toLocaleString():"—"}`),
    row("Lockout", h.lockout?["r","LOCKED"]:["g","CLEAR"], h.lockout||"no emergency lockout")
  ];
}
function vHealth(){
  return head("06","Health", "integrity & ops — broker is truth")
   + `<div class="rise">${statusRows().join("")}</div>`
   + `<div class="note">Fail-closed by design: a stale/RED feed places no trades. No control on this terminal can arm trading, modify sizing, or clear a lockout — it is display-only.</div>`;
}

/* ---------- render + nav ---------- */
const VIEWS={overview:vOverview,playbook:vPlaybook,fleet:vFleet,trades:vTrades,calendar:vCalendar,health:vHealth};
async function renderView(){
  const fn=VIEWS[VIEW]; const out=await fn();
  $("v-"+VIEW).innerHTML=out;
}
async function refresh(){
  try{ S=await (await fetch("/api/state")).json(); }catch(e){ return; }
  barStat(); await renderView();
}
document.querySelectorAll(".nv").forEach(b=>b.onclick=()=>{
  document.querySelectorAll(".nv").forEach(x=>x.classList.remove("on"));
  document.querySelectorAll(".view").forEach(x=>x.classList.remove("on"));
  b.classList.add("on"); VIEW=b.dataset.view; $("v-"+VIEW).classList.add("on");
  if(VIEW==="calendar") CAL=null;
  renderView();
  location.hash=VIEW;
});
refresh().then(()=>{ if(location.hash){ const t=document.querySelector(`.nv[data-view="${location.hash.slice(1)}"]`); if(t) t.click(); } });
setInterval(refresh, 30000);
