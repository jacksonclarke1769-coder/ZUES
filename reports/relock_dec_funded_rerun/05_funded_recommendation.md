# Funded Recommendation (Fable auditor, 2026-07-06)
Survival doctrine applied: funded optimises for not-dying, not for speed.

1. Funded use the eval config? **No** — proven numerically: the negative control (A900/6+VPC600/3
   through the funded simulator) busts 54.8% with median paid $1,499. Phase-split confirmed.
2. Best survival row: **A-kept 300/4 + VPC 150/1 → E[paid] $8,974, bust 2.4% (model-observed),
   stress-survivor at 0.02R.** (Top-E$ cell A250/4+VPC300/2 = $10,291 at bust 14.3% — watchlist.)
3. Kept-D1c A only? Kept-D1c A **as the core, yes** (unfiltered funded remains NOT-VIABLE);
   but a small VPC leg adds real value at near-zero bust cost at the default sizing.
4. Add optional-small VPC? **Yes** — 150/1 (default) improves E[paid] over A-alone with
   negligible bust change; the larger 300/2 leg is the watchlist upgrade.
5. A funded sizing: **$300 / cap 4** (kept-D1c stream).
6. VPC funded sizing: **$150 / cap 1** (default) · $300/cap-2 watchlist.
7. Expected paid: **~$8,974** per funded account (model-observed, overlapping-starts wide CI).
8. Bust rate: **2.4%** model-observed at default (14.3% at watchlist cell).
9. Safety-net reach: ~100% at conservative cells (per matrix; top rows all reach).
10. Time-to-paid: median months in matrix CSV (~18-30mo class for conservative cells) — slow by
    design; the ladder completes or account closes at CLOSED_MAX.
11. Slippage/fill tolerance: default row survives the funded stress bar (0.02R, 2x costs, entry
    realism); winners-fill remains the machine-level universal (telemetry-governed).
12. Robust enough for the DEC? **Yes — as the funded line of the re-lock DEC**, with the wide-CI
    caveat verbatim and "model-observed" language mandatory.
13. Default: **A-kept 300/4 + VPC 150/1.**
14. Watchlist: **A-kept 250/4 + VPC 300/2** ($10.3k / 14.3% — operator may prefer after real
    funded telemetry exists).
15. Disabled: unfiltered-A funded (all cells NOT-VIABLE), eval-style sizing in funded (negative
    control), VPC-only funded (never tested as viable core).
