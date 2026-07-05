# L10 — Micro Trend Pullback + Time Stop

**Status: TESTED THIS SPRINT (new candidate, never tried before). VERDICT: REJECTED.**

## Definition

- Sessions: Asia (18:00–00:00 ET) and London (02:00–05:00 ET), tested separately, genuine ET clock time (`load_spine()`, no DST drift).
- Trend = causal EMA20 > EMA50 on 5m AND close above both (mirror for short) — recursive `.ewm()`, no look-ahead.
- Entry = pullback TOUCH of EMA20 (signal bar's H/L straddles EMA20) while the trend condition holds on that same closed bar → next-bar-open.
- Stop = recent swing (trailing 12-bar / 1h high or low, computed from bars strictly before the signal bar) OR 1×ATR14 from entry (grid both).
- Target = 1R / 1.5R (grid).
- Time stop: force exit at {6, 12} bars if neither hit (`el_common.simulate_bars` — bar-count exit, same stop-first-tie convention).
- Max 1 trade/session/direction.
- Data: NQ 5m, 2016-01-01 → 2026-05-25 ET (10.4y). Engine: `l10_micro_trend_pullback.py`; full grid: `l10_grid.csv`.

## Full grid (16 cells: 2 sessions × 2 stop variants × 2 targets × 2 time-stops) @ 1.0pt cost

| session | stop | target | time-stop | n | WR | PF | exp_r | trades/wk |
|---|---|---|---|---|---|---|---|---|
| asia | swing | 1R | 6 | 2860 | 45.3% | 0.83 | −0.274 | 6.75 |
| asia | swing | 1R | 12 | 2860 | 47.0% | 0.87 | −0.269 | 6.75 |
| asia | swing | 1.5R | 6 | 2860 | 41.9% | 0.84 | −0.270 | 6.75 |
| asia | swing | 1.5R | 12 | 2860 | 42.4% | 0.87 | −0.266 | 6.75 |
| asia | atr | 1R | 6 | 2860 | 48.7% | 0.81 | −0.145 | 6.75 |
| asia | atr | 1R | 12 | 2860 | 49.9% | 0.84 | −0.142 | 6.75 |
| asia | atr | 1.5R | 6 | 2860 | 42.7% | 0.85 | −0.130 | 6.75 |
| asia | atr | 1.5R | 12 | 2860 | 41.9% | 0.87 | −0.135 | 6.75 |
| london | swing | 1R | 6 | 3206 | 47.1% | 0.90 | −0.230 | 5.92 |
| london | swing | 1R | 12 | 3206 | 48.1% | 0.88 | −0.237 | 5.92 |
| london | swing | 1.5R | 6 | 3206 | 43.5% | **0.91** | −0.217 | 5.92 |
| london | swing | 1.5R | 12 | 3206 | 42.1% | 0.90 | −0.227 | 5.92 |
| london | atr | 1R | 6 | 3206 | 49.0% | 0.82 | −0.203 | 5.92 |
| london | atr | 1R | 12 | 3206 | 50.0% | 0.83 | −0.200 | 5.92 |
| london | atr | 1.5R | 6 | 3206 | 40.8% | 0.86 | −0.191 | 5.92 |
| london | atr | 1.5R | 12 | 3206 | 40.8% | 0.86 | −0.193 | 5.92 |

**Every single cell has PF < 1.0.** Best cell = `london/swing/1.5R/t6`, PF 0.91.

## Best cell yearly splits (`london/swing/1.5R/t6`) @ 1.0pt

| year | n | PF | year | n | PF |
|---|---|---|---|---|---|
| 2016 | 257 | 0.71 | 2021 | 328 | 0.88 |
| 2017 | 251 | 0.50 | 2022 | 332 | 0.79 |
| 2018 | 287 | 0.65 | 2023 | 337 | 0.95 |
| 2019 | 330 | 0.75 | 2024 | 328 | 1.05 |
| 2020 | 320 | 0.91 | 2025 | 313 | 1.21 |

Last 6 full years (2020–2025): only 2/6 positive (2024, 2025).

## Best cell @ 2.0pt hostile

n=3,206, PF **0.76**, exp_r −0.455.

## Mechanical rejection-bar check

| gate | result |
|---|---|
| PF < 1.15 @ 1.0pt → REJECTED | best cell PF = 0.91 — **fails, REJECTED** |
| Positive in < 4 of last 6 full years → REJECTED (one-regime) | 2/6 — **also fails independently** |
| < 100 trades/10.4y → REJECTED (frequency) | n = 3,206 — passes (not the binding constraint) |

**Verdict: REJECTED — PF gate (0.91 < 1.15) and one-regime gate (2/6) both fire independently on the best-of-16-cell result. No cell in the grid clears PF 1.0, let alone 1.15.** No hostile re-test needed to reach this verdict (already dead at baseline cost); the 2.0pt result (PF 0.76) is reported for completeness and confirms further cost-fragility. Family confirms the prior register: Asia/London mechanized session strategies do not have edge on NQ.
