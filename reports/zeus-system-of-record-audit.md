# ZEUS SYSTEM-OF-RECORD AUDIT (ZEUS-TRUTH)
_2026-06-21 · audit only · no logic/sizing/flag changes · no live run_

---

## 1. EXECUTIVE VERDICT

**The live execution model does NOT match the researched/backtested model.** Every validation
stat this project owns (PF 1.32, ~+49R/yr, eval-survival, win-rate, the runner comparison) was
computed on **Exit #3 partials (50% @ +1R, 50% @ +2R)**. The **live TradersPost bridge sends the
FULL position to a SINGLE +2R target** — no partials, no runner, no two-leg. They are different
systems. The +$1,400 paper figure is the *live* single-target model's number, and it **overstates
the researched model by ~25–33%**.

Three exit models coexist, all different, for the SAME trade:

| Layer | Exit model | $ on the $1,400 trade (3 MNQ) |
|---|---|---|
| Backtest (`model01_sweep_mss_fvg`) — **all validation** | Exit #3 fractional partial (1.5@1R + 1.5@2R) | **+$1,050** |
| Paper SimBot (`bot.py` + `TwoLegBracket`) | Exit #3 integer partial (1@1R + 2@2R) | **+$1,167** |
| **Live bridge (`auto_live`→`bridge_traderspost`→TradersPost)** | **full 3 @ single 2R target** | **+$1,400** ← recorded |

This is a **BLOCKER**: until one exit model is chosen and all three layers are aligned to it,
live P&L cannot be trusted against any backtested number.

---

## 2. SYSTEM INVENTORY

| System | File(s) | Purpose | Status |
|---|---|---|---|
| Profile A engine | `strategy_engine_profileA` (framework) | NQ NY-Open OTE liquidity-reversal signals | **ACTIVE_EVAL** |
| Profile B engine | framework model | 2nd setup | **RESEARCH_ONLY** (not imported in `auto_live`/`bot`) |
| D1c DriftGate | `d1c_filter.py`, `auto_live.py` | drift-direction filter on A | **ACTIVE_EVAL** (1m feed + `TV_REALTIME_CONFIRMED=1`) |
| ARES sizing/guard | `auto_safety.py`, `ares_mode.py` | eval-attack sizing + worst-day cap + daily stop | **ACTIVE_EVAL** |
| P3 cushion-brake | research/`challenger/` | near-floor size cut | **RESEARCHED_NOT_CODED** (absent from `auto_live` + `bot`) |
| Flatten/EOD guardian | `flatten.py`, `scheduler.py` | wall-clock EOD + emergency flatten | **CODED_WIRED** (EOD live in paper) |
| HEIMDALL / heartbeat | `heimdall.py`, `heimdall_monitor.py` | health tiers + dead-man | **CODED_WIRED** |
| Dashboard | `zeus_server.py` (:8777) | Flask read-mostly UI | **BUILT_AND_ACTIVE** |
| TradersPost bridge | `bridge_traderspost.py`, `bridge_sender.py` | webhook payloads + dedup | **WIRED_PROVEN(Stage 2)** — single-target only |
| Live feed (TV CDP) | `tv_feed.py` | REAL CME 5m/1m via Chrome :9222 | **WIRED** (env dependency) |
| Feed self-healer | `feed_watch.py` | auto-reload throttled tab | **CODED_WIRED** |
| Full-auto preflight | `full_auto_preflight.py`, `monday_preflight.py` | gate stack | **CODED_WIRED** |
| Controlled-live gate | `go_live_test.sh`, flags | supervised live arming | **CODED** (flags present) |
| Decision logger | `d1c_filter.log_decision`, journal | audit of keeps/blocks | **ACTIVE** |
| Two-leg bracket (SIM) | `tradovate_client.TwoLegBracket` | partial Exit #3 state machine | **SIM_ONLY** (not used by live bridge) |
| Two-leg LIVE path | `tradovate_client` (gated) | direct-Tradovate brackets | **CODED_NOT_WIRED** (bot uses bridge, not this) |
| B1 runner | `b1_runner.py`, `sim_broker.py` | journaled live lifecycle + recon | **CODED_NOT_WIRED** (direct-Tradovate path; blocked on creds) |
| Paper/replay engine | `bot.SimBot`, `paper_live.py` | signal brain + simulated partial fills | **ACTIVE** (paper P&L) |
| Live engine | `auto_live.LiveAuto` | gates → bridge send | **WIRED_PROVEN** (single-target) |
| Eval mode | `auto_safety.EVAL_TIERS`, `--mode eval` | ARES 50K-conservative | **ACTIVE_EVAL** |
| Funded mode | `--mode funded` (sizing swap only) | post-pass | **NOT_FULLY_CODED** |

---

## 3. PROFILE TABLE

| Profile | Research | Live status | Eval | Funded | Exit model | Issue |
|---|---|---|---|---|---|---|
| **A** (NY-Open OTE reversal) | validated | **ACTIVE** | YES (3 MNQ) | planned A4→A2 | live=single 2R / backtest=partial | **exit mismatch** |
| **B** (2nd setup) | researched | **not wired** | no | planned B2 | n/a | not imported in live engine |

**Profile A** — sweep → MSS → FVG → OTE limit entry; stop 2 ticks beyond swept extreme; 2R target;
NY-AM (09:30–11:30 ET); 5m engine (1m for D1c drift); flat 14:30. D1c applied. Backtest uses Exit #3
partial; **live sends full qty to one target** (mismatch). Allowed to send live only behind both flags
+ `--live --confirm` + URL.

**Profile B** — `grep` of `auto_live.py`/`bot.py` returns **nothing** for B. Not imported, not sized,
not sent. RESEARCH_ONLY. To enable: port the B engine into the live brain, add parity tests, add a
2nd D1c policy decision (or exempt B), extend the bridge per-strategy routing. B2 sizing exists only
in the ARES table, never used live.

---

## 4. EXIT / RUNNER TRUTH

### Research exit model (what was validated)
**Exit #3** = bank 50% at +1R, hold remaining 50% to +2R, **no trailing, no breakeven**
(`config.py:33`, `STRAT.partial=[(1.0,0.5)]`). Winners cap at **+1.5R blended**. Stats: PF ~1.32,
~48% win, ~+49R/12mo, ~2.8 trades/wk. **NO runner** — "remainder runs to +2R" is a fixed ceiling.

### Live exit model (what the bot actually sends)
`auto_live.py:118` → `BP.build_entry(qty=spec["am"]=3, target=sig["target"])` → `bridge_traderspost._wire`
builds **ONE order**: `quantity=3`, ONE `stopLoss{stopPrice}`, ONE `takeProfit{limitPrice}` at the
2R target. **No TP1, no second leg, no partial, no runner.** Full 3 MNQ → single 2R target.
- On a win: +2R on full position = **+$1,400**.
- On a loss: −1R on full position = **−$700** (= the daily stop, in one trade).
- A trade that runs +1.9R then reverses to stop = **full −1R live**, where Exit #3 would have banked
  +1R on half (≈ 0R net). **Live single-target has materially higher variance than the backtest.**

### Paper exit model (SimBot)
`bot.py:151` `tp1_alloc=qty//2, tp2_alloc=qty-qty//2` → for 3 MNQ: **1 contract @ +1R, 2 @ +2R**
(integer partial). Win = **+$1,167**. This is the partial model — but **integer rounding at 3 MNQ
already diverges from the backtest's fractional 1.5/1.5** ($1,050).

### Truth table
| Mode | Exit model | Qty handling | TP1? | TP2? | Runner? | P&L vs research |
|---|---|---|---|---|---|---|
| Backtest | Exit #3 fractional | 1.5 / 1.5 | ✅ | ✅ | ❌ | baseline |
| Paper (SimBot) | Exit #3 integer | 1 / 2 | ✅ | ✅ | ❌ | +11% (rounding) |
| Controlled live | **single target** | **3 / 0** | ❌ | full→2R | ❌ | **+33% on wins, higher variance** |
| Eval live | **single target** | **3 / 0** | ❌ | full→2R | ❌ | same |
| Funded live | **single target** (+sizing swap) | full | ❌ | full→2R | ❌ | same; P3/B absent |

**Runners: researched? NO (never — Exit #3 is fixed-target). Live? NO. The only runner-based edge in
the project is the separate, un-deployed NQ Momentum strategy.**

---

## 5. THE $1,400 RECONSTRUCTION

Reported: SHORT 3 MNQ, entry 30654.83, stop 30771.50, target 30421.49.
- risk = 116.67 pts · reward = 233.34 pts · **RR = 2.00**

| Exit assumption | P&L (3 MNQ) |
|---|---|
| **FULL 3 @ 2R** | **+$1,400** ✅ matches |
| Exit #3 integer (1@1R + 2@2R) | +$1,167 |
| Exit #3 fractional (1.5/1.5) | +$1,050 |
| 2@1R + 1@2R | +$933 |
| full 3 @ 1R | +$700 |

`trade_results.record_resolved` → `pnl_from_r(result_r, entry, stop, contracts) =
result_r × |entry−stop| × $2 × contracts`. Solving $1,400 = result_r × 116.67 × $2 × 3 ⇒
**result_r = 2.0 applied to the full 3 contracts.** The recorder was handed "+2R on the whole
position." **Confirmed: the $1,400 used full-qty-single-target, NOT the partial/runner model.**

Caveats: (1) the bridge log shows the short sent at 10:46 ET then an **EOD cancel+exit at 18:30** — no
intermediate TP-hit webhook — so "TP hit" in the note is **unverified**; the trade may have been EOD-
flattened, not target-hit. (2) `paper.db` (SimBot fills) has **0 trades on 06-16** — the SimBot partial
engine never produced this row; it came from the live-path `record_resolved` abstraction. So the $1,400
is the **single-target accounting of an unverified resolution**, not a simulated partial fill.

---

## 6. EVAL VS FUNDED

| Phase | Account state | Profiles | Size | Exit model | D1c | Risk mode | Coded? |
|---|---|---|---|---|---|---|---|
| **Eval** | ARES eval | A only | 3 MNQ | single 2R target | ACTIVE_EVAL_FILTER | −$700 daily stop, worst-day<buffer | ✅ |
| **Funded/passed** | (design) A+B, A4/B2 | A(+B) | A2/B1 | (design) | (design) | P3 brake + retention | ❌ |

**FUNDED MODE NOT FULLY CODED.** `auto_live --mode funded` only swaps `fund_qty=2` (sizing). There is
**no P3 in the live or sim engine** (grep empty), **no Profile B**, no payout-protection, no funded
survival logic. Funded mode today = "eval engine with smaller size." Everything else funded is design
docs only.

---

## 7. PAPER vs LIVE DIFFERENCES

| Difference | Paper (SimBot) | Live eval (bridge) | Impact |
|---|---|---|---|
| **Exit model** | Exit #3 partial (1@1R,2@2R) | **full qty @ single 2R** | **different P&L per trade** |
| Win on $1,400 trade | $1,167 | $1,400 | +20% live |
| Fills | simulated, conservative stop-first | TradersPost→Tradovate real | unverified live fills |
| Reconciliation | n/a | **none through TradersPost** | live P&L unconfirmed |
| Data | Dukascopy CFD proxy (5m) | TV/CME (1m→5m) | basis + signal divergence (saw it 06-16) |
| D1c | depends on feed (SHADOW on 5m) | ACTIVE on 1m | filter differs by feed |
| Recording | paper.db (partial) | trade_results.csv (single-target) | **the bot disagrees with itself** |

The SimBot brain and the LiveAuto arm run **simultaneously** in a live session and compute **different
P&L for the same trade** (partial vs single-target). The dashboard reads the single-target ledger.

---

## 8. ORDER ROUTING / TRADERSPOST

| Routing feature | Status | Evidence |
|---|---|---|
| Payload = one entry order | ✅ | `_wire` builds single dict |
| One stop | ✅ | `stopLoss{type:stop,stopPrice}` |
| One target | ✅ | `takeProfit{limitPrice}` |
| Multiple take-profits / partials | ❌ **NOT SUPPORTED** | only one `takeProfit` key |
| Runner / trailing | ❌ | none |
| Dedup (signalId) | ✅ | deterministic `ZB-…` in `extras` |
| Flatten = cancel then exit | ✅ | EOD logs show cancel+exit |
| Always bracketed | ✅ | entry carries stop+target |
| Account mapping explicit | ✅ | `account=` in meta; URL per account |
| Stop/target attach-fail handling | ⚠️ partial | Stage-2 verified attach; **no live recon to confirm per-trade** |

**To route the intended Exit #3 live you must split into ≥2 orders** (e.g. 1 MNQ TP@1R + 2 MNQ TP@2R,
shared stop) or use a TP-ladder if TradersPost supports one. Neither is built.

---

## 9. GAP LIST

### Critical correctness
| Gap | Severity | Why | Fix |
|---|---|---|---|
| Live exit ≠ backtested exit (single-target vs partial) | **BLOCKER** | every validated stat is for the partial model; live is unvalidated | choose ONE model; align all 3 layers |
| Paper (partial) ≠ live (single-target) recording | **BLOCKER** | bot disagrees with itself; dashboard overstates | make `record_resolved` use the chosen model |
| No validated stats for single-target full-qty | **HIGH** | if we keep single-target, PF/survival/eval% are unknown | backtest single-target before trusting |

### Live execution
| Gap | Severity | Why | Fix |
|---|---|---|---|
| No broker-truth reconciliation on bridge | **HIGH** | `http 200` ≠ fill; can't confirm stop/target/flat | B1 direct path, or manual recon (current) |
| "TP hit" notes unverified | **HIGH** | 06-16 likely EOD-flattened, logged as +2R | record only confirmed resolutions |

### Auditability
| Gap | Severity | Why | Fix |
|---|---|---|---|
| Two ledgers (paper.db vs trade_results.csv) diverge | MEDIUM | no single source of P&L truth | unify on one resolution path |

### Eval-specific
| Gap | Severity | Why | Fix |
|---|---|---|---|
| Single-target = full −1R losses (−$700 = daily stop in one trade) | **HIGH** | higher variance than backtested; eval-survival math assumed partial | re-run eval-survival on the live model |

### Funded-mode
| Gap | Severity | Why | Fix |
|---|---|---|---|
| P3 not coded | **HIGH** | funded survival depends on it | port P3 into the live engine |
| Profile B not coded | MEDIUM | funded design is A+B | port B + parity |
| Funded mode = sizing swap only | MEDIUM | no payout/retention/survival logic | build funded mode |

### Data feed
| Gap | Severity | Why | Fix |
|---|---|---|---|
| Dukascopy proxy ≠ CME; feeds diverge (06-16) | MEDIUM | paper/live signals can differ | document; prefer TV/CME live; zero-basis feed later |
| TV CDP env dependency | MEDIUM | feed must be up+GREEN at open | the Monday startup step |

---

## 10. STATUS LEGEND APPLIED
- **PROVEN LIVE:** bridge entry+bracket attach (Stage 2, 1 MNQ, 06-15).
- **WIRED BUT NOT PROVEN:** full-auto single-target eval entry in-session (never filled real).
- **PAPER ONLY:** SimBot partial P&L; the $1,400.
- **CODED BUT NOT WIRED:** B1 runner, TwoLegBracket live path.
- **RESEARCHED BUT NOT CODED:** P3, Profile B, funded survival.
- **BUILT AND ACTIVE:** A, D1c, ARES, dashboard, guardians, feed, gates.

---

## 11. WHAT MUST BE FIXED (next build order)
1. **DECIDE THE EXIT MODEL** (operator call): (A) match research → build split-order/partial routing in
   the bridge so live = Exit #3; or (B) adopt single-target → re-backtest & re-validate it as official.
2. **Align all three layers** to the chosen model (backtest, SimBot recording, bridge payload).
3. **Unify P&L recording** so paper and live use one resolution path; record only confirmed resolutions.
4. **Re-run eval-survival** on the live model (variance differs).
5. **Port P3** into the live engine (funded survival prerequisite).
6. **Broker-truth reconciliation** (B1 direct path) before unsupervised.
7. **Profile B + funded mode** (post-eval).

**Until #1–#3 are done, do not treat any live/paper P&L as validated.**
