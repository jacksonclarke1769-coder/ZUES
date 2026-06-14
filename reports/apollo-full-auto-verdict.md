# APOLLO — Full Auto GO / NO-GO Verdict
_2026-06-14 · audit + build sprint · Profile A/B/D1c logic UNTOUCHED · safety only tightened_

## ❌ FULL AUTO NO-GO → TOMORROW = MANUAL ONLY
(Upgrades to **SEMI-AUTO** once TradersPost Stages 1–3 pass; **FULL AUTO** only after a real-time **1m** feed is also proven.)

The machinery is built and unit-proven. The two live proofs that decide safety — **real-time data** and **a live order reaching MFFU** — are **unproven and unprovable tonight** (market closed; webhook URL held locally). Per the prime directive, that is a hard NO-GO.

---

## Required items
| # | Item | Status |
|---|---|---|
| 1 | Live data status | ❌ DATA_NOT_READY (`reports/apollo-live-data.md`) |
| 2 | Feed timeframe | 5m available; **1m engine path refused** (would change Profile A; aggregator unbuilt) |
| 3 | Real-time CME entitlement | ❌ UNVERIFIED (`TV_REALTIME_CONFIRMED` not set; can't detect with market closed) |
| 4 | TradersPost ping | ⏳ NOT RUN (operator + local URL + open market) |
| 5 | 1-MNQ bracket → MFFU | ⏳ NOT RUN |
| 6 | Flatten/cancel | ⏳ NOT RUN |
| 7 | D1c mode | **SHADOW** (auto-forced: feed is 5m / realtime unconfirmed). Active-eval-filter is gated behind real-time 1m. |
| 8 | ARES mode | READY (eval, 50K-conservative, A3/B2); refuses funded accounts |
| 9 | Daily stop | ✅ −$700 (50K-conservative), restart-proof (DailyGuard) |
| 10 | Dashboard status | ✅ **YELLOW** (honest): green=False, data_ready=False, traderspost_proven=False |
| 11 | Emergency flatten | ✅ present + tested (see Task 6) |
| 12 | **Final verdict** | **FULL AUTO NO-GO — MANUAL ONLY** |

---

## What this sprint BUILT + PROVED (offline)
- **Full-auto master gate** (`auto_safety.full_auto_preflight`): `--live` is refused unless DATA_READY **and** TradersPost proven (URL + `PROVEN.flag` + `traderspost-approved.flag` + `bracket-verified.flag`) **and** dashboard green **and** `full-auto-approved.flag` **and** explicit account **and** ARES armed **and** daily stop set **and** emergency flatten available **and** dup ledger readable. Fail-closed. (8 refusal paths + 1 pass path unit-tested.)
- **D1c feed enforcement** (Task 4): `resolve_d1c_for_feed` forces **SHADOW** on any non-1m or non-realtime feed; ACTIVE_EVAL_FILTER only on real-time 1m. Never upgrades, never touches Profile B.
- **Runner gating** (Task 5): `--live` now requires `--confirm`; `--feed tradingview-1m` refused (protects 5m Profile A); `--mode/--execution` flags added; dashboard kept truthful (`execution_route`/`webhook_mode`/`auto_exec_mode`).
- **Approval flag** (`full-auto-approved.flag`): gate REQUIRES it; **deliberately NOT created** — that is your final human arming step after proofs. No flag → no full auto.
- Tests: **240 passing** (+12 APOLLO). 1 failure = pre-existing `test_vulcan` (`SAFETY.enabled=True`; still safe via `paper=True`), unrelated.

## Task 6 — emergency controls verified (offline)
- Emergency flatten path importable (`ops_flatten`) and gate-required.
- Duplicate lock: signalId dedup (pending→confirmed; failed stays pending → no double order). ✅ tests
- Daily stop cannot be bypassed by restart (DailyGuard persistent). ✅ tests
- ARES cannot run on funded accounts (`ares_mode` refuses; dashboard RED if forced). ✅ tests
- Wrong/explicit account enforced (no silent default). ✅ gate
- Dashboard cannot show false green (tri-state gated on data + execution proof). ✅ verified YELLOW
- 81 emergency-control-related tests pass.

---

## Allowed commands
**Tonight (paper only — no orders):**
```
python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative --feed tradingview-5m --d1c-mode shadow
```
**After TradersPost Stages 1–3 pass + real-time confirmed (SEMI/FULL, 5m + D1c shadow):**
```
TV_REALTIME_CONFIRMED=1 TRADERSPOST_LIVE_URL='<url>' \
python3 auto_live.py --mode eval --account MFFU-50K-1 --tier 50K-conservative \
  --feed tradingview-5m --execution traderspost --d1c-mode shadow --live --confirm
```
(requires `full-auto-approved.flag` + `PROVEN.flag` + green dashboard, else the gate refuses)

## NOT allowed
```
# 1m engine feed — refused (would change 5m Profile A):
... --feed tradingview-1m ... --live --confirm
# any --live without --confirm, without proofs, or with D1c active on a 5m feed
```

## Remaining blockers (to reach SEMI/FULL)
1. Confirm TradingView real-time CME → `export TV_REALTIME_CONFIRMED=1`.
2. Run TradersPost Stages 1→2→3 with local URL; verify attach + flatten at MFFU; `touch evidence/launchlock/traderspost/PROVEN.flag`.
3. Create `evidence/approvals/full-auto-approved.flag` (final human arming).
4. For D1c-active full auto: build + validate the real-time **1m** dual-stream (1m→5m aggregator or Databento). Until then D1c = SHADOW.

---
## Final principle
We did not make the bot *look* ready. The gate now makes it **impossible** to go live without proof. The proofs aren't done → **MANUAL ONLY. No shortcuts.**
