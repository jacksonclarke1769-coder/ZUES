"""
SMC3 Stage-2 Task B — trade classification (causal, entry-time).

On the BASELINE trades (default Config), bucket by causal entry-time context and
report per bucket: n, WR, **avg R, total R** (R is the headline; $ secondary).

Every feature is known AT/BEFORE the entry bar's close (causal):
  - session (ET) / et_hour / day-of-week      : from the entry timestamp
  - direction (long/short)                    : the trade itself
  - stop-width bucket (risk_pts)              : chosen at entry (tight<20/mid/wide>60)
  - HTF-trend alignment (60m EMA50, daily EMA20): last HTF bar CLOSED <= entry
  - sweep magnitude (pts beyond swept level)  : engine-recorded at fire
  - 5m-confirm type (BOS/FVG/both)            : engine-recorded at latch
  - ATR percentile (5m ATR14 vs trailing 500) : last 5m bar closed <= entry

THE KEY MEASUREMENT: does WR / avg R vary MATERIALLY across any causal bucket, or
is it pinned near 33-37% everywhere?  We quantify the WR-spread and avgR-spread
(max-min across buckets with n>=100) per feature.  Any bucket with a real, causal,
IS+OOS-stable positive-R gradient is flagged as a filter candidate w/ before/after.

Appends the Task-B tables to STAGE2.md.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from smc3_engine import Config, run_backtest
from engine import resample_ohlc, wilder_atr, ema_series

DATA = "/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet"
OUT = "/Users/jacksonclarke/trading-team/backtests/zeus-occ-optimize/smc3/STAGE2.md"

IS_YEARS = (2021, 2022, 2023, 2024)
OOS_YEARS = (2025, 2026)
MIN_N = 100   # distrust sub-buckets below this


def et_session(hour: int) -> str:
    # SMC session split (ET); the 16:00-18:00 gap = "Break"
    if hour >= 18 or hour < 2:  return "Asia"
    if 2 <= hour < 8:           return "London"
    if 8 <= hour < 12:          return "NY-AM"
    if 12 <= hour < 16:         return "NY-PM"
    return "Break"


DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# --------------------------------------------------------------------------- #
def build_features(tdf: pd.DataFrame, df1m: pd.DataFrame) -> pd.DataFrame:
    f = tdf.copy().reset_index(drop=True)
    entry_ns = f["entry_time"].values.astype("datetime64[ns]").astype("int64")
    et = f["entry_time"].dt.tz_convert("America/New_York")
    hours = et.dt.hour.to_numpy()
    f["et_hour"] = hours
    f["session"] = [et_session(int(h)) for h in hours]
    f["dow"] = [DOW[d] for d in et.dt.dayofweek.to_numpy()]
    f["risk_pts"] = f["risk_pts"].astype(float)

    # --- 60m EMA50 trend side (causal: last 60m bar closed <= entry) ---
    h60 = resample_ohlc(df1m, 60)
    H_close_ns = np.asarray(h60.index.view("int64"), dtype="int64") + np.int64(60) * 60 * 1_000_000_000
    H_close = h60["close"].to_numpy(float)
    H_ema50 = ema_series(H_close, 50)
    j60 = np.searchsorted(H_close_ns, entry_ns, side="right") - 1
    h_side = np.where(j60 >= 0, np.sign(H_close[np.clip(j60, 0, None)] - H_ema50[np.clip(j60, 0, None)]), 0)

    # --- daily EMA20 trend side (causal: prior completed ET day) ---
    et_idx = df1m.index.tz_convert("America/New_York")
    et_date = pd.Series(et_idx.date, index=df1m.index)
    dgrp = df1m.groupby(et_date)
    daily = pd.DataFrame({"close": dgrp["close"].last()})
    daily.index = pd.to_datetime([str(d) for d in daily.index])
    D_close = daily["close"].to_numpy(float)
    D_ema20 = ema_series(D_close, 20)
    day_close_utc = pd.to_datetime(daily.index).tz_localize("America/New_York").tz_convert("UTC")
    D_close_ns = day_close_utc.view("int64") + np.int64(24) * 3600 * 1_000_000_000  # next-day 00:00 ET
    jd = np.searchsorted(D_close_ns, entry_ns, side="right") - 1
    d_side = np.where(jd >= 0, np.sign(D_close[np.clip(jd, 0, None)] - D_ema20[np.clip(jd, 0, None)]), 0)

    # trade direction as +1 long / -1 short
    dir_sign = np.where(f["dir"].to_numpy() == "long", 1.0, -1.0)
    # align = +1 if trade dir agrees with HTF trend side, -1 if counter, 0 if flat
    f["htf60_align"] = np.where(h_side == 0, "flat",
                        np.where(dir_sign == h_side, "with-60m", "counter-60m"))
    f["daily_align"] = np.where(d_side == 0, "flat",
                        np.where(dir_sign == d_side, "with-daily", "counter-daily"))

    # --- 5m ATR(14) percentile vs trailing 500 completed 5m bars (causal) ---
    c5 = resample_ohlc(df1m, 5)
    C5_close_ns = np.asarray(c5.index.view("int64"), dtype="int64") + np.int64(5) * 60 * 1_000_000_000
    A5 = wilder_atr(c5["high"].to_numpy(float), c5["low"].to_numpy(float),
                    c5["close"].to_numpy(float), 14)
    j5 = np.searchsorted(C5_close_ns, entry_ns, side="right") - 1
    atr_pctile = np.full(len(f), np.nan)
    W = 500
    for t in range(len(f)):
        j = int(j5[t])
        if j < 20:
            continue
        lo = max(0, j - W + 1)
        win = A5[lo:j + 1]
        win = win[np.isfinite(win)]
        cur = A5[j]
        if len(win) >= 30 and np.isfinite(cur):
            atr_pctile[t] = (win < cur).mean() * 100
    f["atr_pctile"] = atr_pctile

    # --- categorical buckets ---
    f["risk_bucket"] = pd.cut(f["risk_pts"], bins=[-np.inf, 20, 60, np.inf],
                              labels=["tight<20", "mid20-60", "wide>60"])
    # sweep magnitude tertiles on IS
    ism = f[f["exit_time"].dt.year.isin(IS_YEARS)]["sweep_mag"]
    q1, q2 = np.nanpercentile(ism, [33.33, 66.67])
    f["sweep_bucket"] = pd.cut(f["sweep_mag"], bins=[-np.inf, q1, q2, np.inf],
                               labels=[f"sm<{q1:.1f}", f"sm{q1:.1f}-{q2:.1f}", f"sm>{q2:.1f}"])
    # atr percentile buckets
    f["atr_bucket"] = pd.cut(f["atr_pctile"], bins=[-np.inf, 33.33, 66.67, np.inf],
                             labels=["atr-lo", "atr-mid", "atr-hi"])
    f["hour_band"] = pd.cut(f["et_hour"], bins=[-1, 2, 8, 12, 16, 24],
                            labels=["0-2", "2-8", "8-12", "12-16", "16-24"])
    return f


# --------------------------------------------------------------------------- #
def bucket_table(f: pd.DataFrame, col, order=None):
    """Per-bucket n / WR / avgR / totR, plus IS & OOS avgR/totR."""
    rows = []
    vals = order if order is not None else [v for v in f[col].dropna().unique()]
    for v in vals:
        sub = f[f[col] == v]
        if len(sub) == 0:
            continue
        R = sub["R"].to_numpy(); d = sub["net_dollars"].to_numpy()
        iss = sub[sub["exit_time"].dt.year.isin(IS_YEARS)]
        oos = sub[sub["exit_time"].dt.year.isin(OOS_YEARS)]
        rows.append({
            "bucket": str(v), "n": len(sub),
            "wr": (d > 0).mean() * 100,
            "avgR": R.mean(), "totR": R.sum(),
            "is_n": len(iss), "is_avgR": iss["R"].mean() if len(iss) else np.nan,
            "is_totR": iss["R"].sum() if len(iss) else 0.0,
            "oos_n": len(oos), "oos_avgR": oos["R"].mean() if len(oos) else np.nan,
            "oos_totR": oos["R"].sum() if len(oos) else 0.0,
        })
    return pd.DataFrame(rows)


def spread(tbl: pd.DataFrame):
    """WR-spread and avgR-spread across buckets with n>=MIN_N."""
    t = tbl[tbl["n"] >= MIN_N]
    if len(t) < 2:
        return np.nan, np.nan, t
    return (t["wr"].max() - t["wr"].min()), (t["avgR"].max() - t["avgR"].min()), t


def render_bucket(name, tbl, L):
    P = L.append
    wr_s, r_s, big = spread(tbl)
    P(f"### {name}   (WR-spread {wr_s:.1f}pp, avgR-spread {r_s:+.4f}R across n>={MIN_N} buckets)\n"
      if not np.isnan(wr_s) else f"### {name}\n")
    P("| bucket | n | WR% | avgR | totR | IS n | IS avgR | IS totR | OOS n | OOS avgR | OOS totR |")
    P("|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in tbl.iterrows():
        flag = "" if r["n"] >= MIN_N else " *"
        P(f"| {r['bucket']}{flag} | {r['n']} | {r['wr']:.1f} | {r['avgR']:+.4f} | {r['totR']:+.1f} | "
          f"{r['is_n']} | {r['is_avgR']:+.4f} | {r['is_totR']:+.1f} | "
          f"{r['oos_n']} | {r['oos_avgR']:+.4f} | {r['oos_totR']:+.1f} |")
    P("\n_`*` = n < 100 (distrust)._\n")
    return wr_s, r_s


def main():
    df = pd.read_parquet(DATA)
    r = run_backtest(df, Config())
    tdf = r.trades
    f = build_features(tdf, df)

    L = []
    P = L.append
    P("\n\n---\n")
    P("## Task B — trade classification (causal, entry-time) on baseline trades\n")
    P(f"Baseline: n={len(f)}, WR {(f['net_dollars']>0).mean()*100:.1f}%, "
      f"total R {f['R'].sum():+.1f}, avg R {f['R'].mean():+.4f}.  "
      "R = net$/(risk_pts*$20) per trade (risk-normalized).  All features causal "
      "(known at/before entry-bar close).  `*` = n<100.\n")

    features = [
        ("By session (ET)", "session", ["Asia", "London", "NY-AM", "NY-PM", "Break"]),
        ("By ET hour-band", "hour_band", ["0-2", "2-8", "8-12", "12-16", "16-24"]),
        ("By direction", "dir", ["long", "short"]),
        ("By stop-width (risk pts)", "risk_bucket", ["tight<20", "mid20-60", "wide>60"]),
        ("By 60m EMA50 alignment", "htf60_align", ["with-60m", "counter-60m", "flat"]),
        ("By daily EMA20 alignment", "daily_align", ["with-daily", "counter-daily", "flat"]),
        ("By sweep magnitude", "sweep_bucket", None),
        ("By 5m-confirm type", "confirm_type", ["BOS", "FVG", "both"]),
        ("By ATR percentile (5m)", "atr_bucket", ["atr-lo", "atr-mid", "atr-hi"]),
        ("By day-of-week", "dow", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sun"]),
    ]

    spreads = []
    print(f"\nBaseline n={len(f)} WR {(f['net_dollars']>0).mean()*100:.1f}% "
          f"totR {f['R'].sum():+.1f} avgR {f['R'].mean():+.4f}\n")
    for title, col, order in features:
        tbl = bucket_table(f, col, order)
        wr_s, r_s = render_bucket(title, tbl, L)
        spreads.append((title, wr_s, r_s, tbl))
        print(f"{title:32s} WRspread {wr_s if np.isnan(wr_s) else round(wr_s,1)}pp  "
              f"avgRspread {r_s if np.isnan(r_s) else round(r_s,4)}R")
        # console per-bucket
        for _, rr in tbl.iterrows():
            tag = "" if rr["n"] >= MIN_N else "*"
            print(f"    {rr['bucket']:14s}{tag:1s} n={rr['n']:5d} WR={rr['wr']:.1f} "
                  f"avgR={rr['avgR']:+.4f} IS={rr['is_avgR']:+.4f}(n{rr['is_n']}) "
                  f"OOS={rr['oos_avgR']:+.4f}(n{rr['oos_n']})")

    # ---- filter-candidate scan: bucket with IS>0 AND OOS>0 avgR, both n>=MIN_N ----
    P("## Task B — filter-candidate scan (IS>0 AND OOS>0 avg R, both n>=100)\n")
    cands = []
    for title, col, order in features:
        tbl = bucket_table(f, col, order)
        for _, rr in tbl.iterrows():
            if (rr["is_n"] >= MIN_N and rr["oos_n"] >= MIN_N
                    and rr["is_avgR"] > 0 and rr["oos_avgR"] > 0):
                cands.append((title, rr))
    if cands:
        P("| feature | bucket | IS n | IS avgR | OOS n | OOS avgR | overall avgR | overall totR |")
        P("|---|---|---|---|---|---|---|---|")
        for title, rr in cands:
            P(f"| {title} | {rr['bucket']} | {rr['is_n']} | {rr['is_avgR']:+.4f} | "
              f"{rr['oos_n']} | {rr['oos_avgR']:+.4f} | {rr['avgR']:+.4f} | {rr['totR']:+.1f} |")
        P("")
        # before/after for each candidate (keep-bucket vs baseline)
        P("**Before/after (keep only the bucket vs full baseline):**\n")
        P("| filter | baseline avgR | baseline totR | kept n | kept avgR | kept totR | kept IS avgR | kept OOS avgR |")
        P("|---|---|---|---|---|---|---|---|")
        base_avgR = f["R"].mean(); base_totR = f["R"].sum()
        for title, rr in cands:
            P(f"| keep {rr['bucket']} | {base_avgR:+.4f} | {base_totR:+.1f} | {rr['n']} | "
              f"{rr['avgR']:+.4f} | {rr['totR']:+.1f} | {rr['is_avgR']:+.4f} | {rr['oos_avgR']:+.4f} |")
        P("")
    else:
        P("**No causal bucket has positive avg R in BOTH IS and OOS at n>=100.** "
          "There is no IS+OOS-stable positive-R filter candidate.\n")

    # ---- spread summary ----
    P("## Task B — spread summary (does outcome depend on context?)\n")
    P("| feature | WR-spread (pp) | avgR-spread (R) |")
    P("|---|---|---|")
    for title, wr_s, r_s, _ in spreads:
        P(f"| {title} | {'-' if np.isnan(wr_s) else f'{wr_s:.1f}'} | "
          f"{'-' if np.isnan(r_s) else f'{r_s:+.4f}'} |")
    P("")

    with open(OUT, "a") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n[appended Task B to]", OUT)
    print("\nFilter candidates (IS>0 & OOS>0, n>=100 both):", len(cands))
    for title, rr in cands:
        print(f"  {title} :: {rr['bucket']}  IS {rr['is_avgR']:+.4f}(n{rr['is_n']})  "
              f"OOS {rr['oos_avgR']:+.4f}(n{rr['oos_n']})  overall totR {rr['totR']:+.1f}")


if __name__ == "__main__":
    main()
