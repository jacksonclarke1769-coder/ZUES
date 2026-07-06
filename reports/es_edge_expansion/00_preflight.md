# ES Edge Expansion — Preflight (2026-07-06)

- Worktree: ~/trading-team/bot/zeus-es-research · branch research/es-pass-rate @ b8e42f2 (off main b8e42f2)
- CONSOLIDATION NOTE: this program absorbs the es_third_lane program (preflight-only stage) into the full 14-model register; single worktree per operator's verify-and-document clause; outputs → reports/es_edge_expansion/
- LIVE HOLD ACTIVE · go-live-recert.sh untouched · funded hash: 95276d506ec33330…
- Tracked modifications: 0 (expect 0; config.py is a provisioned gitignored copy)
- ES data: ~/trading-team/data/nq/ES_1m_24h.parquet (validation = report 01) · ES→MES sizing (MES $5/pt, tick 0.25) · costs: honest 1pt/side prior convention pending validation-lane confirmation
- Benchmark: NQ A900/6+VPC600/3 = 37.4/18.0/44.6 f/slot 5.89 flip 0.068R · Gold lane KILLED b8e42f2 (not revived) · ES A-port DEAD (KRONOS PF 0.718, cited not re-run) · ES-ORB PF 1.22 = incumbent prior, REVALIDATION REQUIRED (VPC-rescue pattern)
- Global evaluation rules acknowledged: closed-candle signals, next-bar-open default, 1m truth, adverse-first, costs always, REJECTED_FILL_MIRAGE / WATCHLIST_ONE_REGIME / REJECTED_DENOMINATOR_ARTIFACT labels in force

## Gate
auto_safety.py: OK
== gate.sh: ALL CHECKS GREEN ==
