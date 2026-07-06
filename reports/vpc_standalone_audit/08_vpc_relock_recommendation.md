# VPC Re-Lock Recommendation (Fable auditor, 2026-07-06)
RESEARCH/CERT-PREP ONLY · LIVE HOLD ACTIVE · nothing wired, nothing promoted.

## The 15 answers
1. **What is VPC?** VWAP-Pullback Continuation (nq_vwap_pullback.py): in an established NQ trend
   (slope/trend gates), price pierces session VWAP and closes back through → next-bar-open market
   entry with the trend; 2.5×ATR stop, 5.0×ATR trailing exit; 10:00–15:00 ET; max 2/day; 5m bars
   off real 1m Databento. The harvestable expression of opening-drive persistence.
2. **Standalone stats:** 408 trades 2022-2026 (~1.8/wk), PF 1.294 native / **1.318 at 1m truth**,
   WR 45.1%, net +5,320pt (1m), long PF 1.35 / short 1.23 (both positive — no direction confound),
   5/5 years positive, IS 1.21 / OOS 1.39, maxDD ~$2.1-2.6k per 1 MNQ.
3. **Standalone edge?** Yes — modest and real. But NOT an eval business alone: at (600,4) it
   passes only 10.8% (86% expiry; 1.8/wk is too slow for the 30-day clock). Same disease as
   solo Profile A, opposite symptom severity.
4. **Mainly a portfolio diversifier?** Yes — precisely quantified: its value is CALENDAR WIDENING,
   not hedging. 225 of its days are days A sleeps (PF 1.26 on exactly those days); co-active
   correlation 0.358, offset days (23) fewer than joint-loss days (65). It fills A's empty days.
5. **Eval sizing:** VPC @$600/cap-4 as the second leg of A@600/6 (the re-lock candidate row at 1m
   truth: **28.7 pass / 17.0 bust / 54.4 expire**, ~3.95 tr/wk, funded/slot-yr ~4.0).
6. **Funded sizing:** optional small leg @$200/cap-2 (+$1,275 E[paid] vs A-alone, 0% observed bust)
   — degrades under heavy slippage; keep small or omit; operator's choice in the DEC.
7. **Improves pass/bust?** Pass +18.7pp / bust +12.0pp / **expire −30.8pp** vs A-alone at the
   recommended sizing — the expire reduction is the dominant mechanism (see 4).
8. **Materially reduces expiry?** Yes — the single largest effect in the portfolio.
9. **Materially increases bust?** Yes, +12pp from a 3.5% base — the price of trading more; the
   exchange rate (1.56 pass-pp per bust-pp) and slot-year throughput justify it.
10. **Survives stress?** Standalone break 0.093R; portfolio 0.046R; chase-entry stress mild
    (cert already survived 3pt flat costs); parameter plateau on all three grids; 1m-truth
    re-walk POSITIVE (PF 1.294→1.318, 11/408 flips, mechanism documented).
11. **D1c contamination?** None — structurally immune (derives timestamps from the tz-aware
    index; zero attach_drift/drift-gate references; verified by grep + poison canary 217/217).
12. **Falsely rejected on 07-04?** Yes — the rejection compared VPC against the look-ahead-
    inflated 58.2% machine at wrong-side $1,200 sizing. Both premises died with
    INC-20260706-1141. Rejection VOID; the audit re-adjudicates VPC as certified-eligible.
13. **Execution-lane work:** the big three genuinely-new builds: (a) live ATR-trail management —
    NO order-modify/replace path exists in the bridge today and no live strategy trails; (b) A-vs-
    VPC conflict arbitration (same-instrument opposite-direction policy does not exist); (c) kill-
    switch semantics for an in-flight trailing position. Plus: VPC-lane timestamps MUST be index-
    derived (the latest_signal() defect class), telemetry/journals, watchdog two-lane position
    parity, dry-run/replay/paper-shadow harnesses. Copy-adaptable: engine registration, bar
    dispatch, sizing/cap enforcement, EXITLOCK pattern, config locks. Full table in 07_*.
14. **Eligible to wire live now?** **No.** Sequence: operator approves re-lock DEC → live
    latest_signal() fix → VPC execution lane built + line-audited + 9-test-class harness →
    paper shadow → separate arming approval.
15. **Next operator decision:** the re-lock DEC (A@600/6 + VPC@600/4 eval · kept-A 250/4 funded ±
    VPC small · exit choice · D1c phase-split) — this audit clears VPC's part of that decision.

## Incidents during this audit (both contained)
- **INC-20260706-1627 (pandas)**: unpinned pandas 3.0.3 in .venv corrupted the 18:00-anchored
  daily resample (wrong PDH/PDL → 548-trade ghost stream). Caught by stream canaries in every
  affected lane; adjudicated by ground truth; pinned, healed, permanent gate canary added.
  Certified numbers unaffected. Third defect class caught by canaries this week.
- PF-freeze flags on $100-150 standalone funnel cells: adjudicated q=1 quantization-selection
  artifacts (small-stop trade selection), not edge. Never quote.
