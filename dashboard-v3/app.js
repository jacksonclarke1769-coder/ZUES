/**
 * ZEUS MISSION DECK — app.js
 * Vanilla ES module, no build toolchain.
 * Three.js vendored at /v3/vendor/three.module.js — DYNAMICALLY imported so a
 * vendor load failure can never prevent this module (and the boot) from running.
 *
 * Data flow: fetch polling → local cache → DOM update.
 * All displayed numbers must trace to a /api/* endpoint.
 *
 * FAILURE-PROOF BOOT (post-incident hardening):
 *  - skip handler bound SYNCHRONOUSLY at script start (before any await)
 *  - every preflight fetch has a 3s timeout; failures paint the phase RED
 *  - a hard 8s watchdog force-completes boot into the deck no matter what
 *  - every JSON parse is guarded (safeJson) — a bad payload marks the source
 *    degraded instead of throwing unhandled
 *  - ALL asset/API paths are ABSOLUTE (/v3/... or /api/...): the page is served
 *    at /v3 (no trailing slash) so relative paths resolve against "/" and hit
 *    the OLD dashboard/ static route. That bug blanked the deck once. Never again.
 */

// ─── STATE ───────────────────────────────────────────────────────────────────
const S = {
  mode: 0,           // 0=OPERATE 1=FLEET 2=ENGINEER 3=ARCHIVE
  state: null,       // /api/state payload
  heartbeat: null,   // /api/heartbeat payload
  validation: null,  // /api/validation payload
  telemetry: null,   // /api/exec_telemetry payload
  forecast: null,    // /api/forecast payload (conditional P(pass))
  degraded: {},      // source → error string (JSON guard / timeout marks these)
  alertAcked: new Set(),
  webglOk: false,
  bootDone: false,
  bootSkipped: false,
  reactor: null,
  raf: null,
  visible: true,
};

// ─── SKIP HANDLER — bound synchronously, FIRST, before any await ─────────────
function _skipBoot() { S.bootSkipped = true; finishBoot(); }
document.addEventListener('keydown', _skipBoot);
// boot-skip pill exists in the DOM already (module script runs after parse)
document.getElementById('boot-skip')?.addEventListener('click', _skipBoot);

// ─── HARD WATCHDOG — deck must appear within 8s no matter what ───────────────
const _bootWatchdog = setTimeout(() => finishBoot(), 8000);

// ─── SAFE FETCH: timeout + guarded JSON parse ────────────────────────────────
async function safeJson(url, timeoutMs = 3000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { signal: ctrl.signal });
    const text = await r.text();
    try {
      const data = JSON.parse(text);
      return { ok: r.ok, status: r.status, data, error: r.ok ? null : `HTTP ${r.status}` };
    } catch {
      return { ok: false, status: r.status, data: null,
               error: `non-JSON response (HTTP ${r.status}) from ${url}` };
    }
  } catch (e) {
    return { ok: false, status: 0, data: null,
             error: e.name === 'AbortError' ? `timeout ${timeoutMs}ms: ${url}` : String(e) };
  } finally {
    clearTimeout(timer);
  }
}

// mark/clear a degraded data source (never throw on bad data)
function markSource(key, res) {
  if (res.ok) delete S.degraded[key];
  else S.degraded[key] = res.error;
  return res.ok;
}

// ─── FINISH BOOT — idempotent; the ONLY path into the deck ───────────────────
function finishBoot() {
  if (S.bootDone) return;
  S.bootDone = true;
  clearTimeout(_bootWatchdog);
  document.removeEventListener('keydown', _skipBoot);

  const bootEl = document.getElementById('boot');
  bootEl.style.transition = 'opacity .4s';
  bootEl.style.opacity = '0';
  setTimeout(() => { bootEl.style.display = 'none'; }, 450);

  document.getElementById('app').style.display = 'grid';

  // Post-boot init — everything here is guarded; a data problem must NEVER
  // leave the operator staring at black.
  try { startClock(); } catch (e) { console.warn('clock init failed', e); }
  try { startPolling(); } catch (e) { console.warn('polling init failed', e); }
  initThreeJS().then(r => { S.reactor = r; }).catch(e => {
    console.warn('3D init failed:', e);
    document.getElementById('webgl-fallback')?.classList.add('visible');
  });
}

// ─── BOOT SEQUENCE ────────────────────────────────────────────────────────────
const SAME_DAY_KEY = 'zeus_v3_boot_date';
const BOOT_PHASES = [
  { label: 'Feed',       endpoint: '/api/heartbeat',      key: 'heartbeat' },
  { label: 'Read-back',  endpoint: '/api/state',          key: 'state' },
  { label: 'Risk',       endpoint: '/api/state',          key: 'state' },
  { label: 'Guardian',   endpoint: '/api/state',          key: 'state' },
  { label: 'Dead-man',   endpoint: '/api/heartbeat',      key: 'heartbeat' },
  { label: 'Telemetry',  endpoint: '/api/exec_telemetry', key: 'telemetry' },
];

async function runBoot() {
  const logEl  = document.getElementById('boot-log');
  const certEl = document.getElementById('boot-certified');
  const boltPath = document.getElementById('bolt-path');
  const bootBolt = document.getElementById('boot-bolt');

  // Same-day revisit — shorten boot
  const today = new Date().toISOString().slice(0, 10);
  const fast = localStorage.getItem(SAME_DAY_KEY) === today;
  localStorage.setItem(SAME_DAY_KEY, today);

  const delay = ms => new Promise(r =>
    (fast || S.bootSkipped || S.bootDone) ? r() : setTimeout(r, ms));

  // Animate bolt glyph
  bootBolt.style.opacity = '1';
  boltPath.style.transition = 'stroke-dashoffset .8s ease-out';
  requestAnimationFrame(() => { boltPath.style.strokeDashoffset = '0'; });

  await delay(fast ? 50 : 900);

  // Phase preflight loop — each phase REALLY pings its endpoint (3s timeout).
  // Failure paints RED and moves on; it never hangs the boot.
  for (const phase of BOOT_PHASES) {
    if (S.bootSkipped || S.bootDone) break;
    const line = document.createElement('div');
    line.textContent = `[ .. ]  ${phase.label}`;
    logEl.appendChild(line);
    const res = await safeJson(phase.endpoint, 3000);
    markSource(phase.key, res);
    if (res.ok) {
      line.innerHTML = `<span class="ok">[ OK ]</span>  ${phase.label}`;
      // cache what we fetched so the deck paints instantly after boot
      if (phase.key === 'state') S.state = res.data;
      if (phase.key === 'heartbeat') S.heartbeat = res.data;
      if (phase.key === 'telemetry') S.telemetry = res.data;
    } else {
      line.innerHTML = `<span class="err">[FAIL]</span>  ${phase.label} — ${res.error}`;
    }
    await delay(fast ? 10 : 300);
  }

  // Certified line from /api/validation (guarded)
  if (!S.bootSkipped && !S.bootDone) {
    const vr = await safeJson('/api/validation', 3000);
    if (markSource('validation', vr)) S.validation = vr.data;
    const ver = S.validation?.dll_recert_selected_machine?.verified
             || S.validation?.verified;
    certEl.textContent = ver
      ? `ZEUS MISSION DECK  ·  CERTIFIED ${ver}`
      : 'ZEUS MISSION DECK  ·  CERTIFICATION UNAVAILABLE';
    certEl.style.opacity = '1';
    if (!ver) certEl.style.color = 'var(--amber)';
    await delay(fast ? 50 : 700);
  }

  finishBoot();
}

// ─── ET CLOCK ─────────────────────────────────────────────────────────────────
function startClock() {
  const el = document.getElementById('spine-clock');
  const tick = () => {
    const et = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit',
      second: '2-digit', hour12: false,
    }).format(new Date());
    el.textContent = `ET ${et}`;
  };
  tick();
  setInterval(tick, 1000);
}

// ─── ODOMETER ─────────────────────────────────────────────────────────────────
const _odoCache = new Map();
function odo(el, val) {
  if (!(el instanceof Element)) return;
  const key = el.dataset.odoKey || (el.dataset.odoKey = Math.random().toString(36).slice(2));
  if (_odoCache.get(key) === val) return;
  _odoCache.set(key, val);
  el.textContent = val;
  el.classList.remove('roll');
  void el.offsetWidth; // reflow
  el.classList.add('roll');
}

// ─── MODE SWITCHING ───────────────────────────────────────────────────────────
function setMode(m) {
  S.mode = m;
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.toggle('active', +b.dataset.mode === m));
  document.querySelectorAll('.spine-dot').forEach(d => d.classList.toggle('active', +d.dataset.mode === m));
  document.querySelectorAll('.mode-view').forEach(v => v.classList.toggle('active', +v.dataset.modeView === m));
}

// ─── FORMAT HELPERS ──────────────────────────────────────────────────────────
const fmt$ = v => (v == null ? '—' : `$${v >= 0 ? '' : '-'}${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
const fmtPts = v => (v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}pts`);

// ─── SPINE UPDATE ────────────────────────────────────────────────────────────
function updateSpine(st, hb) {
  if (!st) return;
  const mode = st.meta?.mode || 'SIM';
  const modeEl = document.getElementById('spine-mode');
  modeEl.textContent = mode;
  modeEl.className = mode === 'LIVE' ? 'live' : mode === 'PAPER' ? 'paper' : 'sim';

  const verEl = document.getElementById('spine-ver');
  const ver = S.validation?.dll_recert_selected_machine?.verified || S.validation?.verified;
  verEl.textContent = ver ? `v${ver}` : 'v—';

  document.getElementById('spine-runner').textContent = st.meta?.mode || '—';

  const feedEl = document.getElementById('spine-feed');
  if (S.degraded.heartbeat) {
    feedEl.textContent = 'DEGRADED';
    feedEl.className = 'red';
    feedEl.title = S.degraded.heartbeat;
  } else {
    const dataState = hb?.data_state || (hb?.data_ready ? 'GREEN' : 'RED');
    feedEl.textContent = dataState || '—';
    feedEl.className = (dataState === 'GREEN') ? 'green' : 'red';
    feedEl.title = '';
  }

  const hbEl = document.getElementById('spine-heartbeat');
  if (S.degraded.heartbeat || !hb || hb.freshness_s == null) {
    hbEl.textContent = 'DEAD';
    hbEl.className = 'dead';
  } else {
    hbEl.textContent = `${hb.freshness_s}s`;
    hbEl.className = hb.stale ? 'dead' : hb.freshness_s < 30 ? 'fresh' : 'stale';
  }

  const accts = st.accounts || [];
  document.getElementById('spine-account').textContent = accts.length
    ? accts.map(a => a.name?.replace('APEX-50K-', '')).join(' · ')
    : '—';
}

// ─── FLEET BAYS (left rail, operate mode) ────────────────────────────────────
// ─── ACTIVE EVAL MISSION ─────────────────────────────────────────────────────
function updateMission(c) {
  const el = document.getElementById('mission-body');
  const dot = document.getElementById('dot-mission');
  if (!el) return;
  if (!c || c.active === false) {
    el.innerHTML = '<div class="dimmed small mono">No active campaign</div>';
    if (dot) dot.className = 'ph-dot';
    return;
  }
  const money = n => '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  const bal = c.current_balance, start = c.start_balance || 50000;
  const prog = Math.max(0, Math.min(100, ((bal - start) / ((c.target_balance || 53000) - start)) * 100));
  const cushion = c.cushion ?? 0;
  const cushClass = cushion > 1500 ? 'green' : cushion > 800 ? 'amber' : 'green';
  const live = c.balance_source === 'live';
  const days = c.days_left;
  const daysClass = days == null ? '' : days > 10 ? '' : days > 4 ? 'amber' : 'amber';
  if (dot) dot.className = 'ph-dot g';
  const check = (c.checklist || []).map(item => {
    const done = /done|✓/i.test(item);
    return `<li class="${done ? 'done' : ''}"><span class="box">${done ? '☑' : '☐'}</span><span>${item.replace(/\s*\(done\)/i, '')}</span></li>`;
  }).join('');
  el.innerHTML = `
    <div class="msn-status">${c.status || ''}</div>
    <div class="msn-grid">
      <div class="msn-cell"><span class="l">Balance</span><span class="v gold">${money(bal)}</span></div>
      <div class="msn-cell"><span class="l">To pass (+)</span><span class="v">${money(c.to_pass)}</span></div>
      <div class="msn-cell"><span class="l">Cushion → floor</span><span class="v ${cushClass}">${money(cushion)}</span></div>
      <div class="msn-cell"><span class="l">Days left</span><span class="v ${daysClass}">${days == null ? '—' : days + 'd'}</span></div>
    </div>
    <div class="msn-bar"><i style="width:${prog.toFixed(0)}%"></i></div>
    <div class="msn-src">${c.firm || 'Apex'} 50K · ${c.machine || ''} · balance <b>${live ? 'LIVE read-back' : 'operator-confirmed ' + (c.balance_asof || '')}</b></div>
    <ul class="msn-check">${check}</ul>`;
}

function updateForecast(f) {
  const el = document.getElementById('forecast-body');
  const dot = document.getElementById('dot-forecast');
  if (!el) return;
  if (!f || f.available === false) {
    el.innerHTML = `<div class="dimmed small mono">${f && f.note ? f.note : 'forecast unavailable'}</div>`;
    if (dot) dot.className = 'ph-dot';
    return;
  }
  // colour the pass number by the dominant-failure-mode level
  const lvlClass = { pass: 'green', tight: 'amber', bust: 'red', marginal: 'amber' }[f.level] || '';
  if (dot) dot.className = 'ph-dot ' + (f.level === 'pass' ? 'g' : f.level === 'bust' ? 'r' : 'b');
  const pct = v => (v == null ? '—' : v.toFixed(1) + '%');
  // compact single-line slip warning (full table lives in tools_eval_forecast.py)
  const s10 = (f.sensitivity || []).find(s => Math.abs(s.slip_r - 0.10) < 1e-6);
  const slipLine = s10
    ? `0.10R slip → ${pct(s10.pass_pct)} pass · ${pct(s10.bust_pct)} bust`
    : '';
  el.innerHTML = `
    <div class="fc-head">
      <div class="fc-big ${lvlClass}">${pct(f.pass_pct)}<span class="fc-lbl">P(pass)</span></div>
      <div class="fc-vs">vs <b>${f.certified_pass}%</b> certified<br><span class="dimmed small">fresh-start</span></div>
    </div>
    <div class="fc-grid">
      <div class="fc-cell"><span class="l">Bust</span><span class="v red">${pct(f.bust_pct)}</span></div>
      <div class="fc-cell"><span class="l">Expire</span><span class="v amber">${pct(f.expire_pct)}</span></div>
      <div class="fc-cell"><span class="l">Median→target</span><span class="v">${f.median_days_to_pass == null ? '—' : f.median_days_to_pass + 'd'}</span></div>
      <div class="fc-cell"><span class="l">Days left</span><span class="v">${f.days_left == null ? '—' : f.days_left + 'd'}</span></div>
    </div>
    <div class="fc-verdict ${f.level}">${f.verdict || ''}</div>
    <div class="fc-slip">⚠ ${slipLine}</div>`;
}

function updateFleet(st) {
  const accts = st?.accounts || [];
  const fleetEl = document.getElementById('fleet-body');
  const dotEl = document.getElementById('dot-accounts');

  if (accts.length === 0) {
    fleetEl.innerHTML = '<div class="dimmed small mono">No accounts registered</div>';
    dotEl.className = 'ph-dot';
    return;
  }

  const allSafe = accts.every(a => a.status === 'SAFE');
  dotEl.className = 'ph-dot ' + (allSafe ? 'g' : 'a');

  fleetEl.innerHTML = accts.map(a => {
    const bal = a.balance ?? 0;
    const floor = a.floor ?? 0;
    const cushion = bal - floor;
    const cushPct = a.dd ? Math.max(0, Math.min(100, 100 * cushion / a.dd)) : 0;
    const phase = a.phase || 'EVAL';
    const isEval = phase === 'EVAL';
    const statusCls = a.status === 'SAFE' ? 'green' : a.status === 'WARNING' ? 'amber' : 'red';
    return `
      <div class="bay">
        <div class="bay-title" title="${a.name}">${a.name?.replace('APEX-50K-', '') || a.name}</div>
        <div class="kv">
          <span class="kv-k">Phase</span>
          <span class="kv-v ${statusCls}">${phase}</span>
        </div>
        <div class="kv">
          <span class="kv-k">Balance</span>
          <span class="kv-v">${fmt$(bal)}</span>
        </div>
        <div class="kv">
          <span class="kv-k">Cushion</span>
          <span class="kv-v ${cushion < 500 ? 'red' : cushion < 1500 ? 'amber' : 'green'}">${fmt$(cushion)}</span>
        </div>
        <div class="bay-prog-outer">
          <div class="bay-prog-inner ${isEval ? 'eval' : ''}" style="width:${cushPct.toFixed(1)}%"></div>
        </div>
      </div>`;
  }).join('');
}

// ─── EVAL PIPELINE ────────────────────────────────────────────────────────────
function updateEval(st) {
  const ev = st?.playbook?.eval;
  const el = document.getElementById('eval-body');
  if (!ev) { el.innerHTML = '<div class="dimmed small mono">No eval data</div>'; return; }

  const accts = (st?.accounts || []).filter(a => a.phase === 'EVAL');

  el.innerHTML = `
    <div class="kv">
      <span class="kv-k">Config</span>
      <span class="kv-v blue small">${ev.size || '—'}</span>
    </div>
    <div class="kv">
      <span class="kv-k">Pass rate</span>
      <span class="kv-v green">${ev.pass_pct != null ? ev.pass_pct + '%' : '—'}</span>
    </div>
    <div class="kv">
      <span class="kv-k">Bust rate</span>
      <span class="kv-v amber">${ev.bust_pct != null ? ev.bust_pct + '%' : '—'}</span>
    </div>
    <div class="kv">
      <span class="kv-k">Median days</span>
      <span class="kv-v">${ev.median_days != null ? ev.median_days + 'd' : '—'}</span>
    </div>
    ${accts.map(a => {
      const bal = a.balance ?? 50000;
      const prog = Math.max(0, Math.min(100, 100 * (bal - 50000) / 3000));
      return `
        <div style="margin-top:6px">
          <div class="dimmed small mono" style="margin-bottom:3px">${a.name?.replace('APEX-50K-', '') || a.name} → $3k target</div>
          <div class="bay-prog-outer">
            <div class="bay-prog-inner eval" style="width:${prog.toFixed(1)}%"></div>
          </div>
          <div class="kv" style="margin-top:2px">
            <span class="kv-k">Progress</span>
            <span class="kv-v blue">${fmt$(bal - 50000)} / $3,000</span>
          </div>
        </div>`;
    }).join('')}
  `;
}

// ─── EDGE HEALTH ─────────────────────────────────────────────────────────────
function updateEdge(st) {
  const strats = st?.strategies || {};
  const el = document.getElementById('edge-body');
  const dotEl = document.getElementById('dot-edge');
  if (!strats.A && !strats.B) {
    el.innerHTML = '<div class="dimmed small mono">No trade history</div>';
    return;
  }
  const healthClass = h => ({ 'FULL STRENGTH': 'green', 'WATCHING': 'amber', 'DEGRADED': 'amber', 'CRITICAL': 'red', 'HALTED': 'red' }[h] || 'dim');
  // v2026.07.02 machine: Profile A is the ONLY production lane. B's monitor may still report
  // (research telemetry) but must never read as an active edge — render it OFF, exclude from health.
  const hs = ['A'].map(k => strats[k]?.health || 'HALTED');
  const worst = hs.includes('HALTED') || hs.includes('CRITICAL') ? 'r'
              : hs.includes('DEGRADED') || hs.includes('WATCHING') ? 'a' : 'g';
  dotEl.className = 'ph-dot ' + worst;

  el.innerHTML = ['A', 'B'].map(k => {
    const s = strats[k];
    if (!s) return '';
    if (k === 'B') return `
      <div class="kv">
        <span class="kv-k">Profile B</span>
        <span class="kv-v dimmed">OFF — not in machine</span>
      </div>`;
    const tot = s.total;
    return `
      <div class="kv">
        <span class="kv-k">Profile ${k}</span>
        <span class="kv-v ${healthClass(s.health)}">${s.health}</span>
      </div>
      ${s.vs_validation != null ? `
      <div class="kv">
        <span class="kv-k">vs validation</span>
        <span class="kv-v ${s.vs_validation >= 90 ? 'green' : s.vs_validation >= 70 ? 'amber' : 'red'}">${s.vs_validation}%</span>
      </div>` : ''}
      ${tot ? `
      <div class="kv">
        <span class="kv-k">Trades</span>
        <span class="kv-v">${tot.n}</span>
      </div>
      <div class="kv">
        <span class="kv-k">WR</span>
        <span class="kv-v">${tot.wr}%</span>
      </div>
      <div class="kv">
        <span class="kv-k">PF</span>
        <span class="kv-v ${tot.pf >= 1.2 ? 'green' : tot.pf >= 1 ? 'amber' : 'red'}">${tot.pf ?? '—'}</span>
      </div>` : ''}
    `;
  }).join('<div style="height:4px"></div>');
}

// ─── RISK THERMOMETER ────────────────────────────────────────────────────────
function updateThermo(st) {
  const port = st?.portfolio || {};
  const today_usd = port.today_usd ?? 0;
  const dll = 1000;

  const pnlEl = document.getElementById('thermo-pnl');
  odo(pnlEl, fmt$(today_usd));
  pnlEl.className = today_usd >= 0 ? 'pos' : 'neg';

  const lossPct = Math.max(0, Math.min(100, (-today_usd / dll) * 100));
  const fillEl = document.getElementById('thermo-fill');
  fillEl.style.width = lossPct + '%';
  fillEl.style.background = lossPct > 55 ? 'var(--red)' : lossPct > 30 ? 'var(--amber)' : 'var(--green)';

  const accts = st?.accounts || [];
  let minFloorDist = null;
  for (const a of accts) {
    if (a.balance != null && a.floor != null) {
      const d = a.balance - a.floor;
      if (minFloorDist == null || d < minFloorDist) minFloorDist = d;
    }
  }
  const floorEl = document.getElementById('thermo-floor');
  odo(floorEl, minFloorDist != null ? fmt$(minFloorDist) : '—');
  floorEl.className = 'kv-v' + (minFloorDist != null && minFloorDist < 500 ? ' red' : minFloorDist != null && minFloorDist < 1500 ? ' amber' : ' green');

  document.getElementById('dot-thermo').className =
    'ph-dot ' + (lossPct > 55 ? 'r' : lossPct > 30 ? 'a' : 'g');
}

// ─── POSITIONS ────────────────────────────────────────────────────────────────
function updatePositions(st) {
  const accts = st?.accounts || [];
  const el = document.getElementById('positions-body');
  const dotEl = document.getElementById('dot-pos');
  const openAccts = accts.filter(a => (a.open_qty || 0) > 0);
  if (!openAccts.length) {
    el.innerHTML = '<div class="dimmed small mono">No open positions</div>';
    dotEl.className = 'ph-dot';
    return;
  }
  dotEl.className = 'ph-dot b';
  el.innerHTML = openAccts.map(a => {
    const side = (a.open_side || 'LONG').toLowerCase();
    return `
      <div class="pos-row">
        <span class="mono small">${a.name?.split('-').pop() || a.name}</span>
        <span class="pr-side ${side}">${side.toUpperCase()}</span>
        <span class="mono small">${a.open_qty}q</span>
        <span class="mono small ${(a.unrealized_usd ?? 0) >= 0 ? 'green' : 'red'}">${fmt$(a.unrealized_usd ?? 0)}</span>
      </div>`;
  }).join('');
}

// ─── RECENT SIGNALS ──────────────────────────────────────────────────────────
function updateSignals(st) {
  const trades = (st?.trades || []).slice(0, 5);
  const el = document.getElementById('signals-body');
  if (!trades.length) {
    el.innerHTML = '<div class="dimmed small mono">No recent signals</div>';
    return;
  }
  el.innerHTML = trades.map(t => {
    const dt = new Date(t.ts);
    const timeStr = dt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'America/New_York' });
    const pnl = t.usd != null ? (t.usd >= 0 ? `<span class="green">+${t.usd.toFixed(0)}</span>` : `<span class="red">${t.usd.toFixed(0)}</span>`) : '<span class="dimmed">open</span>';
    return `
      <div class="kv">
        <span class="kv-k mono small">${timeStr} ${t.strategy || '?'}</span>
        <span class="kv-v">${pnl}</span>
      </div>`;
  }).join('');
}

// ─── SAFETY LIGHTS ────────────────────────────────────────────────────────────
function updateSafety(st) {
  const lights = st?.lights || {};
  const el = document.getElementById('safety-body');
  const dotEl = document.getElementById('dot-safety');
  // 'off' = deliberately-inactive lane (Profile B under the v2026.07.02 machine): dim, and
  // EXCLUDED from health aggregation — off is not a fault.
  const vals = Object.values(lights).filter(v => v !== 'off');
  const allGreen = vals.length && vals.every(v => v === 'green');
  dotEl.className = 'ph-dot ' + (allGreen ? 'g' : vals.some(v => v === 'red') ? 'r' : 'a');
  el.innerHTML = Object.entries(lights).map(([k, v]) => `
    <div class="kv">
      <span class="kv-k">${k}</span>
      <span class="kv-v ${v === 'off' ? 'dimmed' : v === 'green' ? 'green' : v === 'yellow' ? 'amber' : 'red'}">${v.toUpperCase()}</span>
    </div>`).join('') || '<div class="dimmed small mono">No lights data</div>';
}

// ─── FLEET ECONOMICS (fleet mode) ────────────────────────────────────────────
function updateEconomics(st) {
  const econ = st?.playbook?.economics || {};
  document.getElementById('economics-body').innerHTML = `
    <div class="kv">
      <span class="kv-k">Per funded acct/mo</span>
      <span class="kv-v gold">${fmt$(econ.per_acct_mo)}</span>
    </div>
    <div class="kv">
      <span class="kv-k">Fleet 20 model/mo</span>
      <span class="kv-v">${fmt$(econ.fleet20_mo)}</span>
    </div>
    <div class="kv">
      <span class="kv-k">Eval → mature</span>
      <span class="kv-v">${econ.eval_to_mature_wk != null ? econ.eval_to_mature_wk + 'wk' : '—'}</span>
    </div>
    <div class="kv">
      <span class="kv-k">Momentum</span>
      <span class="kv-v small dimmed">${econ.momentum || '—'}</span>
    </div>
  `;
}

// ─── WEEKLY P&L (fleet mode) ─────────────────────────────────────────────────
function updateWeekly(st) {
  const wk = st?.weekly || {};
  const weeks = wk.weeks || [];
  document.getElementById('weekly-body').innerHTML = `
    <div class="kv">
      <span class="kv-k">This week</span>
      <span class="kv-v ${(wk.current || 0) >= 0 ? 'green' : 'red'}">${fmtPts(wk.current)}</span>
    </div>
    <div class="kv">
      <span class="kv-k">Last week</span>
      <span class="kv-v">${fmtPts(wk.last)}</span>
    </div>
    <div class="kv">
      <span class="kv-k">4wk avg</span>
      <span class="kv-v">${fmtPts(wk.avg4)}</span>
    </div>
    <div class="kv">
      <span class="kv-k">12wk avg</span>
      <span class="kv-v">${fmtPts(wk.avg12)}</span>
    </div>
    ${weeks.slice(0, 6).map(w => `
      <div class="kv small">
        <span class="kv-k mono">${w.week}</span>
        <span class="kv-v ${(w.total || 0) >= 0 ? 'green' : 'red'} small">${fmtPts(w.total)}</span>
      </div>`).join('')}
  `;
}

// ─── PAYOUTS (fleet mode) ────────────────────────────────────────────────────
function updatePayouts(st) {
  const accts = (st?.accounts || []).filter(a => a.phase === 'FUNDED');
  const el = document.getElementById('payouts-body');
  if (!accts.length) {
    el.innerHTML = '<div class="dimmed small mono">No funded accounts</div>';
    return;
  }
  el.innerHTML = accts.map(a => `
    <div class="kv">
      <span class="kv-k">${a.name?.replace('APEX-50K-', '') || a.name}</span>
      <span class="kv-v gold">${fmt$(a.paid || 0)} paid</span>
    </div>`).join('');
}

// ─── RECON (fleet mode) ──────────────────────────────────────────────────────
function updateRecon(st) {
  const recon = st?.recon || {};
  const dotEl = document.getElementById('dot-recon');
  const ok = !recon.unknown_positions && !recon.unknown_fills && !recon.naked_alerts;
  dotEl.className = 'ph-dot ' + (ok ? 'g' : 'r');
  document.getElementById('recon-body').innerHTML = `
    <div class="kv">
      <span class="kv-k">Unknown positions</span>
      <span class="kv-v ${recon.unknown_positions ? 'red' : 'green'}">${recon.unknown_positions ?? 0}</span>
    </div>
    <div class="kv">
      <span class="kv-k">Unknown fills</span>
      <span class="kv-v ${recon.unknown_fills ? 'red' : 'green'}">${recon.unknown_fills ?? 0}</span>
    </div>
    <div class="kv">
      <span class="kv-k">Naked alerts</span>
      <span class="kv-v ${recon.naked_alerts ? 'amber' : 'green'}">${recon.naked_alerts ?? 0}</span>
    </div>
  `;
}

// ─── EXEC TELEMETRY (engineer mode) ──────────────────────────────────────────
function updateTelemetry(telem) {
  const el = document.getElementById('telemetry-body');
  if (S.degraded.telemetry) {
    el.innerHTML = `<div class="small mono" style="color:var(--red)">TELEMETRY DEGRADED — ${S.degraded.telemetry}</div>`;
    return;
  }
  if (!telem) { el.innerHTML = '<div class="dimmed small mono">Loading…</div>'; return; }
  if (!telem.rows?.length) {
    el.innerHTML = '<div class="dimmed small mono">No telemetry recorded yet</div>';
    return;
  }
  const rows = telem.rows.slice(-20);
  const latencies = rows.map(r => parseFloat(r.latency_ms || 0)).filter(v => !isNaN(v));
  const maxLat = latencies.length ? Math.max(...latencies) : 1;
  el.innerHTML = `
    <div class="kv">
      <span class="kv-k">Records</span>
      <span class="kv-v">${telem.count}</span>
    </div>
    <div style="margin-top:8px">
      ${rows.map(r => {
        const lat = parseFloat(r.latency_ms || 0);
        const pct = Math.min(100, (lat / Math.max(maxLat, 1)) * 100);
        return `
          <div class="kv small">
            <span class="kv-k mono">${r.ts?.slice(11, 19) || '—'}</span>
            <span class="kv-v">${lat.toFixed(0)}ms</span>
          </div>
          <div class="latency-bar" style="width:${pct.toFixed(0)}%;margin-bottom:2px"></div>`;
      }).join('')}
    </div>
  `;
}

// ─── D1c KEEP-RATE (engineer mode) ────────────────────────────────────────────
function updateD1c(st) {
  const cand = st?.regime_monitor?.d1c_candidate;
  const shadow = st?.regime_monitor?.d1c_shadow;
  document.getElementById('d1c-body').innerHTML = `
    ${cand ? `
      <div class="kv">
        <span class="kv-k">Keep PF</span>
        <span class="kv-v green">${cand.keep_pf ?? '—'}</span>
      </div>
      <div class="kv">
        <span class="kv-k">Drop PF</span>
        <span class="kv-v red">${cand.drop_pf ?? '—'}</span>
      </div>
      <div class="kv">
        <span class="kv-k">Keep rate</span>
        <span class="kv-v blue">${cand.validated_keep_rate ?? '—'}%</span>
      </div>
      <div class="kv">
        <span class="kv-k">Status</span>
        <span class="kv-v amber small">${cand.paper_only ? 'PAPER ONLY' : 'PRODUCTION'}</span>
      </div>` : '<div class="dimmed small mono">No D1c data</div>'}
    ${shadow ? `
      <div class="kv" style="margin-top:4px">
        <span class="kv-k">Shadow state</span>
        <span class="kv-v">${shadow.state || '—'}</span>
      </div>
      <div class="kv">
        <span class="kv-k">Decisions</span>
        <span class="kv-v">${shadow.total ?? '—'}</span>
      </div>` : ''}
  `;
}

// ─── ARCHIVE (archive mode) ──────────────────────────────────────────────────
function updateArchive(val) {
  if (!val) return;
  const el = document.getElementById('archive-body');
  const archLeft = document.getElementById('caveats-body');

  // Invalidated/superseded entries — the honesty wall. Handles both shapes:
  // string notes (e.g. _INVALIDATED_2026-07-02 is a prose audit note) and
  // object blocks with a reason field. Also surfaces _SUPERSEDED_* sub-keys.
  const hist = [];
  for (const [k, v] of Object.entries(val)) {
    if (k.startsWith('_INVALIDATED')) {
      hist.push({ key: k.replace(/^_/, ''), reason: typeof v === 'string' ? v : (v?.reason || JSON.stringify(v)) });
    }
    if (v && typeof v === 'object') {
      for (const [sk, sv] of Object.entries(v)) {
        if (sk.startsWith('_SUPERSEDED')) {
          hist.push({ key: k, reason: typeof sv === 'string' ? sv : JSON.stringify(sv) });
        }
      }
    }
  }
  if (val.retired_fabrications) {
    hist.push({ key: 'retired_fabrications',
                reason: val.retired_fabrications.reason || JSON.stringify(val.retired_fabrications) });
  }

  const certs = [
    { key: 'dll_recert_selected_machine', label: 'DLL Recert (deployed)', data: val.dll_recert_selected_machine },
    { key: 'funded_40_recert', label: 'Funded 40 Recert', data: val.funded_40_recert },
    { key: 'recert_1m_truth', label: '1m Truth Recert', data: val.recert_1m_truth },
  ].filter(c => c.data);

  el.innerHTML = certs.map(c => `
    <div class="kv">
      <span class="kv-k small">${c.label}</span>
      <span class="kv-v green small">${c.data?.verified || '—'}</span>
    </div>
    <div class="dimmed small mono" style="margin-bottom:4px">${Array.isArray(c.data?.harness) ? c.data.harness.join(', ') : c.data?.harness || ''}</div>
  `).join('');

  archLeft.innerHTML = hist.length ? hist.map(h => `
    <div style="margin-bottom:8px">
      <div class="strike">${h.key}</div>
      <div class="invalid-badge">INVALIDATED</div>
      <div class="dimmed small mono" style="margin-top:2px">${(h.reason || '').slice(0, 220)}</div>
    </div>
  `).join('') : '<div class="dimmed small mono">No invalidated entries</div>';
}

// ─── ALERTS ──────────────────────────────────────────────────────────────────
function updateAlerts(st) {
  const alerts = st?.alerts || [];
  const tray = document.getElementById('alert-tray');
  const dimEl = document.getElementById('room-dim');
  const bannerEl = document.getElementById('red-banner');

  const sevAlerts = alerts.filter(a => a.tier !== 'GREEN' && !S.alertAcked.has(a.name));
  tray.innerHTML = sevAlerts.slice(0, 6).map(a => {
    const cls = a.tier === 'BLACK' || a.tier === 'RED' ? 'red' : 'amber';
    return `<div class="alert-pill ${cls}" title="Click to acknowledge" data-name="${a.name}">[${a.tier}] ${a.name}: ${a.detail || ''}</div>`;
  }).join('');

  tray.querySelectorAll('.alert-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const name = pill.dataset.name;
      S.alertAcked.add(name);
      fetch('/api/ack', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, note: 'ack via v3 dashboard' }) }).catch(() => {});
      pill.remove();
    });
  });

  const hasRed = sevAlerts.some(a => a.tier === 'RED' || a.tier === 'BLACK');
  dimEl.classList.toggle('active', hasRed);
  if (hasRed) {
    const redA = sevAlerts.find(a => a.tier === 'RED' || a.tier === 'BLACK');
    const action = st?.actions?.[0] || 'Review alert — consult playbook';
    bannerEl.textContent = `[${redA.tier}] ${redA.name} — ${action}`;
    bannerEl.classList.add('active');
  } else {
    bannerEl.classList.remove('active');
  }
}

// ─── FLIGHT DECK ─────────────────────────────────────────────────────────────
function updateDeck(st) {
  const activity = st?.activity || [];
  const deckEl = document.getElementById('deck');
  const emptyEl = document.getElementById('deck-empty');

  if (!activity.length) {
    emptyEl.style.display = '';
    return;
  }
  emptyEl.style.display = 'none';
  deckEl.querySelectorAll('.deck-event').forEach(e => e.remove());

  activity.forEach(ev => {
    const div = document.createElement('div');
    div.className = 'deck-event';
    const dt = new Date(ev.ts || Date.now());
    const timeStr = dt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'America/New_York' });
    const text = ev.text || '';
    const cls = text.includes('Filled') ? 'fill' : text.includes('closed') ? 'exit' : text.includes('Alert') ? 'alert' : '';
    div.innerHTML = `<div class="de-time">${timeStr} ET</div><div class="de-text ${cls}">${text}</div>`;
    deckEl.appendChild(div);
  });
}

// ─── MASTER UPDATE — each panel guarded so one bad payload can't blank all ───
function updateAll() {
  const st = S.state;
  if (!st) return;
  const painters = [
    () => updateSpine(st, S.heartbeat),
    () => updateMission(S.campaign),
    () => updateForecast(S.forecast),
    () => updateFleet(st),
    () => updateEval(st),
    () => updateEdge(st),
    () => updateThermo(st),
    () => updatePositions(st),
    () => updateSignals(st),
    () => updateSafety(st),
    () => updateEconomics(st),
    () => updateWeekly(st),
    () => updatePayouts(st),
    () => updateRecon(st),
    () => updateTelemetry(S.telemetry),
    () => updateD1c(st),
    () => updateAlerts(st),
    () => updateDeck(st),
    () => { if (S.validation) updateArchive(S.validation); },
  ];
  for (const p of painters) {
    try { p(); } catch (e) { console.warn('panel paint failed:', e); }
  }
  if (S.webglOk && S.reactor) {
    try { S.reactor.onDataUpdate(st, S.heartbeat, S.campaign); } catch (e) { console.warn('3D update failed:', e); }
  }
}

// ─── DATA FETCHING (guarded; a bad source degrades, never throws) ────────────
async function fetchAll() {
  const [sr, hr, tr, cr, fr] = await Promise.all([
    safeJson('/api/state', 4000),
    safeJson('/api/heartbeat', 3000),
    safeJson('/api/exec_telemetry', 3000),
    safeJson('/api/campaign', 3000),
    safeJson('/api/forecast', 4000),
  ]);
  if (markSource('state', sr)) S.state = sr.data;
  if (markSource('heartbeat', hr)) S.heartbeat = hr.data;
  if (markSource('telemetry', tr)) S.telemetry = tr.data;
  if (markSource('campaign', cr)) S.campaign = cr.data;
  if (markSource('forecast', fr)) S.forecast = fr.data;
  if (!S.validation) {
    const vr = await safeJson('/api/validation', 3000);
    if (markSource('validation', vr)) S.validation = vr.data;
  }
  updateAll();
}

// ─── 3D REACTOR — three.js is DYNAMICALLY imported (absolute path) so its
//     failure can never take the whole module (and the boot) down with it. ────
async function initThreeJS() {
  const canvas = document.getElementById('canvas-3d');
  const fallback = document.getElementById('webgl-fallback');

  let THREE;
  try {
    THREE = await import('/v3/vendor/three.module.js');
  } catch (e) {
    console.warn('three.js failed to load:', e);
    fallback.classList.add('visible');
    canvas.style.display = 'none';
    return null;
  }

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch {
    fallback.classList.add('visible');
    canvas.style.display = 'none';
    return null;
  }

  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x0A0B0D, 1);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, -0.35, 6.0);   // pulled back + slightly up so the launch rail sits fully in frame
  camera.lookAt(0, -0.2, 0);

  // ── Dodecahedron reactor core ──
  const dodeGeo = new THREE.DodecahedronGeometry(1, 0);
  const dodeMat = new THREE.MeshStandardMaterial({
    color: 0x0d0f16, metalness: 0.95, roughness: 0.28,   // obsidian body, not flat gold
    emissive: 0xD4A947, emissiveIntensity: 0.03,
  });
  const dodeMesh = new THREE.Mesh(dodeGeo, dodeMat);
  scene.add(dodeMesh);

  const edgesGeo = new THREE.EdgesGeometry(dodeGeo);
  const edgesMat = new THREE.LineBasicMaterial({ color: 0xF2CB63, transparent: true, opacity: 0.85 });
  dodeMesh.add(new THREE.LineSegments(edgesGeo, edgesMat));

  // soft molten-gold halo behind the core (fake bloom, GPU-cheap billboard)
  const haloCanvas = document.createElement('canvas'); haloCanvas.width = haloCanvas.height = 128;
  const hx = haloCanvas.getContext('2d');
  const hg = hx.createRadialGradient(64, 64, 4, 64, 64, 64);
  hg.addColorStop(0, 'rgba(212,169,71,0.55)'); hg.addColorStop(0.4, 'rgba(212,169,71,0.14)'); hg.addColorStop(1, 'rgba(212,169,71,0)');
  hx.fillStyle = hg; hx.fillRect(0, 0, 128, 128);
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({
    map: new THREE.CanvasTexture(haloCanvas), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  halo.scale.set(5.2, 5.2, 1); scene.add(halo);

  // ── Pulsing ring (heartbeat freshness indicator) ──
  const ringGeo = new THREE.TorusGeometry(1.3, 0.012, 8, 80);
  const ringMat = new THREE.MeshBasicMaterial({ color: 0xD4A947, transparent: true, opacity: 0.5 });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.rotation.x = Math.PI / 2;
  scene.add(ring);

  // ── Orbital rings + satellites (funded/eval accounts) ──
  const orbitRings = [];
  const satellites = [];
  function addOrbitRing(radius, color = 0x2E6FEF, tilt = 0.3) {
    const geo = new THREE.TorusGeometry(radius, 0.008, 8, 80);
    const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.25 });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = tilt;
    mesh.rotation.z = Math.random() * Math.PI;
    scene.add(mesh);
    return mesh;
  }
  function addSatellite(orbitRadius, color = 0xD4A947, speed = 0.4) {
    const geo = new THREE.OctahedronGeometry(0.06, 0);
    const mat = new THREE.MeshStandardMaterial({ color, metalness: 0.8, roughness: 0.2 });
    const mesh = new THREE.Mesh(geo, mat);
    const pivot = new THREE.Object3D();
    mesh.position.x = orbitRadius;
    pivot.add(mesh);
    scene.add(pivot);
    satellites.push({ pivot, mesh, speed, angle: Math.random() * Math.PI * 2 });
  }

  // ── Launch rail (static): the track evals climb toward the +target ignition line ──
  const RAIL_Y = -1.85, RAIL_X0 = -1.45, RAIL_X1 = 1.55;
  const railLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(RAIL_X0, RAIL_Y, 0), new THREE.Vector3(RAIL_X1, RAIL_Y, 0)]),
    new THREE.LineBasicMaterial({ color: 0xD4A947, transparent: true, opacity: 0.22 }));
  scene.add(railLine);
  // ignition line at the target end (+$3k)
  const tgtMark = new THREE.Mesh(new THREE.PlaneGeometry(0.02, 0.16),
    new THREE.MeshBasicMaterial({ color: 0x39C07E, transparent: true, opacity: 0.6 }));
  tgtMark.position.set(RAIL_X1, RAIL_Y, 0); scene.add(tgtMark);

  // ── Eval vehicles (climb the launch rail) ──
  const evalVehicles = [];
  function addEvalVehicle(progress, lane = 0, fuel = 1) {
    // launch vehicle climbs the rail with progress-to-target; a gold flame whose length encodes
    // remaining 30-day fuel; colour warms blue->gold as it nears ignition. Sized to read clearly.
    const grp = new THREE.Group();
    const bodyCol = new THREE.Color(0x2E6FEF).lerp(new THREE.Color(0xF2CB63), progress);
    const body = new THREE.Mesh(new THREE.ConeGeometry(0.075, 0.24, 10),
      new THREE.MeshStandardMaterial({ color: bodyCol, metalness: 0.7, roughness: 0.25,
        emissive: bodyCol, emissiveIntensity: 0.6 }));
    body.rotation.z = -Math.PI / 2;                    // nose points along +x (toward target)
    grp.add(body);
    const flame = new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.22 * Math.max(0.2, fuel), 7),
      new THREE.MeshBasicMaterial({ color: 0xF2CB63, transparent: true, opacity: 0.7,
        blending: THREE.AdditiveBlending, depthWrite: false }));
    flame.rotation.z = Math.PI / 2; flame.position.x = -0.2; grp.add(flame);
    // glow sprite so it reads against the dark stage
    const gc = document.createElement('canvas'); gc.width = gc.height = 64;
    const gg = gc.getContext('2d').createRadialGradient(32, 32, 2, 32, 32, 32);
    gg.addColorStop(0, 'rgba(242,203,99,0.6)'); gg.addColorStop(1, 'rgba(242,203,99,0)');
    const gx = gc.getContext('2d'); gx.fillStyle = gg; gx.fillRect(0, 0, 64, 64);
    const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(gc),
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    glow.scale.set(0.7, 0.7, 1); grp.add(glow);
    grp.position.set(RAIL_X0 + progress * (RAIL_X1 - RAIL_X0), RAIL_Y + 0.06 - lane * 0.26, 0);
    scene.add(grp);
    evalVehicles.push(grp);
  }

  // ── Particles (payout streams; well under the 2k budget) ──
  const PARTICLE_COUNT = 800;
  const pPositions = new Float32Array(PARTICLE_COUNT * 3);
  const pAlphas = new Float32Array(PARTICLE_COUNT);
  const pSpeeds = new Float32Array(PARTICLE_COUNT);
  const pActive = new Uint8Array(PARTICLE_COUNT);
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    pPositions[i * 3] = (Math.random() - 0.5) * 8;
    pPositions[i * 3 + 1] = (Math.random() - 0.5) * 8;
    pPositions[i * 3 + 2] = (Math.random() - 0.5) * 3;
    pSpeeds[i] = 0.005 + Math.random() * 0.015;
  }
  const pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
  const pMat = new THREE.PointsMaterial({ color: 0xD4A947, size: 0.03, transparent: true, opacity: 0.7 });
  scene.add(new THREE.Points(pGeo, pMat));

  // ── Lighting ──
  scene.add(new THREE.AmbientLight(0x222244, 2));
  const gold = new THREE.PointLight(0xD4A947, 2, 8);
  gold.position.set(2, 2, 2);
  scene.add(gold);
  const blue = new THREE.PointLight(0x2E6FEF, 1, 8);
  blue.position.set(-2, -1, 1);
  scene.add(blue);

  // ── Resize ──
  function onResize() {
    const c = document.getElementById('center');
    camera.aspect = c.clientWidth / Math.max(1, c.clientHeight);
    camera.updateProjectionMatrix();
    renderer.setSize(c.clientWidth, c.clientHeight, false);
  }
  new ResizeObserver(onResize).observe(document.getElementById('center'));
  onResize();

  let _hbFreshness = 0;
  let _payoutEvent = 0;
  let _t = 0;

  function onDataUpdate(st, hb, campaign) {
    _hbFreshness = hb?.freshness_s ?? 999;

    satellites.forEach(s => s.pivot.removeFromParent());
    satellites.length = 0;
    orbitRings.forEach(r => r.removeFromParent());
    orbitRings.length = 0;

    const accts = st?.accounts || [];
    // FUNDED accounts orbit as satellites (altitude = cushion)
    accts.filter(a => a.phase === 'FUNDED').forEach((a, i) => {
      const r = 1.6 + i * 0.35;
      const cushion = (a.balance ?? 0) - (a.floor ?? 0);
      const height = 0.2 + (cushion / (a.dd ?? 2500)) * 0.8;
      orbitRings.push(addOrbitRing(r * height, 0xD4A947));
      addSatellite(r * height, 0xD4A947, 0.2 + i * 0.07);
    });

    // EVAL vehicles on the launch rail — merged from LIVE STATE accounts + the active
    // campaign, deduped by label, so EVERY started eval renders automatically (state path =
    // bot-registered; campaign path = operator-declared in evidence/eval_campaign.json).
    evalVehicles.forEach(v => v.removeFromParent());
    evalVehicles.length = 0;
    const evalList = [];
    const seen = new Set();
    const push = (label, bal, start, tgt, days, clock) => {
      const key = String(label || '').trim() || `eval${evalList.length}`;
      if (seen.has(key)) return; seen.add(key);
      const prog = Math.max(0, Math.min(1, ((bal ?? start) - start) / (tgt - start)));
      const fuel = (days != null && clock) ? Math.max(0, days / clock) : 1;
      evalList.push({ prog, fuel });
    };
    accts.filter(a => a.phase === 'EVAL').forEach(a =>
      push(a.account || a.label, a.balance, 50000, 53000, a.days_left, 30));
    (campaign && campaign.active !== false ? [campaign, ...(campaign.evals || [])] : [])
      .filter(e => e && (e.current_balance != null || e.start_balance != null))
      .forEach(e => push(e.account_label || e.account_id, e.current_balance,
                         e.start_balance || 50000, e.target_balance || 53000,
                         e.days_left, e.clock_days || 30));
    evalList.forEach((e, i) => addEvalVehicle(e.prog, i, e.fuel));

    if (accts.some(a => a.phase === 'FUNDED' && (a.paid || 0) > 0)) {
      _payoutEvent = 80;
    }
  }

  function animate() {
    S.raf = requestAnimationFrame(animate);
    if (!S.visible) return;          // paused while tab hidden
    _t += 0.01;

    dodeMesh.rotation.y = _t * 0.07;   // slower, more deliberate spin
    dodeMesh.rotation.x = _t * 0.04;

    const fresh = Math.max(0, 1 - _hbFreshness / 180);
    const beat = 0.5 + 0.5 * Math.sin(_t * (fresh > 0.5 ? 6 : 3));
    const pulse = fresh * (0.05 + 0.05 * Math.sin(_t * (fresh > 0.5 ? 6 : 3)));
    const arrhythm = fresh < 0.3 ? Math.sin(_t * 13) * 0.03 * (1 - fresh * 3) : 0;
    ring.material.opacity = 0.2 + pulse + arrhythm;
    // the core breathes: edges brighten and the halo swells on each heartbeat
    edgesMat.opacity = 0.45 + 0.45 * beat * (0.4 + 0.6 * fresh);
    const hs = 4.6 + 1.0 * beat * fresh;
    halo.scale.set(hs, hs, 1);
    halo.material.opacity = 0.35 + 0.5 * fresh;
    halo.material.color.setHex(_hbFreshness > 180 ? 0xE5484D : _hbFreshness > 60 ? 0xE0A93E : 0xD4A947);
    ring.material.color.setHex(_hbFreshness > 180 ? 0xE5484D : _hbFreshness > 60 ? 0xE0A93E : 0xD4A947);
    ring.rotation.z = _t * 0.05;

    satellites.forEach(s => {
      s.angle += s.speed * 0.016;
      s.pivot.rotation.y = s.angle;
    });

    if (_payoutEvent > 0) {
      _payoutEvent--;
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        if (!pActive[i] && Math.random() < 0.03) {
          pActive[i] = 1;
          pPositions[i * 3] = (Math.random() - 0.5) * 0.5;
          pPositions[i * 3 + 1] = (Math.random() - 0.5) * 0.5;
          pPositions[i * 3 + 2] = 0;
          pAlphas[i] = 1;
        }
      }
    }
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      if (pActive[i]) {
        pPositions[i * 3] += (pPositions[i * 3] * 0.02) * pSpeeds[i] * 40;
        pPositions[i * 3 + 1] += pSpeeds[i] * 0.8;
        pAlphas[i] -= 0.015;
        if (pAlphas[i] <= 0) { pActive[i] = 0; pAlphas[i] = 0; }
      }
    }
    pGeo.attributes.position.needsUpdate = true;

    gold.intensity = 1.5 + 0.5 * Math.sin(_t * (fresh > 0.5 ? 6 : 2));

    renderer.render(scene, camera);
  }

  animate();
  S.webglOk = true;
  return { onDataUpdate };
}

// ─── VISIBILITY API — pauses the render loop when the tab is hidden ─────────
document.addEventListener('visibilitychange', () => {
  S.visible = !document.hidden;
});

// ─── KEYBOARD MODE SWITCH (post-boot) ────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (!S.bootDone) return;
  const num = parseInt(e.key);
  if (num >= 1 && num <= 4) setMode(num - 1);
});

// ─── MODE BUTTON / SPINE DOT CLICK ───────────────────────────────────────────
document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => setMode(+btn.dataset.mode));
});
document.querySelectorAll('.spine-dot').forEach(dot => {
  dot.addEventListener('click', () => setMode(+dot.dataset.mode));
});

// ─── POLLING ─────────────────────────────────────────────────────────────────
let _pollStarted = false;
function startPolling() {
  if (_pollStarted) return;
  _pollStarted = true;
  fetchAll().catch(e => console.warn('poll failed:', e));
  setInterval(() => fetchAll().catch(e => console.warn('poll failed:', e)), 4000);
}

// ─── MAIN — runBoot can never hang the deck (watchdog + idempotent finish) ───
runBoot().catch(e => {
  console.warn('boot sequence error (forcing deck):', e);
  finishBoot();
});
