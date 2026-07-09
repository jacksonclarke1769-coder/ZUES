"""
Build the day-sequence derived ledger for the SMC3 NY-AM (09:30-12:00 ET) trade
set. Per trade: ET date, day-of-week, dir, R, win, signal# within ET day,
prev-trade result (same day), minutes since prev EXIT / prev ENTRY (same day),
and daily cumulative R BEFORE the trade (sorted by entry_time within day).

Research-only. Writes reports/ifvg_optimisation/09_sequence_ledger.csv
"""
from __future__ import annotations
import sys
import pandas as pd

sys.path.insert(0, "..")
from engine import load_data                       # noqa: E402
from smc3_engine import run_backtest, Config        # noqa: E402

DATA = "/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet"
OUT = "/Users/jacksonclarke/trading-team/backtests/zeus-occ-optimize/smc3/reports/ifvg_optimisation/09_sequence_ledger.csv"


def main():
    df = load_data(DATA)
    t = run_backtest(df, Config(useSession=True, sessStart="09:30", sessEnd="12:00")).trades
    t = t[t.reason.isin(["target", "stop"])].copy()

    # sanity check vs known baseline
    assert len(t) == 1624, f"n mismatch: {len(t)}"

    et_entry = t["entry_time"].dt.tz_convert("America/New_York")
    et_exit = t["exit_time"].dt.tz_convert("America/New_York")

    t["et_date"] = et_entry.dt.date
    t["dow"] = et_entry.dt.day_name()
    t["win"] = t["R"] > 0

    # sort by entry within day (should already be chronological, but enforce)
    t = t.sort_values(["et_date", "entry_time"]).reset_index(drop=True)

    t["signal_num"] = t.groupby("et_date").cumcount() + 1

    t["prev_result"] = t.groupby("et_date")["win"].shift(1)
    t["prev_result"] = t["prev_result"].map({True: "win", False: "loss"})
    t["prev_result"] = t["prev_result"].fillna("none")

    # minutes since prev EXIT (same day) — prev trade's exit_time to this entry_time
    t["_prev_exit_time"] = t.groupby("et_date")["exit_time"].shift(1)
    t["min_since_prev_exit"] = (
        t["entry_time"] - t["_prev_exit_time"]
    ).dt.total_seconds() / 60.0

    # minutes since prev ENTRY (same day)
    t["_prev_entry_time"] = t.groupby("et_date")["entry_time"].shift(1)
    t["min_since_prev_entry"] = (
        t["entry_time"] - t["_prev_entry_time"]
    ).dt.total_seconds() / 60.0

    # daily cumulative R BEFORE this trade
    t["day_cum_R_before"] = t.groupby("et_date")["R"].cumsum() - t["R"]

    cols = [
        "et_date", "dow", "entry_time", "exit_time", "dir", "R", "win",
        "signal_num", "prev_result", "min_since_prev_exit", "min_since_prev_entry",
        "day_cum_R_before", "reason", "hold_min",
    ]
    out = t[cols].copy()
    out.to_csv(OUT, index=False)
    print(f"[written] {OUT}  rows={len(out)}")
    print(out.head(8).to_string())


if __name__ == "__main__":
    main()
