# ES Third-Lane — Preflight (2026-07-06)

- Worktree: ~/trading-team/bot/zeus-es-research · branch research/es-pass-rate off main@b8e42f2
- LIVE HOLD ACTIVE · go-live-recert.sh untouched · funded hash: 95276d506ec33330…
- NQ benchmark: A900/6+VPC600/3 = 37.4/18.0/44.6, f/slot 5.89, flip 0.068R (main@1a8152f) · Gold lane: KILLED b8e42f2 (window artifact — not revived here)
- ES data: ~/trading-team/data/nq/ES_1m_24h.parquet (validation pending, 01_data_validation.md) · symbol ES→MES for sizing (MES $5/pt, ES $50/pt, tick 0.25)
- PRIOR ART: ES A-port DEAD (KRONOS PF 0.718, cited not re-run) · ES-ORB continuation = VALIDATED 2nd edge (PF 1.22, all yrs, corr 0.17) rejected vs the OLD fictional machine → REVALIDATION REQUIRED (VPC-rescue pattern; gold-style extended-window treatment)

## Gate
- NOTE: first gate run failed at collection (fresh worktree lacks gitignored config.py — provisioned by read-only copy from main checkout; .venv not needed, system python3 pandas 2.3.3). Re-run below is authoritative.

!!!!!!!!!!!!!!!!!!! Interrupted: 12 errors during collection !!!!!!!!!!!!!!!!!!!
12 errors in 2.66s

auto_safety.py: OK
== gate.sh: ALL CHECKS GREEN == (post-provisioning)
