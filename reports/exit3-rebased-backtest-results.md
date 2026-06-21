# ZEUS EXIT #3 REBASED BACKTEST VERDICT
_2026-06-21 · research only · official model `EXIT3_FIXED_PARTIAL` · supersedes all single-target / synthetic tables_

**Model:** Profile A only · D1c ACTIVE (drift = signal-bar close − 09:30 ET open) · **Exit #3 integer split
(1 MNQ @ +1R, 2 MNQ @ +2R, shared stop, no trail, no breakeven)** · A3 = 3 MNQ ($6/pt) · −$700 daily hard
stop · **cost ≈ $6/trade (~$2/contract round-turn × 3)** · conservative stop-first fills · flat 14:30 ET.
Engine: `backtests/ict-nq-framework/_exit3_rebase_windows.py`. Data: 2014-01-03 → 2026-05-25 (framework feed
lags live ~4wk).

## Master table (official Exit #3)
| Window | Trades | WR | PF | Net $ | Total R | Exp R | Max DD $ | Stops | Eval verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Last 30 days | 7 | 43% | 4.64 | +2,129 | +2.7 | +0.39 | 252 | 0 | too few trades for +$3k (71%) |
| Last 3 months | 23 | 52% | 3.42 | +6,118 | +8.8 | +0.38 | 1,336 | 0 | **PASS 2026-03-13** |
| Last 5 months | 44 | 50% | 2.69 | +9,611 | +14.5 | +0.33 | 1,450 | 1 | **PASS 2026-01-29** |
| Last 12 months | 101 | 53% | 2.61 | +18,666 | +46.2 | +0.46 | 1,565 | 2 | **PASS 2025-09-10** |
| Last 3 years | 303 | 53% | 2.49 | +43,951 | +141.4 | +0.47 | 1,699 | 2 | **PASS 2023-09-27** |
| Full (12.4y) | 1172 | 48% | 1.82 | +68,584 | +353.3 | +0.30 | 3,302 | 6 | BREACH (deep history) |

**Every recent window (3mo–3yr) keeps max DD UNDER the $2,000 eval buffer and PASSES.** Only the full
12-year history breaches (some pre-strategy-era regime has a >$2k run — that's the ~tail the 81% pass-rate prices).

## Exit #3 vs OLD single-target (context only — single-target is NOT official)
| Window | E3 Net | E3 PF | **E3 Max DD** | SG Net | SG PF | **SG Max DD** | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| 30 days | +2,129 | 4.64 | **252** | +1,299 | 1.76 | 731 | E3 better both |
| 3 months | +6,118 | 3.42 | **1,336** | +5,393 | 2.26 | 2,231 | E3 safer + more |
| 5 months | +9,611 | 2.69 | **1,450** | +9,046 | 2.13 | 2,231 | E3 safer + more |
| 12 months | +18,666 | 2.61 | **1,565** | +20,448 | 2.39 | **2,231** | E3 −9% net, **−30% DD** |
| 3 years | +43,951 | 2.49 | **1,699** | +46,840 | 2.21 | 2,231 | E3 −6% net, −24% DD |
| Full | +68,584 | 1.82 | **3,302** | +69,104 | 1.64 | 5,595 | E3 −41% DD |

**Answers:**
- **Did Exit #3 reduce drawdown?** YES — by ~24–41% in every window; keeps DD **under the $2k buffer** in all recent windows (single-target sits at $2,231, over it).
- **Did Exit #3 reduce P&L?** Marginally in long windows (12mo −9%), but HIGHER in short windows. Small return give-up for large DD reduction.
- **Did Exit #3 improve eval survival?** YES — DD under buffer = eval-safe; single-target's $2,231 DD breaches the $2k ceiling.
- **Does single-target remain disqualified?** **YES** — max DD $2,231 > $2,000 buffer across recent windows.

---

## Detailed sections

### Last 30 days (2026-04-25 → 05-25)
7 trades (3W/4L) · WR 43% · PF 4.64 · **net +$2,129** (gross +$2,171) · Exp +0.39R · max DD $252 ·
avg win +$905 / avg loss −$146 · best day +$2,093 / worst −$230 · 0 stop days · max 3 consec losses ·
2 up weeks / 1 down · only 71% of the +$3k target (too few trades in 30d — not a fail, just short).

### Last 3 months (2026-02-23 → 05-25)
23 trades (12W/11L) · WR 52% · PF 3.42 · **net +$6,118** · Exp +0.38R · max DD $1,336 (R 2.5) ·
avg win +$720 / loss −$230 · 8 up weeks / 2 down · 0 stop days · **PASS 2026-03-13** (204% of target, min cushion $1,396).

### Last 5 months (2025-12-24 → 05-25)
44 trades (22W/22L) · WR 50% · PF 2.69 · **net +$9,611** · Exp +0.33R · max DD $1,450 · 1 stop day ·
14 up weeks / 4 down · **PASS 2026-01-29** (min cushion $935).

### Last 12 months (2025-05-25 → 05-25)
101 trades (54W/46L/1 scratch) · WR 53% · PF 2.61 · **net +$18,666** · Exp +0.46R · max DD $1,565 ·
avg win +$560 / loss −$252 · biggest win +$1,456 / loss −$1,284 · 2 stop days · max 7 consec losses ·
33 up weeks / 12 down · avg week +$415 / median +$370 · **PASS 2025-09-10**.

### Last 3 years (2023 → 2026)
303 trades · WR 53% · PF 2.49 · **net +$43,951** · Exp +0.47R · max DD $1,699 · 2 stop days · **PASS 2023-09-27**.

### Full available (2014 → 2026, 12.4y)
1172 trades · WR 48% · PF 1.82 · **net +$68,584** · Exp +0.30R · max DD **$3,302** · 6 stop days · **BREACH**
(a >$2k drawdown exists somewhere in 12 years of regimes; expected tail, drives the <100% pass rate).

---

## $1,400 paper-trade sanity (Phase 6)
The old +$1,400 paper result is **invalid under the official model.** It assumed full 3 MNQ at +2R
(233pt × $6). Under Exit #3 integer split that same short = 1@+1R ($233) + 2@+2R ($933) = **≈ $1,167**,
not $1,400. The current backtest and live routing **never book full 3 MNQ at +2R** — confirmed by
`tools/check_exit3_parity.py` (live payload == $1,167 == integer Exit #3; ≠ $1,400).

## Verdict
Exit #3 is the correct eval model: **eval-safe drawdown (under the $2k buffer in all recent windows),
PF 2.5–3.4 recent, passes the +$3k target in every multi-month window.** It costs a few % of long-run
return vs single-target but removes the buffer-breaching drawdown that disqualified single-target.
**Live remains BLOCKED** pending the Monday live-feed paper proof + operator approval — the backtest
validates the model, not the live arming.
