"""
STEP 3 -- exit-model battery for the SMC3 exit-model audit.  Entries are
FROZEN (smc3_engine.py default Config, entry logic untouched); only the
exit rule varies across ~34 models (headline 7 + broader battery).  Each
model is replayed SEQUENTIALLY, single-position-at-a-time, over the SAME
frozen entry list -- an entry is skipped if the position from the PREVIOUS
entry (under THIS model's exit) is still open, or if the model's own rule
says "skip this trade" (e.g. no valid DOL).  n differs per model; this is
reported, not hidden.

Writes:
  reports/ifvg_optimisation/10_dol_exit_audit.csv   (one row per model)
  reports/ifvg_optimisation/10_dol_exit_audit.md     (compact, sorted)

Research-only.
"""
from __future__ import annotations
import sys, os, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import load_data  # noqa: E402
from smc3_engine import run_backtest, Config  # noqa: E402
from dol10_levels import DolLevels  # noqa: E402
from dol10_walker import simulate, POINT_VALUE  # noqa: E402
from dol10_pathstats import path_stats_one, _first_touch  # noqa: E402  (read-only reuse)

DATA = "/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet"
REPDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports/ifvg_optimisation")
HORIZON_BARS = 4000
LONG, SHORT = 1, -1


def r_price(entry, risk_pts, k, is_long):
    return entry + k * risk_pts if is_long else entry - k * risk_pts


def build_entries(df, dl, tdf):
    h = df["high"].to_numpy(float); l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    t_open_ns = df.index.view("int64").astype("int64")
    entries = []
    for _, tr in tdf.iterrows():
        entry_idx = int(tr["entry_idx"])
        dir_ = LONG if tr["dir"] == "long" else SHORT
        is_long = dir_ == LONG
        entry = float(tr["entry"]); stop = float(tr["stop"]); risk_pts = float(tr["risk_pts"])
        entry_time_ns = int(tr["entry_time"].value)
        target_2R = float(tr["target"])

        dol_price, dol_type, dol_known, dol_artifact = dl.nearest_causal_dol(entry_idx, entry, entry_time_ns, is_long)
        dol_dist_R = abs(dol_price - entry) / risk_pts if np.isfinite(dol_price) else np.nan

        opp_price, opp_type, opp_known, _ = dl.nearest_causal_dol(entry_idx, entry, entry_time_ns, not is_long)

        sf_price, sf_type, sf_known = dl.session_so_far_dol(entry_idx, entry, is_long)

        src = {}
        for s in ("pdh_pdl", "prior_session", "confirmed_1h", "confirmed_4h", "equal_hl", "htf_pocket"):
            src[s] = dl.source_target(s, entry_idx, entry, entry_time_ns, is_long)[0]

        et = tr["entry_time"].tz_convert("America/New_York")
        ny_am = (et.hour == 9 and et.minute >= 30) or (10 <= et.hour < 12)

        # --- DOL-vs-stop-vs-2R timing (operator hardening item #3) ---
        ps = path_stats_one(h, l, entry_idx, dir_, entry, stop, risk_pts, HORIZON_BARS)
        stop_abs = ps["stop_abs_idx"]
        stop_abs_val = stop_abs if stop_abs is not None else float("inf")
        start = entry_idx + 1; end = min(start + HORIZON_BARS, len(h))
        dol_touch_idx = _first_touch(h, l, dir_, dol_price, start, end) if np.isfinite(dol_price) else None
        r2_touch_idx = _first_touch(h, l, dir_, target_2R, start, end)
        if dol_touch_idx is not None and r2_touch_idx is not None and dol_touch_idx == r2_touch_idx:
            dol_before_2R = dol_dist_R < 2.0
        elif dol_touch_idx is not None:
            dol_before_2R = (r2_touch_idx is None) or (dol_touch_idx < r2_touch_idx)
        else:
            dol_before_2R = False
        r2_before_dol = (r2_touch_idx is not None) and (not dol_before_2R) and (dol_touch_idx is not None or True) \
            if np.isfinite(dol_price) else False
        dol_before_stop = (dol_touch_idx is not None) and (dol_touch_idx < stop_abs_val)
        r2_before_stop = (r2_touch_idx is not None) and (r2_touch_idx < stop_abs_val)
        neither_before_stop = (not dol_before_stop) and (not r2_before_stop)

        entries.append(dict(
            entry_idx=entry_idx, entry_time_ns=entry_time_ns, entry_time=tr["entry_time"],
            dir_=dir_, is_long=is_long, entry=entry, stop=stop, risk_pts=risk_pts,
            target_2R=target_2R, dol_price=dol_price, dol_type=dol_type, dol_dist_R=dol_dist_R,
            opp_price=opp_price, sf_price=sf_price,
            src_pdh_pdl=src["pdh_pdl"], src_prior_session=src["prior_session"],
            src_confirmed_1h=src["confirmed_1h"], src_confirmed_4h=src["confirmed_4h"],
            src_equal_hl=src["equal_hl"], src_htf_pocket=src["htf_pocket"],
            year=int(et.year), dow=et.day_name(), ny_am=bool(ny_am),
            artifact=bool(dol_artifact),
            dol_before_stop=bool(dol_before_stop), dol_before_2R=bool(dol_before_2R),
            r2_before_dol=bool(r2_before_dol), neither_before_stop=bool(neither_before_stop),
        ))
    return entries, h, l, c, t_open_ns


# --------------------------------------------------------------------------- #
# Model spec builders: each returns (legs|None, time_cutoff_idx|None,
# effective_stop_initial|None, skip:bool)
# --------------------------------------------------------------------------- #
def mk_fixed(k):
    def f(e):
        p = r_price(e["entry"], e["risk_pts"], k, e["is_long"])
        return [dict(qty=1.0, price=p, tag=f"{k}R", move_stop_to=None)], None, None, False
    return f


def mk_partial(splits):
    """splits: list of (qty, r_mult, move_to_be_after) sorted ascending r_mult."""
    def f(e):
        legs = []
        for qty, k, be in splits:
            p = r_price(e["entry"], e["risk_pts"], k, e["is_long"])
            legs.append(dict(qty=qty, price=p, tag=f"{k}R", move_stop_to=(e["entry"] if be else None)))
        return legs, None, None, False
    return f


def mk_partial_1r_be_then_dol():
    def f(e):
        if not np.isfinite(e["dol_price"]):
            return None, None, None, True
        legs = [dict(qty=0.5, price=r_price(e["entry"], e["risk_pts"], 1.0, e["is_long"]),
                    tag="1R", move_stop_to=e["entry"]),
               dict(qty=0.5, price=e["dol_price"], tag="DOL", move_stop_to=None)]
        legs.sort(key=lambda x: abs(x["price"] - e["entry"]))
        return legs, None, None, False
    return f


def mk_dol_source(source_key):
    def f(e):
        p = e[source_key]
        if not np.isfinite(p):
            return None, None, None, True
        return [dict(qty=1.0, price=p, tag=source_key, move_stop_to=None)], None, None, False
    return f


def mk_dol_nearest():
    def f(e):
        if not np.isfinite(e["dol_price"]):
            return None, None, None, True
        return [dict(qty=1.0, price=e["dol_price"], tag="DOL", move_stop_to=None)], None, None, False
    return f


def mk_hybrid_tp1_dol(tp1_r):
    def f(e):
        if not np.isfinite(e["dol_price"]):
            return None, None, None, True
        legs = [dict(qty=0.5, price=r_price(e["entry"], e["risk_pts"], tp1_r, e["is_long"]),
                    tag=f"{tp1_r}R", move_stop_to=None),
               dict(qty=0.5, price=e["dol_price"], tag="DOL", move_stop_to=None)]
        legs.sort(key=lambda x: abs(x["price"] - e["entry"]))
        return legs, None, None, False
    return f


def mk_dol_range(lo, hi):
    def f(e):
        d = e["dol_dist_R"]
        if not np.isfinite(d) or d < lo or d > hi:
            return None, None, None, True
        return [dict(qty=1.0, price=e["dol_price"], tag="DOL", move_stop_to=None)], None, None, False
    return f


def mk_dol_min(lo):
    def f(e):
        d = e["dol_dist_R"]
        if not np.isfinite(d) or d < lo:
            return None, None, None, True
        return [dict(qty=1.0, price=e["dol_price"], tag="DOL", move_stop_to=None)], None, None, False
    return f


def mk_dol_max(hi):
    def f(e):
        d = e["dol_dist_R"]
        if not np.isfinite(d) or d > hi:
            return None, None, None, True
        return [dict(qty=1.0, price=e["dol_price"], tag="DOL", move_stop_to=None)], None, None, False
    return f


def mk_dol_capped(cap):
    def f(e):
        d = e["dol_dist_R"]
        if not np.isfinite(d):
            return None, None, None, True
        p = e["dol_price"] if d <= cap else r_price(e["entry"], e["risk_pts"], cap, e["is_long"])
        tag = "DOL" if d <= cap else f"{cap}R_cap"
        return [dict(qty=1.0, price=p, tag=tag, move_stop_to=None)], None, None, False
    return f


def mk_time_cutoff(minutes):
    def f(e):
        p = e["target_2R"]
        cutoff_idx = e["entry_idx"] + minutes
        return [dict(qty=1.0, price=p, tag="2R", move_stop_to=None)], cutoff_idx, None, False
    return f


def _et_cutoff_idx(entry_time, hh, mm, t_open_ns, entry_idx):
    et = entry_time.tz_convert("America/New_York")
    cutoff = et.normalize() + pd.Timedelta(hours=hh, minutes=mm)
    cutoff_ns = int(cutoff.tz_convert("UTC").value)
    if cutoff_ns <= int(entry_time.value):
        return entry_idx + 1
    idx = int(np.searchsorted(t_open_ns, cutoff_ns, side="left"))
    return max(idx, entry_idx + 1)


def mk_session_time_cutoff(hh, mm, t_open_ns):
    def f(e):
        cutoff_idx = _et_cutoff_idx(e["entry_time"], hh, mm, t_open_ns, e["entry_idx"])
        return [dict(qty=1.0, price=e["target_2R"], tag="2R", move_stop_to=None)], cutoff_idx, None, False
    return f


def mk_opposite_dol_sweep():
    def f(e):
        stop = e["stop"]
        if np.isfinite(e["opp_price"]):
            eff = max(stop, e["opp_price"]) if e["is_long"] else min(stop, e["opp_price"])
        else:
            eff = stop
        return [dict(qty=1.0, price=e["target_2R"], tag="2R", move_stop_to=None)], None, eff, False
    return f


def run_model(name, builder, entries, h, l, c, t_open_ns, horizon_bars=HORIZON_BARS,
             cost_mult=1.0, extra_slip=0.0):
    busy_until = -1
    trades = []
    n_skipped_rule = 0
    n_skipped_busy = 0
    for e in entries:
        if e["entry_time_ns"] < busy_until:
            n_skipped_busy += 1
            continue
        legs, time_cutoff_idx, eff_stop, skip = builder(e)
        if skip:
            n_skipped_rule += 1
            continue
        horizon_idx = e["entry_idx"] + horizon_bars
        res = simulate(h, l, c, t_open_ns, e["entry_idx"], e["dir_"], e["entry"], e["stop"],
                      e["risk_pts"], legs, horizon_idx, time_cutoff_idx=time_cutoff_idx,
                      effective_stop_initial=eff_stop, cost_mult=cost_mult, extra_slip_pts=extra_slip)
        trades.append(dict(entry_time=e["entry_time"], year=e["year"], dow=e["dow"], ny_am=e["ny_am"],
                          is_long=e["is_long"], dol_dist_R=e["dol_dist_R"],
                          dol_before_stop=e["dol_before_stop"], dol_before_2R=e["dol_before_2R"],
                          r2_before_dol=e["r2_before_dol"], neither_before_stop=e["neither_before_stop"],
                          **res))
        busy_until = res["exit_time_ns"]
    return trades, n_skipped_rule, n_skipped_busy


def compute_stats(name, trades, n_skipped_rule, n_skipped_busy, n_total_frozen):
    if len(trades) == 0:
        return dict(model=name, n=0)
    df = pd.DataFrame(trades)
    R = df["R"].to_numpy()
    wins = R[R > 0]; losses = R[R < 0]
    n = len(df)
    wr = float((R > 0).mean() * 100)
    gp = wins.sum(); gl = -losses.sum()
    pf = gp / gl if gl > 0 else (np.inf if gp > 0 else np.nan)
    avgR = float(R.mean()); totR = float(R.sum())
    eq = np.cumsum(R); peak = np.maximum.accumulate(eq)
    maxdd = float(-(eq - peak).min()) if len(eq) else 0.0
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0

    yrs = df["year"]
    yr_avg = df.groupby("year")["R"].mean()
    yrs_pos = int((yr_avg > 0).sum())
    n_yrs = int(yr_avg.shape[0])
    ex2024 = df[df.year != 2024]["R"]
    exFri = df[df.dow != "Friday"]["R"]
    exBoth = df[(df.year != 2024) & (df.dow != "Friday")]["R"]
    long_avg = df[df.is_long]["R"].mean() if df.is_long.any() else np.nan
    short_avg = df[~df.is_long]["R"].mean() if (~df.is_long).any() else np.nan
    nyam = df[df.ny_am]["R"]
    nyam_ex24 = df[(df.ny_am) & (df.year != 2024)]["R"]

    have_dol = df["dol_dist_R"].notna()
    dol_pct = float(have_dol.mean() * 100)
    avg_dol_dist = float(df.loc[have_dol, "dol_dist_R"].mean()) if have_dol.any() else np.nan
    d = df.loc[have_dol, "dol_dist_R"]
    buckets = {
        "<0.5R": float((d < 0.5).mean() * 100) if len(d) else np.nan,
        "0.5-1R": float(((d >= 0.5) & (d < 1.0)).mean() * 100) if len(d) else np.nan,
        "1-2R": float(((d >= 1.0) & (d < 2.0)).mean() * 100) if len(d) else np.nan,
        "2-3R": float(((d >= 2.0) & (d < 3.0)).mean() * 100) if len(d) else np.nan,
        ">3R": float((d >= 3.0).mean() * 100) if len(d) else np.nan,
    }
    horizon_to = float(df["horizon_timeout"].mean() * 100)

    pct_dol_before_stop = float(df.loc[have_dol, "dol_before_stop"].mean() * 100) if have_dol.any() else np.nan
    pct_dol_before_2R = float(df.loc[have_dol, "dol_before_2R"].mean() * 100) if have_dol.any() else np.nan
    pct_2R_before_dol = float(df.loc[have_dol, "r2_before_dol"].mean() * 100) if have_dol.any() else np.nan
    pct_neither_before_stop = float(df["neither_before_stop"].mean() * 100)

    return dict(
        model=name, n=n, n_skipped_rule=n_skipped_rule, n_skipped_busy=n_skipped_busy,
        n_frozen=n_total_frozen, wr_pct=wr, pf_R=float(pf) if np.isfinite(pf) else pf,
        avgR=avgR, totR=totR, maxDD_R=maxdd, avg_win_R=avg_win, avg_loss_R=avg_loss,
        yrs_pos=yrs_pos, n_years=n_yrs, avgR_ex2024=float(ex2024.mean()) if len(ex2024) else np.nan,
        avgR_exFri=float(exFri.mean()) if len(exFri) else np.nan,
        avgR_exBoth=float(exBoth.mean()) if len(exBoth) else np.nan,
        long_avgR=float(long_avg), short_avgR=float(short_avg),
        nyam_avgR=float(nyam.mean()) if len(nyam) else np.nan,
        nyam_avgR_ex2024=float(nyam_ex24.mean()) if len(nyam_ex24) else np.nan,
        dol_exists_pct=dol_pct, avg_dol_dist_R=avg_dol_dist,
        dol_bucket_lt0_5=buckets["<0.5R"], dol_bucket_0_5_1=buckets["0.5-1R"],
        dol_bucket_1_2=buckets["1-2R"], dol_bucket_2_3=buckets["2-3R"], dol_bucket_gt3=buckets[">3R"],
        pct_horizon_timeout=horizon_to,
        pct_dol_before_stop=pct_dol_before_stop, pct_dol_before_2R=pct_dol_before_2R,
        pct_2R_before_dol=pct_2R_before_dol, pct_neither_before_stop=pct_neither_before_stop,
        artifact_count=0,
    )


def main():
    t0 = time.time()
    df = load_data(DATA)
    res = run_backtest(df, Config())
    tdf = res.trades
    assert len(tdf) == 5056
    dl = DolLevels(df)
    entries, h, l, c, t_open_ns = build_entries(df, dl, tdf)
    n_total = len(entries)
    print(f"[setup] {n_total} frozen entries, DOL levels built ({time.time()-t0:.1f}s)")

    models = {
        # --- family 1: fixed-R ---
        "fixed_1R": mk_fixed(1.0), "fixed_1.25R": mk_fixed(1.25), "fixed_1.5R": mk_fixed(1.5),
        "fixed_2R_baseline": mk_fixed(2.0), "fixed_2.5R": mk_fixed(2.5), "fixed_3R": mk_fixed(3.0),
        # --- family 2: partials ---
        "partial_50@1R_50@2R": mk_partial([(0.5, 1.0, False), (0.5, 2.0, False)]),
        "partial_50@1R_50@3R": mk_partial([(0.5, 1.0, False), (0.5, 3.0, False)]),
        "partial_33@1R_33@2R_34@3R": mk_partial([(0.33, 1.0, False), (0.33, 2.0, False), (0.34, 3.0, False)]),
        "partial_50@0.75R_50@1.5R": mk_partial([(0.5, 0.75, False), (0.5, 1.5, False)]),
        "partial_50@1R_BE_rest@2R": mk_partial([(0.5, 1.0, True), (0.5, 2.0, False)]),
        "partial_50@1R_BE_rest@DOL": mk_partial_1r_be_then_dol(),
        # --- family 3/4: DOL targets ---
        "dol_nearest_any": mk_dol_nearest(),
        "dol_PDH_PDL_only": mk_dol_source("src_pdh_pdl"),
        "dol_prior_session_only": mk_dol_source("src_prior_session"),
        "dol_confirmed_1H_only": mk_dol_source("src_confirmed_1h"),
        "dol_confirmed_4H_only": mk_dol_source("src_confirmed_4h"),
        "dol_session_so_far_only": mk_dol_source("sf_price"),
        "dol_equal_HL_only": mk_dol_source("src_equal_hl"),
        "dol_htf_pocket_only": mk_dol_source("src_htf_pocket"),
        # --- family 5: hybrids ---
        "hybrid_TP1@1R_TP2@DOL": mk_hybrid_tp1_dol(1.0),
        "hybrid_TP1@0.75R_TP2@DOL": mk_hybrid_tp1_dol(0.75),
        "hybrid_DOL_0.75to3R": mk_dol_range(0.75, 3.0),
        "hybrid_DOL_min1R": mk_dol_min(1.0),
        "hybrid_skip_DOL_lt0.75R": mk_dol_min(0.75),
        "hybrid_skip_DOL_gt3R": mk_dol_max(3.0),
        "hybrid_DOL_capped2R": mk_dol_capped(2.0),
        "hybrid_DOL_capped3R": mk_dol_capped(3.0),
        # --- family 6: time/failure ---
        "time_15min": mk_time_cutoff(15), "time_30min": mk_time_cutoff(30), "time_60min": mk_time_cutoff(60),
        "time_NYAM_end_12:00ET": mk_session_time_cutoff(12, 0, t_open_ns),
        "time_session_close_16:00ET": mk_session_time_cutoff(16, 0, t_open_ns),
        "time_opposite_DOL_swept": mk_opposite_dol_sweep(),
        # --- operator headline-hardening extras (not already present above) ---
        "headline_skip_DOL_lt0.5R": mk_dol_min(0.5),
    }

    rows = []
    for name, builder in models.items():
        trades, n_skip_rule, n_skip_busy = run_model(name, builder, entries, h, l, c, t_open_ns)
        stats = compute_stats(name, trades, n_skip_rule, n_skip_busy, n_total)
        rows.append(stats)
        print(f"  {name:32s} n={stats.get('n',0):5d}  avgR={stats.get('avgR', float('nan')):+.4f}  "
             f"PF={stats.get('pf_R', float('nan')):.3f}" if stats.get("n", 0) else f"  {name:32s} n=0")

    out = pd.DataFrame(rows)
    os.makedirs(REPDIR, exist_ok=True)
    out.to_csv(os.path.join(REPDIR, "10_dol_exit_audit.csv"), index=False)
    print(f"\n[written] {REPDIR}/10_dol_exit_audit.csv  ({time.time()-t0:.1f}s total)")

    return out, entries, h, l, c, t_open_ns, models


if __name__ == "__main__":
    main()
