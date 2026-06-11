# KEY ARRIVAL RUNBOOK — exact commands, in order

Scope: the moment Tradovate demo/API credentials (or a funded account's credentials)
arrive. Nothing here trades. Spike day is DEMO ONLY.

## STEP 0 — secrets (5 min, BEFORE anything touches the repo)

```bash
# macOS keychain (one per secret; repeat for password/cid/sec/device_id):
security add-generic-password -a nqbot -s tradovate_password -w '<PASTE>'
# retrieve pattern (what config.py will use):
security find-generic-password -a nqbot -s tradovate_password -w
```
- config.py: fill name/app_id/cid placeholders by READING from keychain at import
  (or export env vars in the service unit on the VPS — never literals in the file).
- `git status --short` must stay EMPTY after this step (config.py is gitignored —
  verify it shows nothing).
- If any secret was ever pasted into a chat/terminal history: rotate it today.

## STEP 1 — the first 10 commands once the key works

```bash
cd ~/trading-team/bot/nq-liq-bot
git status --short                                  # 1  MUST be empty
python3 -m pytest -q                                # 2  MUST be 97 passed
python3 migrate_b1.py data/journal.db               # 3  "already current"
python3 locker.py verify                            # 4  "LOCKER OK"
python3 - <<'EOF'                                   # 5  auth-only smoke (no orders)
import config
from tradovate_client import TradovateClient
assert config.TRADOVATE["env"] == "demo", "env must be demo"
cli = TradovateClient(config.TRADOVATE, config.HOSTS)
cli.authenticate()
accts = cli._get("/account/list")
print("AUTH OK · accounts:", [(a.get("name"), a.get("id")) for a in accts])
assert any(a.get("name") == config.TRADOVATE.get("account_spec") for a in accts), \
    "configured account_spec not found — DO NOT PROCEED (silent-fallback hazard)"
EOF
date >> evidence/incidents/key-arrival-log.txt      # 6  start the paper trail
python3 locker.py snapshot                          # 7  journal snapshot pre-spike
python3 spike_day.py                                # 8  THE SPIKE (RTH hours, demo)
open out_spike_results.md                           # 9  operator review, transcribe
                                                    #    GREEN/RED into B1_DESIGN.md §3
git add -A && git commit -m "spike day results"     # 10 commit the evidence
```
Notes: run #8 during liquid RTH (21:30–23:30 Perth). The harness cleans up after
itself; if it aborts mid-run, check the broker UI for working orders before re-run.

## STEP 2 — VPS / dead-man checklist (parallel, ~2-4h, operator)

```
☐ VPS ordered (Chicago/NY metro, Ubuntu LTS, 2GB+)
☐ python3.13 + pinned requirements installed; pytest 97/97 ON THE VPS
☐ secrets as systemd env vars (never files); config.py placeholders intact
☐ tz on VPS = UTC; verify scheduler tests pass there (DST table is tz-db driven)
☐ healthchecks.io (or equiv) check created: 5-min ping, 2-miss alert -> phone+SMS
☐ hourly journal.db sync off-box (cron + locker snapshot)
☐ home Mac demoted to monitor: dashboard read-only, no trading process
☐ single-instance lock path on persistent disk (data/bot.lock)
☐ reboot test: VPS restart -> lock reacquires, recovery runs clean, dead-man green
```

## STEP 3 — letters (10 minutes, TODAY, independent of the key)

```
☐ open evidence/approvals/mffu-approval-request.md  -> paste into MFFU support ticket
☐ open evidence/approvals/topstep-approval-request.md -> paste into Topstep ticket
☐ record send date in evidence/approvals/tracker.md
☐ replies: save as PDF -> locker.file('approvals', <pdf>) -> update tracker
```

## STEP 4 — if the credentials are for a FUNDED account (not demo)

Per OPERATOR_RUNBOOK "account verification": file credentials (keychain), file the
firm's confirmation email to evidence/approvals/, diarize the firm's inactivity rule,
and DO NOT connect the bot to it. The funded account waits for Gates 1–5. No exceptions
— an idle funded account loses nothing; a prematurely-traded one is THOR's #1 statistic.

## KNOWN MISSING CODE (listed, deliberately not built pre-key)

1. `tradovate_client._resolve_account()` silently falls back to `accts[0]` when
   `account_spec` doesn't match — must RAISE instead (B1 item; the smoke test in
   STEP 1 #5 covers the gap until then).
2. `assert_account_spec()` startup check (account name/env/active vs config; plan and
   size remain a MANUAL check against the firm's email — Tradovate doesn't know the
   firm's plan terms). B1 item; runbook covers manually until then.
3. `ops_flatten.py` one-command emergency CLI (B1 wires flatten.py to the live
   adapter; until then: broker mobile app, always legitimate).
