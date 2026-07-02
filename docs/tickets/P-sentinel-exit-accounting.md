# TASK: P — sentinel expected-position accounting on exits

ROLE: Sonnet implement
DE-CERTIFIES: no

## Problem
`ReadbackSentinel.expected` only ever INCREASES (`on_entry` at send time) and resets at the ET day
roll. `on_partial_or_exit` has zero production callers. After any bracket exit the sentinel carries a
stale expectation all day → (a) false DIRECTION_MISMATCH BLACK (A long 10 stops out, B short 5 enters
→ expected +5 vs broker −5 → flatten of a healthy trade), (b) stale positive expected masks same-sign
orphans (audit R4/A5).

## Scope
Wire the modeled exit events to the sentinel in `auto_live.py` (LiveAuto has `self.readback`):
1. A resolutions: in the `_record_resolved` closure (auto_live main loop), for each newly-resolved
   tracker row with a known direction and the traded qty (`_qty`), call
   `readback.on_partial_or_exit(-signed_qty)` (long → -qty, short → +qty). Guard readback None.
2. B resolutions: B is OFF in the selected machine but the code path stays correct — in the same
   closure, when `auto.b_tracker` transitions a trade out of `open` (closed list grows), decrement by
   that trade's signed qty. Track the last-seen closed-count in a local dict (same pattern as _rec).
   Read `profile_b_tracker.py` for the closed-row schema (side + qty fields).
3. Guardian flatten / kill flatten: after a successful account-wide flatten, the bot's expectation is
   FLAT — call `readback.on_flat()`. Wire via the guardian's existing callback/notify seam if one
   exists; otherwise in auto_live where the guardian is constructed, pass a small `on_flatten_ok`
   callback (add that hook to flatten_guardian ONLY if no seam exists — smallest diff wins).
4. Clamp: after any decrement, if sign(expected) flipped relative to before the decrement AND no other
   lane has an open position, set expected via on_flat() instead — never leave a phantom negative from
   double-decrement. (Simple guard: only decrement if abs(expected) >= qty, else on_flat().)

## Files allowed
- auto_live.py, flatten_guardian.py (only if a callback hook must be added), test_readback_sentinel.py
  (extend) or new test_sentinel_exit_accounting.py

## Files forbidden
- live_readback.py (the sentinel API already has what you need), bridge_*, strategy engines,
  everything else

## Success criteria
- Test: entry long 10 → resolved → expected returns to 0 (no MISSING/DIRECTION noise on next poll).
- Test: entry long 10 → stop-out resolved → B-style short 5 entry → expected == −5 (the audit's false
  DIRECTION_MISMATCH scenario can no longer occur).
- Test: guardian-flatten-ok path → expected == 0.
- Test: double-decrement guard → never crosses zero into phantom opposite sign.
- Full suite green.

## Verification
- targeted tests then `python3 -m pytest -q`

## Exit criteria
Standard report; nothing outside allowed files.
