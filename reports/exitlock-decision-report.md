# EXITLOCK — Decision Report
_2026-06-21 · audit + backtest complete · live entries currently BLOCKED by exit-model gate_

## EXITLOCK VERDICT

**Live is correctly BLOCKED, and it should stay blocked until Exit #3 partial routing is built.**
The live bridge trades a single-target full-qty model that was never validated; when backtested it
makes slightly more money but its **max drawdown ($2,231) exceeds the $2,000 eval buffer** and it
survives the historical eval by only **$32**. The validated, buffer-respecting model is **Exit #3**.
Recommendation: **A — build Exit #3 live partials**; keep live blocked (C) until then.

### The 8 answers
1. **Is live aligned with validated stats?** **NO.** Live = full 3 MNQ → one 2R target. Validated = Exit #3 partial.
2. **Is the current live model validated?** **NOW IT IS BACKTESTED — and it fails the eval-safety bar.** Max DD $2,231 > $2k buffer; min eval cushion $32. Not safe to adopt as-is.
3. **Should Monday live be blocked?** **YES.** Already enforced — `exit-model-approved.flag` is absent, every live entry fails closed.
4. **What did the single-target backtest show?** Net +$20,448 vs Exit #3 +$18,356 (+$2,092); win 56% vs 54%; **PF 2.39 vs 2.87 (worse)**; avg loss −$334 vs −$214 (56% bigger); **max DD $2,231 vs $1,486**; eval cushion $32 vs $270. More money, materially more risk, breaches the buffer.
5. **Should we build Exit #3 routing?** **YES.** Two split bracket legs (1 MNQ @1R + 2 MNQ @2R). ~2 days. See `exitlock-exit3-live-routing-scope.md`.
6. **What exact model should EVAL use?** **Exit #3** (integer split 1@1R + 2@2R live — the closest implementable form of the validated model; keeps max DD under the $2k buffer).
7. **What exact model should FUNDED use?** **Exit #3** as well (+ P3 + Profile B, none of which are coded yet — separate workstream). Funded survival depends on keeping DD bounded, which single-target violates.
8. **What must be fixed next?** (1) build Exit #3 split routing; (2) align `record_resolved` + dashboard to the chosen model; (3) only then create `exit-model-approved.flag`; (4) paper-parity check live two-leg P&L == backtest; (5) re-run eval-survival on the aligned model.

---

## Phase 7 — Paper / live P&L audit (where the $1,400 came from)
- **Source:** `trade_results.csv` via `auto_live._record_resolved` → `trade_results.record_resolved`
  → `pnl_from_r(result_r, entry, stop, contracts)`. Solving $1,400 ⇒ **result_r = 2.0 on full 3
  contracts** (full position at the 2R target).
- **Fill-backed?** **NO.** `paper.db` has **0 trades on 06-16**. The SimBot partial engine never
  produced it.
- **Theoretical or bridge-backed?** It's the **live-path single-target resolution**, recorded
  without a confirming fill. The bridge log for 06-16 shows the short sent at 10:46 ET then an **EOD
  cancel+exit at 18:30** — **no TP-hit webhook**. So the "TP hit (gross)" note is **not verified**;
  the position was most likely EOD-flattened, then booked as a clean +2R.
- **Dashboard impact:** the calendar's "+$1,400 month / 100% green / 1 paper day" rests on this one
  unverified, single-target, round-number row.
- **What must change:** (a) `record_resolved` must only book a result that is **backed by a resolution
  event** (TP-hit / stop / EOD-flat at the actual exit price), not a synthesised +2R; (b) the
  dashboard must **label unverified/hypothetical rows distinctly** from fill-backed ones; (c) once the
  exit model is Exit #3, P&L must use the two-leg sum, not full-qty-at-target.

---

## Exit-model truth (all layers)
| Layer | Current exit model | File | Status |
|---|---|---|---|
| Research/backtest | Exit #3 fractional (1.5/1.5) | `models/model01_sweep_mss_fvg` | validated |
| SimBot / paper | Exit #3 integer (1@1R, 2@2R) | `bot.py:151`, `TwoLegBracket` | partial, +11% vs backtest |
| **Live bridge** | **full qty → one 2R target** | `bridge_traderspost._wire`, `auto_live.py:118` | **MISALIGNED** |
| Dashboard P&L | single-target (result_r×full qty) | `trade_results.pnl_from_r` | overstates vs research |
| Audit/reporting | single-target | `trade_results.csv` | unverified row |

---

## RECOMMENDATION: **A — BUILD EXIT #3 LIVE PARTIALS**

Single-target is not materially better — it's +$2k/yr of return bought with a **max DD that breaks the
$2k eval ceiling** and a razor-thin $32 survival margin. For a trailing-DD eval where survival is the
whole game, that disqualifies it. Build the two-leg split routing (scope ready), align all layers,
paper-prove parity, **then** approve.

### Gate status (live)
```
CONTROLLED LIVE = BLOCKED   (exit-model-approved.flag absent)
SEMI-AUTO LIVE  = BLOCKED
FULL-AUTO LIVE  = BLOCKED
PAPER / AUDIT   = ALLOWED
EMERGENCY FLATTEN / CANCEL = ALWAYS ALLOWED (never gated)
```

### Next build order
1. `build_entry` split / two-leg routing (`bridge_traderspost`) + send-Leg-2-first failure policy.
2. `record_resolved` → two-leg sum; only book resolution-event-backed P&L.
3. Dashboard: label hypothetical vs fill-backed.
4. Tests: split payload, two-leg journal, flatten-cancels-both, one-leg-fail, P&L parity.
5. Paper-parity run: live two-leg P&L == backtested Exit #3.
6. **Only then** create `exit-model-approved.flag` and re-run the eval-survival check.

**Monday live: NOT ALLOWED.** Paper/audit only until the above is done.
