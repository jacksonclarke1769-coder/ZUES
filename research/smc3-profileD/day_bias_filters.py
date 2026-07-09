"""
11 -- DAILY-BIAS research pass on the FROZEN SMC3 entries (full baseline,
n=5056, default Config() over NQ_databento_1m_5y.parquet).  Entries are
UNTOUCHED; only a CAUSAL daily-bias ACCEPT/BLOCK filter is applied on top,
isolated per rule, replayed on fixed-2R exits (matching the frozen baseline)
except for the one explicitly-flagged row in family 4 that changes the exit
to "target the DOL" for comparison purposes only.

Research-only.  Reads (does not modify):
  - smc3_engine.py (Config/run_backtest) -- NOT rerun; we reuse the exact
    per-trade ledger already materialised in 10_path_stats.csv (entry_idx,
    entry price, dir, R_baseline, touch_2_0 = reached +2R before stop,
    dol nearest-target fields) so results are guaranteed consistent with the
    STEP1/STEP2/STEP3 audit trail already on disk.
  - dol10_levels.py (DolLevels) -- for the causal PDH/PDL/ONH/ONL level
    arrays (not the trade-level nearest-DOL fields, which come pre-computed
    from 10_path_stats.csv).
  - dol10_walker.py (simulate) + dol10_battery.py's `dol_nearest_any`
    methodology -- reused verbatim for the ONE row that changes the exit.

Causality conventions (documented per the operator's causality contract):
  * "today" for sweep-state features (PDH/PDL, ONH/ONL, first-drive,
    first-30m-fail) = the ET CALENDAR DATE of the entry bar (00:00-24:00 ET).
    A sweep+reclaim / drive / failure event only counts if it happened on a
    STRICTLY PRIOR bar (same calendar date) before the entry bar -- enforced
    via a per-day "cumulative-before" scan, never same-bar-as-entry or later.
  * "daily open" = 18:00-ET-session (Globex) open, i.e. the open price of the
    first bar of the 18:00-ET-anchored session containing the entry (matches
    dol10_levels' PSH/PSL / session_so_far session_date convention).
  * "previous close" = the last 1m close on the ET calendar date labeling
    that same 18:00-session, restricted to bars with time-of-day < 17:00 ET
    (i.e. the settlement-ish close right before that day's ~17:00-18:00 ET
    maintenance gap) -- known well before the session opens, safely causal.
  * ONH/ONL: dol10_levels.DolLevels already enforces `known <= query_open`
    (asserted in dol10_levels.py); additionally, per the spec, ONH/ONL-based
    rules are IN-SCOPE only for entries with ET time-of-day >= 09:30 (the
    overnight window's own completion boundary for THAT calendar date) --
    entries before 09:30 are BLOCKED (out-of-scope) for those rules, and the
    in-scope baseline is reported alongside so the comparison is fair.
  * First-drive (15m/30m): in-scope only for entries with ET time-of-day
    >= 09:45 / >= 10:00 respectively (the window's own close boundary).
  * VWAP: session-anchored (18:00 ET), cumulative typical-price*volume /
    volume computed from bars STRICTLY BEFORE the entry bar within the same
    session (shift-by-1 cumulative sum, never includes the entry bar itself).
    VWAP-slope = current session VWAP (as of entry) vs the session VWAP
    30 minutes earlier (blocked/NaN if that lookback crosses the session
    start). Crossing count = sign changes of (close - running VWAP) among
    bars strictly before entry, same session.

Writes:
  reports/ifvg_optimisation/11_daily_bias.csv
  reports/ifvg_optimisation/11_daily_bias.md
"""
from __future__ import annotations
import sys
import os
import time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import load_data                     # noqa: E402
from dol10_levels import DolLevels                # noqa: E402
from dol10_walker import simulate as dw_simulate  # noqa: E402  (for the ONE exit-changing row)

DATA = "/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet"
HERE = os.path.dirname(os.path.abspath(__file__))
PATHSTATS_CSV = os.path.join(HERE, "reports/ifvg_optimisation/10_path_stats.csv")
OUT_CSV = os.path.join(HERE, "reports/ifvg_optimisation/11_daily_bias.csv")
OUT_MD = os.path.join(HERE, "reports/ifvg_optimisation/11_daily_bias.md")

HORIZON_BARS = 4000
LONG, SHORT = 1, -1
N_BASE = 5056


# --------------------------------------------------------------------------- #
# Generic per-ET-calendar-day "cumulative event happened on a STRICTLY prior
# bar this same day" scan.  day_codes must be a contiguous-block integer
# array (data sorted by time, which it is).
# --------------------------------------------------------------------------- #
def cum_before_by_day(flag: np.ndarray, day_codes: np.ndarray) -> np.ndarray:
    n = len(flag)
    out = np.zeros(n, dtype=bool)
    change = np.empty(n, dtype=bool)
    change[0] = True
    change[1:] = day_codes[1:] != day_codes[:-1]
    starts = np.where(change)[0]
    ends = np.r_[starts[1:], n]
    fi = flag.astype(np.int8)
    for s, e in zip(starts, ends):
        cm = np.maximum.accumulate(fi[s:e])
        out[s + 1:e] = cm[:-1].astype(bool)
    return out


def cumsum_before_by_day(vals: np.ndarray, day_codes: np.ndarray) -> np.ndarray:
    """Running cumulative SUM using only STRICTLY PRIOR bars this same day
    (bar 0 of each day -> 0.0)."""
    n = len(vals)
    out = np.zeros(n, dtype=float)
    change = np.empty(n, dtype=bool)
    change[0] = True
    change[1:] = day_codes[1:] != day_codes[:-1]
    starts = np.where(change)[0]
    ends = np.r_[starts[1:], n]
    for s, e in zip(starts, ends):
        cs = np.cumsum(vals[s:e])
        out[s] = 0.0
        out[s + 1:e] = cs[:-1]
    return out


# --------------------------------------------------------------------------- #
# Build the full 1m-bar feature set (once).
# --------------------------------------------------------------------------- #
def build_features():
    t0 = time.time()
    df = load_data(DATA)
    N = len(df)
    h = df["high"].to_numpy(float); l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float); o = df["open"].to_numpy(float)
    v = df["volume"].to_numpy(float)
    t_open_ns = df.index.view("int64").astype("int64")
    et = df.index.tz_convert("America/New_York")
    et_date = np.asarray(et.date)
    tod_min = np.asarray(et.hour) * 60 + np.asarray(et.minute)
    day_codes = pd.factorize(et_date, sort=False)[0]

    sess_date = np.asarray((et - pd.Timedelta(hours=18)).date)   # 18:00 ET anchor
    sess_codes = pd.factorize(sess_date, sort=False)[0]

    print(f"[data] {N} 1m bars ({time.time()-t0:.1f}s)")

    dl = DolLevels(df)
    print(f"[dol] causal levels built ({time.time()-t0:.1f}s)")

    # ---- Family 1/2: PDH/PDL, ONH/ONL sweep+reclaim event, cumulative-before-today ----
    PDL = dl.PDL; PDH = dl.PDH; ONL = dl.ONL; ONH = dl.ONH; ON_known = dl.ON_known
    with np.errstate(invalid="ignore"):
        pdl_evt = (l < PDL) & (c > PDL)
        pdh_evt = (h > PDH) & (c < PDH)
        onl_evt = (l < ONL) & (c > ONL) & (ON_known >= 0)
        onh_evt = (h > ONH) & (c < ONH) & (ON_known >= 0)
    pdl_evt = np.nan_to_num(pdl_evt, nan=0.0).astype(bool)
    pdh_evt = np.nan_to_num(pdh_evt, nan=0.0).astype(bool)
    onl_evt = np.nan_to_num(onl_evt, nan=0.0).astype(bool)
    onh_evt = np.nan_to_num(onh_evt, nan=0.0).astype(bool)

    pdl_swept_before = cum_before_by_day(pdl_evt, day_codes)
    pdh_swept_before = cum_before_by_day(pdh_evt, day_codes)
    onl_swept_before = cum_before_by_day(onl_evt, day_codes)
    onh_swept_before = cum_before_by_day(onh_evt, day_codes)
    print(f"[sweep-state] PDH/PDL/ONH/ONL event flags built ({time.time()-t0:.1f}s)")

    # ---- Family 3: daily open (18:00 ET session open) + previous close (last
    #      1m close < 17:00 ET on the calendar date that labels the session) ----
    sess_df = pd.DataFrame({"sess": sess_date, "open": o})
    first_open = sess_df.groupby("sess", sort=False)["open"].first()
    daily_open_map = first_open.to_dict()
    daily_open = np.array([daily_open_map[d] for d in sess_date], dtype=float)

    pre17 = tod_min < 17 * 60
    pre17_df = pd.DataFrame({"day": et_date, "close": c})[pre17]
    last_close_pre17 = pre17_df.groupby("day", sort=False)["close"].last()
    prev_close_map = last_close_pre17.to_dict()
    # session labeled D's prev_close = last-close-before-17:00-ET on date D
    prev_close = np.array([prev_close_map.get(d, np.nan) for d in sess_date], dtype=float)

    # ---- Family 5: first-15m / first-30m drive (09:30-09:45 / 09:30-10:00 ET) ----
    m15 = (tod_min >= 570) & (tod_min < 585)
    m30 = (tod_min >= 570) & (tod_min < 600)
    d15 = pd.DataFrame({"day": et_date, "open": o, "close": c, "high": h, "low": l})[m15]
    d30 = pd.DataFrame({"day": et_date, "open": o, "close": c, "high": h, "low": l})[m30]
    w15_open = d15.groupby("day", sort=False)["open"].first().to_dict()
    w15_close = d15.groupby("day", sort=False)["close"].last().to_dict()
    w30_open = d30.groupby("day", sort=False)["open"].first().to_dict()
    w30_close = d30.groupby("day", sort=False)["close"].last().to_dict()
    w30_high = d30.groupby("day", sort=False)["high"].max().to_dict()
    w30_low = d30.groupby("day", sort=False)["low"].min().to_dict()

    def _drive_dir(open_map, close_map, days):
        out = np.full(len(days), np.nan)
        for i, d in enumerate(days):
            oo = open_map.get(d); cc = close_map.get(d)
            if oo is None or cc is None:
                continue
            out[i] = 1.0 if cc > oo else (-1.0 if cc < oo else 0.0)
        return out

    drive15_dir = _drive_dir(w15_open, w15_close, et_date)
    drive30_dir = _drive_dir(w30_open, w30_close, et_date)
    have15 = np.array([d in w15_open for d in et_date])
    have30 = np.array([d in w30_open for d in et_date])
    scope15 = have15 & (tod_min >= 585)
    scope30 = have30 & (tod_min >= 600)

    w30h_arr = np.array([w30_high.get(d, np.nan) for d in et_date], dtype=float)
    w30l_arr = np.array([w30_low.get(d, np.nan) for d in et_date], dtype=float)
    post30 = tod_min >= 600
    with np.errstate(invalid="ignore"):
        fail_high_evt = post30 & (h > w30h_arr) & (c < w30h_arr)
        fail_low_evt = post30 & (l < w30l_arr) & (c > w30l_arr)
    fail_high_evt = np.nan_to_num(fail_high_evt, nan=0.0).astype(bool)
    fail_low_evt = np.nan_to_num(fail_low_evt, nan=0.0).astype(bool)
    fail_high_before = cum_before_by_day(fail_high_evt, day_codes)
    fail_low_before = cum_before_by_day(fail_low_evt, day_codes)
    print(f"[first-drive] 15m/30m drive + 30m-fail-reversal flags built ({time.time()-t0:.1f}s)")

    # ---- Family 6: VWAP (18:00-ET session-anchored), slope, cross count ----
    typical = (h + l + c) / 3.0
    pv = typical * v
    cum_pv_before = cumsum_before_by_day(pv, sess_codes)
    cum_v_before = cumsum_before_by_day(v, sess_codes)
    with np.errstate(invalid="ignore", divide="ignore"):
        vwap_before = np.where(cum_v_before > 0, cum_pv_before / cum_v_before, np.nan)

    # bars-since-session-start (for the 30-min-lookback slope + "has enough history")
    change = np.empty(N, dtype=bool)
    change[0] = True
    change[1:] = sess_codes[1:] != sess_codes[:-1]
    sess_start_idx = np.where(change)[0]
    # map each bar -> index of its session's first bar
    sess_first_idx = np.zeros(N, dtype=np.int64)
    cur = 0
    starts_list = sess_start_idx.tolist() + [N]
    for k in range(len(sess_start_idx)):
        s, e = starts_list[k], starts_list[k + 1]
        sess_first_idx[s:e] = s
    bars_since_sess_start = np.arange(N) - sess_first_idx

    lag = 30
    vwap_lag30 = np.full(N, np.nan)
    ok_lag = bars_since_sess_start >= lag
    vwap_lag30[ok_lag] = vwap_before[np.arange(N)[ok_lag] - lag]
    vwap_slope_up = vwap_before > vwap_lag30
    vwap_slope_dn = vwap_before < vwap_lag30
    have_slope = ok_lag & np.isfinite(vwap_before) & np.isfinite(vwap_lag30)

    with np.errstate(invalid="ignore"):
        sign_now = np.sign(c - vwap_before)
    sign_prev = np.roll(sign_now, 1)
    cross_evt = (sign_now != sign_prev) & (sign_now != 0) & (sign_prev != 0) \
        & np.isfinite(vwap_before) & (bars_since_sess_start >= 1)
    cross_evt = np.nan_to_num(cross_evt, nan=0.0).astype(bool)
    cross_count_before = cumsum_before_by_day(cross_evt.astype(float), sess_codes)
    print(f"[vwap] session VWAP + slope + cross-count built ({time.time()-t0:.1f}s)")

    feat = dict(
        et_date=et_date, sess_date=sess_date, tod_min=tod_min,
        pdl_swept_before=pdl_swept_before, pdh_swept_before=pdh_swept_before,
        onl_swept_before=onl_swept_before, onh_swept_before=onh_swept_before,
        daily_open=daily_open, prev_close=prev_close,
        drive15_dir=drive15_dir, drive30_dir=drive30_dir,
        scope15=scope15, scope30=scope30,
        fail_high_before=fail_high_before, fail_low_before=fail_low_before,
        vwap_before=vwap_before, vwap_slope_up=vwap_slope_up, vwap_slope_dn=vwap_slope_dn,
        have_slope=have_slope, cross_count_before=cross_count_before,
    )
    return df, dl, feat, h, l, c, t_open_ns


# --------------------------------------------------------------------------- #
# Merge onto the frozen trade ledger (from 10_path_stats.csv)
# --------------------------------------------------------------------------- #
def build_trade_frame(feat):
    t = pd.read_csv(PATHSTATS_CSV, parse_dates=["entry_time", "exit_time"])
    assert len(t) == N_BASE, f"unexpected n={len(t)}"
    idx = t["entry_idx"].to_numpy(int)
    t["is_long"] = t["dir"] == "long"

    for col in ("pdl_swept_before", "pdh_swept_before", "onl_swept_before", "onh_swept_before",
                "daily_open", "prev_close", "drive15_dir", "drive30_dir",
                "scope15", "scope30", "fail_high_before", "fail_low_before",
                "vwap_before", "vwap_slope_up", "vwap_slope_dn", "have_slope",
                "cross_count_before", "tod_min"):
        t[col] = feat[col][idx]

    t["entry_ge_930"] = t["tod_min"] >= 570   # ON-scope boundary

    # --- nearest-DOL direction bias (family 4): dist to nearest DOL ABOVE / BELOW
    #     price regardless of trade direction, reusing the already-computed,
    #     per-trade-direction "distance_to_target_R" (own-direction target)
    #     and "opp_dol_dist_R" (mirror-direction target) from 10_path_stats.csv.
    dist_above = np.where(t["is_long"], t["distance_to_target_R"], t["opp_dol_dist_R"])
    dist_below = np.where(t["is_long"], t["opp_dol_dist_R"], t["distance_to_target_R"])
    t["dist_above"] = dist_above
    t["dist_below"] = dist_below
    have_above = np.isfinite(dist_above); have_below = np.isfinite(dist_below)
    bias_dir = np.full(len(t), "none", dtype=object)
    both = have_above & have_below
    bias_dir[both & (dist_above < dist_below)] = "long"
    bias_dir[both & (dist_below < dist_above)] = "short"
    bias_dir[both & (dist_above == dist_below)] = "tie"
    bias_dir[have_above & ~have_below] = "long"
    bias_dir[~have_above & have_below] = "short"
    t["dol_bias_dir"] = bias_dir
    t["dol_bias_dist_R"] = np.where(bias_dir == "long", dist_above,
                             np.where(bias_dir == "short", dist_below, np.nan))
    t["dol_dir_matches"] = (t["dol_bias_dir"] == t["dir"])

    # --- first-sweep direction lock (family 6g), rerun on the FULL baseline ---
    t = t.sort_values("entry_time").reset_index(drop=True)
    t["_et_date_"] = t["entry_time"].dt.tz_convert("America/New_York").dt.date
    t["first_dir_today"] = t.groupby("_et_date_")["dir"].transform("first")
    t["dir_lock_ok"] = t["dir"] == t["first_dir_today"]

    return t


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def metrics_for(sub: pd.DataFrame, rcol="R_baseline") -> dict:
    n = len(sub)
    if n == 0:
        return dict(n=0, wr=np.nan, pf=np.nan, avgR=np.nan, totR=0.0, maxdd=0.0,
                    yrs_pos=0, ex2024=np.nan, exfri=np.nan, exboth=np.nan,
                    long_avgR=np.nan, short_avgR=np.nan, p2r=np.nan)
    R = sub[rcol].to_numpy(float)
    wr = float((R > 0).mean() * 100)
    gw = R[R > 0].sum(); gl = -R[R < 0].sum()
    pf = gw / gl if gl > 0 else (np.inf if gw > 0 else np.nan)
    avgR = float(R.mean()); totR = float(R.sum())
    cum = np.cumsum(sub.sort_values("entry_time")[rcol].to_numpy(float))
    dd = float((cum - np.maximum.accumulate(cum)).min()) if len(cum) else 0.0
    yr_r = sub.groupby("year")[rcol].sum()
    yrs_pos = int((yr_r > 0).sum())
    ex2024 = sub.loc[sub["year"] != 2024, rcol].mean() if (sub["year"] != 2024).any() else np.nan
    exfri = sub.loc[sub["dow"] != "Friday", rcol].mean() if (sub["dow"] != "Friday").any() else np.nan
    both_m = (sub["year"] != 2024) & (sub["dow"] != "Friday")
    exboth = sub.loc[both_m, rcol].mean() if both_m.any() else np.nan
    long_avgR = sub.loc[sub["is_long"], rcol].mean() if sub["is_long"].any() else np.nan
    short_avgR = sub.loc[~sub["is_long"], rcol].mean() if (~sub["is_long"]).any() else np.nan
    p2r = float(sub["touch_2_0"].mean() * 100) if "touch_2_0" in sub.columns else np.nan
    return dict(n=n, wr=wr, pf=pf, avgR=avgR, totR=totR, maxdd=dd, yrs_pos=yrs_pos,
                ex2024=ex2024, exfri=exfri, exboth=exboth,
                long_avgR=long_avgR, short_avgR=short_avgR, p2r=p2r)


def denom_flag(sub: pd.DataFrame, m: dict, scope_n: int) -> str:
    if m["n"] == 0:
        return "n=0"
    flags = []
    reduction = 100.0 * (1 - m["n"] / scope_n) if scope_n else np.nan
    if reduction > 70:
        flags.append("reduction>70%")
    if m["n"] < 50:
        flags.append("n<50")
    yr_r = sub.groupby("year")["R_baseline"].sum()
    if m["totR"] > 0 and len(yr_r) and yr_r.max() > m["totR"]:
        flags.append("one-year-carry")
    non_fri = sub[sub["dow"] != "Friday"]
    if m["totR"] > 0 and len(non_fri) and non_fri["R_baseline"].sum() <= 0:
        flags.append("Friday-only")
    return ",".join(flags) if flags else "ok"


BASE_COST_DOLLARS = 15.0   # $5 RT commission + $10 (2 ticks @ $20/pt) RT slippage
                           # -- identical convention to day_sequence_stress.py


def stress(sub: pd.DataFrame, rcol="R_baseline"):
    """2x costs and -0.01R / -0.02R slip, using the EXACT same convention as
    day_sequence_stress.py (apply_cost_mult / apply_flat_slip): 2x costs =
    one extra full cost-stack ($15 = comm+slippage) per trade, converted to R
    via that trade's own risk_dollars; slip rows are a flat R-space haircut."""
    R = sub[rcol].to_numpy(float)
    risk_dollars = sub["risk_pts"].to_numpy(float) * 20.0
    extra_R_costs = (2.0 - 1.0) * BASE_COST_DOLLARS / risk_dollars
    R_2x = R - extra_R_costs
    R_s1 = R - 0.01
    R_s2 = R - 0.02
    return (float(R_2x.mean()), float(R_s1.mean()), float(R_s2.mean()))


# --------------------------------------------------------------------------- #
# Rule table
# --------------------------------------------------------------------------- #
def run_rules(t: pd.DataFrame):
    rows = []

    def add(name, keep_mask, scope_mask=None, rcol="R_baseline", note=""):
        scope_mask = np.ones(len(t), dtype=bool) if scope_mask is None else scope_mask
        scope_n = int(scope_mask.sum())
        sub = t[keep_mask & scope_mask]
        m = metrics_for(sub, rcol=rcol)
        flag = denom_flag(sub, m, scope_n) if m["n"] else "n=0"
        reduction = 100.0 * (1 - m["n"] / scope_n) if scope_n else np.nan
        r2x, rs1, rs2 = stress(sub, rcol=rcol) if m["n"] else (np.nan, np.nan, np.nan)
        rows.append(dict(rule=name, scope_n=scope_n, n=m["n"], wr=m["wr"], pf=m["pf"],
                         avgR=m["avgR"], totR=m["totR"], maxdd=m["maxdd"], yrs_pos=m["yrs_pos"],
                         ex2024=m["ex2024"], exfri=m["exfri"], exboth=m["exboth"],
                         long_avgR=m["long_avgR"], short_avgR=m["short_avgR"],
                         reduction=reduction, p2r=m["p2r"], denom_flag=flag,
                         artifact_count=0, stress_2xcost=r2x, stress_slip01=rs1,
                         stress_slip02=rs2, note=note))

    # ================= Family 1: PDH/PDL sweep-state ==========================
    add("F1.after_PDL_sweep_longs_only", (t["dir"] == "long") & t["pdl_swept_before"])
    add("F1.after_PDH_sweep_shorts_only", (t["dir"] == "short") & t["pdh_swept_before"])
    add("F1.after_PDL_sweep_block_shorts", ~((t["dir"] == "short") & t["pdl_swept_before"]))
    add("F1.after_PDH_sweep_block_longs", ~((t["dir"] == "long") & t["pdh_swept_before"]))

    # ================= Family 2: ONH/ONL sweep-state (scope: ET>=09:30) =======
    on_scope = t["entry_ge_930"].to_numpy()
    add("F2.after_ONL_sweep_longs_only", (t["dir"] == "long") & t["onl_swept_before"], on_scope)
    add("F2.after_ONH_sweep_shorts_only", (t["dir"] == "short") & t["onh_swept_before"], on_scope)
    add("F2.after_ONL_sweep_block_shorts", ~((t["dir"] == "short") & t["onl_swept_before"]), on_scope)
    add("F2.after_ONH_sweep_block_longs", ~((t["dir"] == "long") & t["onh_swept_before"]), on_scope)

    # ================= Family 3: Open/close bias ==============================
    above_open = t["entry"] > t["daily_open"]
    above_pc = t["entry"] > t["prev_close"]
    add("F3.longs_only_above_open", (t["dir"] == "long") & above_open)
    add("F3.shorts_only_below_open", (t["dir"] == "short") & ~above_open)
    add("F3.longs_only_above_prevclose", (t["dir"] == "long") & above_pc)
    add("F3.shorts_only_below_prevclose", (t["dir"] == "short") & ~above_pc)
    add("F3.longs_only_above_BOTH", (t["dir"] == "long") & above_open & above_pc)
    add("F3.shorts_only_below_BOTH", (t["dir"] == "short") & ~above_open & ~above_pc)

    # ================= Family 4: Nearest-DOL direction bias ===================
    dolmatch = t["dol_dir_matches"].to_numpy()
    have_dist = np.isfinite(t["dol_bias_dist_R"].to_numpy())
    add("F4.dol_direction_only", dolmatch & have_dist)
    add("F4.dol_direction_0.75to3R", dolmatch & have_dist &
        (t["dol_bias_dist_R"] >= 0.75) & (t["dol_bias_dist_R"] <= 3.0))
    add("F4.dol_direction_skip_lt0.5R", dolmatch & have_dist & (t["dol_bias_dist_R"] >= 0.5))
    add("F4.dol_direction_skip_gt3R", dolmatch & have_dist & (t["dol_bias_dist_R"] <= 3.0))

    # ================= Family 5: First-drive ==================================
    add("F5.long_only_15m_drive_up", (t["dir"] == "long") & (t["drive15_dir"] == 1.0), t["scope15"].to_numpy())
    add("F5.short_only_15m_drive_down", (t["dir"] == "short") & (t["drive15_dir"] == -1.0), t["scope15"].to_numpy())
    add("F5.long_only_30m_drive_up", (t["dir"] == "long") & (t["drive30_dir"] == 1.0), t["scope30"].to_numpy())
    add("F5.short_only_30m_drive_down", (t["dir"] == "short") & (t["drive30_dir"] == -1.0), t["scope30"].to_numpy())
    add("F5.rev_30mHigh_sweptFailed_short", (t["dir"] == "short") & t["fail_high_before"], t["scope30"].to_numpy())
    add("F5.rev_30mLow_sweptFailed_long", (t["dir"] == "long") & t["fail_low_before"], t["scope30"].to_numpy())

    # ================= Family 6: VWAP / day-type ===============================
    above_vwap = t["entry"] > t["vwap_before"]
    have_vwap = np.isfinite(t["vwap_before"].to_numpy())
    have_slope = t["have_slope"].to_numpy()
    add("F6.longs_only_above_VWAP", (t["dir"] == "long") & above_vwap, have_vwap)
    add("F6.shorts_only_below_VWAP", (t["dir"] == "short") & ~above_vwap, have_vwap)
    add("F6.longs_only_VWAP_slope_up", (t["dir"] == "long") & t["vwap_slope_up"].to_numpy(), have_slope)
    add("F6.shorts_only_VWAP_slope_down", (t["dir"] == "short") & t["vwap_slope_dn"].to_numpy(), have_slope)
    add("F6.block_gt3_VWAP_crossings", t["cross_count_before"] <= 3, have_vwap)
    add("F6.block_both_ONH_ONL_swept", ~(t["onh_swept_before"] & t["onl_swept_before"]), on_scope)
    add("F6.first_sweep_dir_lock", t["dir_lock_ok"].to_numpy())

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Family-4 combined row: direction-of-DOL eligibility + target-the-DOL exit
# --------------------------------------------------------------------------- #
def combined_dol_row(t: pd.DataFrame, dl: DolLevels, h, l, c, t_open_ns):
    dolmatch = t["dol_dir_matches"].to_numpy()
    have_dist = np.isfinite(t["dol_bias_dist_R"].to_numpy())
    eligible = dolmatch & have_dist
    sub = t[eligible].sort_values("entry_time").reset_index(drop=True)

    # baseline (fixed-2R) metrics on the SAME eligible subset, for a fair compare
    m_fixed2r = metrics_for(sub, rcol="R_baseline")

    # target-the-DOL exit, replayed SEQUENTIALLY single-position (matches the
    # exact dol10_battery.py `dol_nearest_any` methodology, for apples-to-apples
    # comparison against dol_htf_pocket_only avgR +0.0842 / n=3773)
    busy_until = -1
    R_new = []
    kept_idx = []
    for i, tr in sub.iterrows():
        if int(tr["entry_time"].value) < busy_until:
            continue
        entry_idx = int(tr["entry_idx"]); dir_ = LONG if tr["dir"] == "long" else SHORT
        entry = float(tr["entry"]); stop = float(tr["stop"]); risk_pts = float(tr["risk_pts"])
        dol_price = float(tr["dol_price"])
        if not np.isfinite(dol_price):
            continue
        legs = [dict(qty=1.0, price=dol_price, tag="DOL", move_stop_to=None)]
        horizon_idx = entry_idx + HORIZON_BARS
        res = dw_simulate(h, l, c, t_open_ns, entry_idx, dir_, entry, stop, risk_pts,
                          legs, horizon_idx)
        R_new.append(res["R"])
        kept_idx.append(i)
        busy_until = res["exit_time_ns"]

    sub_dol = sub.loc[kept_idx].copy()
    sub_dol["R_dol_target"] = R_new
    m_dol = metrics_for(sub_dol, rcol="R_dol_target")

    return dict(eligible_n=int(eligible.sum()), fixed2r=m_fixed2r, dol_target=m_dol,
                sequential_n=len(sub_dol))


def main():
    t0 = time.time()
    df, dl, feat, h, l, c, t_open_ns = build_features()
    t = build_trade_frame(feat)
    print(f"[merge] trade frame ready n={len(t)} ({time.time()-t0:.1f}s)")

    res = run_rules(t)
    combo = combined_dol_row(t, dl, h, l, c, t_open_ns)

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    res_out = res.copy()
    res_out.to_csv(OUT_CSV, index=False)
    print(f"[written] {OUT_CSV}")

    # baseline row for reference
    base_m = metrics_for(t, rcol="R_baseline")

    res_sorted = res.sort_values("ex2024", ascending=False)

    lines = []
    P = lines.append
    P("# 11 -- Daily-bias research pass on frozen SMC3 entries (n=5056 baseline)\n")
    P(f"Baseline (no bias filter): n={base_m['n']}, WR={base_m['wr']:.2f}%, avgR={base_m['avgR']:+.4f}, "
     f"totR={base_m['totR']:+.1f}, yrs+={base_m['yrs_pos']}/6, ex2024={base_m['ex2024']:+.4f}, "
     f"P(+2R)={base_m['p2r']:.1f}%.\n")
    P("Sorted by **ex-2024 avgR**.\n")
    P("| rule | scope_n | n | WR% | PF(R) | avgR | totR | maxDD(R) | yrs+/6 | ex2024 | exFri | exBoth | "
     "long_avgR | short_avgR | reduc% | P(+2R)% | 2xcost_avgR | slip-0.01_avgR | slip-0.02_avgR | flag |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in res_sorted.iterrows():
        pf_s = "inf" if r["pf"] == np.inf else (f"{r['pf']:.3f}" if pd.notna(r["pf"]) else "-")
        P(f"| {r['rule']} | {r['scope_n']:.0f} | {r['n']:.0f} | {r['wr']:.1f} | {pf_s} | "
         f"{r['avgR']:+.4f} | {r['totR']:+.1f} | {r['maxdd']:.2f} | {r['yrs_pos']:.0f}/6 | "
         f"{r['ex2024']:+.4f} | {r['exfri']:+.4f} | {r['exboth']:+.4f} | "
         f"{r['long_avgR']:+.4f} | {r['short_avgR']:+.4f} | {r['reduction']:.1f}% | "
         f"{r['p2r']:.1f}% | {r['stress_2xcost']:+.4f} | {r['stress_slip01']:+.4f} | "
         f"{r['stress_slip02']:+.4f} | {r['denom_flag']} |")
    P("")
    P("## Family-4 combined row: direction-of-nearest-DOL eligibility + target-the-DOL exit\n")
    P(f"Eligible n={combo['eligible_n']} (direction-of-DOL match, DOL defined). "
     f"Fixed-2R on this SAME eligible subset: n={combo['fixed2r']['n']}, avgR={combo['fixed2r']['avgR']:+.4f}, "
     f"PF={combo['fixed2r']['pf']:.3f}, ex2024={combo['fixed2r']['ex2024']:+.4f}, P(+2R)={combo['fixed2r']['p2r']:.1f}%.\n")
    P(f"Target-the-DOL exit (sequential single-position replay, matches dol10_battery `dol_nearest_any` "
     f"methodology): n={combo['dol_target']['n']}, avgR={combo['dol_target']['avgR']:+.4f}, "
     f"PF={combo['dol_target']['pf']:.3f}, ex2024={combo['dol_target']['ex2024']:+.4f}.\n")
    P("Reference (previously tested, `10_dol_exit_audit`/`10_dol_exit_summary`): `dol_htf_pocket_only` "
     "avgR +0.0842, PF 1.103, n=3773 (different universe -- ALL frozen entries, no direction-of-DOL "
     "eligibility filter, single-source htf-pocket target, not nearest-of-pool).\n")
    P("_Method: allow-only / block-only causal filters applied ISOLATED to the frozen n=5056 SMC3 ledger "
     "(default Config, fixed-2R exits unchanged except the one flagged row above). Sweep-state, "
     "first-drive and VWAP features are built from strictly-prior bars only (see docstring in "
     "day_bias_filters.py for the exact causal conventions). stress columns = direct R-space haircut "
     "(2x commission-equivalent / -0.01R / -0.02R slip), consistent with this repo's other stress scripts. "
     "artifact_count=0 throughout (causality is asserted in dol10_levels.py / enforced by construction "
     "in the cumulative-before-today scan, which only ever looks at STRICTLY PRIOR same-day bars)._")

    with open(OUT_MD, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[written] {OUT_MD}  ({time.time()-t0:.1f}s total)")
    print(res_sorted.to_string())
    print("\nCOMBINED ROW:", combo)


if __name__ == "__main__":
    main()
