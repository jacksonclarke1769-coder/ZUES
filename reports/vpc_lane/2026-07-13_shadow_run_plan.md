# VPC lane — shadow-run plan + pre-arm checklist (post gate-waiver)

Authority: DEC-20260713-1156 (waive the A-N30 sequencing gate) + DEC-20260713-1038 (VPC deployable).
Status: nothing armed; lane resolves SHADOW by construction (VPC_LANE_EMISSION_MODE absent from live
config). This run changes no config and sends no orders. LIVE HOLD active.

## Purpose (the shadow run does DOUBLE duty)
1. **Blocker-1 acceptance (GATING, from 2026-07-07 register):** prove the watchdog produces
   **ZERO orphan/parity false-positives** across the full observation session while VPC's trail
   issues cancel-replace churn (~1 replace / 1m bar during an active trade). The 90s in-flight grace
   (`watchdog.py:68` INFLIGHT_GRACE_S) is the mechanism; this run is its empirical proof. Equally
   important: confirm the grace does NOT *blind* the watchdog for a whole trade — a genuinely naked
   or mis-sized VPC position during trail churn must still raise. (Inject one synthetic naked-position
   case in a paper replay to prove the watchdog still fires — a silent watchdog is as bad as a
   spammy one.)
2. **Fill / economics calibration:** for every would-be VPC trade, log emit-time vs next-5m-open,
   the modeled market-entry fill (next-open) and the realized shadow fill, the per-bar trail steps,
   and the would-be exit. Compare the shadow R-stream to the certified **1m-truth PF 1.318** within
   tolerance. This is the live analog of the fill-parity evidence Profile A was meant to provide —
   now sourced from VPC's own (simpler, market-order) fills.

## What to run
- `auto_live.py --feed tradingview-1m` — native 1m -> D1c drift-gate, aggregated 5m -> engine
  (`auto_live.py:1166`). The **dual 1m feed is required**: the engine emits on 5m closes, but the
  VPC trail must step on **1m** bars to match the certified 1m-truth target (peak-on-close), which is
  the convention ARM B proved bit-for-bit. A 5m-only feed would step the trail at the wrong
  granularity — do NOT run the shadow on `tradingview-5m` for economics parity.
- The VPC lane constructs additively and resolves SHADOW automatically (`auto_live.py:159-183`);
  the watchdog runs in the same process. No arming field is set; no broker is touched.
- Prerequisite: logged-in Chrome on :9222 with NQ 1m real-time (per the D1c real-time-feed rule).
  If the feed is not confirmed real-time 1m, D1c forces SHADOW anyway — acceptable here (we want
  shadow), but economics parity needs the real 1m stream for the trail walk.

## Observation targets (exit criteria)
- **Blocker-1:** ≥ ~8-10 VPC trades that actually activate the trail (enough cancel-replace cycles to
  exercise the watchdog across trend days), with **0 orphan/parity false-positives** logged, AND the
  injected synthetic-naked case correctly raised. This is the hard GATING acceptance.
- **Economics sanity:** N ≥ 30 would-be VPC trades; shadow R-stream PF within tolerance of 1.318
  (points-PF) / dollar-PF 1.33-1.37; realized entry slip and trail-exit slip within the ~24-tick
  breakeven margin (tripwire clean). "Short" per operator = do not block arming on a full quarter,
  but Blocker-1's zero-false-positive proof is non-negotiable.
- Emit-vs-fill gap holds at 0 bars on the live (delayed/reconnecting) feed — confirm no live timing
  pathology defeats the structural next-open fill.

## Pre-arm checklist (all must be true before operator recert)
1. Blocker-1 acceptance met (zero watchdog false-positives + watchdog still fires on real naked) ✅/❌
2. Shadow economics track certified 1m-truth PF within tolerance ✅/❌
3. Slip tripwire clean over the observation (entry + trail-exit market fills) ✅/❌
4. Trail parity ARM B green (already ✅ — 408/408 bit-for-bit) and re-run in the shadow build ✅/❌
5. Suite green (currently 968 pass / 1 skip) ✅/❌
6. Operator re-lock DEC fixes the sizing row (balanced A900/6+VPC600/3 vs VPC-standalone sizing) and
   the exit line (Exit#3 vs fixed-1.5R) — VPC-standalone sizing is the cleaner first deploy since A
   is on hold ✅/❌
7. `go-live-recert.sh` promotes the staged block so `VPC_LANE_EMISSION_MODE=arm_live` exists —
   **operator action only; Claude never flips this field.** ✅/❌

## Explicitly out of scope / not waived
The gate-waiver (DEC-20260713-1156) removed ONLY the Profile-A-N30 precondition. Blockers 1-3 stand;
2 & 3 are built, 1 closes on this run. Arming remains an operator recert action, not a Claude action.
