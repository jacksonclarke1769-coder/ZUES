# SMC3 Baseline — HTF Sweep -> 5M Confirm -> 1M Entry (NQ 1m, 5y)

Data: `/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet`
Span: 2021-06-23 00:00:00+00:00 -> 2026-06-22 23:59:00+00:00  (1,769,367 1m bars)
Run time: 5.0s   |   engine: `smc3_engine.py`  (default Config)

## No-lookahead assertion
- Global stepped-source check (all 60m/5m values close <= 1m open): **PASS**
- Per-fired-trade source-bar check (60m & 5m source close <= trigger open): **PASS** (5056/5056 trades)
- 1m pivots use left=right=2 (confirmed 2 bars late); 5m 2/2; 60m 3/3. Entry = trigger-bar CLOSE.

## Funnel (cross-check vs Pine stats table)
| stage | count |
|---|---|
| HTF sweeps (60m sweep+reclaim events) | 21,732 |
| 5m confirms (latch transitions) | 5,613 |
| 1m triggers (trigger-true bars) | 38,326 |
| valid trades (fired, risk OK) | 5,057 |
| risk rejects (fired, risk invalid) | 420 |
| open at data end (excluded from stats) | 1 |

_Funnel definitions: sweeps = 1m bars where longSweep|shortSweep set/refresh context; confirms = 5m-latch false->true transitions; triggers = 1m bars where (longTrigger|shortTrigger) true (includes bars while a position is open / before flat); valid+rejects counted only on flat, in-session trigger attempts._

## Closed-trade stats (full 5y)
| metric | value |
|---|---|
| n (closed) | 5056 |
| win % | 34.36% |
| PF | 1.036 |
| net $ | 79,410 |
| avg $/trade | 15.7 |
| avg winner | 1,304.3 |
| avg loser | -658.7 |
| total R | -52.9 |
| avg R | -0.010 |
| maxDD $ | 61,825 |
| median hold (min) | 31 |

_Costs: commission $2.50/side ($5.00 round-trip) + 1 tick (0.25pt) adverse slippage entry & exit.  NQ point=$20._

## Per calendar year
| year | n | WR% | PF | net$ |
|---|---|---|---|---|
| 2021 | 493 | 33.7 | 0.989 | -1,665 |
| 2022 | 1042 | 33.9 | 1.091 | 45,085 |
| 2023 | 984 | 33.1 | 0.944 | -18,795 |
| 2024 | 948 | 36.9 | 1.163 | 58,660 |
| 2025 | 1066 | 34.6 | 1.068 | 34,800 |
| 2026 | 523 | 33.1 | 0.883 | -38,675 |

## IS (2021-2024) vs OOS (2025-2026 H1)
| window | n | WR% | PF | net$ | totalR | maxDD$ |
|---|---|---|---|---|---|---|
| IS 2021-24 | 3467 | 34.5 | 1.062 | 83,285 | -37.9 | 55,625 |
| OOS 2025-26H1 | 1589 | 34.1 | 0.995 | -3,875 | -15.0 | 61,825 |

## Sample trades (faithfulness eyeball)
| entry_time (UTC) | dir | entry | stop | target | exit | R | reason | hold_min |
|---|---|---|---|---|---|---|---|---|
| 2021-06-23 14:41 | short | 14280.00 | 14296.75 | 14246.50 | 14246.50 | 1.96 | target | 118 |
| 2021-06-23 16:56 | long | 14261.25 | 14250.00 | 14283.75 | 14283.75 | 1.93 | target | 29 |
| 2021-06-24 02:50 | short | 14297.75 | 14301.00 | 14291.25 | 14301.00 | -1.23 | stop | 47 |
| 2021-06-24 09:46 | short | 14349.50 | 14357.50 | 14333.50 | 14357.50 | -1.09 | stop | 160 |
| 2021-06-24 15:00 | short | 14388.75 | 14404.25 | 14357.75 | 14404.25 | -1.05 | stop | 71 |

## Faithfulness notes
- **Multi-TF stepping (no lookahead):** 60m/5m values read via searchsorted (side='right') on the closed-HTF-bar close-time array vs the 1m OPEN time — mirrors request.security(lookahead_off). A 60m bar becomes readable only on the 1m bar opening at its close.
- **Pivot confirmation lag:** ta.pivothigh/low(L,R) confirmed R bars late (60m 3/3 = 3h, 5m/1m 2/2). 'Last confirmed pivot' = valuewhen carry-forward.
- **Entry = trigger-bar CLOSE** (process_orders_on_close=true). Exits simulated on 1m bars STARTING THE BAR AFTER entry; stop-first when one bar spans both.
- **Costs** applied to every fill: 1-tick adverse slippage on entry & exit + $2.50/side commission. Target hits land ~+1.93..1.99R, stops ~-1.0..-1.25R (tight-risk trades pay proportionally more cost) — visible in the samples.
- **One position at a time**; a valid fire consumes its context; invalid-risk triggers are counted (risk_rejects) but do NOT consume context (can retry).
- **R vs $ divergence:** total R = -52.9 (NEGATIVE) while net $ = 79,410 (positive). Fixed 1-contract sizing lets a few wide-stop winners dominate raw dollars, but on a risk-normalized (1R-per-trade) basis expectancy is slightly negative (avg R -0.010/trade). Honest read: no robust edge, essentially a coin-flip around the 2R/1R breakeven.
- **1 trade still open** at data end, excluded from closed-trade stats.

## Lookahead / plausibility flags
- None. No config window shows PF>2.5 or WR>70%.
- 2R/1R structure => breakeven WR ~= 33.3%. Observed WR = 34.4% (above breakeven), consistent with PF 1.036.

