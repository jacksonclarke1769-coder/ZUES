# A+VPC Optimisation — Frontier Report (Fable auditor, 2026-07-06)
CSV: this file + 08_robustness_stability.csv are the decision surface. All configs below survive
the config-level mirage bar (no 0.015R deaths; flips 0.048-0.081R; 2x/3x costs pass) — the old
throughput-mirage signature is ABSENT (mechanism: higher budget at modest caps, not contract
scaling). Winners-fill-75% collapse is UNIVERSAL (machine-level, incl. baseline) — governed by
the live fill-telemetry kill line (15% adverse touch-without-fill), not a config selector
(auditor adjudication in 07_top_cell_stress.md).

| class | config | pass/bust/exp | flip R | f/slot-yr | E$/attempt* | verdict |
|---|---|---|---|---|---|---|
| CONSERVATIVE | A700/4 + VPC600/6 | 30.7/11.7/57.6 | 0.067 | ~4.7 | $2,325 | SURVIVES — bust nearly halved vs baseline, pass still +2pp |
| **BALANCED (auditor pick)** | **A900/6 + VPC600/3** | **37.4/18.0/44.6** | **0.068** | **5.89** | **$2,861** | SURVIVES — +8.7pp pass / +1.0pp bust / better flip than baseline |
| THROUGHPUT | A900/6 + VPC700/3 | 39.3/19.6/41.1 | 0.076 | 6.37 | $3,013 | SURVIVES — frontier max; 2025 carries 47% of advantage (under flag, noted) |
| pareto variant | A-1/day@600/6 + VPC[10-14]@600/4 | 29.3/15.9/54.9 | 0.077 | ~4.3 | $2,213 | survives; marginal gain, operational complexity not justified |
| baseline | A600/6 + VPC600/4 | 28.7/17.0/54.4 | 0.055 | 4.22 | $2,165 | DOMINATED (S6 on risk; S5/S3 on output) |
| REJECTED one-regime | A800/4+VPC600/5 · A800/4+VPC600/4 | 31.7/12.0 · 30.7/12.1 | — | — | — | >50% of advantage in 2025 |
| REJECTED (prior) | all cap-10-A throughput combos | 41-45 pass | 0.015-0.019 | — | — | fill mirages (salvage program) |

*E$ = pass%×$8,000−$131, funded value pending re-lock funded re-run at chosen config.
Conflict rule: R0 naive union (11 alternatives tested — 7 denominator artifacts, rest null; A and
VPC almost never fire within 60min of each other). Daily risk: shared $550 (25 variants — none
beat it without artifact). VPC window: full 10:00-15:00 (all restrictions starve the widener).
Exits: current certified (A-1.5R lifts pass to ~32.5 at baseline sizing but is a certification
event — priced separately in the DEC, not bundled).
