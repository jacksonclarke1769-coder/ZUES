# TASK: AA — execution telemetry: make the live system measure its own fill quality

ROLE: Sonnet implement (operator-approved scope: telemetry only, zero strategy/order changes)
DE-CERTIFIES: no (observational logging only)

## Problem
Sensitivity analysis says fill quality is the #1 business variable (-0.05R/trade of slippage costs
~18% of funded lifetime value), and the execution dataset is n≈1 confirmed fill (12 live entry-class
sends ever, most unverified phantom-era; 0 FILL_CONFIRMED rows). Execution intelligence cannot be
researched offline — the system must record it as it trades.

## Scope — one new module exec_telemetry.py + wiring, CSV out/exec/exec_telemetry.csv
Per A signal, append ONE row as events occur (fail-safe writes, never blocks the order path):
1. signal_bar_ts, decision_wall_ts (latency: bar close -> decision)
2. webhook_send_wall_ts + http status (bridge latency; from BridgeSender result — wrap, don't modify)
3. expected_entry (the limit price), stop, target, qty
4. fill evidence via read-back: first poll where net matches -> fill_confirm_wall_ts; scrape the
   positions-table avg-price column (readback_tradingview already parses rows — add avg_price field
   read-only) -> actual_fill_px, slippage_pts = (actual - expected) * direction
5. resolution: modeled result vs (when panel readable) realized balance delta per closed day
6. unfilled path: on_missing fired -> row marked MISSED (the adverse-selection counter)
Plus tools_exec_report.py: reads the CSV, prints n, fill rate, mean/median/worst slippage,
latency percentiles, expectancy-attribution estimate vs certified — the weekly operator report.

## Files allowed
exec_telemetry.py (new), tools_exec_report.py (new), auto_live.py (wiring only), 
readback_tradingview.py (ADD avg-price field to the existing row parse — read-only scrape),
tests (new). Forbidden: bridge_traderspost.py order construction, strategy engines, sizing, exits.

## Success criteria
- A paper session produces rows with timestamps + expected prices; unit tests for the CSV writer,
  slippage math (both directions), MISSED path; full suite green; zero new order-path branches
  (telemetry exceptions swallowed loudly).
