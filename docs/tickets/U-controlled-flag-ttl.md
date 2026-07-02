# TASK: U — controlled-test approval flag gets a 24h TTL

ROLE: Sonnet implement
DE-CERTIFIES: no

## Problem
`evidence/approvals/controlled-tv-full-live-test-approved.flag` was meant to authorize ONE supervised
session, but it exists permanently, so every live launch passes the strongest preflight gate
(`auto_safety.py:~383-392` hard-blocks tradingview feeds for production but waves controlled-test
through). The one-time authorization became a standing bypass (audit R8/A3).

## Scope
In the preflight path that accepts the controlled-test flag (`auto_safety.py`):
- Accept the flag ONLY if its mtime is within the last 24 hours. Older → BLOCK with a message telling
  the operator to `touch` it deliberately to re-authorize a supervised session (include the exact path
  in the message).
- Print the flag's age when accepting (so every launch shows how fresh the authorization is).
- Do NOT delete the flag automatically (the operator owns evidence/approvals/).

## Files allowed
- auto_safety.py, test_configlock.py or new test_controlled_flag_ttl.py, go-live-recert.sh (add a
  `touch evidence/approvals/controlled-tv-full-live-test-approved.flag` line right after the operator
  confirmation prompt, with a comment that this re-authorizes THIS session — keeping launches working)

## Files forbidden
- evidence/approvals/ contents themselves, auto_live.py, everything else

## Success criteria
- Test: flag mtime now → accepted; mtime 25h ago (os.utime) → blocked with the re-touch message.
- go-live-recert.sh re-touches the flag AFTER the human confirmation prompt (so authorization is a
  conscious act per launch), and the script otherwise unchanged.
- Full suite green.

## Verification
- targeted tests then `python3 -m pytest -q`; `bash -n go-live-recert.sh`

## Exit criteria
Standard report; nothing outside allowed files.
