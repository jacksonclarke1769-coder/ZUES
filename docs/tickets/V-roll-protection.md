# TASK: V — quarterly roll protection (NQ1! feed vs MNQ orders)

ROLE: Sonnet implement
DE-CERTIFIES: no

## Problem
The feed is continuous `NQ1!`; orders go out as bare-root `MNQ` (`bridge_traderspost.py:18-21`,
"Override TP_SYMBOL per active contract month at deploy time" — never done). Around quarterly volume
roll (~Wed/Thu before 3rd-Friday expiry: Mar/Jun/Sep/Dec) TradingView and TradersPost/Tradovate can
resolve DIFFERENT contracts for a few days → bracket prices off by the calendar spread (~75-150 NQ
pts) in one direction (audit R8/A7). Next window: ~2026-09-09 → 2026-09-18.

## Scope
1. `bridge_traderspost.py`: allow an env override `TP_SYMBOL_MNQ` (e.g. `MNQU2026`) — when set, all
   MNQ payloads use it as the ticker. Read at build time (os.environ), not import time, so tests can
   monkeypatch.
2. New pure helper (in `market_calendar.py`): `roll_window(d)` → True when date d is within the 8
   calendar days ENDING on quarterly expiry (3rd Friday of Mar/Jun/Sep/Dec). Computed for any year —
   no hardcoded dates.
3. Preflight (`full_auto_preflight.py`): during `roll_window(today)`, BLOCK unless `TP_SYMBOL_MNQ` is
   set, with a message explaining the roll risk and the fix. Outside the window: no change.
4. `.env.example`: add commented `# TP_SYMBOL_MNQ=MNQU2026  # pin during quarterly roll weeks`.
5. OPERATOR_RUNBOOK.md: 4-6 line "Roll week" section (when, what to set, verify chart contract).

## Files allowed
- bridge_traderspost.py, market_calendar.py, full_auto_preflight.py, .env.example,
  OPERATOR_RUNBOOK.md, test_market_calendar.py (extend), new test_roll_protection.py

## Files forbidden
- auto_live.py, tv_feed.py, everything else. Do NOT change any price/qty/bracket construction.

## Success criteria
- Tests: roll_window truth-table (2026-09-09 True, 2026-09-18 True, 2026-09-19 False, 2026-08-01
  False, 2027-03 window correct); TP_SYMBOL_MNQ override appears in a built payload ticker and normal
  behavior (bare MNQ) when unset; preflight blocks in-window without the env, passes with it.
- Payloads byte-identical to today when env unset and outside roll window.
- Full suite green.

## Verification
- targeted tests then `python3 -m pytest -q`

## Exit criteria
Standard report; nothing outside allowed files.
