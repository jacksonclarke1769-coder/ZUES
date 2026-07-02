# ZEUS Command Reference

Commands are grouped by safety level. Run SAFE commands any time. Run RESTRICTED commands
only with operator approval and after the pre-launch checklist. Never run DANGEROUS commands
without explicit instruction from the operator.

---

## SAFE — run any time, no operator approval needed

These commands do not place orders, send webhooks, connect to the broker, or change any live
configuration.

### Setup and environment

```bash
# First-time setup (idempotent, safe to re-run)
./setup-zeus.sh

# Activate the virtual environment (required before most Python commands)
source .venv/bin/activate

# Check Python version
python3 --version
```

### Testing and verification

```bash
# Full test suite — must be 0 failed before any task is "done" (~30s)
python3 -m pytest -q

# Run a specific test file (faster feedback during development)
python3 -m pytest test_d1c_eval.py -v

# Check that docs don't reference the old machine
python3 tools_doc_consistency.py

# Check doc consistency and list every hit (useful for debugging)
python3 tools_doc_consistency.py --list
```

### Research harnesses (read-only, no live connection)

These tools read historical data and compute statistics. They do not connect to any broker
or send any orders.

```bash
# Re-run the eval size research (produces reports/account_size_research_*.json)
python3 tools_account_size_research.py

# Re-run the funded payout model (Apex 4.0 ladder)
python3 apex_funded_40.py

# Re-run the per-year eval pass rates
python3 apex_eval_peryear.py

# Look-ahead canary check on a specific feature (supply the feature name)
python3 lookahead_canary.py
```

### Dashboard (read-only view of live/paper data)

```bash
# Start the dashboard server (http://127.0.0.1:8000 by default)
cd dashboard-v3 && python3 server.py

# Or from the repo root:
python3 dashboard_server.py
```

The dashboard only reads from the SQLite store. It does not place orders.

### Claude Code

```bash
# Open Claude Code (reads AGENTS.md/CLAUDE.md/SUBAGENTS.md automatically)
claude

# Open Claude Code with a specific task
claude "explain what the D1c filter does"
```

### Git (standard development)

```bash
git status                  # see what changed
git diff                    # review changes before staging
git log --oneline -20       # recent history
git add <specific-file>     # stage a file (never use git add -A or git add . without review)
git commit -m "message"     # commit staged changes
```

---

## RESTRICTED — requires operator approval before running

These commands connect to live systems, start the bot, or monitor live data. They are safe
in themselves when run correctly, but must not be run without the operator pre-launch
checklist (see `README.md`).

### Live bot launch (OPERATOR APPROVAL REQUIRED)

```bash
# The ONLY approved way to start the live bot
./go-live-recert.sh
```

This script performs a pre-flight check (config validation, configlock, parity verification,
credential check) before starting `auto_live.py`. Never start the bot by calling
`python3 auto_live.py` directly.

### Live data feed watcher

```bash
# Monitors the NQ market data feed (Chrome :9222 must be open with NQ 1m chart)
python3 feed_watch.py
```

### Live watchdog (must be paired with go-live-recert.sh)

```bash
# Heartbeat watchdog — kills the bot if the main loop stalls
python3 deadman_watch.py --live
```

This is normally started by `go-live-recert.sh`. Do not start it independently.

### Paper trading mode

```bash
# Paper mode: connects to TradersPost but sends simulated fills (no real orders)
python3 paper_live.py
```

Paper mode is safer than live mode but still requires a working feed and configured `.env`.
Confirm with the operator before running.

### TradersPost bridge test (Stage 1 / Stage 2)

```bash
# Stage 1: ping TradersPost (sends no order)
python3 bridge_test.py --stage 1

# Stage 2: sends a 1-MNQ "Working" bracket (a real test order — confirm with operator first)
python3 bridge_test.py --stage 2
```

Stage 2 sends a real order. Only run under operator instruction.

---

## DANGEROUS — only run under explicit operator instruction

These commands can place real orders, change live configuration, expose credentials, or
kill a running trading process. Do not run them unless the operator has explicitly asked
you to in writing.

### Order placement / flatten

```bash
# Emergency flatten — closes all open positions immediately
python3 ops_flatten.py

# Flatten guardian (manual trigger — normally automatic)
python3 flatten_guardian.py --force
```

### Credential and config changes

```bash
# Editing .env (never do this without operator instruction)
nano .env    # or any text editor — never print contents to Terminal

# Copying a new config.py over the existing one
cp config.example.py config.py    # wipes current config — confirm first
```

### Killing live processes

```bash
# Find and kill a running auto_live.py
ps aux | grep auto_live
kill <PID>
```

Only kill a live process if the operator has confirmed it should be stopped. A running
process may be managing an open position — killing it without first flattening the position
leaves an orphaned trade on the account.

### Approval flags

```bash
# Creating an approval flag (arms a live behavior — OPERATOR ONLY)
touch evidence/approvals/EXITLOCK.flag
```

Never create approval flags without operator instruction. They change what the live bot
does at runtime.

---

## Quick reference card

| Command | Safety | What it does |
|---|---|---|
| `./setup-zeus.sh` | SAFE | First-time project setup |
| `python3 -m pytest -q` | SAFE | Run all tests |
| `python3 tools_doc_consistency.py` | SAFE | Check docs are up to date |
| `python3 tools_account_size_research.py` | SAFE | Re-run eval size research |
| `python3 dashboard_server.py` | SAFE | View live dashboard |
| `claude` | SAFE | Open Claude Code |
| `./go-live-recert.sh` | RESTRICTED | Start the live bot |
| `python3 feed_watch.py` | RESTRICTED | Watch live market data |
| `python3 paper_live.py` | RESTRICTED | Paper trading |
| `python3 bridge_test.py --stage 2` | RESTRICTED | Send a test order |
| `python3 ops_flatten.py` | DANGEROUS | Close all positions immediately |
| Writing `.env` | DANGEROUS | Credential file |
| `kill <live-process>` | DANGEROUS | Kill running bot |
| `touch evidence/approvals/*.flag` | DANGEROUS | Arm live behavior |
