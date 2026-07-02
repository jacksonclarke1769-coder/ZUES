# TASK: Q — positive fill confirmation + order TTL (v1, conservative scope)

ROLE: Sonnet implement (DEPENDS ON ticket P being merged first — uses its exit accounting)
DE-CERTIFIES: no (risk-reducing only; certified entry/exit prices unchanged)

## Problem
(a) `readback.on_entry` fires at webhook-SEND time, not fill time — an entry that never fills is only
ever ORANGE (MISSING_POSITION never halts/alerts) and the resting limit is NEVER cancelled until EOD:
an abandoned limit can fill hours later, unattended (audit R5/A3, D7/A6). The 06-30 phantom sessions
were exactly this class.

## Scope (v1 — deliberate limits)
1. **MISSING escalation → cancel + reconcile.** In `live_readback.py` add an optional
   `on_missing=None` callback + `missing_confirm=N` (default 6 polls ≈ 2min): when MISSING_POSITION
   has been confirmed for N consecutive polls (bot expects a position, broker flat), fire
   `on_missing(expected)` ONCE per episode, then reset the episode counter when the state clears.
   MISSING stays ORANGE (never halts) — this only adds the callback.
2. **auto_live wires on_missing** to: (a) send `BP.build_cancel` via the sender with a fresh
   timestamped signal_ts (cancels ALL working MNQ orders — SAFE here only because the selected machine
   is single-lane A-only; assert/log that no other lane believes it is open before sending), (b) call
   `readback.on_flat()` (the position we believed in does not exist), (c) telegram-alert
   "entry unfilled at broker → working orders cancelled; modeled tracker may diverge (phantom-trade
   guard)". Do NOT touch the modeled tracker rows (v1 keeps modeled P&L as-is — divergence direction
   is fail-safe for the daily stop and is alerted).
3. **Positive confirmation logging:** on the first poll where broker net matches a nonzero expected,
   journal (`journal.append("FILL_CONFIRMED", ...)` pattern — see existing journal usage in
   auto_live) and log once per episode. No behavior change — this creates the truth trail the fills
   audit needs.
4. **Order TTL note:** the A entry-limit lifecycle is owned by the model's fill window; the cancel in
   (2) IS the TTL for the live order (fires ~2min after the model gives up expecting the position).
   Document this in a comment where on_missing is wired.

## Files allowed
- live_readback.py (callback + counter only — do NOT change tier/halt semantics),
  auto_live.py, test_readback_sentinel.py (extend) or new test_fill_confirm_ttl.py

## Files forbidden
- bridge_traderspost.py, bridge_sender.py, paper_live.py, profile_b_tracker.py, strategy engines

## Success criteria
- Test: expected=+10, broker flat for N confirmed polls → on_missing fired exactly once with 10;
  expected reset to 0 via the wiring; a second episode later can fire again.
- Test: expected=+10, broker +10 → FILL_CONFIRMED journaled once, no on_missing.
- Test: MISSING still never halts (existing test stays green).
- Test: on_missing wiring does NOT send cancel when another lane reports an open position (the guard).
- Full suite green.

## Verification
- targeted tests then `python3 -m pytest -q`

## Exit criteria
Standard report; nothing outside allowed files. List residual gaps honestly (v1 does not reconcile
modeled tracker rows; queue-position fill quality still unmeasured).
