# 00 — Baseline reproduction (CANARY) — Ideas 3/4/5/6 sprint

**RESEARCH ONLY.** Frozen certified Profile A stream (exit3 + D1c, 1m-truth fills). No entry/exit/live change of any kind.

- repo HEAD: `c03e7318441a6539155d9e885f2bd2df95cd08e2`
- provenance: reports/apex_validation.json -> cap10_relock_2026-07-05 (DEC-20260705-1102): eval pass_pct 47.8 / bust 15.9 / expire 36.2 / median 16d, same A10 Exit#3+D1c config this file's canary reproduces via eval_funnel(as_rows(kept),1200,10).

## Canary @ (cap10, $1200 — certified/deployed)
- got:      pass=47.8 bust=15.9 exp=36.2 med=16d n=395
- expected: pass=47.8 bust=15.9 exp=36.2 med=16d n=395
- **MATCH**

## Canary @ (cap15, $1000 — standing candidate, for reference)
- pass=55.2 bust=13.4 exp=31.4 med=15d n=395

## Stream confirmations
- n kept (certified): 435  (pre-D1c raw ny_am signals: 705)
- WR (raw 435-trade pass, R>0 share): 58.6% — expected ~58.6%
- trades/week over full span (2021-06-25 10:25:00-04:00 -> 2026-06-17 09:40:00-04:00, 259.6 weeks): 1.68 — expected ~1.7-1.8/wk

## Firewall
`assert_parity()` (byte-for-byte vs `tools_sim_parity_check.load_rows()`) checked before any of the above is trusted — see console output / calling script's PARITY FIREWALL line.

---
All numbers RESEARCH ONLY / SIM CONDITIONAL. No commits.
