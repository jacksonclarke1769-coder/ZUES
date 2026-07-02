> ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
> that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
> **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
> `reports/apex_validation.json`. Kept for historical reference only.

# APOLLO — TradersPost Execution Proof
_2026-06-14_

## Verdict: **TRADERSPOST_NOT_READY**

The Stage 1–3 live sequence **cannot be run by me**: it needs (a) the **webhook URL you hold locally** and (b) an **open market**. Both are absent tonight. The helpers are built and unit-proven; the live route is **not yet proven**. Built ≠ proven.

## Stage commands (operator runs; never paste the URL into chat or a file)
```
# Stage 1 — Ping (account + routing + strategy mapping)
TRADERSPOST_TEST_URL='<test url>' python3 bridge_test.py --account MFFU-50K-1 --ping
#   PASS = 2xx, correct MFFU account mapping, no malformed fields, evidence saved (stage1-ping.json)

# Stage 2 — 1 MNQ bracket (qty hard-forced to 1)
TRADERSPOST_LIVE_URL='<live url>' python3 bridge_test.py --account MFFU-50K-1 --one-mnq --ref <price> --mode live --confirm
#   PASS = reaches MFFU Tradovate; correct symbol/side; limit price; STOP attaches; TARGET attaches; no dup
#   (evidence saved: stage2-1mnq.json)

# Stage 3 — Flatten / cancel
TRADERSPOST_LIVE_URL='<live url>' python3 bridge_test.py --account MFFU-50K-1 --flatten
#   PASS = position flat, working orders cancelled, no orphan order (evidence saved: stage3-flatten.json)
```

## Built + verified offline
- `--ping` / `--one-mnq` / `--flatten` modes, each saving evidence under `evidence/launchlock/traderspost/`.
- `--one-mnq`: **qty hard-forced to 1** (ignores `--qty`), limit+stop+target present, **deterministic signalId** → a retry is **dedup-blocked** (no duplicate order). Unit-tested (`test_bridge_test_stage2.py`).
- Stage 0 dry-run schema check: **ALL PASS** (`stage0-dryrun.json`).
- Duplicate protection: `bridge_sender` marks `pending` before send and only `confirmed` blocks resend; a failed send stays `pending` so the same signalId cannot create a second order. Covered by bridge tests.

## Proof checklist (operator to complete during market hours)
| Item | Status |
|---|---|
| TradersPost account + MFFU Tradovate connected | ⏳ operator confirm |
| Webhook URL exists (env, not in git) | ⏳ operator holds locally |
| Stage 1 ping 2xx + account mapping | ⏳ not run |
| Stage 2 1-MNQ reaches MFFU; stop+target attach | ⏳ not run |
| Stage 3 flatten/cancel; no orphan | ⏳ not run |
| Duplicate webhook blocked (live) | ⏳ verify on Stage 2 retry |

## After Stages 1–3 pass
Create the attestation flag (this is what flips execution toward GREEN):
```
touch evidence/launchlock/traderspost/PROVEN.flag
```

**TRADERSPOST_NOT_READY** until the above is done with eyes on the broker.
