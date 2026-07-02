> ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
> that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
> **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
> `reports/apex_validation.json`. Kept for historical reference only.

# LAUNCHLOCK — Final Launch Status & Verdict (post-fix)
_Updated 2026-06-14 after the fix sprint · Profile A/B/D1c logic UNTOUCHED_

## CAN THIS MACHINE SAFELY PLACE AUTOMATED TRADES TOMORROW NIGHT?
# ❌ NO — FULL AUTO NO-GO.
**Tomorrow mode: MANUAL ONLY (MODE C)**, upgradeable to **SEMI-AUTO (MODE B)** iff TradersPost Stages 1–3 pass first (operator-run, needs local URL).

Reason it is still NO-GO after the fixes: warmup depth is fixed and the dashboard is now honest, but **two facts remain UNPROVEN and cannot be proven from here**: (a) TradingView real-time CME entitlement, (b) the live TradersPost→MFFU execution route. Market is closed (audit run Sun); no live tick or live order could be validated.

---

## What the fix sprint changed (built + verified)
- **Warmup depth FIXED.** TradingView feed now warms from **Dukascopy 45d (current, credential-free), basis-aligned to the CME frame**, then live-tails TradingView. Verified: **8,409 bars, 43-day span, `warmup_ok=True`**, measured **basis +27.96 pts**. Prev-day & prev-week levels now valid. (`--warmup-source`, default `dukascopy`.)
- **DATA_READY flag ADDED** (`tv_feed.data_status()`): true only if warmup ≥2 wks AND realtime confirmed AND not stale AND zero resets this session. Entitlement can't be auto-verified → **defaults false** until `TV_REALTIME_CONFIRMED=1`. Persisted to the dashboard DB each bar.
- **Dashboard false-green FIXED** (`zeus_server`): tri-state **GREEN/YELLOW/RED**. GREEN requires `data_ready` AND `traderspost_proven` AND D1c/bridge ok. Verified: currently **YELLOW** with blockers listed.
- **TradersPost Stage-2 helper ADDED** (`bridge_test.py --one-mnq`): qty hard-forced to 1, explicit/derived limit+stop+target, deterministic signalId (retry-dedup), evidence saved. Plus `--ping` (Stage 1) and `--flatten` (Stage 3), all writing evidence.
- Tests: **228 passing** (+ new tv_feed/data_status/bridge_test coverage). 1 failure = pre-existing `test_vulcan` (`SAFETY.enabled=True`, still safe since `paper=True`).

---

## 1. TradingView warmup status — ✅ FIXED
8,409 bars / 43-day span / `warmup_ok=True`. No more one-day limitation. Basis +27.96 pts applied to align warmup to CME frame.

## 2. Real-time CME entitlement — ❌ UNVERIFIED (operator must confirm)
Cannot be auto-detected (market closed). Until confirmed, `DATA_READY=false` by design. Set `TV_REALTIME_CONFIRMED=1` only after you verify the TradingView plan streams real-time CME (not delayed).

## 3. Data liveness — ⚠️ NOT READY (correctly)
`DATA_READY=false`: entitlement unverified + bars stale (market closed). Will also require a live session with zero connection resets.

## 4. TradersPost Stage 1 (ping) — ⏳ NOT RUN (operator, local URL)
`TRADERSPOST_TEST_URL='<url>' python3 bridge_test.py --account MFFU-50K-1 --ping`

## 5. TradersPost Stage 2 (1-MNQ bracket) — ⏳ NOT RUN
`TRADERSPOST_LIVE_URL='<url>' python3 bridge_test.py --account MFFU-50K-1 --one-mnq --ref <price> --mode live --confirm`
(qty forced to 1; resting bracket derived from `--ref`; evidence → `stage2-1mnq.json`)

## 6. TradersPost Stage 3 (cancel/flatten) — ⏳ NOT RUN
`TRADERSPOST_LIVE_URL='<url>' python3 bridge_test.py --account MFFU-50K-1 --flatten`

## 7. Dashboard status — ✅ HONEST
**YELLOW**, `green=False`, `data_ready=False`, `traderspost_proven=False`, blockers enumerated. Will not show GREEN until data + execution proven.

## 8. Remaining blockers (full auto)
1. TradingView real-time CME entitlement unconfirmed.
2. Live data session not soaked (zero-reset, non-stale) — needs market open.
3. TradersPost Stages 1–3 never run (no webhook sent; bracket attach + cancel unproven).
4. `evidence/launchlock/traderspost/PROVEN.flag` not created (operator attests after Stage 2+3).
5. Tradovate direct API creds still incomplete (`cid`/`sec`/`account_spec`) — direct route dead (TradersPost is the only path).

## 9. Tomorrow mode
**MANUAL ONLY (MODE C).** → MODE B after Stages 1–3 pass + entitlement confirmed.

## 10. Exact commands ALLOWED
```
# Supervised PAPER data (deep warmup, D1c shadow, NO orders):
python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative --feed tradingview --d1c-mode shadow
# TradersPost proof (operator's local URL):
TRADERSPOST_TEST_URL='<url>' python3 bridge_test.py --account MFFU-50K-1 --ping            # Stage 1
TRADERSPOST_LIVE_URL='<url>' python3 bridge_test.py --account MFFU-50K-1 --one-mnq --ref <px> --mode live --confirm  # Stage 2
TRADERSPOST_LIVE_URL='<url>' python3 bridge_test.py --account MFFU-50K-1 --flatten         # Stage 3
```

## 11. Exact command NOT allowed
```
python3 auto_live.py ... --live      # unattended full automation — FORBIDDEN until DATA READY + TRADERSPOST READY
```

## 12. Fix list before tomorrow night (remaining = all operator-side)
1. Confirm TradingView real-time CME entitlement → export `TV_REALTIME_CONFIRMED=1`.
2. Run TradersPost Stages 1 → 2 → 3 with your local URL; verify stop+target attach and flatten at MFFU.
3. After Stage 2+3 verified, create `evidence/launchlock/traderspost/PROVEN.flag` (this is what flips the dashboard toward GREEN).
4. Optional: fix `config.SAFETY["enabled"]→False` to clear the red vulcan posture test.

---
## Final principle check
Built ≠ proven. The warmup, the DATA_READY gate, the honest dashboard, and the Stage-2 sender are now **built and unit-proven**. The two things that decide live safety — real-time data entitlement and a live order reaching MFFU — are **still unproven**. Therefore: **MANUAL/SUPERVISED ONLY. No accidental live automation.**
