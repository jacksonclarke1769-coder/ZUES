# TASK: S — EOD flatten: retry until ok, alert on failure

ROLE: Sonnet implement
DE-CERTIFIES: no

## Problem
`scheduler.py` `_due_once` marks a scheduled event FIRED the moment it is due, BEFORE the flatten
result is known (`scheduler.py:97-112`); `flatten_guardian.tick()` persists the fired-state
(`flatten_guardian.py:~130`). If TradersPost is down at 15:30/14:30 ET, the flatten fails once and is
never retried that day — a position can ride past the Apex 4:59pm ET flat requirement (audit R7/A8).

## Scope
Change the guardian's EOD-flatten (and kill-flatten if it shares the path) semantics to:
1. An event that comes due is attempted; it is marked fired/persisted ONLY when the flatten returns
   ok=True (`sender.flatten` returns a dict with an `ok` flag — inspect `bridge_sender.flatten`).
2. On failure: log loudly, telegram-alert (guardian already has notify access — check; if not, print
   is acceptable BUT prefer wiring the existing Telegram the guardian was constructed with), and RETRY
   on subsequent guardian ticks with a minimum 60s spacing, until ok or the process exits.
3. Each retry uses a FRESH reason (the guardian already timestamps reasons — preserve that).
4. Restart semantics unchanged for the SUCCESS case: a fired(ok) event stays fired across restarts.

Design note (decision made): implement as "attempted-at" tracking in the guardian around the scheduler,
OR a `confirm()` step in the scheduler — whichever is the smaller diff given the actual API. Do not
redesign the scheduler beyond what this needs.

## Files allowed
- scheduler.py, flatten_guardian.py, test_lock_scheduler.py / test_flatten_guardian.py (extend),
  or a new test_eod_flatten_retry.py

## Files forbidden
- auto_live.py, bridge_sender.py, bridge_traderspost.py, everything else

## Success criteria
- Test: sender whose flatten returns ok=False → event NOT persisted as fired; next tick ≥60s later
  retries; sender flips to ok=True → fired persisted; no further attempts.
- Test: success-on-first-attempt behavior byte-identical to today (fired once, persisted, restart-safe).
- Full suite green.

## Verification
- targeted tests then `python3 -m pytest -q`

## Exit criteria
Standard report; nothing outside allowed files.
