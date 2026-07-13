"""Full overnight->RTH edge search. Reports EVERY config (anti-data-mining).
Families:
  A  Opening-range breakout, direction=break or fade, gated by overnight-range regime. R=OR width.
  B  Overnight high/low break during RTH (ON levels as liquidity). fixed-pt stop.
  C  Gap fade / continuation in first RTH hour.
Gauntlet applied downstream (gauntlet.py) to any config that clears a screening bar.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import on_features as OF
import sim_engine as SE

COST = 0.75
d1 = OF.load_1m()
rth = SE.rth_1m_by_day(d1)
f = pd.read_parquet("research/edge_discovery/_daily_features.parquet")

# precompute OR high/low per day for orm windows
def or_levels(orm):
    out = {}
    for day, g in rth.groupby("date"):
        end = pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=30) + pd.Timedelta(minutes=orm)
        orb = g[g.index < end]
        if len(orb) < orm - 2:
            continue
        out[pd.Timestamp(day)] = (orb["high"].max(), orb["low"].min(), end)
    return out

OR15 = or_levels(15); OR30 = or_levels(30)
ORD = {15: OR15, 30: OR30}


def gate_days(gate):
    if gate == "all":
        return set(f.index)
    if gate == "exp":
        return set(f.index[f["on_rng_ratio"] > 1.2])
    if gate == "comp":
        return set(f.index[f["on_rng_ratio"] < 0.8])


def fam_A(orm, gate, mode, target, cost=COST, entry_delay=0):
    days = gate_days(gate)
    ORl = ORD[orm]
    trades = []
    for day in days:
        day = pd.Timestamp(day)
        if day not in ORl:
            continue
        orh, orl, end = ORl[day]
        width = orh - orl
        if width < 5:
            continue
        force = day + pd.Timedelta(hours=15, minutes=59)
        trig_end = day + pd.Timedelta(hours=10, minutes=30)
        for brk_side, lvl, opp in [(1, orh, orl), (-1, orl, orh)]:
            side = brk_side if mode == "breakout" else -brk_side
            # stop/target relative to entry level (approx; R=width)
            if mode == "breakout":
                stop = opp
                r = width
            else:  # fade: enter at the break level, stop beyond by width, mean-revert
                stop = lvl + brk_side * width  # further in breakout direction
                r = width
            tgt = None; trail = None
            if target == "1R":
                tgt = lvl + side * 1 * r
            elif target == "2R":
                tgt = lvl + side * 2 * r
            elif target == "close":
                tgt = None
            elif target == "trail":
                trail = r
            trades.append(dict(date=day, side=side, entry_level=lvl,
                               trig_start=end, trig_end=trig_end, stop=stop,
                               target=tgt, trail_atr=trail, exit_ts=force,
                               brk=brk_side, tag=f"A_{orm}_{gate}_{mode}_{target}"))
    df = SE.simulate(trades, rth, cost, entry_delay=entry_delay)
    if len(df) == 0:
        return df
    # one trade/day: keep earliest entry (bracket resolves to first breakout)
    df = df.sort_values("ent_ts").groupby("date", as_index=False).first()
    return df


def fam_B(stop_pts, target, cost=COST):
    trades = []
    force_h, force_m = 15, 59
    for day in f.index:
        day = pd.Timestamp(day)
        row = f.loc[day]
        onh, onl = row["on_high"], row["on_low"]
        force = day + pd.Timedelta(hours=force_h, minutes=force_m)
        trig_start = day + pd.Timedelta(hours=9, minutes=30)
        trig_end = day + pd.Timedelta(hours=10, minutes=30)
        for side, lvl in [(1, onh), (-1, onl)]:
            stop = lvl - side * stop_pts
            if target == "1R":
                tgt = lvl + side * stop_pts
            elif target == "2R":
                tgt = lvl + side * 2 * stop_pts
            else:
                tgt = None
            trades.append(dict(date=day, side=side, entry_level=lvl, trig_start=trig_start,
                               trig_end=trig_end, stop=stop, target=tgt, trail_atr=None,
                               exit_ts=force, tag=f"B_{stop_pts}_{target}"))
    df = SE.simulate(trades, rth, cost)
    if len(df) == 0:
        return df
    df = df.sort_values("ent_ts").groupby("date", as_index=False).first()
    return df


def fam_C(gap_thr, mode, stop_pts, target, cost=COST):
    # enter market at 09:35 (after first 5m) if |gap|>thr; fade=trade toward prior close, cont=with gap
    trades = []
    for day in f.index:
        day = pd.Timestamp(day)
        row = f.loc[day]
        if abs(row["gap"]) < gap_thr or row["gap_abs"] > 200:  # roll guard
            continue
        gsign = 1 if row["gap"] > 0 else -1
        side = -gsign if mode == "fade" else gsign
        entry_ts = day + pd.Timedelta(hours=9, minutes=35)
        # emulate market entry: entry_level = a price certain to fill (use open of 09:35 via tiny level)
        # use side-appropriate extreme level so first bar fills
        lvl = row["rth_open"]  # near open; will fill on first bar in window
        force = day + pd.Timedelta(hours=15, minutes=59)
        trig_end = day + pd.Timedelta(hours=9, minutes=40)
        if target == "gapfill":
            tgt = row["prior_rth_close"]
        elif target == "1R":
            tgt = lvl + side * stop_pts
        elif target == "2R":
            tgt = lvl + side * 2 * stop_pts
        else:
            tgt = None
        stop = lvl - side * stop_pts
        trades.append(dict(date=day, side=side, entry_level=lvl, trig_start=entry_ts,
                           trig_end=trig_end, stop=stop, target=tgt, trail_atr=None,
                           exit_ts=force, tag=f"C_{gap_thr}_{mode}_{stop_pts}_{target}"))
    df = SE.simulate(trades, rth, cost)
    return df


def run_all():
    results = []
    dfs = {}
    # Family A grid
    for orm in [15, 30]:
        for gate in ["all", "exp", "comp"]:
            for mode in ["breakout", "fade"]:
                for target in ["1R", "2R", "close", "trail"]:
                    tag = f"A_{orm}_{gate}_{mode}_{target}"
                    df = fam_A(orm, gate, mode, target)
                    dfs[tag] = df
                    s = SE.stats(df); s["tag"] = tag; results.append(s)
    # Family B
    for stop_pts in [20, 40]:
        for target in ["1R", "2R", "close"]:
            tag = f"B_{stop_pts}_{target}"
            df = fam_B(stop_pts, target)
            dfs[tag] = df
            s = SE.stats(df); s["tag"] = tag; results.append(s)
    # Family C
    for gap_thr in [30, 60]:
        for mode in ["fade", "cont"]:
            for target in ["gapfill", "1R", "2R", "close"]:
                tag = f"C_{gap_thr}_{mode}_30_{target}"
                df = fam_C(gap_thr, mode, 30, target)
                dfs[tag] = df
                s = SE.stats(df); s["tag"] = tag; results.append(s)
    R = pd.DataFrame(results)
    return R, dfs


if __name__ == "__main__":
    R, dfs = run_all()
    R = R.sort_values("pf", ascending=False)
    pd.set_option("display.width", 200)
    print(f"TOTAL CONFIGS: {len(R)}")
    print(R[["tag", "n", "pf", "wr", "tot", "avg"]].to_string(index=False))
    import pickle
    with open("research/edge_discovery/_search_dfs.pkl", "wb") as fh:
        pickle.dump(dfs, fh)
    R.to_csv("research/edge_discovery/_search_results.csv", index=False)
    print("\nsaved _search_results.csv + _search_dfs.pkl")
