"""INC-20260707 RE-CERTIFICATION — STEP 0: Databento-native emission-achievability replay.

MEASUREMENT ONLY. Frozen strategy untouched (no entry/exit/session/filter/sizing change), no
arming, no hold-lift, no VPC wiring. NOT part of the test gate.

VENDOR RULE (single-vendor, everything Databento): this intentionally does NOT use
htf.build_features / D.load_spine (Dukascopy) -- that combination caused the PF-0.05 cross-vendor
artifact this incident traces back to. Both the full-history backtest-reference feature frame AND
the bar-by-bar live-engine drive below are built from DB.load_databento_5m()
(= apex_eval_eod_databento.load_databento_5m, the certified Databento 5m loader also used by
tools_1m_truth_recert.load_frames / tools_account_size_research.main).

METHOD: mirrors analysis_inc0707_missing.py's bar-by-bar ProfileAEngine drive (instrumenting `tr`
at every decision poll to classify surfacing / tail(3) clustering / staleness) with one change of
substance: the ground-truth "missing" (freshness-suppressed) flag is derived IN-LINE by replicating
latest_signal()'s own decision logic (ny_am check, acted_ts dedup, 10-min freshness gate) during
the same poll loop, rather than reading Dukascopy's out_parity.csv (out of bounds under the
single-vendor rule -- that file was built by test_signal_parity.py off htf.build_features /
D.load_spine). This is the same method test_signal_parity.py itself uses to get real "in_live"
ground truth (calling the production decision path), just Databento-fed and inlined here so the
per-trade surfacing/tail3/staleness diagnostics are available in the same pass.

Ground truth NOT re-derived here (per auditor): freshness gate = 10min, true tz-aware fill instant
via strategy_engine_profileA._derive_fill_instant, D1c/1m-truth walk conventions in
tools_1m_truth_recert. The 23 Dukascopy-dropped trades were classified IRREDUCIBLE (engine
surface-lag median 35min) in the prior (Dukascopy) run; this script's job is to confirm or refute
that the SAME pattern holds natively on Databento.

Usage:
  python3 databento_emission_replay.py --start 2025-06-01 --end 2025-12-01 --tag slice   # feasibility
  python3 databento_emission_replay.py --start 2021-01-01 --end 2026-07-01 --tag full    # full history
"""
import argparse, os, sys, time, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
sys.path.insert(0, os.path.join(FW, "engine"))
sys.path.insert(0, os.path.join(FW, "models"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, FW)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import model01_sweep_mss_fvg as M1                                   # noqa: E402  frozen model
import config                                                          # noqa: E402
import apex_eval_eod_databento as DB                                  # noqa: E402  CERTIFIED Databento 5m loader
from strategy_engine_profileA import ProfileAEngine, PROFILE_A, NY, _derive_fill_instant  # noqa: E402
import tools_1m_truth_recert as T1M                                    # noqa: E402

WARMUP_DAYS = 45
DEC_MIN_LO, DEC_MIN_HI = 9 * 60 + 30, 13 * 60 + 35

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "reports", "inc_20260707_recert")


def build_full_history_feats(df5):
    """Full-history causal feature frame off Databento 5m bars -- the SAME feature construction
    ProfileAEngine._features() uses live, just fed the full history instead of a rolling buffer
    (the pattern already certified in tools_account_size_research.main / tools_1m_truth_recert.main:
    `eng.buf = df5; feats = eng._features()`)."""
    eng = ProfileAEngine(config.STRAT)
    eng.buf = df5
    return eng._features()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-06-01")
    ap.add_argument("--end", default="2025-12-01")
    ap.add_argument("--tag", default=None, help="output filename suffix; use 'full' for the "
                     "full-history run so achievable_keys.csv gets the exact unsuffixed name")
    ap.add_argument("--skip-1m-truth", action="store_true",
                     help="skip the per-trade 1m-truth re-fill (faster, quick feasibility check)")
    args = ap.parse_args()

    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    TEST_START = pd.Timestamp(args.start, tz=NY)
    TEST_END = pd.Timestamp(args.end, tz=NY)
    tag = args.tag or f"{args.start}_{args.end}"
    RAW_CSV = os.path.join(OUT_DIR, f"emission_replay_raw_{tag}.csv")
    KEYS_CSV = (os.path.join(OUT_DIR, "achievable_keys.csv") if args.tag == "full"
                else os.path.join(OUT_DIR, f"achievable_keys_{tag}.csv"))

    print("[0/4] loading Databento 5m (DB.load_databento_5m, certified loader) ...", flush=True)
    df5 = DB.load_databento_5m()
    print(f"      bars {df5.index.min()} -> {df5.index.max()}  ({len(df5):,})", flush=True)

    # ---------- 1) BACKTEST REFERENCE (Databento-native full-history feats) ----------
    print("[1/4] building full-history backtest reference (Databento feats) ...", flush=True)
    feats_full = build_full_history_feats(df5)
    bt = M1.run(feats_full, "NQ", PROFILE_A)
    bt = bt[bt.session == "ny_am"].copy()
    bt["date"] = bt["date"].astype(str)
    bt["k"] = [_derive_fill_instant(feats_full.index, int(fb)).isoformat() for fb in bt["fill_bar"]]
    bt["fdate"] = pd.to_datetime(bt["date"]).dt.tz_localize(NY)
    ref = bt[(bt.fdate >= TEST_START) & (bt.fdate < TEST_END)].copy().reset_index(drop=True)
    print(f"      ny_am trades total={len(bt)}  in-window={len(ref)}", flush=True)

    ref["fill_instant"] = [_derive_fill_instant(feats_full.index, int(fb)) for fb in ref["fill_bar"]]
    ref["exit_instant"] = [feats_full.index[int(eb)] for eb in ref["exit_bar"]]
    ref["hold_time_min"] = (ref["exit_instant"] - ref["fill_instant"]).dt.total_seconds() / 60.0

    # ---------- 2) DRIVE LIVE ENGINE BAR-BY-BAR ON DATABENTO, REPLICATING latest_signal() ----------
    print("[2/4] feeding Databento bars into ProfileAEngine, replicating latest_signal() @ every "
          "poll (this IS the achievability ground truth -- no Dukascopy CSV involved) ...", flush=True)
    feed = df5[(df5.index >= TEST_START - pd.Timedelta(days=WARMUP_DAYS)) & (df5.index < TEST_END)]
    eng = ProfileAEngine({"nyam_start_min": 570, "nyam_end_min": 690, "flat_min": 870})
    eng.acted_ts = set(bt[bt.fdate < TEST_START]["k"])          # same warmup-dedup seed convention

    ref_keys = set(ref["k"])
    first_surface_poll = {}   # k -> recent at first poll where k appears ANYWHERE in tr (ny_am rows)
    first_tail3_poll = {}     # k -> recent at first poll where k appears in tr.tail(3)
    emitted = {}              # k -> True once the latest_signal()-replica logic actually emits it

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

        # -- tail(3): REPLICATES latest_signal()'s exact decision logic (ny_am check, acted_ts
        # dedup, 10-min freshness) so `emitted` is the achievability ground truth for this
        # Databento-native replay -- no external/Dukascopy CSV needed.
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
            if k in eng.acted_ts:
                continue
            if (recent - ets) <= pd.Timedelta(minutes=10):
                eng.acted_ts.add(k)
                if k in ref_keys:
                    emitted[k] = True

        if npoll % 2000 == 0:
            print(f"      poll {npoll}  {ts}  surfaced={len(first_surface_poll)}/{len(ref)}  "
                  f"tail3={len(first_tail3_poll)}/{len(ref)}  emitted={len(emitted)}/{len(ref)}  "
                  f"({time.time()-t0:.0f}s)", flush=True)

    print(f"      done: {npoll} decision polls, {len(first_surface_poll)}/{len(ref)} surfaced-ever-in-tr, "
          f"{len(first_tail3_poll)}/{len(ref)} reached tail(3), {len(emitted)}/{len(ref)} emitted "
          f"(achievable)  ({time.time()-t0:.0f}s)", flush=True)

    ref["first_surface_poll"] = ref["k"].map(first_surface_poll)
    ref["first_tail3_poll"] = ref["k"].map(first_tail3_poll)
    ref["staleness_min"] = (
        (ref["first_tail3_poll"] - ref["fill_instant"]).dt.total_seconds() / 60.0
    )
    ref["achievable"] = ref["k"].map(emitted).fillna(False).astype(bool)
    ref["missing"] = ~ref["achievable"]
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

    # ---------- 3) 1M-TRUTH R per trade (optional; skip for a fast feasibility check) ----------
    if not args.skip_1m_truth:
        print("[3/4] 1m-truth re-fill per trade (tools_1m_truth_recert.walk_1m, Databento 1m+5m) ...",
              flush=True)
        d1, df5b = T1M.load_frames()          # RD.load_1m() + DB.load_databento_5m() -- both Databento
        mp = T1M.M1Map(d1, df5b)
        idx5 = df5b.index

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
    else:
        print("[3/4] skipping 1m-truth re-fill (--skip-1m-truth) ...", flush=True)
        ref["r_1mtruth"] = np.nan
    ref["win"] = ref["r_result"] > 0

    # ---------- 4) write raw table + achievable-keys subset ----------
    print("[4/4] writing raw CSV + achievable-keys CSV + summary ...", flush=True)
    out_cols = ["k", "achievable", "missing", "fill_instant", "exit_instant", "hold_time_min",
                "first_surface_poll", "first_tail3_poll", "staleness_min", "freshness_passed",
                "pushed_out_of_tail3", "direction", "r_result", "r_1mtruth", "win"]
    out = ref[out_cols].rename(columns={"k": "key", "r_result": "backtest_R"})
    out = out.sort_values("fill_instant")
    out.to_csv(RAW_CSV, index=False)
    print(f"      -> {RAW_CSV}", flush=True)

    ach = out[out["achievable"]][["key"]].copy()
    ach.to_csv(KEYS_CSV, index=False)
    print(f"      -> {KEYS_CSV}  ({len(ach)} achievable keys)", flush=True)

    # ---------- SUMMARY ----------
    miss = ref[ref["missing"]].copy()
    n_miss = len(miss)
    print("\n================= DATABENTO EMISSION-REPLAY SUMMARY =================", flush=True)
    print(f"Window: {args.start} .. {args.end}", flush=True)
    print(f"Backtest ny_am trades in window: {len(ref)}   missing(suppressed): {n_miss}   "
          f"achievable: {len(ref) - n_miss}", flush=True)

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
        print("\nHYPOTHESIS TEST: insufficient rows with both staleness_min and hold_time_min.", flush=True)

    never_surfaced = miss[miss["first_surface_poll"].isna()]
    surfaced_but_no_tail3_fresh = miss[
        miss["first_surface_poll"].notna() & (~miss["freshness_passed"]) &
        (miss["pushed_out_of_tail3"])
    ]
    stale_at_surface = miss[
        miss["first_surface_poll"].notna() &
        (((miss["first_surface_poll"] - miss["fill_instant"]).dt.total_seconds() / 60.0) > 10.0)
    ]
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
    bucket_stats("ALL missing", miss)

    print(f"\nRaw table:       {RAW_CSV}", flush=True)
    print(f"Achievable keys: {KEYS_CSV}", flush=True)
    print(f"Elapsed: {time.time()-t0:.0f}s", flush=True)
    print("===========================================================\n", flush=True)


if __name__ == "__main__":
    main()
