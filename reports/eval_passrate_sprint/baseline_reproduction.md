# 1A — Baseline Reproduction

**SIM CONDITIONAL — pending live fill evidence**

- Harness path: `tools_sprint_cap_risk.py` (1A section), calling `tools_eval_sizing_sweep.run_cell(cap=10, budget=1200)` on the stream returned by `tools_sim_parity_check.load_rows()`
- Data source: Databento 5m (`apex_eval_eod_databento.load_databento_5m`) + 1m truth (`run_d1c_real.load_1m` via `tools_1m_truth_recert.M1Map`) — loaded transitively inside `load_rows()`
- Provenance pointer: `reports/apex_validation.json` -> `current_machine` = `cap10_relock_2026-07-05`
- Repo HEAD commit: `17c112b6caa6b48615344a51db66b93a723ff8da`

| | n | pass% | bust% | expire% | median days |
|---|---|---|---|---|---|
| Reproduced | 395 | 47.8 | 15.9 | 36.2 | 16 |
| Certified  | 395 | 47.8 | 15.9 | 36.2 | 16 |

## Verdict: **REPRODUCED**

