"""
INC-20260707 — measurement lane, READ-ONLY. NOT part of the test gate.

Objective (per auditor spec): confirm or refute the hypothesis that model01.run() only
appends a trade to `tr` after `_simulate` resolves its EXIT, so a trade surfaces to the
live engine at ~exit time rather than at fill time (staleness ~ hold_time) -- vs. the
alternative mechanisms of tail(3) clustering (other trades pushing a fresh trade out of
the 3-row window latest_signal() inspects) or plain poll-cadence granularity.

This script does NOT touch: bot.py, the poll cadence, the 10-min freshness gate, the
frozen model (model01_sweep_mss_fvg.py / strategy_engine_profileA.py), any config/live
file, or test_signal_parity.py. It duplicates test_signal_parity.py's bar-by-bar drive
(same window / WARMUP_DAYS / DEC_MIN window / ProfileAEngine feed) and additionally
INSTRUMENTS the tr contents at every decision-bar poll -- something latest_signal()'s
plain return value cannot show, since it only reports the trade it acts on (or None).

GROUND TRUTH (per auditor, not re-derived here): out_parity.csv (the current, post-fafe12d
gate output committed at 652938c) already shows 71 backtest ny_am trades in this window,
48 in_live=True, 23 in_live=False (0 extra, 0 field mismatches, matched byte-identical).
This script uses that file's `in_live` column as the authoritative "missing" flag rather
than re-deriving it from a second freshness/acted_ts replica (which would risk exactly the
two-independent-paths drift class fafe12d closed). Everything else in the per-trade table
(surfacing/tail3/staleness/1m-truth) is new instrumentation this script adds.
"""
import os, sys, time
import numpy as np, pandas as pd

FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
sys.path.insert(0, os.path.join(FW, "engine"))
sys.path.insert(0, os.path.join(FW, "models"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data as D, htf, model01_sweep_mss_fvg as M1
from strategy_engine_profileA import ProfileAEngine, PROFILE_A, NY, _derive_fill_instant
import tools_1m_truth_recert as T1M

TEST_START = pd.Timestamp("2025-06-01", tz=NY)
TEST_END = pd.Timestamp("2025-12-01", tz=NY)
WARMUP_DAYS = 45
DEC_MIN_LO, DEC_MIN_HI = 9 * 60 + 30, 13 * 60 + 35

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "reports", "inc_20260707")
RAW_CSV = os.path.join(OUT_DIR, "missing_classification_raw.csv")
PARITY_CSV = os.path.join(HERE, "out_parity.csv")


def main():
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)

    # ---------- ground-truth missing/matched flag (do NOT re-derive: read the gate's own output) ----------
    parity = pd.read_csv(PARITY_CSV)
    live_ok = dict(zip(parity["key"], parity["in_live"]))

    # ---------- 1) BACKTEST REFERENCE (same construction as test_signal_parity.py) ----------
    print("[1/4] building full-history backtest reference ...", flush=True)
    f = htf.build_features("NQ", "5m")
    f.index.name = "timestamp"
    bt = M1.run(f, "NQ", PROFILE_A)
    bt = bt[bt.session == "ny_am"].copy()
    bt["date"] = bt["date"].astype(str)
    bt["k"] = [_derive_fill_instant(f.index, int(fb)).isoformat() for fb in bt["fill_bar"]]
    bt["fdate"] = pd.to_datetime(bt["date"]).dt.tz_localize(NY)
    ref = bt[(bt.fdate >= TEST_START) & (bt.fdate < TEST_END)].copy().reset_index(drop=True)
    print(f"      ny_am trades total={len(bt)}  in-window={len(ref)}", flush=True)

    ref["fill_instant"] = [_derive_fill_instant(f.index, int(fb)) for fb in ref["fill_bar"]]
    ref["exit_instant"] = [f.index[int(eb)] for eb in ref["exit_bar"]]
    ref["hold_time_min"] = (ref["exit_instant"] - ref["fill_instant"]).dt.total_seconds() / 60.0
    ref["missing"] = ~ref["k"].map(live_ok).fillna(False).astype(bool)

    # ---------- 2) DRIVE LIVE ENGINE BAR-BY-BAR, INSTRUMENTING tr AT EVERY POLL ----------
    print("[2/4] feeding bars into live ProfileAEngine, instrumenting tr @ every decision poll ...", flush=True)
    base = D.load_spine("NQ", "5m")
    feed = base[(base.index >= TEST_START - pd.Timedelta(days=WARMUP_DAYS)) & (base.index < TEST_END)]
    eng = ProfileAEngine({"nyam_start_min": 570, "nyam_end_min": 690, "flat_min": 870})
    eng.acted_ts = set(bt[bt.fdate < TEST_START]["k"])   # same warmup seed as test_signal_parity

    ref_keys = set(ref["k"])
    first_surface_poll = {}   # k -> recent at first poll where k appears ANYWHERE in tr (ny_am rows)
    first_tail3_poll = {}     # k -> recent at first poll where k appears in tr.tail(3)

    vals = feed[["Open", "High", "Low", "Close"]].values
    idx = feed.index
    npoll = 0
    for n in range(len(feed)):
        ts = idx[n]
        eng.add_bar(ts, vals[n, 0], vals[n, 1], vals[n, 2], vals[n, 3], 0)
        if ts < TEST_START:
            continue
        m = ts.hour * 60 + ts.minute
        if not (DEC_MIN_LO <= m <= DEC_MIN_HI):
            continue
        if len(eng.buf) < 2000:            # mirrors latest_signal()'s own warmup gate
            continue
        npoll += 1
        try:
            feats = eng._features()
            tr = M1.run(feats, "NQ", PROFILE_A, realtime=True)
        except Exception:
            continue
        if not len(tr):
            continue
        recent = eng.buf.index.max()

        # -- surfacing: ANY ny_am row anywhere in tr this poll (irrespective of tail(3)) --
        ny = tr[tr.session == "ny_am"]
        for _, t in ny.iterrows():
            try:
                ets = _derive_fill_instant(feats.index, t["fill_bar"])
            except Exception:
                continue
            k = ets.isoformat()
            if k in ref_keys and k not in first_surface_poll:
                first_surface_poll[k] = recent

        # -- tail(3): what latest_signal() actually inspects --
        for _, t in tr.tail(3).iterrows():
            if t["session"] != "ny_am":
                continue
            try:
                ets = _derive_fill_instant(feats.index, t["fill_bar"])
            except Exception:
                continue
            k = ets.isoformat()
            if k in ref_keys and k not in first_tail3_poll:
                first_tail3_poll[k] = recent

        if npoll % 2000 == 0:
            print(f"      poll {npoll}  {ts}  surfaced={len(first_surface_poll)}/{len(ref)}  "
                  f"tail3={len(first_tail3_poll)}/{len(ref)}  ({time.time()-t0:.0f}s)", flush=True)

    print(f"      done: {npoll} decision polls, {len(first_surface_poll)}/{len(ref)} surfaced-ever-in-tr, "
          f"{len(first_tail3_poll)}/{len(ref)} reached tail(3)  ({time.time()-t0:.0f}s)", flush=True)

    ref["first_surface_poll"] = ref["k"].map(first_surface_poll)
    ref["first_tail3_poll"] = ref["k"].map(first_tail3_poll)
    ref["staleness_min"] = (
        (ref["first_tail3_poll"] - ref["fill_instant"]).dt.total_seconds() / 60.0
    )
    # staleness only grows poll-over-poll (recent grows, fill_instant fixed), so the FIRST
    # tail(3) appearance is the only/best shot -> freshness_passed uses it directly.
    ref["freshness_passed"] = ref["staleness_min"].notna() & (ref["staleness_min"] <= 10.0)
    surfaced_while_fresh = (
        ref["first_surface_poll"].notna()
        & (((ref["first_surface_poll"] - ref["fill_instant"]).dt.total_seconds() / 60.0) <= 10.0)
    )
    # clustering drop: it WAS visible in tr while still fresh, but never (or only once already
    # stale) made it into the 3-row window latest_signal() inspects -> a distinct failure mode
    # from plain staleness (where it isn't even visible in tr while fresh).
    ref["pushed_out_of_tail3"] = ref["missing"] & surfaced_while_fresh & (~ref["freshness_passed"])

    # ---------- 3) 1M-TRUTH R per trade, at its certified fill (for the auditor's 3-distribution step) ----------
    print("[3/4] 1m-truth re-fill per trade (tools_1m_truth_recert.walk_1m) ...", flush=True)
    d1, df5 = T1M.load_frames()
    mp = T1M.M1Map(d1, df5)
    idx5 = df5.index

    def r_1mtruth(row):
        ets = row["fill_instant"]
        pos = idx5.get_indexer([ets])[0]
        if pos < 0:
            pos = int(np.searchsorted(idx5.values, ets.to_datetime64(), side="left"))
            if pos >= len(idx5):
                return np.nan
        d = 1 if row["direction"] == "long" else -1
        entry, stop, target = float(row["entry"]), float(row["stop"]), float(row["target"])
        risk = abs(entry - stop)
        partials = [(entry + d * rl * risk, frac) for rl, frac in (PROFILE_A.get("partial") or [])]
        w = T1M.walk_1m(mp, int(pos), d, entry, stop, target, partials, max_5m_bars=M1.MAX_HOLD)
        return w[0] if w else np.nan

    ref["r_1mtruth"] = ref.apply(r_1mtruth, axis=1)
    ref["win"] = ref["r_result"] > 0

    # ---------- 4) write raw table ----------
    print("[4/4] writing raw CSV + summary ...", flush=True)
    out_cols = ["k", "missing", "fill_instant", "exit_instant", "hold_time_min",
                "first_surface_poll", "first_tail3_poll", "staleness_min", "freshness_passed",
                "pushed_out_of_tail3", "direction", "r_result", "r_1mtruth", "win"]
    out = ref[out_cols].rename(columns={"k": "key", "r_result": "backtest_R"})
    out = out.sort_values("fill_instant")
    out.to_csv(RAW_CSV, index=False)
    print(f"      -> {RAW_CSV}", flush=True)

    # ---------- SUMMARY ----------
    miss = ref[ref["missing"]].copy()
    n_miss = len(miss)
    print("\n================= INC-20260707 SUMMARY =================", flush=True)
    print(f"Backtest ny_am trades in window: {len(ref)}   missing(live): {n_miss}   "
          f"matched(live): {len(ref) - n_miss}", flush=True)

    # hypothesis test: staleness_min ~= hold_time_min ?
    both = miss.dropna(subset=["staleness_min", "hold_time_min"])
    if len(both) >= 2:
        corr = both["staleness_min"].corr(both["hold_time_min"])
        diff = (both["staleness_min"] - both["hold_time_min"])
        print(f"\nHYPOTHESIS TEST (surface-at-exit / staleness ~= hold_time), n={len(both)}:", flush=True)
        print(f"  corr(staleness_min, hold_time_min) = {corr:.3f}", flush=True)
        print(f"  mean staleness_min = {both['staleness_min'].mean():.1f}   "
              f"mean hold_time_min = {both['hold_time_min'].mean():.1f}", flush=True)
        print(f"  mean(staleness - hold_time) = {diff.mean():.1f}   "
              f"median = {diff.median():.1f}   std = {diff.std():.1f}", flush=True)
    else:
        corr = float("nan")
        print("\nHYPOTHESIS TEST: insufficient rows with both staleness_min and hold_time_min.", flush=True)

    # bucket the 23 misses into 3 mechanisms
    never_surfaced = miss[miss["first_surface_poll"].isna()]
    surfaced_but_no_tail3_fresh = miss[
        miss["first_surface_poll"].notna() & (~miss["freshness_passed"]) &
        (miss["pushed_out_of_tail3"])
    ]
    # staleness-driven: it DID surface but already stale (surfaced-not-fresh) or first
    # surfaced fresh yet was already stale by the time it reached tail3 with a LARGE gap
    # (i.e. the surface itself lagged past the 10-min window) -> surface-at-exit / hold-time driven.
    stale_at_surface = miss[
        miss["first_surface_poll"].notna() &
        (((miss["first_surface_poll"] - miss["fill_instant"]).dt.total_seconds() / 60.0) > 10.0)
    ]
    # poll-cadence granularity: reached tail3 fresh-ish but staleness just marginally over 10min
    # (missed by ~one 5m poll bar rather than a large surface-at-exit or clustering gap)
    poll_cadence = miss[
        miss["staleness_min"].notna() & (miss["staleness_min"] > 10.0) & (miss["staleness_min"] <= 15.0) &
        (~miss.index.isin(stale_at_surface.index))
    ]

    print(f"\nBUCKETS (of the {n_miss} missing):", flush=True)
    print(f"  never surfaced in tr at all (buffer window issue):     {len(never_surfaced)}", flush=True)
    print(f"  stale AT first surfacing (surface-at-exit / hold-time): {len(stale_at_surface)}", flush=True)
    print(f"  pushed_out_of_tail3 (visible+fresh but buried by tail(3) clustering): "
          f"{len(surfaced_but_no_tail3_fresh)}", flush=True)
    print(f"  poll-cadence granularity (staleness 10-15min, one bar late): {len(poll_cadence)}", flush=True)

    def bucket_stats(name, sub):
        if not len(sub):
            print(f"  {name:<55} n=0")
            return
        w = int((sub["r_result"] > 0).sum()); l = len(sub) - w
        print(f"  {name:<55} n={len(sub):2d}  sum(backtest_R)={sub['r_result'].sum():+7.2f}  "
              f"sum(r_1mtruth)={sub['r_1mtruth'].sum(skipna=True):+7.2f}  win/loss={w}/{l}", flush=True)

    print("\nPER-BUCKET R / WIN-LOSS:", flush=True)
    bucket_stats("never surfaced", never_surfaced)
    bucket_stats("stale at surface (surface-at-exit/hold-time)", stale_at_surface)
    bucket_stats("pushed_out_of_tail3 (clustering)", surfaced_but_no_tail3_fresh)
    bucket_stats("poll-cadence granularity (10-15min)", poll_cadence)
    bucket_stats("ALL 23 missing", miss)

    print(f"\nRaw table: {RAW_CSV}", flush=True)
    print(f"Elapsed: {time.time()-t0:.0f}s", flush=True)
    print("===========================================================\n", flush=True)


if __name__ == "__main__":
    main()
