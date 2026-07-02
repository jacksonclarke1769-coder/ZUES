# ZEUS — Automated NQ Futures Trading Bot

ZEUS is a fully automated trading bot for **NQ (E-mini Nasdaq-100) futures** on a real
prop-firm account (**Apex Funding 50K evaluation**), routed live through **TradersPost →
Tradovate**.

> **New here?** Start with [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md).
> Never used Claude Code? Read [`docs/CLAUDE_CODE_GUIDE.md`](docs/CLAUDE_CODE_GUIDE.md).
> Safety rules: [`docs/SAFETY.md`](docs/SAFETY.md).

---

## What ZEUS is

ZEUS watches the NQ Nasdaq-100 futures market every minute during the New York trading
session. When it detects a specific, pre-certified pattern, it sends an automated order to
Tradovate through the TradersPost webhook bridge. It then manages the trade — adjusting
stops, taking partial profits, and closing — exactly as the backtest specified.

**Real capital is at stake.** The bot runs on a live Apex 50K evaluation account. A mistake
can lose real money, and a serious mistake can fail the entire evaluation. Every engineering
decision in this codebase reflects that constraint.

---

## What it trades

| Item | Detail |
|---|---|
| Instrument | NQ (E-mini Nasdaq-100 futures), traded as micro-contracts (MNQ) |
| Venue | Tradovate, routed via TradersPost webhook |
| Session | New York AM: roughly 09:30–11:30 ET |
| Strategy | **Profile A** — ICT Optimal Trade Entry (OTE) on sweep-then-reversal |
| Exit | **Exit#3** — fixed partial at 1R + trail remainder |
| Filter | **D1c ACTIVE_EVAL_FILTER** — daily momentum screen that skips low-probability days |

Profile B (Opening Range Breakout) and the momentum feature are **OFF** in the current
machine. Do not re-enable them without a full certification run.

---

## The Locked Machine (ZEUS Rev B — v2026.07.02b)

The configuration below is **operator-approved and production-locked**. No code change may
alter entries, exits, sizing, filters, or their timing without a new harness run recorded in
`reports/apex_validation.json` and explicit operator approval.

```
Profile A · Exit#3 · D1c ACTIVE_EVAL_FILTER
Size-to-risk $1,200 per contract budget (up to 10 MNQ)
Profile B: OFF · Momentum lane: OFF
Daily stop: $550
Launch ONLY via: ./go-live-recert.sh
```

**Before any live restart**, the operator must:
1. Rotate the Tradovate password (the old one was exposed on 2026-07-02).
2. Verify the Apex trailing drawdown on the live dashboard — config assumes $2,500; if it
   shows $2,000, update `config.py EVAL.trail_dd` first.
3. Confirm the Tradovate account-manager panel is readable in the `:9222` Chrome tab.
4. Start ONLY with `./go-live-recert.sh`. Any `auto_live.py` started before 2026-07-02
   ~11:00 AWST runs an OLD machine and must not be trusted.

---

## Certified Eval Numbers

These numbers come from `reports/apex_validation.json §dll_recert_selected_machine`,
produced by `tools_account_size_research.py` on real Databento 1m data (2026-07-02).

| Metric | Value | Label |
|---|---|---|
| Pass rate | **58.2%** | CERTIFIED |
| Bust rate | **29.1%** | CERTIFIED |
| Expire rate | **12.7%** | CERTIFIED |
| Median days to outcome | **~11 days** | CERTIFIED |
| Expected value per attempt | ~$7,040 | CERTIFIED |
| Worst single day | −$1,000 (DLL cap) | CERTIFIED |

The Apex 50K EOD evaluation enforces a **$1,000 Daily Loss Limit** (operator-confirmed
2026-07-02). The $1,200 size-to-risk budget was chosen specifically to keep the worst
single-trade excursion inside that cap.

**Per-year pass rates** (same harness):

| Year | Pass % |
|---|---|
| 2021 | 53.2 |
| 2022 | 48.3 |
| 2023 | 60.2 |
| 2024 | 55.8 |
| 2025 | 63.2 |
| 2026 | 68.0 |
| **All** | **58.2** |

---

## Funded Account Numbers (Model-Based)

These numbers come from `apex_funded_40.py` on the same Databento data. They model the
Apex 4.0 payout ladder. They have NOT been validated on a live funded account.

| Metric | Value | Label |
|---|---|---|
| Funded size | A4 (4 MNQ), $480 budget | MODEL-BASED |
| Lifetime E[payout] per account | ~$12.7k | MODEL-BASED |
| Estimated account lifespan | ~15–16 months | MODEL-BASED |
| Gross income per month | ~$785/mo | MODEL-BASED |
| 20-account fleet gross/mo | ~$16–17k/mo | MODEL-BASED |
| Eval→first payout probability | ~53–58% | MODEL-BASED |
| Funded→first payout probability | ~91–100% (0% bust observed) | MODEL-BASED |
| Actual payouts received | Not yet confirmed | NEEDS-LIVE-VALIDATION |
| Fill quality vs backtest | Not yet measured | NEEDS-LIVE-VALIDATION |

---

## Architecture Overview

```
TradingView (NQ 1m chart, Chrome :9222)
        │  price feed via tv_feed.py
        ▼
  auto_live.py (main loop)
        │  signal from strategy_engine_profileA.py
        │  D1c filter from d1c_filter.py
        ▼
  bridge_traderspost.py  ──►  TradersPost webhook  ──►  Tradovate orders
        │
  auto_safety.py + runtime_config.py (CONFIGLOCK)
  flatten_guardian.py + deadman_watch.py
        │
  store.py (SQLite)  ──►  dashboard-v3/ (FastAPI + UI)
```

Key files:

| File | What it does |
|---|---|
| `auto_live.py` | Main live loop: data → signal → order → risk → persist |
| `strategy_engine_profileA.py` | Profile A signal engine (mirrors the backtest exactly) |
| `d1c_filter.py` | D1c daily momentum filter |
| `bridge_traderspost.py` | Sends orders via TradersPost webhook |
| `auto_safety.py` | Pre-trade safety gates (configlock, daily stop, drawdown) |
| `runtime_config.py` | CONFIGLOCK — prevents mid-session config changes |
| `flatten_guardian.py` | Emergency flatten watchdog |
| `deadman_watch.py` | Heartbeat watchdog; kills the process if the loop stalls |
| `store.py` | SQLite persistence (trades, P&L, events) |
| `dashboard-v3/` | Live dashboard UI |
| `go-live-recert.sh` | The ONLY approved way to start the live bot |

---

## Safety Philosophy

**Fail closed.** Every error path that could reach an order must BLOCK trading, not continue.
A gate failure may only ever cost income — it must never add risk.

**Live must match certified.** The code that trades is the code that was measured. Any change
to strategy logic de-certifies the machine. "It should be roughly the same" is not a measurement.

**Numbers trace to the harness.** Every statistic shown anywhere — dashboard, docs, Telegram —
must trace to `reports/apex_validation.json`, which traces to a committed harness on real data.

Read the full engineering contract in [`AGENTS.md`](AGENTS.md).

---

## Setup (First Time)

```bash
# 1. Clone the repo
git clone <repo-url>
cd nq-liq-bot

# 2. Run the safe setup script (no live trading, no secrets written)
./setup-zeus.sh

# 3. Open Claude Code for guided assistance
claude
```

The setup script checks Python 3.11+, creates a virtual environment, installs dependencies,
creates `.env` from `.env.example` if it doesn't already exist, and prints next steps.

For a step-by-step walkthrough, see [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md).

---

## Using Claude Code

Open `claude` in this directory. ZEUS uses a two-model role split:

- **Planning, research, audits, certification** → main session (Fable-class reasoning)
- **Implementation against an approved spec** → `zeus-implementer` sub-agent (Sonnet)

See [`docs/CLAUDE_CODE_GUIDE.md`](docs/CLAUDE_CODE_GUIDE.md) for safe prompts and what to avoid.

---

## What NOT to Touch

| Do not touch | Why |
|---|---|
| `config.py` | Gitignored local secrets + live config; edit only with operator approval |
| `evidence/approvals/*.flag` | Approval flags arm live behaviors; only the operator creates them |
| `.env` | Credentials; never print, commit, or share |
| `go-live-recert.sh` | The certified launch path; changes require re-certification |
| Any strategy logic file | Any change de-certifies the machine |
| Any live process | Kill/restart only under operator instruction |

---

## Folder Structure

```
nq-liq-bot/
├── auto_live.py              Main live loop
├── strategy_engine_profileA.py  Profile A signal engine
├── d1c_filter.py             D1c daily filter
├── bridge_traderspost.py     Order webhook
├── auto_safety.py            Safety gates
├── config_defaults.py        Committed defaults (no secrets)
├── config.py                 Local config (gitignored)
├── go-live-recert.sh         Certified launch script
├── setup-zeus.sh             Safe first-time setup
├── requirements.txt          Python dependencies
├── AGENTS.md                 Engineering contract (read first)
├── SUBAGENTS.md              Fable/Sonnet role split
├── docs/                     Documentation
│   ├── GETTING_STARTED.md    Total-beginner setup guide
│   ├── CLAUDE_CODE_GUIDE.md  How to use Claude Code safely
│   ├── SAFETY.md             Safety rules
│   ├── COMMANDS.md           Command reference
│   └── development_workflow.md  Three-gate change workflow
├── reports/
│   └── apex_validation.json  Source of truth for all statistics
├── evidence/approvals/       Operator approval flags
├── tests/                    Additional test modules
├── tools_*.py                Research harnesses (read-only, not for live)
└── dashboard-v3/             Live dashboard
```

---

## Common Commands

See [`docs/COMMANDS.md`](docs/COMMANDS.md) for the full reference with safety labels.

```bash
# Setup
./setup-zeus.sh                  # First-time safe setup

# Tests (always run before declaring anything done)
python3 -m pytest -q             # Full suite (~30s, must be 0 failed)
python3 tools_doc_consistency.py # Check docs don't reference the old machine

# Dashboard (read-only, safe)
cd dashboard-v3 && python3 server.py   # View live dashboard

# Research harnesses (safe — no orders, no live connection)
python3 tools_account_size_research.py  # Re-run eval size research
python3 apex_funded_40.py               # Re-run funded model

# RESTRICTED — requires operator approval before use
./go-live-recert.sh              # Start the live bot
```

---

## Operator Checklist (Before Any Live Session)

- [ ] Tradovate password rotated (required; old credential was exposed 2026-07-02)
- [ ] Chrome :9222 open with NQ 1m chart, logged-in feed (logged-out = DATA RED)
- [ ] Apex trailing drawdown confirmed on dashboard (config assumes $2,500)
- [ ] `config.py` matches certified machine: A10 · Exit#3 · D1c · $1,200 budget · B OFF · mm OFF
- [ ] `./go-live-recert.sh` is the launch command (NOT `auto_live.py` directly)
- [ ] Daily stop of $550 confirmed cold
- [ ] No processes left over from before 2026-07-02 ~11:00 AWST

---

## Research Status

| Research area | Status |
|---|---|
| Profile A (Exit#3 + D1c) | CERTIFIED — current live machine |
| Profile B (ORB) | OFF — edge near-breakeven on 1m-truth fills; removed 2026-07-02 |
| Momentum lane | OFF — pending warmup engineering + re-certification (audit D1/H) |
| HTF alignment filter | INVALIDATED 2026-07-02 — never armed, removed |
| Apex 4.0 funded model | Harness-certified; live payouts not yet received |

All research harnesses are committed files in the repo root (`tools_*.py`, `apex_*.py`).
Results are recorded in `reports/apex_validation.json`. Never run research from `/tmp`.

---

## Historical Docs Disclaimer

Several documents in this repo describe earlier versions of the machine or trading modes
that are no longer active:

| Document | What it describes | Status |
|---|---|---|
| `docs/ARES_DAILY_CHECKLIST.md` | Manual ARES trading mode | OBSOLETE |
| `docs/ARES_KILL_SWITCH.md` | Manual ARES kill-switch rules | OBSOLETE |
| `RUNBOOK_SINGLE1R.md` | Single-1R exit mode (demoted 2026-07-02) | SUPERSEDED |
| `MONDAY_SESSION.md` | Earlier multi-firm session notes | Historical |

These are kept as audit trail. They do not describe the current machine.
The current machine is always described by `AGENTS.md` (locked config block) and this README.
