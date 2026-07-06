# A1 — Honest Baseline Reproduction

HONEST-RECERT DRAFT — pending auditor verdict

Incident: INC-20260706-1141 (D1c lookahead fix). Repo HEAD: `818cda8f924f031924aa6c6e6f677e4dbd251260`.
LIVE HOLD ACTIVE — no live/config/funded changes made. Research only.

## Stream canaries (both post-INC-fix)

| stream | source | n | PF | WR% | netR | reference | match |
|---|---|---|---|---|---|---|---|
| UNFILTERED | `tools_1m_truth_recert.a_streams(...)["exit3"]`, filled==True | 705 | 1.237 | 42.8 | +74.7 | n=705 PF=1.237 WR=42.8 netR=+74.7 | MATCH |
| KEPT (honest D1c) | `tools_sim_parity_check.load_rows()` | 583 | 1.361 | 44.9 | +89.2 | n=583 PF=1.361 WR=44.9 netR=+89.2 | MATCH |

Data span: 2021-06-22 20:00:00-04:00 .. 2026-06-22 19:59:00-04:00 (260.7 weeks).

## (10, $1,200) kept-stream eval row

Apex 50K spec (start $50,000, trail $2,500, target $3,000, DLL $1,000, ARES stop $550),
`MAX_A_QTY` overridden to cap=10, budget=$1,200, via `build_events`/`day_rows`/`eval_run`-equivalent
trade-level walk (`tools_salvage_track_a.run_cell`, verified structurally identical to
`tools_account_size_research.build_events`+`day_rows`+`eval_run`).

| | pass% | bust% | expire% | median_days(pass) | n |
|---|---|---|---|---|---|
| computed | 31.4 | 37.3 | 31.2 | 16.0 | 525 |
| reference | 31.4 | 37.3 | 31.2 | 16 | 525 |

Tolerance: 0.5pp per leg. Verdict: **MATCH**

## Canary verdict

All three canaries MATCH within tolerance. Proceeding to A2/A3.
