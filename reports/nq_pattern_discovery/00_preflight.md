# NQ Pattern Discovery — Preflight (2026-07-06)

- Repo HEAD: 4bf64ebac2f6e3ac5b86222a9bb4ad6420b31ec8 (salvage program 4bf64eb, re-cert 818cda8 in history)
- Vault heartbeat: dd3ccbc.. lineage · Incident INC-20260706-1141 · re-cert vault 7ed877a
- LIVE HOLD: ACTIVE · go-live-recert.sh untouched · latest_signal() live fix: TICKETED, NOT DONE (operator-gated)
- Funded hash: 95276d506ec33330… · Eval lock: 3ca389fc5a8a9fe4…
- Tracked modifications: 0 (expect 0)
- DATA: ~/trading-team/data/nq/ NQ+ES+YM+RTY 1m/5m 24h parquet (2014-2026, Databento-sourced, real volume); loaders engine/data.py load_spine + tag_sessions (asia/london/ny_am/lunch/pm; pre_ny added 2026-07-06); causal HTF engine/htf.py; primitives.py (swings/FVG/sweep/displacement); 1m walker + canary salvage_b_misc_common.py; honest A streams via tools_sim_parity_check.load_rows (kept 583) + tools_1m_truth_recert.a_streams (unfiltered 705); funnel via tools_account_size_research (pinned formulas)

## Gate
auto_safety.py: OK
== gate.sh: ALL CHECKS GREEN ==
