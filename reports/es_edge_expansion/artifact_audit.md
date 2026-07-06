# ES Edge Expansion — Artifact Audit (Fable auditor, 2026-07-06)
- Canaries: every stream/benchmark canary exact (M1 cell, honest-A, VPC 1m-truth, cap-10 internal,
  benchmark 37.4/18.0/44.6; the stress lane independently reproduced the benchmark flip 0.068R).
- 1m truth + adverse-first: all lanes via the shared walkers; valid-day mask enforced program-wide.
- Freeze flags: two tiny-n M11 cells (n=21/38) — WATCHLIST_ONE_REGIME, dead with family. M8 best
  1.79 — un-adjudicable on proxy data (see below). No other PF>1.8 anywhere in ~5,000 cells.
- Direction confound: long/short splits reported per lane; no M1-style confound found.
- Denominator artifacts: count columns everywhere; portfolio flags mechanical; none found.
- DST: validated 4/4 boundaries; the gold-lane method reused.
- Roll artifacts: N/A (CFD continuous) — flagged as a REALISM LIMIT, not a convenience.
- PROXY CAVEAT (the program's biggest): Dukascopy CFD index, documented optimistic bias vs real
  futures, worst at the open — where M8's gap edges live. All numbers research-grade only.
- KNOWN DEFECT (open): lane_c_common.load_1m_rth_by_date() strips tz via .values; simulate_exit
  re-localizes → blocked M8 regeneration (4th appearance of the tz-seam class). Logged; fix folds
  into any future M8-with-real-data work. No certified numbers touched (research-lane only).
- Refusal/spec discipline: one implementer boundary-stop resolved by template-conformant re-spec
  with mechanical flags (the repo contract working as written).
