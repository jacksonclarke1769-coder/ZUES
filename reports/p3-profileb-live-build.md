# P3 + Profile B — Live Engine Build
_2026-06-21 · suite 378→397 green · live still BLOCKED · paper-first_

## What was built
| Piece | File | Status |
|---|---|---|
| **P3 cushion brake** | `p3_brake.py` | hysteresis latch (ON <40%·dd, OFF ≥60%·dd), `size()` → (max(A//2,1), 0) braked; restart-safe; fail-safe brakes on bad cushion |
| **Profile B engine** | `strategy_engine_profileB.py` | streaming ORB (OR=09:30–09:45, break→ATR stop 1.0 / target 1.5); one trade/day; never consults D1c |
| **Live wiring** | `auto_live.py` | P3 sizes Profile A in `on_decision`; new `on_b_signal` routes B (single bracket, B-tier size, P3 zeros B); B engine fed in the bar loop; cushion read from `mffu.distance_to_floor` |
| **Tests** | `test_p3_brake.py` (7), `test_profile_b.py` (6), `test_p3_b_live.py` (7) | 20 new, all green |

## How it behaves (verified)
- **P3 on A:** cushion ≥$1,200 → full A3; cushion <$800 → A halved (3→1), B→0; hysteresis holds the band.
- **Profile B:** ORB break emits `long/short` at the OR level, ATR stop/target (R:R 1.5), routes a **single bracket** (`strategy="B"`, not Exit #3 — B has its own exit), **never touches D1c**, blocked by kill-switch / daily-stop / P3.
- **Still gated:** B is a buy/sell entry → blocked live by the EXITLOCK flag (absent). Nothing goes live.

## ⚠️ HONEST deploy-readiness (read this)
**Built + tested ≠ ready for live money Monday.** These are validated in *backtest*; their *live* behaviour is unproven. Named gaps before real money:
1. **No Profile B backtest-parity harness.** Profile A has "0 signal mismatches" parity; B does **not** yet. The streaming engine matches the batch logic in design but isn't proven bar-for-bar vs the validated B backtest — B could diverge from its modelled P&L.
2. **B paper-P&L not tracked on the calendar.** The PaperTracker records A fills; B routes webhooks + logs to ARGUS but its P&L isn't wired into `trade_results` yet.
3. **P3 cushion = paper state.** It reads the SimBot's `mffu` cushion (correct for paper). For real *funded* P3, cushion needs broker-truth (the B1 recon path, not built).
4. **Zero live/paper validation.** First real run is Monday paper.
5. **Tier is still EVAL.** auto_live uses `EVAL_TIERS` (A3/B2). The funded A2/B1 sizing path isn't the active config.

## Recommendation
**Run P3 + Profile B in PAPER Monday** — alongside the Exit #3 paper proof — to start earning their proof (ARGUS will log every A and B decision). Do **not** take real money on B/P3 until: (a) a B parity harness confirms the engine matches the backtest, (b) B P&L is tracked, (c) at least one clean paper session. Live stays blocked behind `exit-model-approved.flag` regardless.

## Status
- **Live today:** Profile A Exit #3 — aligned, gated, audited.
- **Built + tested, paper-ready:** P3 brake, Profile B (this build).
- **Still needed for B/P3 live:** parity harness, B P&L tracking, paper validation, funded broker-truth cushion.
