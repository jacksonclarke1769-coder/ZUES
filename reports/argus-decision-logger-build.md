# ARGUS — Live-Engine Decision Logger + Session Auditor (build)
_2026-06-21 · auditability only · live still BLOCKED · suite 350→365 green_

## 1. Files changed
| File | Change |
|---|---|
| `decision_log.py` | **NEW** — `DecisionLogger`: append-only JSONL, fail-safe, secret-scrubbed, row builders (`no_signal`/`candidate_rejected`/`blocked`/`signal`) |
| `auto_live.py` | wired logger into `LiveAuto` (`logger=`, `_dlog` fail-safe); rows at every branch (reject/data/d1c/ares/exitlock/paper/live); per-bar `no_signal` in `_engine_bar`; session_id in `run()` |
| `tools/audit_live_engine_session.py` | **NEW** — session auditor + missed-trade logic + fixtures |
| `test_argus.py` | **NEW** — 15 tests |

## 2. Log path
`logs/live_engine_decisions/<ET-date>.jsonl` — one JSON object per line, append-only.

## 3. Schema fields (per row)
`schema_version, session_id, timestamp_utc, timestamp_et, account, mode, feed_source, data_state,
data_ready, last_bar_ts, last_bar_age_s, profile, engine_timeframe, bar_ts, candidate_detected,
candidate_id, side, setup_stage, rejection_reason, d1c_mode, d1c_checked, d1c_allowed, d1c_reason,
ares_checked, ares_allowed, ares_reason, exit_model, qty_total, tp1_qty, tp1_target, tp2_qty,
tp2_target, stop_price, entry_price, signal_id_base, webhook_intended, webhook_sent,
traderspost_status, final_action`
`final_action ∈ {no_signal, candidate_rejected, data_blocked, d1c_blocked, ares_blocked,
exitlock_blocked, paper_signal, live_send, skipped, error}`. **No URLs/keys/secrets ever written.**

## 4. Auditor command
```
python3 tools/audit_live_engine_session.py --date YYYY-MM-DD --session ny-am
python3 tools/audit_live_engine_session.py --date today
```
Verdicts: `SESSION CLEAN — NO SETUP | CLEAN — TRADE TAKEN | BLOCKED BY DATA | INCONCLUSIVE — LOGGING GAP | FAIL — POSSIBLE MISSED TRADE`. Writes `reports/live-engine-decision-audit-<date>.md` (20-point report).

## 5. No-signal proof
Fixture `no_signal` → 24 rows → **SESSION CLEAN — NO SETUP**. A zero-trade session is now provable.

## 6. Blocked/rejected proof
Logger writes distinct rows for candidate_rejected / data_blocked / d1c_blocked / ares_blocked /
exitlock_blocked (each tested). The live `on_decision` emits these at every gate.

## 7. Exit #3 fields included
Every row carries `exit_model=EXIT3_FIXED_PARTIAL`; signal rows carry `tp1_qty/tp1_target/tp2_qty/
tp2_target/stop_price` — the auditor sees the aligned model.

## 8. Tests added
15 (`test_argus.py`): each row type, valid JSON, secret redaction, **logger-failure-cannot-raise**,
**engine-send-path-unaffected-by-logger-error**, auditor CLEAN/INCONCLUSIVE/no-rows verdicts, feed-issue
detection, no-URL-in-report.

## 9. Test result
`test_argus.py` 15/15 · **full suite 365 passed, 0 failed.**

## 10. Live status — **BLOCKED.** `exit-model-approved.flag` absent (not created).

## 11. Monday paper-session command
```bash
cd ~/trading-team/bot/nq-liq-bot
export TV_REALTIME_CONFIRMED=1
python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative \
  --feed tradingview-1m --d1c-mode active-eval-filter         # no --live, no URL, no flag
```
After the session:
```bash
python3 tools/audit_live_engine_session.py --date today --session ny-am
python3 tools/check_exit3_parity.py
```
A clean session = `SESSION CLEAN — NO SETUP` (or `TRADE TAKEN` with two-leg Exit #3 P&L) + parity PASS.
