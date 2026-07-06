# JOB 4 (B8) -- YM/RTY Port Closure -- RESEARCH ONLY (tombstone)

Runtime: 29.7s. Frozen Profile A v2 (Exit#3, entry_type=ote, rr=2.0) ported via `models.model01_sweep_mss_fvg.run()` + `engine.htf.build_features()` -- identical engine call KRONOS Candidate E used for ES (`kronos_validate_CE.py`), instrument swapped.

ES reference (CITED, NOT RE-RUN, per instructions): full N=1,530, PF 0.718, expR -0.171, IS 2014-2021 PF 0.596, negative in 11/13 years, 2x slip PF 0.480 (`reports/kronos-vs-zeus-2026-06-12.md` Candidate E).

## Cost scaling (documented)

| instrument | tick | slip_ticks | SLIP ($/pt terms) | $/point (SPECS) |
|---|---|---|---|---|
| NQ (ref) | 0.25 | 4 | 1.0pt | $20 |
| ES (cited) | 0.25 | 4 | 1.0pt | $50 |
| YM | 1.0 | 1 | 1.0pt | $5.0 |
| RTY | 0.1 | 10 | 1.0pt | $50.0 |

## Results

### YM (src=YM_5m_24h_full.parquet)

- N=1460, full PF=1.14, full expR=0.0611
- IS 2014-2021: n=928, PF=1.111
- OOS 2022-2026: n=532, PF=1.196
- years positive: 11/13; last-6-full-years positive: 6/6
- frequency: 2.259 tr/wk
- per-year: {2014: {'n': 125, 'pf': 0.854, 'tot_r': np.float64(-9.68)}, 2015: {'n': 105, 'pf': 1.181, 'tot_r': np.float64(8.25)}, 2016: {'n': 100, 'pf': 1.163, 'tot_r': np.float64(7.08)}, 2017: {'n': 110, 'pf': 1.091, 'tot_r': np.float64(4.23)}, 2018: {'n': 132, 'pf': 1.334, 'tot_r': np.float64(18.68)}, 2019: {'n': 127, 'pf': 1.101, 'tot_r': np.float64(5.77)}, 2020: {'n': 125, 'pf': 1.107, 'tot_r': np.float64(6.2)}, 2021: {'n': 104, 'pf': 1.125, 'tot_r': np.float64(5.47)}, 2022: {'n': 121, 'pf': 1.216, 'tot_r': np.float64(11.43)}, 2023: {'n': 123, 'pf': 1.157, 'tot_r': np.float64(8.41)}, 2024: {'n': 112, 'pf': 1.446, 'tot_r': np.float64(18.48)}, 2025: {'n': 126, 'pf': 1.165, 'tot_r': np.float64(8.31)}, 2026: {'n': 50, 'pf': 0.847, 'tot_r': np.float64(-3.46)}}
- **VERDICT: DEAD** -- reasons: PF 1.140 < 1.15

### RTY (src=RTY_5m_24h_full.parquet)

- N=938, full PF=0.707, full expR=-0.1758
- IS 2018-2021: n=426, PF=0.611
- OOS 2022-2026: n=512, PF=0.803
- years positive: 2/9; last-6-full-years positive: 1/6
- frequency: 2.308 tr/wk
- per-year: {2018: {'n': 40, 'pf': 0.34, 'tot_r': np.float64(-21.74)}, 2019: {'n': 114, 'pf': 0.423, 'tot_r': np.float64(-53.36)}, 2020: {'n': 123, 'pf': 0.806, 'tot_r': np.float64(-14.01)}, 2021: {'n': 149, 'pf': 0.757, 'tot_r': np.float64(-20.19)}, 2022: {'n': 121, 'pf': 0.664, 'tot_r': np.float64(-22.88)}, 2023: {'n': 117, 'pf': 1.051, 'tot_r': np.float64(2.93)}, 2024: {'n': 113, 'pf': 0.803, 'tot_r': np.float64(-12.71)}, 2025: {'n': 115, 'pf': 0.584, 'tot_r': np.float64(-29.15)}, 2026: {'n': 46, 'pf': 1.282, 'tot_r': np.float64(6.2)}}
- **VERDICT: DEAD** -- reasons: PF 0.707 < 1.15; only 1/6 of last-6-full-years PF>=1.0

## Verdict

**DEAD on both instruments -- TOMBSTONE CONFIRMED.** The NY-AM liquidity-raid / sweep-MSS-FVG edge does not port to YM or RTY, joining ES (PF 0.718), gold, and session-research as the 4th/5th confirmation that this edge is NQ-specific. Close the cross-instrument-expansion door for this edge family; no further single-instrument ports are worth attempting without a structurally different edge thesis.

**Notable nuance (not a survivor, still DEAD):** YM is a much closer near-miss than ES or RTY -- full PF 1.14 (vs ES 0.718, RTY 0.707), 11/13 years positive, 6/6 of the last 6 full years PF>=1.0, OOS PF 1.196 > IS PF 1.111 (improving, not decaying). It fails the kill gate on the PF>=1.15 line alone (1.140), by a hair, at these exact frozen params/costs. This is worth a FUTURE flag (not actioned here, out of this closure job's scope, and one still-DEAD near-miss does not overturn the 3x NQ-specificity finding) if anyone later wants to re-test YM specifically with its own tuned params rather than NQ's frozen ones.
