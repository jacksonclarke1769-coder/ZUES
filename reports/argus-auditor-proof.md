# ARGUS — Auditor Proof (deterministic, market-closed)
_2026-06-21 · `tools/audit_live_engine_session.py` fixtures_

The market is closed, so the auditor was proven against deterministic fixtures written directly to
the decision log, then read back and classified.

## Fixture 1 — `no_signal` (a clean zero-trade session)
24 in-window `no_signal` rows (GREEN, data_ready), no candidates, no sends.
```
python3 tools/audit_live_engine_session.py --date 2026-06-22 --fixture no_signal
rows=24 corrupt=0 sends=0 blocked=0 no_signal=24
SESSION CLEAN — NO SETUP   ✅
```
Proves: a no-trade day is **provably clean** when the engine logged every bar.

## Fixture 2 — `missing_rows` (a logging gap)
One `no_signal` row + one unresolved candidate (`final_action=skipped`, no gate outcome) + one
corrupt JSONL line.
```
python3 tools/audit_live_engine_session.py --date 2026-06-22 --fixture missing_rows
! 1 candidate row(s) with no resolved final_action
! 1 corrupt/invalid JSONL line(s)
SESSION INCONCLUSIVE — LOGGING GAP   ✅
```
Proves: an incomplete/corrupt log is **never** reported as clean — it is flagged INCONCLUSIVE.

## Missed-trade logic (Phase 6) — verdict drivers
| Condition | Verdict |
|---|---|
| no rows / corrupt JSONL / unresolved candidate | INCONCLUSIVE — LOGGING GAP |
| live_send with no traderspost_status | FAIL — POSSIBLE MISSED TRADE |
| any paper/live signal, complete | CLEAN — TRADE TAKEN |
| data_blocked dominates the window | BLOCKED BY DATA |
| rows present, all no_signal/blocked, no gaps | CLEAN — NO SETUP |

Auditor never prints webhook URLs/secrets (tested). Report → `reports/live-engine-decision-audit-<date>.md`.
