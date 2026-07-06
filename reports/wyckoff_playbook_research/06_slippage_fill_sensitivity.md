# W6 Fill-Realism Stress Test (auditor follow-up, 2026-07-06)

## Preregistered prediction (stated by the auditor BEFORE this script ran)

> both W6 families die under (2a)+(2c): PF < 1.15

(2a)+(2c) worst cell = extra_slip_pts=0.50, tick_pen=2 (deepest penetration + largest slippage stress tested).

**RESULT: prediction REFUTED.**

| family | variant | n | PF | expR | totR |
|---|---|---|---|---|---|
| A_london | 2a2c_combined_slip0.50_tick2 | 449 | 1.24 | 0.152 | 68.2 |
| B_24h | 2a2c_combined_slip0.50_tick2 | 578 | 1.03 | 0.017 | 9.5 |

## Full grid (both families)


### A_london  (5m,1m lb=20 session=london exit=fixed2r)

| variant | extra_slip_pts | tick_pen | r_damage | n | tr_wk | win_pct | PF | expR | totR | maxDD_R |
|---|---|---|---|---|---|---|---|---|---|---|
| 0_baseline_reproduce | 0.0 | 0 | 0.0 | 611 | 0.9446 | 44.5 | 1.2 | 0.132 | 80.5 | -61.9 |
| 1_no_stress (== baseline) | 0.0 | 0 | 0.0 | 611 | 0.9446 | 44.5 | 1.2 | 0.132 | 80.5 | -61.9 |
| 2c_tick_pen_1 | 0.0 | 1 | 0.0 | 549 | 0.8487 | 43.5 | 1.18 | 0.117 | 64.1 | -45.5 |
| 2c_tick_pen_2 | 0.0 | 2 | 0.0 | 449 | 0.6941 | 46.1 | 1.37 | 0.224 | 100.4 | -29.6 |
| 2a_slip_plus_0.25pt | 0.25 | 0 | 0.0 | 611 | 0.9446 | 43.7 | 1.17 | 0.115 | 70.1 | -61.1 |
| 2a2c_combined_slip0.25_tick1 | 0.25 | 1 | 0.0 | 549 | 0.8487 | 43.4 | 1.18 | 0.118 | 64.8 | -45.0 |
| 2a2c_combined_slip0.25_tick2 | 0.25 | 2 | 0.0 | 449 | 0.6941 | 43.4 | 1.23 | 0.148 | 66.4 | -37.4 |
| 2a_slip_plus_0.50pt | 0.5 | 0 | 0.0 | 611 | 0.9446 | 43.5 | 1.18 | 0.117 | 71.7 | -60.3 |
| 2a2c_combined_slip0.50_tick1 | 0.5 | 1 | 0.0 | 549 | 0.8487 | 41.2 | 1.09 | 0.058 | 32.1 | -53.5 |
| 2a2c_combined_slip0.50_tick2 | 0.5 | 2 | 0.0 | 449 | 0.6941 | 43.4 | 1.24 | 0.152 | 68.2 | -36.0 |
| 2b_rdamage_minus_0.02R | 0.0 | 0 | 0.02 | 611 | 0.9446 | 44.5 | 1.17 | 0.112 | 68.3 | -62.9 |
| 2b_rdamage_minus_0.05R | 0.0 | 0 | 0.05 | 611 | 0.9446 | 44.5 | 1.12 | 0.082 | 50.0 | -64.4 |

### B_24h  (5m,1m lb=40 session=24h-control exit=fixed2r)

| variant | extra_slip_pts | tick_pen | r_damage | n | tr_wk | win_pct | PF | expR | totR | maxDD_R |
|---|---|---|---|---|---|---|---|---|---|---|
| 0_baseline_reproduce | 0.0 | 0 | 0.0 | 762 | 1.178 | 45.1 | 1.19 | 0.12 | 91.2 | -69.4 |
| 1_no_stress (== baseline) | 0.0 | 0 | 0.0 | 762 | 1.178 | 45.1 | 1.19 | 0.12 | 91.2 | -69.4 |
| 2c_tick_pen_1 | 0.0 | 1 | 0.0 | 661 | 1.0219 | 43.1 | 1.1 | 0.067 | 44.5 | -61.0 |
| 2c_tick_pen_2 | 0.0 | 2 | 0.0 | 578 | 0.8936 | 43.8 | 1.13 | 0.08 | 46.1 | -53.0 |
| 2a_slip_plus_0.25pt | 0.25 | 0 | 0.0 | 762 | 1.178 | 43.8 | 1.13 | 0.084 | 63.7 | -76.0 |
| 2a2c_combined_slip0.25_tick1 | 0.25 | 1 | 0.0 | 661 | 1.0219 | 41.8 | 1.03 | 0.019 | 12.8 | -80.8 |
| 2a2c_combined_slip0.25_tick2 | 0.25 | 2 | 0.0 | 578 | 0.8936 | 43.4 | 1.11 | 0.072 | 41.4 | -55.4 |
| 2a_slip_plus_0.50pt | 0.5 | 0 | 0.0 | 762 | 1.178 | 42.1 | 1.04 | 0.028 | 21.7 | -78.6 |
| 2a2c_combined_slip0.50_tick1 | 0.5 | 1 | 0.0 | 661 | 1.0219 | 41.3 | 1.01 | 0.008 | 5.6 | -82.3 |
| 2a2c_combined_slip0.50_tick2 | 0.5 | 2 | 0.0 | 578 | 0.8936 | 41.7 | 1.03 | 0.017 | 9.5 | -80.7 |
| 2b_rdamage_minus_0.02R | 0.0 | 0 | 0.02 | 762 | 1.178 | 45.1 | 1.15 | 0.1 | 75.9 | -72.2 |
| 2b_rdamage_minus_0.05R | 0.0 | 0 | 0.05 | 762 | 1.178 | 45.1 | 1.1 | 0.07 | 53.1 | -76.3 |

## Notes

- `n` counts only FILLED setups; tick-penetration misses within the existing fill window are NO-TRADE (dropped), not substituted -- this is why n falls as tick_pen rises, independent of any PF change.

- Slippage is modeled as extra ADVERSE points added to the fill price at the moment of touch (worse for the trader), which mechanically both enlarges risk_pts (entry moves further from the fixed stop-loss price) and reduces gross points to any given exit -- applied on top of the SAME base 1.2pt RT cost used everywhere else in this research line (not a replacement for it).

- R-damage variants are a generic post-hoc haircut (independent of fill mechanics) applied to the (slip=0, tick_pen=0) baseline stream only.

- Baseline sanity check: row '0_baseline_reproduce' should exactly match the certified 03_standalone_results.csv PF/n for each family (confirms no drift in the re-implemented walker vs wyckoff_engine.detect_W6 + simulate_setups).
