# EXIT3 Paper Parity — Session & Ledger Proof
_2026-06-21 (Sunday) · paper/audit only · live BLOCKED_

## Important: live-feed session deferred (market closed)
It is **Sunday 2026-06-21** — the NQ market is closed and the TradingView CDP feed is **down**. A
live-data paper session (Phases 4–7) therefore **could not run**. Instead, parity was proven
**deterministically through the real `auto_live` paper code path** (`tools/exit3_paper_path_proof.py`),
which is stronger than waiting for a live signal because it forces a known signal through the wiring.

## 1–4. Session / feed / DATA_READY / D1c
- Live-feed session: **not run** (market closed). Command for the Monday session is unchanged:
  `TV_REALTIME_CONFIRMED=1 python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative --feed tradingview-1m --d1c-mode active-eval-filter` (no `--live`, no URL).
- Offline proof used `d1c_mode=SHADOW` so the synthetic signal routes; live eval uses ACTIVE_EVAL_FILTER on the 1m feed.

## 5–6. Signals / paper trades (offline proof)
One synthetic Profile A short (the $1,400 trade) driven through `LiveAuto.on_decision` in paper mode:
```
[auto-live] short 3MNQ EXIT3_FIXED_PARTIAL -> exit3 both legs sent
  sell 2 MNQ  tgt 30421.5  stop 30771.5  role entry_tp2   (core, first)
  sell 1 MNQ  tgt 30538.25 stop 30771.5  role entry_tp1   (scalp, second)
```

## 7–8. TP1/TP2 recorded · two-leg Exit #3 (assertions, all PASS)
- ✅ exactly 2 legs routed · ✅ qtys 1 and 2 (no full 3)
- ✅ shared stop on both legs · ✅ TP2 target = +2R · ✅ TP1 target = +1R
- ✅ distinct deterministic signalIds · ✅ no single full-qty @ 2R payload
- ✅ **NO live send** (dry-run only, live_url=None)

## 9. No synthetic full-qty +2R
✅ None produced. Parity tool confirms live = $1,167 (integer Exit #3) ≠ $1,400 (single-target).

## 10. Dashboard realised vs hypothetical
`trade_results.by_day()` for 06-16: **realised pnl = $0 · hypothetical_pnl = $1,400.** The old synthetic
$1,400 row is re-tagged HYPOTHETICAL; `/api/calendar` (which consumes `by_day`) no longer reports it as
realised. The dashboard's realised June net from that row is now $0.

## 11. Missed-trade concern / AUDITABILITY GAP
**AUDITABILITY GAP: persistent live-engine decision logging is still missing.** Tools referenced by the
brief — `tools/audit_missed_trades.py`, `tools/audit_session_signals.py`, `tools/launch-tv-chrome.sh` —
**do not exist**. D1c decisions ARE logged (`out/ares/d1c_eval_log.csv`) and skips are journalled as
STATE_ASSERT, but there is no single "did the engine run clean / miss nothing" session auditor. This
should be built before a live-feed session is treated as proof.

## 12. Final parity verdict
**Parity PROVEN (deterministic):** dry-run payload ✅ · parity tool ✅ · end-to-end paper-path ✅ ·
ledger realised/hypothetical split ✅ · no live sends ✅ · suite 350 green.
**Outstanding before operator approval:** (a) one live-feed paper session on a market day to observe the
engine on real data; (b) the decision-logging auditor (gap above). Live remains BLOCKED.
