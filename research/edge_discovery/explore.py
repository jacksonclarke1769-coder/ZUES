"""Exploratory (no trades yet): do overnight features carry ANY predictive structure into RTH?
Pure correlations/conditional means so we don't build a sim on nothing."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import on_features as OF

d1 = OF.load_1m()
f = pd.read_parquet("research/edge_discovery/_daily_features.parquet")

# Build first-hour RTH stats per day (09:30-10:30) and full-RTH range
t = d1.index
rth = d1[((t.hour > 9) | ((t.hour == 9) & (t.minute >= 30))) & (t.hour < 16)].copy()
rth["date"] = rth.index.normalize()

recs = []
for day, g in rth.groupby("date"):
    o = g["open"].iloc[0]
    h1 = g[g.index < (pd.Timestamp(day) + pd.Timedelta(hours=10, minutes=30))]
    if len(h1) < 10:
        continue
    recs.append(dict(date=pd.Timestamp(day),
                     fh_high=h1["high"].max(), fh_low=h1["low"].min(),
                     fh_range=h1["high"].max() - h1["low"].min(),
                     fh_ret=h1["close"].iloc[-1] - o,
                     full_range=g["high"].max() - g["low"].min(),
                     full_ret=g["close"].iloc[-1] - o))
r = pd.DataFrame(recs).set_index("date")
df = f.join(r, how="inner")
print("joined rows", len(df))

# roll guard: drop gap outliers (|gap|>200 ~ roll) for gap analysis
df["is_roll"] = df["gap_abs"] > 200
print("likely roll/outlier days (|gap|>200):", df["is_roll"].sum())

print("\n=== H1: ON range ratio -> RTH first-hour range ===")
print("corr(on_rng, fh_range):", round(df["on_rng"].corr(df["fh_range"]), 3))
print("corr(on_rng_ratio, fh_range):", round(df["on_rng_ratio"].corr(df["fh_range"]), 3))
# quintiles of on_rng_ratio -> mean fh_range
df["q_onr"] = pd.qcut(df["on_rng_ratio"].rank(method="first"), 5, labels=False)
print(df.groupby("q_onr")[["on_rng_ratio", "fh_range", "full_range"]].mean().round(1).to_string())

print("\n=== H2: gap -> first-hour direction (fill vs continue), roll-guarded ===")
g = df[~df["is_roll"]].copy()
g["gap_bucket"] = pd.cut(g["gap"], [-1e9, -40, -15, 15, 40, 1e9],
                         labels=["gapdn>40", "gapdn15-40", "flat", "gapup15-40", "gapup>40"])
# fill = move back toward prior close (opposite sign of gap). continuation = same sign.
# fh_ret sign vs gap sign:
gb = g.groupby("gap_bucket").agg(n=("fh_ret", "size"),
                                  mean_fh_ret=("fh_ret", "mean"),
                                  median_fh_ret=("fh_ret", "median"),
                                  frac_up=("fh_ret", lambda x: (x > 0).mean()))
print(gb.round(3).to_string())

print("\n=== H3: open position vs ON range -> first-hour direction ===")
df["q_pos"] = pd.qcut(df["open_pos"], 5, labels=False, duplicates="drop")
print(df.groupby("q_pos").agg(n=("fh_ret", "size"),
                               open_pos=("open_pos", "mean"),
                               mean_fh_ret=("fh_ret", "mean"),
                               frac_up=("fh_ret", lambda x: (x > 0).mean())).round(3).to_string())

print("\n=== H3b: open ABOVE ON high or BELOW ON low (breakout at open) ===")
df["above_onh"] = df["rth_open"] > df["on_high"]
df["below_onl"] = df["rth_open"] < df["on_low"]
for lab, m in [("open>ONH", df["above_onh"]), ("open<ONL", df["below_onl"]),
               ("inside", ~df["above_onh"] & ~df["below_onl"])]:
    s = df[m]
    print(f"  {lab:10s} n={len(s):4d} mean_fh_ret={s['fh_ret'].mean():7.2f} frac_up={(s['fh_ret']>0).mean():.3f}")

df.to_parquet("research/edge_discovery/_joined.parquet")
print("\nsaved _joined.parquet")
