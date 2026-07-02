"""tools_exec_report.py — operator fill-quality report from exec_telemetry.csv.

Usage:
    python3 tools_exec_report.py [--csv PATH]

Prints:
  * n trades, fill rate, MISSED/CANCELLED counts
  * slippage: mean / median / worst (pts and R)
  * latency percentiles per stage (bar→decision, decision→webhook, webhook→fill)
  * expectancy-attribution estimate vs certified (sensitivity: -0.05R/trade of slippage)

Degrades gracefully: prints a clear message when n == 0 or the CSV doesn't exist.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Optional


CSV_PATH = "out/exec/exec_telemetry.csv"
# Certified expectancy per-trade (from reports/apex_validation.json — Profile A)
_CERTIFIED_E_R = 0.11          # baseline certified expectancy (R per trade)
_SLIPPAGE_R_PER_POINT = None   # not used; slippage_R is already in R units


def _pct(vals: list[float], p: int) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    i = max(0, min(len(s) - 1, int(len(s) * p / 100)))
    return round(s[i], 3)


def _mean(vals: list[float]) -> Optional[float]:
    if not vals:
        return None
    return round(sum(vals) / len(vals), 3)


def _median(vals: list[float]) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    if n % 2 == 0:
        return round((s[n // 2 - 1] + s[n // 2]) / 2, 3)
    return round(s[n // 2], 3)


def _worst(vals: list[float], high_is_bad: bool = True) -> Optional[float]:
    if not vals:
        return None
    return round(max(vals) if high_is_bad else min(vals), 3)


def _load(csv_path: str) -> list[dict]:
    if not os.path.exists(csv_path):
        return []
    rows = []
    try:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)
    except Exception as e:
        print(f"[exec-report] ⚠ could not read {csv_path}: {e!r}")
    return rows


def _float(v) -> Optional[float]:
    try:
        return float(v) if v not in (None, "", "None") else None
    except (ValueError, TypeError):
        return None


def main(csv_path: str = CSV_PATH) -> None:
    rows = _load(csv_path)

    print(f"\n{'='*62}")
    print(f"  ZEUS EXECUTION TELEMETRY REPORT")
    print(f"  Source: {csv_path}")
    print(f"{'='*62}")

    if not rows:
        print("  ⚠  No data yet — CSV is empty or doesn't exist.")
        print("  Run a paper/live session to collect execution data.")
        print(f"{'='*62}\n")
        return

    n_total = len(rows)
    filled = [r for r in rows if r.get("resolution") == "FILLED"]
    missed = [r for r in rows if r.get("resolution") == "MISSED"]
    cancelled = [r for r in rows if r.get("resolution") == "CANCELLED"]
    pending = [r for r in rows if r.get("resolution") == "PENDING"]

    n_filled = len(filled)
    n_missed = len(missed)
    n_cancelled = len(cancelled)
    n_pending = len(pending)
    fill_rate = round(n_filled / n_total * 100, 1) if n_total > 0 else 0.0

    print(f"\n  SIGNAL COUNTS")
    print(f"  {'Total signals:':30s} {n_total}")
    print(f"  {'Filled:':30s} {n_filled}  ({fill_rate}%)")
    print(f"  {'Missed (unfilled limit):':30s} {n_missed}")
    print(f"  {'Cancelled:':30s} {n_cancelled}")
    if n_pending:
        print(f"  {'Still pending (in-flight):':30s} {n_pending}")

    # slippage from filled rows with panel-readable avg_price
    slip_rows = [r for r in filled if _float(r.get("slippage_pts")) is not None]
    slip_pts = [_float(r["slippage_pts"]) for r in slip_rows]
    slip_r = [_float(r.get("slippage_R")) for r in slip_rows if _float(r.get("slippage_R")) is not None]

    print(f"\n  SLIPPAGE  (n={len(slip_pts)} panel-readable fills)")
    if slip_pts:
        print(f"  {'Mean slippage pts:':30s} {_mean(slip_pts)}")
        print(f"  {'Median slippage pts:':30s} {_median(slip_pts)}")
        print(f"  {'Worst slippage pts:':30s} {_worst(slip_pts)}")
        if slip_r:
            print(f"  {'Mean slippage R:':30s} {_mean(slip_r)}")
            print(f"  {'Median slippage R:':30s} {_median(slip_r)}")
            print(f"  {'Worst slippage R:':30s} {_worst(slip_r)}")
    else:
        print("  No panel-readable fills yet (avg_price column not read).")

    # latency — bar → decision
    b2d = [_float(r.get("bar_to_decision_ms")) for r in rows if _float(r.get("bar_to_decision_ms")) is not None]
    d2w = [_float(r.get("decision_to_webhook_ms")) for r in rows if _float(r.get("decision_to_webhook_ms")) is not None]
    w2f = [_float(r.get("webhook_to_fill_ms")) for r in filled if _float(r.get("webhook_to_fill_ms")) is not None]

    def _lat_block(label: str, vals: list[float]) -> None:
        if not vals:
            print(f"  {label}: no data")
            return
        print(f"  {label} (n={len(vals)}):  "
              f"p50={_pct(vals,50)}ms  p90={_pct(vals,90)}ms  p99={_pct(vals,99)}ms  "
              f"worst={_worst(vals)}ms")

    print(f"\n  LATENCY PERCENTILES")
    _lat_block("bar_close → decision  ", b2d)
    _lat_block("decision → webhook    ", d2w)
    _lat_block("webhook → fill confirm", w2f)

    # expectancy attribution
    print(f"\n  EXPECTANCY ATTRIBUTION")
    print(f"  Certified baseline: {_CERTIFIED_E_R:+.4f} R/trade  (reports/apex_validation.json)")
    if slip_r and n_filled >= 5:
        mean_slip = _mean(slip_r) or 0.0
        adj_e = _CERTIFIED_E_R - mean_slip
        print(f"  Mean slippage:      {mean_slip:+.4f} R/trade")
        print(f"  Adjusted expectancy:{adj_e:+.4f} R/trade")
        pct_erosion = abs(mean_slip / _CERTIFIED_E_R * 100) if _CERTIFIED_E_R else 0.0
        print(f"  Erosion:            {pct_erosion:.1f}% of certified edge  "
              f"({'⚠ MATERIAL' if pct_erosion > 20 else 'OK'})")
        # annualised impact (Profile A ≈ 3 signals/week, 50 weeks)
        annual_trades = n_filled / max(1, n_total) * 150   # modeled A trades/year
        annual_impact = mean_slip * annual_trades * 5.0    # $5/pt MNQ × mean qty ≈ rough $
        print(f"  ≈ annualised impact: ${annual_impact:,.0f}  (rough; assumes 150 A-signals/yr, $5/pt/ct)")
    else:
        print(f"  ⚠  Need ≥ 5 panel-readable fills for attribution  (have {len(slip_r)}).")

    print(f"\n{'='*62}\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="ZEUS execution fill quality report")
    p.add_argument("--csv", default=CSV_PATH, help=f"path to telemetry CSV (default: {CSV_PATH})")
    a = p.parse_args()
    main(a.csv)
    sys.exit(0)
