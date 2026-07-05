# 1F — Near-target protection — SIM CONDITIONAL

Eval-sizing sprint workstream, RESEARCH ONLY. Replayed on the frozen certified Profile A stream via `tools_sprint_state_policies.py`. All numbers below are SIM CONDITIONAL (trade-level replay of a fixed historical stream; not a live guarantee).

## Baselines for comparison
- Certified baseline (10,$1200), P0 none: pass 47.8%, bust 15.9%, exp 36.2%
- Best 1F row overall (any policy/base): **P0_none @ 15,$1000 (candidate)** — pass 55.2%, bust 13.4%, exp 31.4%

## Same-base verdict (isolates the STATE POLICY effect from the sizing-base effect)

| base | flat/null best | real-policy best | delta (real - flat) |
|---|---|---|---|
| 10,$1200 (certified) | P0_none (47.8%) | P1_tiered_half-then-cap10 (48.1%) | +0.3pt |
| 15,$1000 (candidate) | P0_none (55.2%) | P2_one-shot_take-next-only (55.2%) | +0.0pt |

**Verdict:** 1F near-target protection: best real-policy delta over its own same-base flat/null anchor is +0.3pt (n=395 either way) -- AGREES with the prior finding ("account-state sizing policies all dead").

## P3 structural check (not a simulated policy)

`simulate_start_policy` (like `tools_sim_parity_check.simulate_start` and `tools_account_size_research.eval_run` before it) checks `bal >= sb+tg` only at END-OF-DAY and `return`s IMMEDIATELY the first time it is true — the function's control flow makes it structurally impossible for any further day to be processed once PASS is returned. Verified by code inspection: the `PASS` return sits at the bottom of the per-day loop body, before the loop can advance `di`. No entries after target-crossed are possible under this frozen EOD model. Structural check: PASS.

## Near-miss accounts saved vs delayed-into-expiry (counterfactual vs that base's P0)

| policy | base | n saved (P0 not-PASS -> policy PASS) | n delayed-into-expiry (P0 PASS -> policy EXPIRE) |
|---|---|---|---|
| P0_none | 10,$1200 (certified) | 0 | 0 |
| P1_tiered_half-then-cap10 | 10,$1200 (certified) | 4 | 3 |
| P2_one-shot_take-next-only | 10,$1200 (certified) | 0 | 0 |
| P4_near-and-above-start_half | 10,$1200 (certified) | 4 | 3 |
| P0_none | 15,$1000 (candidate) | 0 | 0 |
| P1_tiered_half-then-cap10 | 15,$1000 (candidate) | 3 | 8 |
| P2_one-shot_take-next-only | 15,$1000 (candidate) | 0 | 0 |
| P4_near-and-above-start_half | 15,$1000 (candidate) | 3 | 9 |

## Per-policy funnel (both sizing bases)

| policy | base | n | pass% | bust% | exp% | med/mean days | worst day | E[$/attempt] | n_trades | WR% | PF(R) | expR | clipped% | risk-used$ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P0_none | 10,$1200 (certified) | 395 | 47.8 | 15.9 | 36.2 | 16/16.0 | -1000 | 5959.1 | 2426 | 58.5 | 2.276 | 0.4156 | 66.1 | 775.2 |
| P1_tiered_half-then-cap10 | 10,$1200 (certified) | 395 | 48.1 | 15.9 | 35.9 | 16/16.1 | -1000 | 5991.3 | 2426 | 58.5 | 2.285 | 0.4173 | 63.3 | 754.9 |
| P2_one-shot_take-next-only | 10,$1200 (certified) | 395 | 47.8 | 15.9 | 36.2 | 16/16.0 | -1000 | 5959.1 | 2419 | 58.5 | 2.278 | 0.4157 | 66.2 | 774.6 |
| P4_near-and-above-start_half | 10,$1200 (certified) | 395 | 48.1 | 15.9 | 35.9 | 16/16.1 | -1000 | 5991.3 | 2426 | 58.5 | 2.285 | 0.4173 | 63.3 | 754.9 |
| P0_none | 15,$1000 (candidate) | 395 | 55.2 | 13.4 | 31.4 | 15/16.6 | -1000 | 6893.6 | 2388 | 58.9 | 2.353 | 0.431 | 36.2 | 817.8 |
| P1_tiered_half-then-cap10 | 15,$1000 (candidate) | 395 | 53.9 | 13.4 | 32.7 | 15/16.6 | -1000 | 6732.5 | 2404 | 58.8 | 2.339 | 0.4284 | 34.1 | 774.9 |
| P2_one-shot_take-next-only | 15,$1000 (candidate) | 395 | 55.2 | 13.4 | 31.4 | 15/16.6 | -1000 | 6893.6 | 2381 | 59.0 | 2.36 | 0.4321 | 36.3 | 817.4 |
| P4_near-and-above-start_half | 15,$1000 (candidate) | 395 | 53.7 | 13.4 | 32.9 | 15/16.5 | -1000 | 6700.2 | 2403 | 58.8 | 2.337 | 0.4279 | 33.7 | 776.2 |

## Per-year pass% (2021-2026)

| policy | base | 2021 (n) | 2022 (n) | 2023 (n) | 2024 (n) | 2025 (n) | 2026 (n) |
|---|---|---|---|---|---|---|---|
| P0_none | 10,$1200 (certified) | 51.1% (45) | 38.6% (70) | 52.8% (89) | 35.1% (74) | 62.9% (89) | 35.7% (28) |
| P1_tiered_half-then-cap10 | 10,$1200 (certified) | 51.1% (45) | 38.6% (70) | 51.7% (89) | 36.5% (74) | 64.0% (89) | 35.7% (28) |
| P2_one-shot_take-next-only | 10,$1200 (certified) | 51.1% (45) | 38.6% (70) | 52.8% (89) | 35.1% (74) | 62.9% (89) | 35.7% (28) |
| P4_near-and-above-start_half | 10,$1200 (certified) | 51.1% (45) | 38.6% (70) | 51.7% (89) | 36.5% (74) | 64.0% (89) | 35.7% (28) |
| P0_none | 15,$1000 (candidate) | 57.8% (45) | 48.6% (70) | 66.3% (89) | 36.5% (74) | 66.3% (89) | 46.4% (28) |
| P1_tiered_half-then-cap10 | 15,$1000 (candidate) | 53.3% (45) | 47.1% (70) | 64.0% (89) | 35.1% (74) | 67.4% (89) | 46.4% (28) |
| P2_one-shot_take-next-only | 15,$1000 (candidate) | 57.8% (45) | 48.6% (70) | 66.3% (89) | 36.5% (74) | 66.3% (89) | 46.4% (28) |
| P4_near-and-above-start_half | 15,$1000 (candidate) | 53.3% (45) | 47.1% (70) | 64.0% (89) | 33.8% (74) | 67.4% (89) | 46.4% (28) |
