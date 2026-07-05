# Workstream E — Artifact Audit (2026-07-06)
1. Lookahead canary: PASS (poison-the-future on 4 representative configs spanning both signal paths, entries, exits).
2. Future-poison: PASS (same runs; completed trades byte-identical across cuts).
3. Same-bar ambiguity: PASS structurally (entries only after FVG bar close; 1m fill bar may only stop out).
4. 5m→1m conversion: N/A-by-design — all results generated at 1m truth; no 5m-only number ever existed.
5. Adverse-first ordering: enforced in the 1m walk (stop-first every bar).
6. Year-by-year: no family reached sufficient n; thinness = rejection.
7. Trade-count sanity: kill gate 0.5 tr/wk enforced mechanically.
8. Parameter sensitivity: grids kept coarse/preregistered; no post-hoc tuning permitted or performed.
Flagged PF>1.8 cells (D/15m Asia, n≤17): auditor ruling = small-sample noise, DEAD — NEVER QUOTE.
