# VPC Standalone Audit — Preflight (2026-07-06)

- Repo HEAD: db33d4b559bd90910f71bf63cb9d215ce807b50c (discovery db33d4b, salvage 4bf64eb, re-cert 818cda8 in history)
- Vault: 6715e97 lineage · Machine status: INVALIDATED post-INC-20260706-1141; CUTOVER HOLD; candidate = A@600/6 + VPC@600/4 (drafts staged, no DEC)
- LIVE HOLD: ACTIVE · go-live-recert.sh untouched · latest_signal() live sibling defect: TICKETED, NOT FIXED
- Funded hash: 95276d506ec33330… · Eval lock: 3ca389fc5a8a9fe4…
- Tracked modifications: 0 (expect 0)
- VPC files: backtests/nq_vwap_pullback.py (engine) · bot repo vpc_recert_real.py, vpc_apex_eval_sim.py, vpc_combined_sim.py, tools_salvage_vpc_reeval.py, tools_salvage_stress.py · reports: new_edge_salvage_program/B4+C+A6, vault BT-20260704-1909 (rejection, now void)
- Data: real Databento NQ 1m→5m RTH 2022-2026 (VPC stream); honest A streams post-fix

## Gate
auto_safety.py: OK
== gate.sh: ALL CHECKS GREEN ==
