> ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
> that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
> **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
> `reports/apex_validation.json`. Kept for historical reference only.

# NIGHTWATCH — First Live Bot Launch Check
_2026-06-15 ~05:25 ET · MFFU-50K-1 · ARES eval · A3/B2 · −$700 · TradersPost→Tradovate/MFFU_

## FINAL VERDICT: **MANUAL ONLY**
TradersPost ping / 1-MNQ bracket / flatten are **unproven** (require your local webhook URL + are operator-run). Per the prime directive, no automation until that chain is proven. Data + brain + risk + payload + dashboard all check out; **execution does not yet.**

---

## Phase results
| # | Check | Result |
|---|---|---|
| 1 | Live data | **DATA_READY = FALSE** (flowing & fresh, but real-time entitlement unconfirmed) |
| 2 | Bot data understanding | **BOT_DATA_OK = TRUE** |
| 3 | D1c | **D1C_STATUS = SHADOW** · working = **YES** |
| 4 | Risk controls | **RISK_OK = TRUE** |
| 5 | TradersPost ping | **NOT RUN** (operator + local URL) |
| 6 | 1-MNQ bracket | **NOT RUN** |
| 7 | Flatten/cancel | **NOT RUN** |
| 8 | Payload health | **PAYLOAD_OK = TRUE** |
| 9 | Dashboard truth | **DASHBOARD_TRUTH = TRUE** |

---

### 1 — Live data (DATA_READY = FALSE)
- last bar **05:25 ET**, age **~2 min**, **not stale** · feed **1m** (engine 5m via verified aggregation)
- warmup **45-day span, warmup_ok=TRUE** · basis **+27.72** applied (CME-aligned) · **reset_count 0**
- real-time confirmed: **FALSE** → DATA_READY false (correct, fail-closed)
- NQ/MNQ: real CME `NQ1!`; timestamps correct/ascending ET.
- **Hard rule:** real-time unconfirmed ⇒ no full auto.

### 2 — Bot data understanding (TRUE)
- 8,222 warmup bars parsed, no crash; live 1m appending.
- Prior levels compute sane & causal (shift(1), no lookahead): **pdh 29746.5 / pdl 29216.3 / pwh 29817.1 / pwl 28243.6**.
- Signal-parity + engine tests pass; aggregated 5m = native 5m bar-for-bar.

### 3 — D1c (SHADOW; working = YES)
- Resolved **SHADOW** tonight: feed is 1m but **real-time unconfirmed** → forced SHADOW. With `TV_REALTIME_CONFIRMED=1` it resolves **ACTIVE_EVAL_FILTER** (1m fidelity, 120s staleness).
- Cannot upgrade accidentally (resolve_d1c_for_feed tested). Stale/missing-open/zero-drift → SUSPEND (fail-closed). Disagreement blocks **Profile A only**, never B, never size. Decisions logged. (test_d1c_eval green.)

### 4 — Risk controls (TRUE)
- ARES **armed** on MFFU-50K-1, eval, **A3/B2**, daily_stop **−$700**; account explicit.
- ARES refuses funded accounts (tested). Daily stop restart-proof (DailyGuard). Duplicate **instance lock** active. Kill switch available. **Emergency flatten available**. Dup webhook ledger active.
- **P3:** funded-phase cushion-brake — **N/A during eval** (ARES daily-stop + worst-day<buffer sizing are the active eval brakes). Engages post-funding.

### 5–7 — Execution (NOT RUN)
Helpers built + unit-proven (`--ping`/`--one-mnq`/`--flatten`, qty forced to 1, deterministic signalId, dup-blocked, evidence saved). **No live webhook has been sent** — needs your local URL + open market.

### 8 — Payload health (TRUE)
`auto_runner --dry-run`: account/tier/**size A3/B2**/daily-stop **700**/route traderspost all correct; D1c resolved safely; size_ok. Payload schema (ticker, price, stopLoss.stopPrice, takeProfit.limitPrice, deterministic signalId) proven via Stage 0 + build_entry tests.

### 9 — Dashboard truth (TRUE)
**YELLOW**, green=False, data_ready=False, traderspost_proven=False, exec=paper/dry-run, blockers enumerated. Does **not** show false green.

---

## 10 — Mode verdict: **MANUAL ONLY**
(SEMI-AUTO once Phases 5–7 pass; FULL AUTO additionally needs DATA_READY + real-time + full-auto-approved.flag.)

## 11 — Allowed tonight
```
# Supervised PAPER (live data into brain, no orders):
python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative --feed tradingview-1m --d1c-mode shadow
# Operator execution proof (your local URL):
TRADERSPOST_TEST_URL='<url>' python3 bridge_test.py --account MFFU-50K-1 --ping
```

## 12 — Forbidden tonight
```
python3 auto_live.py ... --live --confirm     # full auto — gate refuses (data + execution unproven)
```

## 13 — Blockers before NY open
1. **Confirm TradingView real-time CME** → `export TV_REALTIME_CONFIRMED=1` (flips DATA_READY path + lets D1c go ACTIVE on 1m).
2. **TradersPost Stage 1 → 2 → 3** with local URL; verify correct MFFU account, stop+target attach, no dup/orphan, flatten clean → `touch evidence/launchlock/traderspost/PROVEN.flag`.
3. **`full-auto-approved.flag`** (final human arming) — only after 1+2.
4. (Optional) Splice TV-aggregated-5m to close the overnight Dukascopy warmup gap (washes out by 09:30; not a blocker).
