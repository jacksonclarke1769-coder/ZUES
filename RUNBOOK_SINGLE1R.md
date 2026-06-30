# SINGLE_1R — Go-Live Runbook

single@1R exit model: full position to a **+1R** target (shared −1R stop), on Profile A **and** B.
Built + gated 2026-06-30. Certified causally-clean + backtest-robust. **Default is OFF (EXIT3).**

## ⚠️ Read first
single@1R has **never traded live or paper**. The certification recommended **paper-test first**;
going straight live skips that. It's your call — both commands are ready below.

## The commands

| Goal | Command | Real orders? | Needs flag? |
|---|---|---|---|
| **Paper-test first (recommended)** | `./paper-single1r.sh` | No (dry-run) | No |
| **GO LIVE (one command)** | `./go-live-single1r.sh` | **YES** | created by the script |
| **Revert to EXIT3** | `pkill -f auto_live.py` then your normal live launch | — | — |

## What `./go-live-single1r.sh` does (one command, fully gated)
1. Requires you to type exactly `GO LIVE SINGLE1R` (no accidental arming).
2. Creates `evidence/approvals/single-1r-approved.flag` (the live gate).
3. Loads the TradersPost webhook from `.env`, sets `TV_REALTIME_CONFIRMED=1`.
4. Runs `full_auto_preflight` — **aborts if not GREEN** (feed RED / dead-man / non-trading-day all block it).
5. Stops the current EXIT3 live session and relaunches with `--exit-model SINGLE_1R --live`.

## The safety gates (all still apply)
- **Triple gate to route live:** `--exit-model SINGLE_1R` **+** `single-1r-approved.flag` **+** preflight GREEN.
  Miss any one → fail-safe to **EXIT3** (never silently routes single@1R live).
- Without the flag, or in paper mode, or by default → **EXIT3** (the frozen validated model).
- $550 daily stop, D1c filter, P3 brake, broker-side brackets, wall-clock EOD flatten, NY-AM window — unchanged.
- The old `else → 2R` misfire is **gone** (unknown exit model = fail-closed, no order).

## Supervising a live SINGLE_1R session
- Watch `logs/live-single1r.log` + the dashboard. No broker read-back — **confirm fills by eye** on TradersPost/Apex.
- Telegram `/stop` (soft halt) and the kill-switch work as normal.
- Keep the feed Chrome logged in; keep this machine awake (processes are session-tied).

## Revert (instant)
`pkill -f auto_live.py`, then relaunch your normal EXIT3 live command (omit `--exit-model`). Optionally
`rm evidence/approvals/single-1r-approved.flag` to re-lock the gate.
