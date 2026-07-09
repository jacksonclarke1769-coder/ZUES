"""
STEP 1 + STEP 2 provenance -- per-trade PATH-STATS ledger for the SMC3
exit-model audit.  Entries are FROZEN (smc3_engine.py default Config,
untouched entry logic).  Research-only.

Writes reports/ifvg_optimisation/10_path_stats.csv

For every closed baseline trade (n=5056):
  * MFE_R / MAE_R and the touch ladder (+0.5/1/1.5/2/3R BEFORE the stop),
    walked bar-by-bar with stop-first-within-a-bar convention, horizon =
    HORIZON_BARS (2 trading days, generous).
  * nearest HEADLINE causal DOL (target_price/type/known_at/dist_R) with a
    hard assert target_known_at <= entry_time (ARTIFACT + excluded if
    violated -- should never trigger given dol10_levels.py's construction).
  * SEPARATE session_so_far DOL (non-headline variant, own columns).
  * opposite-side DOL (mirror direction, for the "exit if opposite DOL
    swept first" exit-battery model).
  * DOL-hit-before-stop / DOL-hit-before-fixed-2R / time-to-DOL / was the
    baseline 2R target farther away than the DOL.
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

DATA = "/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet"
OUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "reports/ifvg_optimisation/10_path_stats.csv")

HORIZON_BARS = 4000   # ~2.8 continuous days of 1m bars ("generous", per spec)
LONG, SHORT = 1, -1
RUNGS = [0.5, 1.0, 1.5, 2.0, 3.0]


def _first_touch(h, l, dir_, level, start, end):
    if not np.isfinite(level):
        return None
    if dir_ == LONG:
        mask = h[start:end] >= level
    else:
        mask = l[start:end] <= level
    if mask.any():
        return start + int(np.argmax(mask))
    return None


def path_stats_one(h, l, entry_idx, dir_, entry, stop, risk_pts, horizon_bars):
    start = entry_idx + 1
    end = min(start + horizon_bars, len(h))
    if end <= start:
        return dict(MFE_R=np.nan, MAE_R=np.nan, stop_hit_in_horizon=False,
                   time_to_stop_min=np.nan, horizon_exhausted_no_stop=True,
                   stop_abs_idx=None, no_data=True,
                   **{f"touch_{r}".replace(".", "_"): False for r in RUNGS})

    seg_h = h[start:end]; seg_l = l[start:end]
    if dir_ == LONG:
        stop_mask = seg_l <= stop
    else:
        stop_mask = seg_h >= stop
    stop_i = int(np.argmax(stop_mask)) if stop_mask.any() else None
    pre_end = stop_i if stop_i is not None else (end - start)

    if pre_end > 0:
        seg_h_pre = seg_h[:pre_end]; seg_l_pre = seg_l[:pre_end]
        if dir_ == LONG:
            mfe = (seg_h_pre.max() - entry) / risk_pts
            mae = (seg_l_pre.min() - entry) / risk_pts
        else:
            mfe = (entry - seg_l_pre.min()) / risk_pts
            mae = (entry - seg_h_pre.max()) / risk_pts
    else:
        mfe = 0.0
        mae = 0.0

    stop_abs_idx = None
    if stop_i is not None:
        stop_bar_extreme = seg_l[stop_i] if dir_ == LONG else seg_h[stop_i]
        stop_mae = ((stop_bar_extreme - entry) / risk_pts if dir_ == LONG
                   else (entry - stop_bar_extreme) / risk_pts)
        mae = min(mae, stop_mae)
        stop_abs_idx = start + stop_i
        time_to_stop_min = stop_i + 1
        stop_hit = True
    else:
        time_to_stop_min = np.nan
        stop_hit = False

    out = dict(MFE_R=mfe, MAE_R=mae, stop_hit_in_horizon=stop_hit,
              time_to_stop_min=time_to_stop_min,
              horizon_exhausted_no_stop=not stop_hit,
              stop_abs_idx=stop_abs_idx, no_data=False)
    for r in RUNGS:
        out[f"touch_{r}".replace(".", "_")] = bool(mfe >= r)
    return out


def main():
    t0 = time.time()
    df = load_data(DATA)
    h = df["high"].to_numpy(float); l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    t_open_ns = df.index.view("int64").astype("int64")
    print(f"[data] {len(df)} 1m bars loaded ({time.time()-t0:.1f}s)")

    res = run_backtest(df, Config())
    tdf = res.trades.copy()
    assert len(tdf) == 5056, f"baseline n mismatch: {len(tdf)}"
    print(f"[baseline] n={len(tdf)} WR={res.metrics['win_pct']:.2f}% PF={res.metrics['pf']:.3f} "
         f"totR={res.metrics['total_R']:.1f}")

    dl = DolLevels(df)
    print(f"[dol] causal level construction done ({time.time()-t0:.1f}s elapsed)")

    rows = []
    n_artifacts = 0
    for _, tr in tdf.iterrows():
        entry_idx = int(tr["entry_idx"])
        dir_ = LONG if tr["dir"] == "long" else SHORT
        entry = float(tr["entry"]); stop = float(tr["stop"]); risk_pts = float(tr["risk_pts"])
        entry_time_ns = int(tr["entry_time"].value)
        is_long = dir_ == LONG

        ps = path_stats_one(h, l, entry_idx, dir_, entry, stop, risk_pts, HORIZON_BARS)
        start = entry_idx + 1
        end = min(start + HORIZON_BARS, len(h))
        stop_abs = ps["stop_abs_idx"]

        # --- headline nearest causal DOL (hard provenance assert) ---
        dol_price, dol_type, dol_known_ns, dol_artifact = dl.nearest_causal_dol(
            entry_idx, entry, entry_time_ns, is_long)
        if dol_known_ns >= 0:
            assert dol_known_ns <= entry_time_ns, "HARD RULE violated: target_known_at > entry_time"
        if dol_artifact:
            n_artifacts += 1
        dol_dist_R = abs(dol_price - entry) / risk_pts if np.isfinite(dol_price) else np.nan

        dol_touch_idx = _first_touch(h, l, dir_, dol_price, start, end) if np.isfinite(dol_price) else None
        # baseline fixed-2R target touch (for "DOL hit before 2R" comparisons)
        r2_touch_idx = _first_touch(h, l, dir_, float(tr["target"]), start, end)

        dol_hit_before_stop = (dol_touch_idx is not None) and (stop_abs is None or dol_touch_idx < stop_abs)
        if dol_touch_idx is not None and r2_touch_idx is not None and dol_touch_idx == r2_touch_idx:
            dol_hit_before_2R = dol_dist_R < 2.0
        elif dol_touch_idx is not None:
            dol_hit_before_2R = (r2_touch_idx is None) or (dol_touch_idx < r2_touch_idx)
        else:
            dol_hit_before_2R = False
        dol_time_to_dol_min = (dol_touch_idx - entry_idx) if dol_touch_idx is not None else np.nan
        was_2R_beyond_dol = bool(np.isfinite(dol_dist_R) and dol_dist_R < 2.0)

        # --- session-so-far (SEPARATE, non-headline) ---
        sf_price, sf_type, sf_known_ns = dl.session_so_far_dol(entry_idx, entry, is_long)
        sf_dist_R = abs(sf_price - entry) / risk_pts if np.isfinite(sf_price) else np.nan

        # --- opposite-side DOL (mirror direction; used by exit-battery model #6) ---
        opp_price, opp_type, opp_known_ns, opp_artifact = dl.nearest_causal_dol(
            entry_idx, entry, entry_time_ns, not is_long)
        opp_dist_R = abs(opp_price - entry) / risk_pts if np.isfinite(opp_price) else np.nan

        et = tr["entry_time"].tz_convert("America/New_York")
        ny_am = (et.hour == 9 and et.minute >= 30) or (10 <= et.hour < 12)

        rows.append(dict(
            entry_idx=entry_idx, entry_time=tr["entry_time"], exit_time=tr["exit_time"],
            dir=tr["dir"], entry=entry, stop=stop, risk_pts=risk_pts,
            target_2R=float(tr["target"]), R_baseline=float(tr["R"]), reason_baseline=tr["reason"],
            year=int(et.year), ny_am=bool(ny_am), dow=et.day_name(),
            MFE_R=ps["MFE_R"], MAE_R=ps["MAE_R"], stop_hit_in_horizon=ps["stop_hit_in_horizon"],
            time_to_stop_min=ps["time_to_stop_min"], horizon_exhausted_no_stop=ps["horizon_exhausted_no_stop"],
            touch_0_5=ps["touch_0_5"], touch_1_0=ps["touch_1_0"], touch_1_5=ps["touch_1_5"],
            touch_2_0=ps["touch_2_0"], touch_3_0=ps["touch_3_0"],
            dol_price=dol_price, target_type=dol_type,
            dol_known_at=(pd.Timestamp(dol_known_ns, tz="UTC") if dol_known_ns >= 0 else pd.NaT),
            distance_to_target_R=dol_dist_R, dol_artifact=bool(dol_artifact),
            dol_hit_before_stop=bool(dol_hit_before_stop), dol_hit_before_2R=bool(dol_hit_before_2R),
            dol_time_to_dol_min=dol_time_to_dol_min, was_2R_beyond_dol=was_2R_beyond_dol,
            sf_price=sf_price, sf_type=sf_type, sf_dist_R=sf_dist_R,
            opp_dol_price=opp_price, opp_dol_type=opp_type, opp_dol_dist_R=opp_dist_R,
        ))

    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"[written] {OUT_CSV} rows={len(out)}  artifacts={n_artifacts}  ({time.time()-t0:.1f}s total)")

    # ---- touch ladder summary (printed; consumed later by report script) ----
    def ladder(sub, label):
        n = len(sub)
        if n == 0:
            print(f"  {label}: n=0"); return
        print(f"  {label}: n={n}  " + "  ".join(
            f"P(+{r}R)={sub[f'touch_{r}'.replace('.', '_')].mean()*100:.1f}%" for r in RUNGS))

    print("\n=== TOUCH-PROBABILITY LADDER (before stop) ===")
    ladder(out, "ALL")
    ladder(out[out.ny_am], "NY-AM (09:30-12:00 ET)")
    for y in sorted(out.year.unique()):
        ladder(out[out.year == y], f"year {y}")

    print("\n=== DOL diagnostics ===")
    have_dol = out[out.dol_price.notna()]
    print(f"  trades with a headline causal DOL: {len(have_dol)}/{len(out)} ({len(have_dol)/len(out)*100:.1f}%)")
    print(f"  avg DOL distance (R): {have_dol.distance_to_target_R.mean():.3f}")
    print(f"  DOL hit before stop: {have_dol.dol_hit_before_stop.mean()*100:.1f}%")
    print(f"  DOL hit before 2R:   {have_dol.dol_hit_before_2R.mean()*100:.1f}%")
    print(f"  2R beyond DOL (DOL closer than 2R): {have_dol.was_2R_beyond_dol.mean()*100:.1f}%")
    print(f"  artifact count (causality violation): {n_artifacts}")


if __name__ == "__main__":
    main()
