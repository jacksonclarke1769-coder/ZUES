# 1D — Cushion-aware sizing — SIM CONDITIONAL

Eval-sizing sprint workstream, RESEARCH ONLY. Replayed on the frozen certified Profile A stream via `tools_sprint_state_policies.py`. All numbers below are SIM CONDITIONAL (trade-level replay of a fixed historical stream; not a live guarantee).

## Baselines for comparison
- Certified baseline (10,$1200), C0 none: pass 47.8%, bust 15.9%, exp 36.2%
- Best 1D row overall (any policy/base): **C0_none @ 15,$1000 (candidate)** — pass 55.2%, bust 13.4%, exp 31.4%

Prior figure quoted for comparison (pre-relock, invalid vintage): P(pass|2-loss)=14.4%, P(pass|3-loss)=1.5%. This harness's own null-policy (C0 @ 10,$1200) cohort figures: P(pass|2-loss)=14.4%, P(pass|3-loss)=1.5% (n_hit2=180, n_hit3=67) -- closely matches the quoted prior figures, a good internal-consistency sanity check.

## Same-base verdict (isolates the STATE POLICY effect from the sizing-base effect)

| base | flat/null best | real-policy best | delta (real - flat) |
|---|---|---|---|
| 10,$1200 (certified) | C0_none (47.8%) | C2_normal-cap10-block (47.8%) | +0.0pt |
| 15,$1000 (candidate) | C0_none (55.2%) | C2_normal-cap10-block (51.6%) | -3.6pt |

**Verdict:** 1D cushion-aware sizing: best real-policy delta over its own same-base flat/null anchor is +0.0pt (n=395 either way) -- AGREES with the prior finding ("account-state sizing policies all dead").

**Bust-vs-expire shape note:** C2 (normal/cap10/block) @ 10,$1200 ties baseline pass% (47.8% vs 47.8%) while cutting bust% from 15.9% to 3.8% and raising expire% from 36.2% to 48.4% -- busts convert to expires, pass% flat. Consistent with the prior finding's mechanism.

## Outcomes-after-double-loss / after-triple-loss cohorts (all policies)

| policy | base | n hit 2-loss | pass% after 2-loss | n hit 3-loss | pass% after 3-loss |
|---|---|---|---|---|---|
| C0_none | 10,$1200 (certified) | 180 | 14.4 | 67 | 1.5 |
| C0_none | 15,$1000 (candidate) | 176 | 25.0 | 64 | 1.6 |
| C1_tiered_100-75-50-25pct | 10,$1200 (certified) | 183 | 13.7 | 72 | 1.4 |
| C1_tiered_100-75-50-25pct | 15,$1000 (candidate) | 179 | 17.9 | 68 | 0.0 |
| C2_normal-cap10-block | 10,$1200 (certified) | 180 | 14.4 | 51 | 2.0 |
| C2_normal-cap10-block | 15,$1000 (candidate) | 174 | 21.3 | 56 | 5.4 |
| C3_double-loss-aware | 10,$1200 (certified) | 180 | 12.8 | 67 | 0.0 |
| C3_double-loss-aware | 15,$1000 (candidate) | 176 | 15.3 | 63 | 0.0 |
| C4_no-rescue-monotone | 10,$1200 (certified) | 189 | 10.6 | 73 | 1.4 |
| C4_no-rescue-monotone | 15,$1000 (candidate) | 183 | 12.0 | 69 | 4.3 |

## Per-policy funnel (both sizing bases)

| policy | base | n | pass% | bust% | exp% | med/mean days | worst day | E[$/attempt] | n_trades | WR% | PF(R) | expR | clipped% | risk-used$ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C0_none | 10,$1200 (certified) | 395 | 47.8 | 15.9 | 36.2 | 16/16.0 | -1000 | 5959.1 | 2426 | 58.5 | 2.276 | 0.4156 | 66.1 | 775.2 |
| C0_none | 15,$1000 (candidate) | 395 | 55.2 | 13.4 | 31.4 | 15/16.6 | -1000 | 6893.6 | 2388 | 58.9 | 2.353 | 0.431 | 36.2 | 817.8 |
| C1_tiered_100-75-50-25pct | 10,$1200 (certified) | 395 | 46.3 | 8.1 | 45.6 | 16/16.1 | -1000 | 5765.8 | 2573 | 58.2 | 2.242 | 0.4084 | 58.9 | 708.5 |
| C1_tiered_100-75-50-25pct | 15,$1000 (candidate) | 395 | 47.3 | 3.0 | 49.6 | 15/16.3 | -1000 | 5894.7 | 2576 | 58.6 | 2.324 | 0.4252 | 29.6 | 722.8 |
| C2_normal-cap10-block | 10,$1200 (certified) | 395 | 47.8 | 3.8 | 48.4 | 16/16.0 | -1000 | 5959.1 | 2293 | 58.5 | 2.264 | 0.4139 | 66.8 | 770.3 |
| C2_normal-cap10-block | 15,$1000 (candidate) | 395 | 51.6 | 2.5 | 45.8 | 15/16.2 | -1000 | 6442.4 | 2250 | 58.8 | 2.349 | 0.4277 | 40.0 | 795.8 |
| C3_double-loss-aware | 10,$1200 (certified) | 395 | 47.1 | 9.1 | 43.8 | 16/16.0 | -1000 | 5862.4 | 2303 | 59.8 | 2.432 | 0.4463 | 61.5 | 764.0 |
| C3_double-loss-aware | 15,$1000 (candidate) | 395 | 50.9 | 5.3 | 43.8 | 15/16.0 | -1000 | 6345.8 | 2276 | 60.1 | 2.492 | 0.4575 | 33.2 | 788.0 |
| C4_no-rescue-monotone | 10,$1200 (certified) | 395 | 39.7 | 4.6 | 55.7 | 16/16.2 | -1000 | 4928.0 | 2689 | 58.6 | 2.296 | 0.4187 | 49.8 | 646.6 |
| C4_no-rescue-monotone | 15,$1000 (candidate) | 395 | 38.7 | 3.8 | 57.5 | 15/15.5 | -1000 | 4799.1 | 2664 | 58.8 | 2.334 | 0.4282 | 23.7 | 650.3 |

## Per-year pass% (2021-2026)

| policy | base | 2021 (n) | 2022 (n) | 2023 (n) | 2024 (n) | 2025 (n) | 2026 (n) |
|---|---|---|---|---|---|---|---|
| C0_none | 10,$1200 (certified) | 51.1% (45) | 38.6% (70) | 52.8% (89) | 35.1% (74) | 62.9% (89) | 35.7% (28) |
| C0_none | 15,$1000 (candidate) | 57.8% (45) | 48.6% (70) | 66.3% (89) | 36.5% (74) | 66.3% (89) | 46.4% (28) |
| C1_tiered_100-75-50-25pct | 10,$1200 (certified) | 48.9% (45) | 37.1% (70) | 51.7% (89) | 33.8% (74) | 62.9% (89) | 28.6% (28) |
| C1_tiered_100-75-50-25pct | 15,$1000 (candidate) | 53.3% (45) | 28.6% (70) | 60.7% (89) | 29.7% (74) | 62.9% (89) | 39.3% (28) |
| C2_normal-cap10-block | 10,$1200 (certified) | 51.1% (45) | 38.6% (70) | 52.8% (89) | 35.1% (74) | 62.9% (89) | 35.7% (28) |
| C2_normal-cap10-block | 15,$1000 (candidate) | 53.3% (45) | 44.3% (70) | 64.0% (89) | 37.8% (74) | 59.6% (89) | 39.3% (28) |
| C3_double-loss-aware | 10,$1200 (certified) | 51.1% (45) | 38.6% (70) | 51.7% (89) | 31.1% (74) | 64.0% (89) | 35.7% (28) |
| C3_double-loss-aware | 15,$1000 (candidate) | 53.3% (45) | 44.3% (70) | 59.6% (89) | 32.4% (74) | 64.0% (89) | 42.9% (28) |
| C4_no-rescue-monotone | 10,$1200 (certified) | 42.2% (45) | 28.6% (70) | 41.6% (89) | 21.6% (74) | 62.9% (89) | 32.1% (28) |
| C4_no-rescue-monotone | 15,$1000 (candidate) | 35.6% (45) | 31.4% (70) | 44.9% (89) | 24.3% (74) | 52.8% (89) | 35.7% (28) |
