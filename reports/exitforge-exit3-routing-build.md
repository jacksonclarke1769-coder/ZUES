# EXITFORGE — Exit #3 Live Partial Routing Build
_2026-06-21 · execution-model alignment · live still BLOCKED · suite 331→350 green_

## 1. Files changed
| File | Change |
|---|---|
| `config.py` | `EXIT_MODEL="EXIT3_FIXED_PARTIAL"` (single source of truth) + `exit3_split(qty)` |
| `bridge_traderspost.py` | `build_entry` gains `role`/`r_target` (backward-compat); **new `build_entry_exit3`** → two ordered legs (core-first), shared stop, +1R/+2R targets, distinct deterministic ids |
| `bridge_sender.py` | **new `send_exit3`** (fail-closed failure policy) + incident block (`incident_blocked`/`_incident`/`clear_incident`); EXITLOCK entry gate unchanged |
| `auto_live.py` | `on_decision` routes via `send_exit3` under EXIT3 mode; `killed()` honours the incident block |
| `trade_results.py` | `pnl_exit3` (two-leg P&L) + `record(fill_backed=…)` HYPOTHETICAL tagging + `by_day` splits `hypothetical_pnl` from realised `pnl` |
| `out/ares/trade_results.csv` | the synthetic +$1,400 row re-tagged **HYPOTHETICAL** (proven not fill-backed) |
| `tools/check_exit3_parity.py` | NEW — parity proof |
| `tools/exit3_dryrun_proof.py` | NEW — dry-run payload proof |
| `test_exitforge.py` | NEW — 19 tests |

## 2. Official exit model
`EXIT3_FIXED_PARTIAL` — split the position into two bracket legs sharing ONE protective stop:
`qty//2` @ +1R and remainder @ +2R. No trailing, no breakeven. For 3 MNQ → **1 @ +1R, 2 @ +2R**
(matches SimBot/backtest integer split). `SINGLE_TARGET` is retained only as a legacy/unvalidated label.

## 3. TP1 leg (scalp) — sent SECOND
`sell/buy 1 MNQ · limit @ entry · stop @ shared stop · takeProfit @ +1R · role entry_tp1 · own signalId`

## 4. TP2 leg (core) — sent FIRST
`sell/buy 2 MNQ · limit @ entry · stop @ shared stop · takeProfit @ +2R (strategy target) · role entry_tp2 · own signalId`

Dry-run proof (the $1,400 short): TP2 `sell 2 @ 30421.5`, TP1 `sell 1 @ 30538.25`, **shared stop 30771.5**, 2 distinct ids, total qty 3. No single full-qty@2R payload is ever built.

## 5. Failure policy (fail-closed, never a half-built position)
- **Core (TP2) fails first** (nothing sent) → `ENTRY_ABORTED`, no order, no flatten.
- **TP1 fails after TP2 sent** → `flatten()` + `PARTIAL_ENTRY_FAILED` + **incident block** (no new entries until `clear_incident(note)`).
- **Any leg missing stop/target** → flatten + incident block.
- Send order is core-first so a failure leaves at most the protected core leg, which is immediately flattened.

## 6. Flatten / cancel
Unchanged and still correct: `flatten()` sends `cancel` (cancels ALL working orders for the ticker — both legs' stops/targets) then `exit`. Covers both legs, idempotent, restart-safe. EXITLOCK gate never blocks exits/cancels/flatten. `bridge_test.py --flatten` path intact.

## 7. Paper / live parity
| Model | $ on the $1,400 trade |
|---|---|
| Backtest fractional (1.5/1.5) | $1,050 |
| **SimBot paper (1@1R+2@2R)** | **$1,167** |
| **Live split payload (sum of legs)** | **$1,167** ✅ |
| Single-target (legacy) | $1,400 ✗ no longer used |
**Paper and live now agree at $1,167.** Residual: integer 1/2 split is ~+11% vs the backtest's
fractional 1.5/1.5 — the closest live-implementable form; documented as the official live model.
`tools/check_exit3_parity.py` asserts live == integer and live != single-target (PASS/PASS).

## 8. Dashboard
`trade_results.by_day` now returns `pnl` (fill-backed/realised) AND `hypothetical_pnl` (projected,
labelled) per day. `/api/calendar` consumes it directly. The synthetic +$1,400 (06-16) is re-tagged
HYPOTHETICAL → **realised P&L for that day is now $0**; the $1,400 surfaces only as `hypothetical_pnl`.
Frontend badge rendering of the hypothetical field is a small follow-up; the hard requirement
(never report it as realised) is met at the API.

## 9. Tests added (19, `test_exitforge.py`)
Split shape (2 legs, qtys, +1R/+2R targets, shared stop, distinct ids, core-first, no full-qty);
gate holds for split path; failure policy (TP2-first-fail abort, TP1-fail flatten+block, missing-bracket
flatten+block, incident clear); per-leg dedup; flatten cancel+exit; two-leg P&L math; hypothetical vs
realised split; no URL in log.

## 10. Test results
- `test_exitforge.py` **19/19 PASS** · `test_exitlock.py` 11/11 · **full suite 350 passed, 0 failed.**
- Parity tool PASS/PASS · dry-run proof integrity YES/YES.

## 11. exit-model-approved.flag — **ABSENT** (not created, by design)
## 12. Live status — **BLOCKED.** Every live entry (both legs) fails closed without the flag.

## 13. Exact next step before live
1. Operator reviews dry-run payloads (`tools/exit3_dryrun_proof.py`) + this report.
2. (Optional) controlled tiny live proof: 1+? split on demo confirming both legs + shared stop attach at Tradovate, then flatten cancels both.
3. Paper session under EXIT3 mode → confirm calendar shows fill-backed two-leg P&L (≈$1,167-scale wins), no hypotheticals as realised.
4. **Operator** creates `evidence/approvals/exit-model-approved.flag`.
5. Re-run eval-survival on the aligned model; only then arm a supervised live session.

**Live does not arm in this task.** Routing built, tested, dry-run-proven; approval is the operator's explicit step.
