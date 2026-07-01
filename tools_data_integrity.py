"""Data-integrity audit of the real Databento 5m NQ feed used in the backtests. Verifies the 3-month
(and 6-month) window is complete: trading days present vs expected weekdays, bars/day (spot partial/hole
days), and the largest intraday gaps (excluding the daily 17:00-18:00 ET maintenance break + weekends).
Confirms 'real data' is also 'complete data'."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_eod_databento as DB
NY = "America/New_York"


def audit(df, label):
    et = df.index.tz_convert(NY)
    dates = et.normalize()
    present = pd.Series(1, index=et).groupby(dates).count()          # bars per calendar day
    days = present.index
    exp = pd.bdate_range(days.min(), days.max())                    # weekdays in the window
    missing = [d for d in exp if d.normalize() not in set(days)]     # weekdays w/ ZERO bars (holiday or hole)
    med = int(present.median())
    lowdays = present[present < 0.6 * med]                           # partial/hole days (<60% of median)

    # intraday gaps: consecutive-bar deltas, excluding weekends + the 17:00-18:00 ET maintenance break
    d = pd.Series(et, index=range(len(et)))
    gaps = []
    for i in range(1, len(et)):
        dt = (et[i] - et[i - 1]).total_seconds() / 60.0
        if dt <= 6 or dt > 24 * 60:                                 # normal 5m, or weekend -> skip
            continue
        # normal daily maintenance: a ~55-70min gap whose prior bar is ~16:55 ET
        if 50 <= dt <= 75 and et[i - 1].hour == 16:
            continue
        gaps.append((et[i - 1], et[i], dt))
    gaps.sort(key=lambda x: -x[2])

    print(f"\n======== {label} ========")
    print(f"  range           : {days.min().date()} -> {days.max().date()}")
    print(f"  bars total      : {len(df):,}   trading days present : {len(days)}")
    print(f"  weekdays in span: {len(exp)}   -> missing (holiday/hole): {len(missing)}")
    print(f"  bars/day        : median {med}   min {int(present.min())}   max {int(present.max())}")
    if len(missing):
        print(f"  missing weekdays: {', '.join(str(m.date()) for m in missing[:12])}"
              + (" …" if len(missing) > 12 else ""))
    if len(lowdays):
        print(f"  low-bar days (<60% median):")
        for dd, n in lowdays.items():
            print(f"      {dd.date()}  {int(n)} bars")
    else:
        print(f"  low-bar days    : none (no partial/hole sessions)")
    print(f"  intraday gaps >6min (excl. weekend + maintenance): {len(gaps)}")
    for a, b, m in gaps[:6]:
        print(f"      {a.strftime('%Y-%m-%d %H:%M')} -> {b.strftime('%H:%M')}  = {m:.0f} min")


def main():
    print("loading real Databento…", flush=True)
    df = DB.load_databento_5m()
    end = df.index.max()
    audit(df[df.index >= end - pd.Timedelta(days=92)], "LAST 3 MONTHS (the weekly-eval pipeline window)")
    audit(df[df.index >= end - pd.Timedelta(days=183)], "LAST 6 MONTHS (the trade-count window)")
    print("\n  [missing weekdays are almost all CME holidays/early-closes; flag any that aren't.]")


if __name__ == "__main__":
    main()
