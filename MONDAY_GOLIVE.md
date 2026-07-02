> ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
> that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
> **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
> `reports/apex_validation.json`. Kept for historical reference only.

# MONDAY GO-LIVE — first live Apex 50K eval

**Config running Monday = the proven eval:** `Apex-50K-eval` · **A10 / B5 / Momentum-6** · $550 daily stop.
Validated ~57% pass, median 7 days (EOD rule, real Databento). Unchanged, lowest-risk config in the system.
(The momentum-on-funded change does NOT touch the eval — it only matters after you pass.)

---

## 1 · Pre-open setup (do before 09:30 ET)

- [ ] **Buy the Apex 50K eval account** (the EOD-drawdown variant — confirm with Apex it's EOD, not intraday trailing).
- [ ] **Wire its Tradovate creds** into `config.py` (account name/id + env). Set env OFF `demo` to the live eval account.
- [ ] **Rotate the old Tradovate demo password** (it leaked into chat history this session).
- [ ] **Flip execution to live:** `webhook_mode` DRY-RUN → LIVE.
- [ ] **Bring up the LOGGED-IN Chrome on :9222**, NQ chart at 1m, real-time edge.
  - A logged-out / throwaway Chrome streams delayed daily bars → `data_state` stays RED → no trades (correct, but you won't trade).
- [ ] **Confirm dashboard `data_state` = GREEN** (`http://localhost:8777`) before the open.
- [ ] **Re-verify ONE bracket** on the REAL Apex account (`bridge_test.py --one-mnq --mode live --confirm`).
      The demo/MFFU bracket-verify does NOT transfer to a new broker connection.
- [ ] Confirm approval flags present: `exit-model-approved`, `bracket-verified`, `traderspost-approved` (in `evidence/approvals/`).

## 2 · Run

```
python3 auto_live.py --tier Apex-50K-eval --profile-momentum --momentum-qty 6 --mode live --confirm
```
- NY-AM killzone 09:30–11:30 ET. Momentum is part of the validated eval stack (mm6).
- Omit `--live`/`--confirm` to run paper first if you want a warm-up hour.

## 3 · During the session — WATCH

- [ ] **Confirm trade #1 of EACH lane (A / B / Momentum) by EYE in Tradovate.** There is NO broker read-back — you are the confirmation. From logs alone a +$369 win and a −$500 naked runner look identical.
- [ ] First bracket lands "Working" (entry + TP + stop staged) → good.
- [ ] Watch `logs/live_engine_decisions/` + the dashboard ledger update.
- [ ] Keep size honest: this is the eval — let it run the frozen config, don't override.

## 4 · Honest expectations (don't panic)

- **~57% pass, median ~7 days.** 15% pass same-day; a long tail runs to the 30-day wire. A slow start is normal — the distribution is wide, NOT a failure.
- **Worst year in backtest was 2022 at ~48%.** Even a cold stretch isn't a broken edge.
- **Fail-closed:** RED/stale feed = zero trades. Broker issue = caught on trade #1. The untested surface (live feed/broker) can only no-op, not blow up.
- **The two numbers that matter:** $550 daily stop caps the day (soft, not a fail); only the **$2,000 EOD trailing drawdown** fails the account.

## 5 · If something's wrong — flatten / halt

- Emergency flatten: `python3 ops_flatten.py` (or the flatten guardian fires at 14:30 ET as backstop).
- Stop the bot: Ctrl-C / kill the `auto_live` process; positions stay bracketed at the broker.
- A stale feed auto-blocks new entries (fail-closed) — you don't have to babysit RED.

---

**Bottom line:** proven config, every offline test green (554 tests, exact live==backtest parity, fail-closed rails),
feed + broker handshake is the only thing a live session proves. Get the account wired, the feed GREEN, verify one
bracket, watch the first fills by eye. The system does the rest.
