# Pass-rate optimization — uncorrelated accelerant + VPC exit-line tuning

**RESEARCH / SIM MEASUREMENT ONLY. Read-only toward strategy code (imports only). Writes confined to
`research/passrate_opt/` + `reports/passrate_opt/`. Nothing armed. No locked/certified config changed.
LIVE HOLD remains in force.** HONEST NUMBERS ONLY — where an edge stream is unavailable or debunked it
is flagged, not fabricated.

Anchor (from `reports/fork_b/01_honest_eval_engines.md`): **VPC standalone $600/cap-3 on Apex-50K EOD =
PASS 12.6% / BUST 3.6% / EXPIRE 83.8% / median 19d.** Its limiter is SPEED (expiry), not bust. Momentum
as an accelerant lifted pass 12.6→20.8% but dragged bust 3.6→24.3% (pass < bust — a bad accelerant).

Engines reused BY IMPORT: `research/fork_b/honest_eval_engines.py` → `tools_account_size_research` (the
certified Apex-50K EOD harness: EOD close-set ratchet/lock, intraday-downside liquidation via marked
trough, $550 daily stop, $1,000 DLL, 30-day clock, rolling 1-eval/trading-day starts). Data = Databento
NQ 1m→5m RTH, 2022-01-03 → 2026-06-22 (88,407 bars).

---

## INVESTIGATION A — Uncorrelated second edge (ES-ORB) as accelerant

### Verdict: **DATA-GATED / DEBUNKED. No honest, cost-inclusive, +EV ES-ORB stream exists.**

The "ES ORB-continuation, PF ~1.22, corr 0.17" figure on record (`strategies/active/es-orb-cont/
EDGE_SPEC.md`, MEMORY) is a **CFD-proxy + pre-1m-truth artifact**. It was independently RE-TESTED and
**KILLED twice** since that spec was written:

| Re-test (honest) | Date | Result |
|---|---|---|
| `bot/zeus-es-research/…/M4_opening_range_breakout_retest.md` (Fable-audited, 1m-truth, adverse-first, valid-day mask, MES costs) | 2026-07-06 | ES-ORB incumbent (OR30/close-outside/immediate/opp-OR-side stop/1.5R): **PF 0.871**, expR −0.063, WR 44.3%, n=2601, maxDD −195.9R → **KILLED** (< 1.15 family bar). "0.871 vs 1.22 claimed — DOES NOT CONFIRM." |
| `backtests/orb-recert-2026-07/FINDINGS.md` (fresh causal engine, same-bar-fill canary) | 2026-07-04 | "**No durable, prop-tradeable ORB edge exists** — continuation, fade, or ATR-cap — across NY/London/Asia. Net-positive configs below the multiple-testing noise floor. ORB stays retired." |

**You cannot accelerate a pass rate with a losing edge.** An honest ES-ORB stream is PF 0.871 — it would
add bust risk exactly like momentum did, but with *negative* expectancy. Running it through the fork_b
funnel would only quantify a drag; there is no +EV stream to run.

**The one marginal real-ish ES edge is also unusable here.** `M1` ES-VWAP-pullback-continuation is the
best ES cell found (PF 1.147, n=2507) — but (a) it is on the **same CFD proxy** (optimistic-bias caveat,
needs real CME futures before certification), and (b) the ES-edge-expansion Wave-3 **already integrated
it into a portfolio funnel** and it **REDUCED pass at every sizing**: benchmark 37.4% → **19.9 / 24.9 /
28.7%** at 300/2, 400/3, 600/4 (`portfolio_integration.md`, `final_verdict.md`). Mechanism: 4.8 tr/wk of
PF-1.12 trades burn shared eval budget faster than they add wins. **Frequency without quality is dilution,
not diversification** — the same lesson fork_b's Item 3 found for breakeven-Profile-A.

### What would be needed to un-gate this (exactly)
1. **Real CME ES/MES futures data** (currently only ~58–60 days exist; everything above is Dukascopy CFD,
   documented to flatter by ~+0.09 PF / +0.08R vs real futures).
2. A **re-certified +EV ES stream on that real data** clearing the ≥1.15 family bar with an honest,
   cost-inclusive (commission + ≥2tk slip), 1m-truth, adverse-first engine — none exists today.
3. Then, and only then, a **VPC + ES joint funnel** through `honest_eval_engines.eval_funnel`. Until (1)
   and (2) land, this is a clean "data-gated" answer — no joint run is honestly possible.

---

## INVESTIGATION B — VPC exit-line / target tuning for SPEED

Harness `research/passrate_opt/exit_line_sweep.py`: ONLY the VPC exit rule changes; signals, gates,
sizing ($600/cap-3), costs (0.75pt RT), daily_stop=120, max_trades=2, data, and the certified eval funnel
are byte-identical to fork_b. **Canary: trail_5.0 reproduces the fork_b VPC baseline exactly
(12.6 / 3.6 / 83.8, med 19d) → engine faithful.**

| exit variant | PF | WR% | n | PASS% | BUST% | EXPIRE% | med days | tr/wk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| trail 3.0×ATR | **1.345** | 46.0 | 411 | 7.2 | **2.1** | 90.8 | 21 | 1.78 |
| trail 4.0×ATR | 1.246 | 45.6 | 408 | 10.3 | 2.3 | 87.4 | **18** | 1.77 |
| **trail 5.0×ATR (BASELINE)** | 1.294 | 44.9 | 408 | **12.6** | 3.6 | 83.8 | 19 | 1.77 |
| trail 6.0×ATR | 1.327 | 46.8 | 408 | **13.1** | 6.2 | 80.8 | 20 | 1.77 |
| fixed 1.5R | 1.213 | 49.5 | 408 | 9.5 | 9.7 | 80.8 | 24 | 1.77 |
| fixed 2.0R | 1.216 | 47.7 | 407 | 10.5 | 11.8 | 77.7 | 22 | 1.76 |
| fixed 2.5R | 1.240 | 47.4 | 407 | 12.8 | 11.8 | 75.4 | 19 | 1.76 |
| fixed 3.0R | 1.262 | 47.4 | 407 | **14.1** | 11.8 | 74.1 | 20 | 1.76 |

### Reading
- **Fixed-R targets are strictly worse for the eval.** Every fixed-R variant carries **BUST 9.7–11.8%**
  (2.7–3.3× the baseline 3.6%) for at best +1.5pp pass. `fixed_3.0R` reaches the highest pass in the sweep
  (14.1%) but at **bust 11.8% ≈ pass** — the exact fragile, pass≈bust shape that disqualified momentum.
  Why: a fixed target caps winners while every loser rides the full 2.5×ATR initial stop to the bitter
  end → bigger per-trade losses → more $550-stop / trailing-DD hits → more busts. The trailing stop is
  itself the better *drawdown-control* exit.
- **Tighter trails raise PF but LOWER pass.** trail_3.0 has the best PF (1.345) and lowest bust (2.1%) but
  pass falls to 7.2% — smaller banked wins take *longer* to reach +$3,000 under the 30-day clock (expiry
  90.8%). Higher per-trade quality, slower to the target. The opposite of the speed goal.
- **Looser trail (6.0) is the only variant that beats baseline pass while keeping pass > bust** — but only
  +0.5pp pass (12.6→13.1) for **+2.6pp bust** (3.6→6.2). A poor trade; a mini-momentum in miniature.
- **Best median-days = trail_4.0 (18d)**, but its pass is *lower* (10.3%) — faster exits bank smaller,
  expire more. Speed of the individual trade ≠ speed to the eval target.

### Verdict (Investigation B)
**There is no free pass-speed in the VPC exit line. The current trail_5.0 exit already sits on the
pass/bust efficient frontier.** No variant raises pass materially without a disproportionate bust cost;
the highest-pass variant (fixed_3.0R 14.1%) fails the pass > bust safety test. **Changing the exit is a
re-certification event and is NOT justified by these numbers** — this is a research measurement, not a
deployment recommendation. Best *defensible* exit for pass-speed = **keep trail_5.0** (or trail_6.0 only
if a +0.5pp pass is worth doubling bust — it is not).

---

## Bottom line
The eval limiter (expiry ~84%) is driven by **signal frequency × edge magnitude**, NOT by the exit and
NOT by a missing second edge that currently exists honestly. Neither the exit line (Inv. B) nor any
available uncorrelated stream (Inv. A) buys pass-speed without a bust tax that erases it. The only honest
lever left is **more genuinely-uncorrelated +EV signal flow**, and building it is **data-gated on real CME
ES/GC futures** (the CFD proxy is exhausted and its ES-ORB/ES-VPC candidates are debunked or diluting).
```
Files: research/passrate_opt/exit_line_sweep.py · reports/passrate_opt/02_exit_sweep.json
```
