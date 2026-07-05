# L6 — London Opening-Drive Pullback

**Status: KILLED BY 1-MINUTE-TRUTH RE-TEST (see bottom section). The 5m-grid "survivor" flag below is SUPERSEDED — this is a fill-granularity artifact, not a real edge. NOT integrated, NOT deployed, DEAD.**

## Definition

- Window: London 02:00–05:00 ET (genuine ET clock time, `ict-nq-framework/engine/data.py:load_spine()` — no UTC/DST drift).
- Drive = first 60 or 90 min of the window (grid). Origin = window's opening price; extreme = the max high (up-drive) or min low (down-drive) reached inside the drive sub-window; drive range = |extreme − origin|. Qualifies if range ≥ X points (grid X ∈ {15, 25, 40}).
- Entry = pullback TOUCH of the 50% or 61.8% retracement level (grid), next-bar-open after the touching bar closes.
- Stop = beyond drive origin (±1 tick) OR beyond the 78.6% retracement (±1 tick) — grid both.
- Target = 1R / 1.5R / drive-extension (127.2% Fibonacci extension of the drive beyond origin) — grid.
- Time stop: force-flat at London end (05:00 ET) if neither hit.
- One trade/day (only one drive direction exists per session by construction — whichever side had the bigger range).
- Causality: origin/extreme/range use only bars strictly inside the completed drive sub-window; entry level is touched-then-next-bar-open; stop-first on intrabar ties (harness convention). No indicator or level references a future bar.
- Data: NQ 5m, 2016-01-01 → 2026-05-25 ET (10.4y), same sample as the rest of this dir.
- Engine: `l6_london_drive_pullback.py`; full grid csv: `l6_grid.csv` (in `backtests/asia-london/`).

## Full grid (72 cells) @ 1.0pt cost

All 72 cells (drive_min × X × entry_pct × stop_variant × target) computed; see `l6_grid.csv` for the raw table. Pattern summary:

- **`stop=origin` family (36 cells)**: PF clusters 1.04–1.27 — modest, in line with the rest of the dead Asia/London family (none clear the ≥1.15 bar with robust support; the few that nominally clear it (e.g. `d90/x15/e0.618/sorigin/1R` PF 1.27) have positive-but-small expectancy, consistent with noise).
- **`stop=78.6%` family (36 cells)**: PF is uniformly elevated, 1.33–2.01 across every X, drive-window and target combination tested — i.e. broad neighboring-cell support within this family, not a single lucky cell.

## Best cell: `d90/x15/e0.618/s78.6/1R` (drive window = first 90 min, X ≥ 15pt, entry at 61.8% retrace, stop at 78.6% retrace, target = 1R)

| metric | value |
|---|---|
| n | 1,346 |
| WR | 56.2% |
| **PF @ 1.0pt** | **2.01** |
| exp_r (mean R) | −0.227 |
| PF @ 2.0pt hostile | **1.54** |
| trades/wk | 2.49 |
| target-hit rate | 34% |
| median risk | 7.1 pts |
| median duration | 0 min (many resolve same-bar) |

### Yearly splits (full years only)

| year | n | PF | exp_r |
|---|---|---|---|
| 2016 | 30 | 1.08 | +0.346 |
| 2018 | 74 | 2.16 | −0.009 |
| 2019 | 70 | 1.21 | −0.524 |
| 2020 | 166 | 2.86 | −0.056 |
| 2021 | 163 | 2.27 | −1.047 |
| 2022 | 200 | 2.42 | +0.058 |
| 2023 | 179 | 2.22 | −0.002 |
| 2024 | 188 | 1.79 | −0.276 |
| 2025 | 193 | 1.97 | −0.233 |
| 2026 (YTD) | 79 | 0.93 | −0.143 |

Last 6 full years (2020–2025): **6/6 positive PF.**

## Mechanical rejection-bar check

| gate | result |
|---|---|
| PF < 1.15 @ 1.0pt → REJECTED | PF = 2.01 — **passes** |
| PF ≥ 1.15 but < 1.10 @ 2.0pt → REJECTED (cost-fragile) | PF = 1.54 @ 2.0pt — **passes** |
| Positive in < 4 of last 6 full years → REJECTED (one-regime) | 6/6 — **passes** |
| < 100 trades/10.4y → REJECTED (frequency) | n = 1,346 — **passes** |
| Best cell only, no neighbor support → REJECTED (curve-fit) | Entire `stop=78.6%` family (all X, both drive windows, all 3 targets) shows PF 1.33–2.01 — **passes (broad support)** |

**Every literal, pre-registered rejection rule is cleared.** Per the task's explicit instruction, this is treated as a survivor: **STOP — do not integrate into the funnel. Flagged for auditor review.**

## Why this is almost certainly a bug/artifact, not a real edge (auditor should check this first)

1. **The elevated-PF family (`stop=78.6%`) is defined by two adjacent Fibonacci levels only 16.8% of the drive range apart** (61.8% entry → 78.6% stop). This produces a genuinely tiny risk denominator (median 7.1 pts vs. 13–50pt median risk everywhere else in this dir's register). Dividing small $ swings by a tiny risk denominator inflates/destabilizes R-multiples — which is exactly why **exp_r (mean R) is negative in every single `stop=78.6%` cell** (range −0.18 to −0.53) even though the **points-based PF is >1** in all of them. A real edge should not show simultaneously positive $-PF and negative mean-R; that divergence is the signature of a risk-denominator artifact, not genuine edge.
2. **Median duration = 0 minutes** and **target-hit rate only 34%** while WR = 56% — most "wins" are not clean 1R target hits, they are the 05:00 time-stop closing marginally in favor. Combined with (1), this smells like the entry bar itself frequently already straddles both the tight stop and the tight target (a normal NQ 5m bar range often exceeds a 7pt stop), so the stop-first-tie convention is doing a lot of unstable, hard-to-verify-by-eye work here — a genuine tick-level replay is warranted before trusting this.
3. **The fixed 1.0/2.0pt round-trip cost convention used throughout this dir was calibrated against typically much wider stops (13–50pt).** For a ~7pt median-risk strategy, that same fixed-point cost eats a much larger, non-comparable fraction of the risk, and real-world stop slippage (as opposed to the flat point charge) would likely be far more damaging than the current 2.0pt hostile test captures. The 2.0pt pass here (PF 1.54) is not a reliable stress test for a stop this tight.

**Recommendation to auditor**: before any further consideration, (a) re-derive on 1m data with an honest intrabar stop/target race (not the 5m stop-first-tie approximation) to see if PF survives, and (b) re-cost proportional to risk (e.g. slippage as % of stop distance) rather than flat points, given the 7pt median risk. Given this family's 100% historical death rate (see citation stubs L1–L9), the strong prior is that this collapses under either check.

## 1m-truth kill test (adversarial verification, this sprint)

**Preregistered prediction (written before running):** PF < 1.15 after honest fills/costs — burden of proof on the strategy to falsify this. Basis: median risk (~7pt) is inside a single 5m NQ bar's typical range, so the 5m stop-first-tie approximation was suspected of manufacturing phantom risk/reward.

**Engine:** `backtests/asia-london/l6_kill_test.py`. Signals (drive/origin/extreme/entry_lvl/stop_lvl/target_lvl) computed identically to `l6_run` on closed 5m bars. Only the fill/exit changed: entry = resting limit at the 61.8%/50% level, filled on the first 1m bar (strictly after the signal 5m bar's close) that touches it; no same-bar entry+exit (stop/target race starts on the *next* 1m bar); stop-first on every subsequent 1m bar; same-day 05:00 ET time-stop unchanged. Costs: 1.25pt round-trip (strict, 0.5pt/side slippage + commission) and 0.75pt (lenient), both flat points (not R-scaled), i.e. the tick-floor cost the auditor's brief called for.

Tested: the reported best cell + 3 best same-family (`stop=78.6%`, `target=1R`) neighbors from `l6_grid.csv`.

### Risk geometry (1m-truth, same population both cost levels)

| cell | n signals | min risk | p10 | median | risk<5pt | risk<3pt |
|---|---|---|---|---|---|---|
| d90/x15/e0.618/s78.6/1R (winner) | 1,346 | 2.77 | 3.33 | 5.86 | 512 (38.0%) | 57 (4.2%) |
| d90/x25/e0.618/s78.6/1R | 946 | 4.45 | 4.95 | 7.24 | 112 (11.8%) | 0 (0%) |
| d90/x15/e0.5/s78.6/1R | 1,475 | 4.54 | 5.49 | 9.92 | 70 (4.7%) | 0 (0%) |
| d90/x40/e0.618/s78.6/1R | 501 | 7.00 | 7.45 | 9.92 | 0 (0%) | 0 (0%) |

38% of the winner cell's trades carry a stop under 5pt — structurally untradeable on real NQ (spread alone eats a large share of the risk). Even the "risk≥5pt only" re-cut below does not rescue the family.

### PF/n/WR/expR, 1m truth, both cost levels, both segments

| cell | cost | segment | n | WR | PF | exp_r |
|---|---|---|---|---|---|---|
| d90/x15/e0.618/s78.6/1R (winner) | 1.25pt | all | 1,258 | 27.7% | **0.29** | −0.670 |
| d90/x15/e0.618/s78.6/1R (winner) | 1.25pt | risk≥5pt | 772 | 29.5% | 0.33 | −0.565 |
| d90/x15/e0.618/s78.6/1R (winner) | 0.75pt | all | 1,258 | 27.7% | 0.33 | −0.580 |
| d90/x15/e0.618/s78.6/1R (winner) | 0.75pt | risk≥5pt | 772 | 29.5% | 0.37 | −0.501 |
| d90/x25/e0.618/s78.6/1R | 1.25pt | all | 883 | 28.9% | 0.32 | −0.591 |
| d90/x25/e0.618/s78.6/1R | 0.75pt | all | 883 | 28.9% | 0.36 | −0.523 |
| d90/x15/e0.5/s78.6/1R | 1.25pt | all | 1,404 | 27.1% | 0.32 | −0.584 |
| d90/x15/e0.5/s78.6/1R | 0.75pt | all | 1,404 | 27.2% | 0.35 | −0.530 |
| d90/x40/e0.618/s78.6/1R | 1.25pt | all | 465 | 30.3% | 0.36 | −0.509 |
| d90/x40/e0.618/s78.6/1R | 0.75pt | all | 465 | 30.3% | 0.39 | −0.460 |

Yearly splits (winner, 1.25pt, all trades): every single year 2016–2026 has PF < 1.0 (range 0.19–0.81; the one "high" reading, 2016 PF 0.81, is n=27). No year survives.

Full CSVs: `backtests/asia-london/l6_kill_test_results.csv`, `backtests/asia-london/l6_kill_test_risk_geometry.csv`.

### Mechanism diagnosis

Cost level barely moves the needle (PF 0.29→0.33 going from 1.25pt down to 0.75pt on the winner cell) — the tick-floor cost is a minor contributor. An ablation forcing the same-bar-entry+exit rule back *on* (walk starts at the fill bar itself instead of the next 1m bar) also barely moves PF (0.29 either way) — the "no same-bar" rule is not the driver either. The collapse is overwhelmingly **fill/exit granularity**: the original 5m stop-first-tie simulation used a single 5m candle's H/L to arbitrate a ~6–10pt stop/target race, which is far too coarse for stops this tight — a real 1-minute intrabar path revisits/violates the tight 78.6%-retracement stop long before the retracement genuinely completes and reverses, something the 5m OHLC approximation cannot see. WR collapses from 56.2% (5m) to 27–30% (1m truth) and PF collapses from 2.01 (winner, 5m/1.0pt) to 0.29 (winner, 1m/1.25pt) — well past net-losing, not just below the 1.15 bar.

### Verdict

**PF < 1.15 confirmed — REJECTED.** Every cell in the family (winner + 3 best neighbors), at both cost levels, in both segments (all trades and risk≥5pt-only), and in every calendar year, comes in at PF 0.19–0.39 — a genuinely negative edge, not merely cost-fragile. Mechanism: **fill/exit granularity (5m stop-first-tie approximation), not the cost floor.** The auditor's preregistered prediction is confirmed and then some. L6 is DEAD; do not integrate, do not re-test without a materially different entry/stop construction (the tight 61.8%/78.6% Fibonacci pairing is the root cause and should not be revisited at this stop width).
