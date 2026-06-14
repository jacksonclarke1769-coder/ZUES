# LAUNCHLOCK — TradersPost Test Stage Log

| Stage | Description | Status | Evidence | Run by |
|---|---|---|---|---|
| 0 | Dry-run payload build + field validation (no send) | ✅ PASS | `stage0-dryrun.json` | Claude, 2026-06-14 |
| 1 | Test webhook (`bridge_test.py --ping`) to TradersPost test strategy | ⏳ PENDING | `stage1-ping.txt` | Operator (local URL) |
| 2 | One 1-MNQ live/test bracket; confirm stop+target attach, no dup | ⏳ PENDING | `stage2-1mnq.txt` | Operator (local URL) |
| 3 | Cancel / flatten; confirm working orders cancel + dashboard updates | ⏳ PENDING | `stage3-flatten.txt` | Operator |

**Rule:** no full-size trade until Stages 1–3 all PASS. Stage 0 proves only that the bridge
builds a schema-correct, dedup-protected payload — it does **not** prove transmission or execution.

## Stage 0 result (2026-06-14)
All required fields present: ticker(MNQ), action(buy), quantity(1), price, stopLoss.stopPrice,
takeProfit.limitPrice, signalId. Dry-run send returned `sent=False` (no webhook by design).
