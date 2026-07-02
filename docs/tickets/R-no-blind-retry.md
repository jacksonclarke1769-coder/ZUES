# TASK: R — no blind webhook retry after a send timeout (entries)

ROLE: Sonnet implement
DE-CERTIFIES: no

## Problem
`bridge_sender.send` retries on any `requests.RequestException` (`bridge_sender.py:~117-126`) —
including a READ TIMEOUT that occurs AFTER TradersPost already accepted the POST. Re-posting an
identical ENTRY payload can double the position (TradersPost has no native dedup — the code's own
comment at `bridge_traderspost.py:78`). Audit R6/A7.

## Scope
In the retry loop, classify the exception:
- CONNECTION-class (requests.ConnectionError — nothing was delivered): retry as today.
- TIMEOUT-class (requests.Timeout / ReadTimeout — delivery unknown): retry ONLY payloads that are
  safe to repeat: `exit` and `cancel` actions (closing/cancelling twice is safe-direction). For ENTRY
  payloads (orders that OPEN exposure — anything with a bracket/limit entry): do NOT retry; mark the
  ledger entry `pending-unverified`, log loudly ("verify position via read-back before re-sending"),
  and return a result with sent=False, reason="timeout-unverified — no blind retry on entries".
- Classification of entry-vs-exit: inspect the payload's action/fields — build_flatten/build_cancel
  produce identifiable actions; if ambiguous, treat as ENTRY (fail-closed: don't retry).

## Files allowed
- bridge_sender.py, test_bridge.py (extend) or new test_no_blind_retry.py

## Files forbidden
- bridge_traderspost.py, auto_live.py, everything else

## Success criteria
- Test: entry payload + mocked ReadTimeout on first post → exactly ONE post attempt, sent=False,
  ledger pending, reason mentions verification.
- Test: exit/cancel payload + ReadTimeout → retried (≥2 attempts) as today.
- Test: ConnectionError on entry → still retried (unchanged behavior).
- Full suite green.

## Verification
- targeted tests then `python3 -m pytest -q`

## Exit criteria
Standard report; nothing outside allowed files.
