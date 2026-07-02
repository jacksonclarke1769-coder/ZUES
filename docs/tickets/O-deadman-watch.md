# TASK: O — external dead-man flattener (deadman_watch.py)

ROLE: Sonnet implement
DE-CERTIFIES: no (safety-only; never opens exposure)

## Problem
The only auto-flatten (FlattenGuardian) is a daemon THREAD inside auto_live.py. If auto_live dies with
a position open, NOTHING acts: heartbeat goes stale, dead-man turns RED, but no process consumes it
(audit R3/A2). We need a small, standalone watchdog process that (1) alerts the operator immediately
and (2) after a grace period fires an emergency flatten through its own bridge sender.

## Scope
New standalone script `deadman_watch.py` + tests. Pattern references (READ, don't modify):
- heartbeat age/dead-man: `heimdall_monitor.py` (`read_heartbeat`, `deadman_status`, freshness logic)
- market-hours guard: `feed_watch.market_likely_open` (import and reuse it — do NOT reimplement)
- flatten route: `bridge_sender.BridgeSender(...).flatten(account, reason=...)` — ALWAYS a fresh
  timestamped reason (see `flatten_guardian.py:85`); live_url from env `TRADERSPOST_LIVE_URL`
  (env_loader is imported for .env); mode "live" only when `--live` passed, else dry-run print.
- telegram: `telegram_notify.Telegram` (fail-safe if unconfigured)
- single instance: `instance_lock.py` pattern

Behavior (pure decision function + thin loop):
- poll every 30s. Compute heartbeat age from `out/heimdall/heartbeat.json` (missing file = infinite age).
- state machine per incident: OK → (age > 180s AND market_likely_open(now ET)) → ALERT (telegram once)
  → (age > 420s, still market open) → FLATTEN once (cancel+exit via sender.flatten, fresh reason,
  telegram result) → HALTED-INCIDENT (no further flattens) → heartbeat fresh again → back to OK (log +
  telegram recovery).
- when market closed: never alert/flatten; reset nothing (age naturally stays stale overnight — the
  market_open guard is what matters).
- CLI: `--account APEX-50K-EVAL-1 --live` (default dry-run: prints what it WOULD send), `--alert-s 180
  --flatten-s 420 --interval 30` overridable.
- Decision logic must live in a pure function `decide(age_s, market_open, state) -> (new_state, action)`
  so it is unit-testable without processes.

## Files allowed
- deadman_watch.py (new), test_deadman_watch.py (new), OPERATOR_RUNBOOK.md (append a short "start the
  external dead-man" line to the session-processes list)

## Files forbidden
- auto_live.py, flatten_guardian.py, heimdall_monitor.py, feed_watch.py, bridge_sender.py,
  evidence/approvals/, .env — everything else

## Success criteria
- `decide()` unit-tested: no action when market closed; ALERT once at >180s; FLATTEN once at >420s;
  no repeat flattens in the same incident; recovery re-arms.
- Flatten path uses a FRESH reason string each firing (test asserts two firings produce different
  signalIds via bridge_traderspost.build_flatten).
- Dry-run default: `--live` absent → no live webhook possible (sender mode dry-run).
- Full suite green.

## Verification
- `python3 -m pytest -q test_deadman_watch.py` then full suite
- `python3 deadman_watch.py --account TEST --interval 1` starts, prints one status line, Ctrl-C clean
  (or a `--once` flag for a single poll — implementer's choice, test it)

## Exit criteria
Standard report (docs/output_format.md); nothing outside allowed files (git diff --stat).
