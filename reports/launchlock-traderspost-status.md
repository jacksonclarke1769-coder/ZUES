> ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
> that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
> **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
> `reports/apex_validation.json`. Kept for historical reference only.

# LAUNCHLOCK — TradersPost Execution Status Audit
_Generated 2026-06-14_

## Verdict: **TRADERSPOST NOT READY** (built, not proven)
The bridge **code** is sound and the payload schema is verified, but **not a single webhook has ever been sent** and the live route to the MFFU Tradovate account is **unproven**. Built ≠ proven.

---

## Checklist
| Item | Status | Evidence |
|---|---|---|
| TradersPost account created? | **UNKNOWN (operator-side)** | Cannot verify from here; operator holds account. |
| MFFU Tradovate account connected? | **UNVERIFIED** | No proof in repo; requires operator confirmation in TradersPost UI. |
| Webhook URL created? | **UNKNOWN / held locally** | `TRADERSPOST_TEST_URL` and `TRADERSPOST_LIVE_URL` **not set** in this env; by prior decision the URL is kept local and not shared. |
| Webhook URL stored as secret? | **By design** | Read from env only, never hardcoded, never in git (`bridge_test.py`). Correct. |
| Strategy mapping confirmed? | **NO** | No round-trip ever performed. |
| Account mapping confirmed? | **NO** | Payload carries `account` in `extras`; mapping to MFFU on TradersPost side never tested. |
| Symbol confirmed (MNQ/contract)? | **PARTIAL** | Bridge maps root→`TP_SYMBOL["MNQ"]`; Stage 0 payload carries the MNQ ticker. Live acceptance at TradersPost/Tradovate **not tested** (prior "Ticker Does Not Exist" for MNQ was fixed in code, not re-proven live). |
| Bracket stop/target confirmed? | **SCHEMA ONLY** | `stopLoss{type:stop,stopPrice}` + `takeProfit{limitPrice}` present & verified in Stage 0. **Never confirmed to attach at the broker.** |
| Duplicate protection confirmed? | **CODE ONLY** | `signalId` dedup (mark pending→confirmed; failed stays pending so retry can't double-order). Logic is correct; **not exercised against live TradersPost.** |
| Test webhook sent? | **NO** | `bridge_last_result` = None; store `webhook_mode`/`execution_route` = None. Nothing ever transmitted. |
| One 1-MNQ test bracket placed? | **NO** | — |
| Cancel/flatten tested? | **NO** | `ops_flatten.py` paper-tested only; live blocked. |

---

## What IS proven (Stage 0 — done today)
`evidence/launchlock/traderspost/stage0-dryrun.json` — synthetic Profile A entry built via `bridge_traderspost.build_entry`, **ALL required fields PASS**:
- ticker (MNQ), action (buy), quantity=1, price, `stopLoss.stopPrice`, `takeProfit.limitPrice`, `signalId` (dedup) — all present.
- dry-run send returns `sent=False, reason="dry-run (no webhook by design)"` → confirmed it **cannot** transmit in current mode.

## What CANNOT be proven from here
Stages 1–3 (test webhook → 1-MNQ live bracket → cancel/flatten) require the **operator's local webhook URL** and a connected MFFU Tradovate account. These are **operator-gated**. Runnable commands are prepared in the test sequence below.

---

## Stage commands (operator runs with local URL; never paste URL into chat)
```
# Stage 1 — Test webhook (benign exit ping on a flat account)
TRADERSPOST_TEST_URL='<your test strategy URL>' python3 bridge_test.py --ping
#   PASS = TradersPost receives it, 2xx, correct account mapping, no malformed fields, no dup.

# Stage 2 — ONE 1-MNQ live/test bracket (only if Stage 1 passed)
TRADERSPOST_LIVE_URL='<your live strategy URL>' python3 bridge_test.py --mode live --one-mnq   # see note
#   PASS = order reaches Tradovate/MFFU, correct account/side/qty=1, STOP attaches, TARGET attaches, no dup.

# Stage 3 — Cancel / flatten
#   Use TradersPost UI or ops_flatten against the same account; confirm working orders cancel + dashboard updates.
```
> Note: `bridge_test.py` currently supports `--ping`. A single 1-MNQ **entry+bracket** test sender may need a one-line `--one-mnq` helper added to `bridge_test.py` (does not touch Profile A/B/D1c). Flag if you want it built.

Capture each stage's output to `evidence/launchlock/traderspost/stageN-*.txt`. **No full-size trade until all stages pass.**
