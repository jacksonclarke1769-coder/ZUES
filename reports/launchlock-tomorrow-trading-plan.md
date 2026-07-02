> ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
> that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
> **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
> `reports/apex_validation.json`. Kept for historical reference only.

# LAUNCHLOCK — Tomorrow Trading Plan (Fallback)
_Generated 2026-06-14 · for the Mon 2026-06-15 NY-AM session_

## Mode: **MANUAL ONLY (MODE C)** — upgrades to SEMI-AUTO (MODE B) **only if** TradersPost Stages 1–3 pass first.

Reason: full automation is NO-GO (data not production-ready; TradersPost execution unproven). No bot `--live` sends.

---

## Account & setup
- **Account:** MFFU 50K (eval)
- **Mode:** ARES Eval Mode
- **Tier:** 50K Conservative
- **Sizing:** **A3 / B2** (3 MNQ on Profile A, 2 on Profile B)
- **Daily hard stop:** **−$700 USD** (manually enforced — bot is not arming the live stop)
- **D1c:** Use **only if** a correct live signal feed is available and the filter applies at validated fidelity. Current feed is **5m**, D1c is **1m-validated** → **do NOT let D1c add or justify size**; treat as advisory/shadow only. If unsure, trade A/B without D1c.

## Rules (hard)
- No revenge trading.
- No trades outside the frozen A + B setups.
- **No size increase because D1c is active** — D1c can only remove trades, never add size.
- Stop for the day after **2 full losses**.
- **Stop immediately if platform / data / bridge is uncertain.**
- Log every trade (`out/ares/ares_trade_tracker.csv`, 21-col schema).

## Execution path tomorrow
1. **Read setups on TradingView** (the chart is the source of truth; Python feed is supervised, not trusted for unattended trading).
2. Enter manually **or**, if Stages 1–3 passed, route a **single** validated signal through TradersPost and **watch it fill** — do not leave it unattended.
3. Manually track PnL vs the −$700 stop. Flatten by 14:30 ET.

## Pre-session 5-minute preflight
- [ ] TradingView logged in, **real-time CME confirmed** (not delayed), chart = NQ.
- [ ] Daily-stop number written down; alarm set.
- [ ] If using the bridge: Stage 1 ping returns 2xx to the correct MFFU account **today**.
- [ ] Dashboard sanity (do not trust "green" alone — verify data + bridge by hand).
- [ ] Decide D1c: shadow/advisory only.

## What would make tomorrow SEMI-AUTO (MODE B)
All three before the session:
1. TradersPost Stage 1 (test webhook) PASS to MFFU.
2. TradersPost Stage 2 (1-MNQ bracket: stop+target attach, no dup) PASS.
3. TradersPost Stage 3 (cancel/flatten) PASS.
Then: human confirms each setup on TradingView, routes one signal at a time through the proven bridge, manual daily stop. **Live data into Python still not required for MODE B.**

## What is NOT allowed
- `auto_live.py ... --live` (unattended full automation) — **forbidden** until DATA READY + TRADERSPOST READY both true.
