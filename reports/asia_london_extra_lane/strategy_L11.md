# L11 — London-Close / Pre-NY Positioning

**Status: TESTED THIS SPRINT (new candidate, never tried before). VERDICT: REJECTED (both variants).**

## Definition

- Window 04:30–08:00 ET ONLY (hard boundary — every open position force-flat at 08:00 via `max_exit_hour=8`; no overlap with NY Profile A prep).
- **(a) Mean-reversion**: causal, session-anchored VWAP computed over 02:00–04:30 ET only (frozen — fully in the past by 04:30, no look-ahead). In the 04:30–08:00 window, first closed bar whose close is ≥ Y points from that frozen VWAP (grid Y ∈ {20, 35}) triggers a fade back toward VWAP, next-bar-open. Stop = the triggering bar's opposite extreme ± 1 tick. Target = the frozen VWAP level.
- **(b) Continuation**: break of the full London-session (02:00–05:00 ET) high/low, evaluated only on bars inside 04:30–08:00. First close beyond the level triggers next-bar-open entry. Stop = breakout bar's opposite extreme ± 1 tick (same convention as this dir's existing S4 baseline). Target 1R/1.5R (grid).
- Causality: VWAP/range windows are both fully completed before the 04:30 trade-window start; entries are next-bar-open after a CLOSE beyond a level; stop-first on ties.
- Data: NQ 5m, 2016-01-01 → 2026-05-25 ET (10.4y). Engine: `l11_london_close_preny.py`; full grid: `l11_grid.csv`.

## Grid @ 1.0pt cost

| variant | cell | n | WR | PF | exp_r | trades/wk |
|---|---|---|---|---|---|---|
| (a) MR | Y=20 | 1850 | 12.6% | 0.81 | −0.807 | 3.41 |
| (a) MR | Y=35 | 1330 | 11.4% | **0.90** | −1.016 | 2.46 |
| (b) continuation | 1R | 2059 | 46.2% | 0.76 | −0.238 | 3.80 |
| (b) continuation | 1.5R | 2059 | 38.6% | 0.77 | −0.242 | 3.80 |

**Every cell in both variants has PF < 1.0.** Best cell overall = MR/Y=35, PF 0.90.

Note on the MR variant: WR ~11-13% with median risk only 2.6pt and median duration 0 minutes is the classic tight-stop/negative-skew signature (see L6's discussion of the same artifact) — here it does NOT even produce a positive $ PF, so it is unambiguously dead regardless of that caveat.

## Best cell yearly splits (MR/Y=35) @ 1.0pt

| year | n | PF | year | n | PF |
|---|---|---|---|---|---|
| 2016 | 19 | 1.98 | 2021 | 159 | 0.88 |
| 2018 | 61 | 1.47 | 2022 | 221 | 0.72 |
| 2019 | 46 | 0.76 | 2023 | 157 | 0.90 |
| 2020 | 161 | 1.20 | 2024 | 187 | 1.21 |
| | | | 2025 | 219 | 0.85 |

Last 6 full years (2020–2025): 2/6 positive (2020, 2024).

## Best cell @ 2.0pt hostile

n=1,330, PF **0.73**, exp_r −2.626.

## Mechanical rejection-bar check

| gate | result |
|---|---|
| PF < 1.15 @ 1.0pt → REJECTED | best cell (either variant) PF ≤ 0.90 — **fails, REJECTED** |
| Positive in < 4 of last 6 full years → REJECTED (one-regime) | 2/6 — also fails independently |
| < 100 trades/10.4y → REJECTED (frequency) | n = 1,330–2,059 — passes (not binding) |

**Verdict: REJECTED — neither variant clears PF 1.0, let alone the 1.15 bar.** Continuation variant is uniformly PF 0.76–0.77 across both targets (no neighbor cell close to threshold); MR variant's best cell (Y=35) also fails the one-regime gate independently. No hostile re-test was needed to reach this verdict; the 2.0pt figure (PF 0.73) is reported for completeness. Confirms the prior register: pre-NY Asia/London-session mechanized strategies have no edge on NQ.
