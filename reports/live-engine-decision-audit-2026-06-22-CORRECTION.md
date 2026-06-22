# ⚠️ CORRECTION — Live-Engine Decision Audit, 2026-06-22 (ny-am)

**The auto-generated report `live-engine-decision-audit-2026-06-22.md` is WRONG.**
It reports `SESSION CLEAN — NO SETUP · sends=0`. That is false. A real Profile B trade
fired, filled, and lost money. This file is the corrected record of truth.

## What actually happened (reconstructed from broker evidence)
| | |
|---|---|
| Trade | **Profile B (ORB) long, 2 MNQ @ 30,926.75** |
| Fill | **Completed at Tradovate, 10:01:56 AM EDT** (in the 09:30–11:30 window) |
| Bracket | stop 30,870.34 · target 31,011.37 (single bracket, attached) |
| Outcome | **stopped out** — equity 49,983.20 → 49,753.40 = **−$229.80** (−$225.64 + ~$4 fees) |
| EOD flatten | 14:30 guardian Cancel + Exit → **Rejected** (benign: position already closed) |
| Daily-stop / DD | within −$700 daily stop; trivial vs $2,000 trailing DD — risk contained |

Evidence: TradersPost notifications (Buy @ 30,926.75 Completed 10:01:56 ET), Tradovate
equity/OPEN-P&L screenshots, and the live runner stdout (`[auto-live] B long 2MNQ ORB
@ 30926.75 stop 30870.34 tgt 31011.37 -> sent`).

## Root cause — why the auditor was blind
`LiveAuto.on_b_signal` DID call `self._dlog("signal", …)` on the success path, but the call
**omitted three REQUIRED keyword args** of `DecisionLogger.signal()` (`tp1_qty`, `tp1_target`,
`tp2_qty`). That raised `TypeError`, which `_dlog`'s fail-safe `try/except` **swallowed
silently** → the decision row was never written → the auditor (which reads the ARGUS jsonl)
saw zero B sends and declared the session clean. Profile A logs correctly; only the B path
was malformed. The single-account live path was affected; the copier's B path was already fine.

## Fix (committed same day, 2026-06-23)
1. `on_b_signal` now passes all required `signal()` args (B single bracket → `tp2_qty=b_size`,
   `tp2_target=target`, `tp1_*=None`). Verified: the call now writes a `final_action="live_send"`,
   `profile="B"` row that the auditor counts.
2. `_dlog` no longer swallows silently — it **prints** `⚠ ARGUS LOG FAILED (…) — DECISION NOT
   RECORDED`, so this bug class can never be invisible again.
3. Full suite green (420). Repro test confirms the previously-dropped call now persists a row.

## Integrity note
The real-time jsonl for 2026-06-22 was NOT back-filled (no fabricated log rows). This report
is the authoritative reconciliation. Going forward, B sends self-record correctly.

## Carry-over
- Profile B single-bracket execution is now **proven on a real fill** (entry + stop round-trip
  at the broker). Profile A multi-leg Exit #3 remains unproven live (no A fill yet).
- Feed reliability (376 RED periods over the run) remains the top hardening item.
