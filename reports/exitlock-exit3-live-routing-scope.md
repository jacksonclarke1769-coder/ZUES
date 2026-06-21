# EXITLOCK — Exit #3 Live Routing Scope (TradersPost)
_2026-06-21 · scope only, not built · how to make the live bridge trade the validated partial model_

## The gap
`bridge_traderspost._wire` emits ONE order with ONE `takeProfit`. To trade Exit #3 (50% @ +1R,
50% @ +2R) the bridge must place the position as **two bracket legs** — there is no single-payload
partial in our implementation.

## Can TradersPost do multi-TP in one order?
No evidence in our code (only one `takeProfit` key; a live 400 already proved the schema is strict).
**Assume NO native TP-ladder.** The robust path is **two separate bracket (OSO) orders**, each
self-protecting. This is "Option 3" and it implements Option 1 cleanly.

## Recommended design — Option 1 via split bracket orders
For 3 MNQ (integer split matching the SimBot/backtest: `qty//2` @1R, remainder @2R):

| Leg | Qty | Entry | Stop | Take-profit | signalId role |
|---|---|---|---|---|---|
| Leg-1 (scalp) | 1 MNQ | OTE | initial stop | **+1R** | `entry_tp1` |
| Leg-2 (core) | 2 MNQ | OTE | initial stop | **+2R** | `entry_tp2` |

Each leg is a complete TradersPost bracket (entry + its own stop + its own target). Total stop
coverage = 1 + 2 = 3 (full position protected). When Leg-1's +1R hits, that contract closes and its
stop disappears; Leg-2 keeps its stop + 2R target. **Result = 1 @ +1R, 2 @ +2R = Exit #3.**

## Q&A (Phase 6 required answers)
| Question | Answer |
|---|---|
| Multiple take-profits in one payload? | Not supported in our bridge; don't rely on it. |
| Split into two bracket orders? | **Yes — the recommended mechanism.** Two `build_entry` calls, split qty, two targets, two roles. |
| Avoid duplicate stops? | Each leg's stop protects ONLY its own qty (1 and 2). Sum = 3 = full position. No double-protection; no naked. |
| Flatten cancels both legs? | Yes — existing `flatten()` sends `cancel` (cancels ALL working for the ticker) then `exit`. Covers both legs. ✅ |
| Journal both legs? | Yes — distinct deterministic `cl_ord_id`/`signalId` per role (`entry_tp1`/`entry_tp2`); both get INTENT/SEND/ACK. |
| One leg sends, other fails? | **Send Leg-2 (core 2 MNQ @ 2R) FIRST.** If Leg-1 then fails, you simply hold 2 MNQ to 2R (a valid, smaller Exit-#3-ish state) — log a degraded-fill WARN, never naked. If Leg-2 fails, abort & don't send Leg-1 (fail closed, no position). |
| Partial fill of a leg? | Each leg is 1–2 MNQ; TradersPost bracket sizes its stop/target to filled qty per leg. Small blast radius. |
| ARES daily loss correct? | P&L = Leg-1 + Leg-2 summed in `record_resolved`; the `DailyGuard` already sums. No change needed. |
| P&L calculated correctly? | `pnl_from_r(1.0,…,1) + pnl_from_r(2.0,…,2)` = the integer-split value (tested). |
| Avoid orphan target/stop? | OSO brackets auto-cancel the sibling on fill; `flatten` cancel-first removes any residual. Add a recon check that working-order qty ≤ open position qty. |

## Build estimate (when approved)
- `bridge_traderspost`: add `build_entry_split(...)` or a `role`+`target_r` param (≈0.5d).
- `auto_live.on_decision`: compute 1R/2R target prices, call builder twice, send Leg-2 then Leg-1,
  handle one-leg-failure policy (≈0.5d).
- `record_resolved`: sum the two legs (≈0.25d).
- Tests: split-payload shape, two-leg journal, flatten-cancels-both, one-leg-fail policy, P&L (≈0.5d).
- ≈ **2 days**, then a paper-parity check that two-leg live P&L == backtested Exit #3.

## Note
Integer split at 3 MNQ (1/2) is already a ~+11% divergence from the backtest's *fractional* 1.5/1.5.
That is the closest live-implementable approximation; document it as the official live model.
