"""
SIGNAL-PARITY TEST — production ProfileAEngine vs the backtest engine.

Objective: prove the live engine (35-day rolling buffer, fed bar-by-bar as in
production) emits the EXACT same signals as the full-history backtest M1.run.
We test parity only, NOT profitability.

Method:
  1. Backtest reference = htf.build_features(full history) -> M1.run -> ny_am trades.
  2. Live = real ProfileAEngine, bars fed sequentially over a test window with a
     35-day+ warmup; the real latest_signal() is called on every NY-AM bar.
  3. For every trade compare: direction, entry, stop, target, sweep level (via
     swept_px / stop), OTE level (via entry), liquidity name, MSS (implied by
     identical entry/stop/target). Report count/signal/entry/stop differences.
Acceptance: 0 mismatches (no missing, no extra, no field diff).
"""
import os, sys, time
import pandas as pd, numpy as np

FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
sys.path.insert(0, os.path.join(FW, "engine"))
sys.path.insert(0, os.path.join(FW, "models"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data as D, htf, model01_sweep_mss_fvg as M1
from strategy_engine_profileA import ProfileAEngine, PROFILE_A, NY, _derive_fill_instant

TEST_START = pd.Timestamp("2025-06-01", tz=NY)
TEST_END   = pd.Timestamp("2025-12-01", tz=NY)
WARMUP_DAYS = 45                      # > BUFFER_DAYS(35) so the buffer is full at TEST_START
# Decision window must extend past the latest possible fill so late-filling backtest
# trades are not falsely reported as "missing": a fill can land W_MSS+W_FILL bars after
# a sweep that itself can occur up to 11:30 ET -> call through ~13:35 ET.
DEC_MIN_LO, DEC_MIN_HI = 9 * 60 + 30, 13 * 60 + 35


def key(date, t):
    return f"{date} {t}"


def main():
    t0 = time.time()
    # ---------- 1) BACKTEST REFERENCE ----------
    print("[1/3] building full-history backtest reference ...", flush=True)
    f = htf.build_features("NQ", "5m"); f.index.name = "timestamp"
    bt = M1.run(f, "NQ", PROFILE_A)
    bt = bt[bt.session == "ny_am"].copy()
    bt["date"] = bt["date"].astype(str)
    # INC-20260707: key BOTH the reference and the warmup-dedup seed off the SAME derivation
    # latest_signal() now uses — _derive_fill_instant(feats.index, fill_bar).isoformat() — NOT a
    # parallel f"{date} {time}" string reconstruction. Two code paths independently building "the
    # same" timestamp is exactly how the INC-20260706-1141 / fafe12d drift hid; seeding this
    # parity tool (whose job is to DETECT drift) from a lookalike would reintroduce that risk.
    # f.index is tz-aware NY and bt.fill_bar positionally indexes it, so this resolves to the true
    # fill instant — byte-identical to the live ts_signal, which is _derive_fill_instant(<live
    # feats.index>, fill_bar).isoformat() for the same fill.
    bt["k"] = [_derive_fill_instant(f.index, int(fb)).isoformat() for fb in bt["fill_bar"]]
    bt["fdate"] = pd.to_datetime(bt["date"]).dt.tz_localize(NY)   # calendar date (correct for ny_am)
    ref = bt[(bt.fdate >= TEST_START) & (bt.fdate < TEST_END)].copy()
    ref_map = {r["k"]: r for _, r in ref.iterrows()}
    print(f"      ny_am trades total={len(bt)}  in test window [{TEST_START.date()}..{TEST_END.date()})={len(ref)}", flush=True)

    # ---------- 2) DRIVE LIVE ENGINE BAR-BY-BAR ----------
    print("[2/3] feeding bars into live ProfileAEngine sequentially ...", flush=True)
    base = D.load_spine("NQ", "5m")                     # raw 5m bars, NY-tz
    feed = base[(base.index >= TEST_START - pd.Timedelta(days=WARMUP_DAYS)) & (base.index < TEST_END)]
    eng = ProfileAEngine({"nyam_start_min": 570, "nyam_end_min": 690, "flat_min": 870})

    # prime acted_ts with every ny_am trade that filled BEFORE the window, so stale
    # warmup trades in tail(3) are not falsely emitted on the first real call.
    eng.acted_ts = set(bt[bt.fdate < TEST_START]["k"])

    live = {}                       # k -> signal dict
    O, H, L, C = base.columns.get_indexer(["Open", "High", "Low", "Close"])
    vals = feed[["Open", "High", "Low", "Close"]].values
    idx = feed.index
    ncall = 0
    for n in range(len(feed)):
        ts = idx[n]
        eng.add_bar(ts, vals[n, 0], vals[n, 1], vals[n, 2], vals[n, 3], 0)
        if ts < TEST_START:
            continue
        m = ts.hour * 60 + ts.minute
        if not (DEC_MIN_LO <= m <= DEC_MIN_HI):
            continue
        sig = eng.latest_signal()
        ncall += 1
        if sig is not None:
            live[sig["ts_signal"]] = sig
        if n % 4000 == 0:
            print(f"      bar {n}/{len(feed)} {ts}  live_signals={len(live)}  calls={ncall}  ({time.time()-t0:.0f}s)", flush=True)
    print(f"      done feed: {len(feed)} bars, {ncall} latest_signal() calls, {len(live)} live signals ({time.time()-t0:.0f}s)", flush=True)

    # ---------- 3) DIFF ----------
    print("[3/3] comparing live vs backtest ...\n", flush=True)
    ref_keys, live_keys = set(ref_map), set(live)
    missing = sorted(ref_keys - live_keys)     # backtest trade NOT reproduced live
    extra   = sorted(live_keys - ref_keys)     # live trade NOT in backtest
    common  = sorted(ref_keys & live_keys)

    def approx(a, b, tol=1e-6):
        return abs(float(a) - float(b)) <= tol

    field_mismatch = []
    n_dir = n_entry = n_stop = n_tgt = 0
    for k in common:
        r, s = ref_map[k], live[k]
        diffs = []
        if r["direction"] != s["side"]:           n_dir += 1;   diffs.append(f"dir {r['direction']}/{s['side']}")
        if not approx(r["entry"], s["entry"]):     n_entry += 1; diffs.append(f"entry {r['entry']}/{s['entry']}")
        if not approx(r["stop"], s["stop"]):       n_stop += 1;  diffs.append(f"stop {r['stop']}/{s['stop']}")
        if not approx(r["target"], s["target"]):   n_tgt += 1;   diffs.append(f"target {r['target']}/{s['target']}")
        if r["liq_swept"] != s["liq"]:                           diffs.append(f"liq {r['liq_swept']}/{s['liq']}")
        if diffs:
            field_mismatch.append((k, diffs))

    nref = len(ref) or 1
    total_signal_diff = len(missing) + len(extra) + len(field_mismatch)

    print("================= SIGNAL-PARITY RESULT =================")
    print(f"Window:                  {TEST_START.date()} .. {TEST_END.date()}")
    print(f"Backtest ny_am trades:   {len(ref)}")
    print(f"Live signals emitted:    {len(live)}")
    print(f"Matched (same key):      {len(common)}")
    print(f"Missing (bt, not live):  {len(missing)}")
    print(f"Extra   (live, not bt):  {len(extra)}")
    print(f"Field mismatches:        {len(field_mismatch)}")
    print("-------------------------------------------------------")
    print(f"Trade count difference:  {len(live) - len(ref):+d}")
    print(f"Signal difference %:     {100*total_signal_diff/nref:.2f}%   (missing+extra+fieldmismatch / bt)")
    print(f"Entry difference %:      {100*n_entry/(len(common) or 1):.2f}%   (of matched trades)")
    print(f"Stop  difference %:      {100*n_stop/(len(common) or 1):.2f}%   (of matched trades)")
    print(f"Direction diff %:        {100*n_dir/(len(common) or 1):.2f}%")
    print(f"Target diff %:           {100*n_tgt/(len(common) or 1):.2f}%")
    print("-------------------------------------------------------")
    verdict = "PASS — 0 mismatches" if total_signal_diff == 0 else "FAIL — DEPLOYMENT BLOCKER"
    print(f"VERDICT: {verdict}")
    print("=======================================================\n")

    if missing:
        print(f"-- MISSING (first 15 of {len(missing)}): backtest trades the live engine did NOT emit --")
        for k in missing[:15]:
            r = ref_map[k]
            print(f"   {k}  {r['direction']:5} entry={r['entry']} stop={r['stop']} tgt={r['target']} liq={r['liq_swept']}")
    if extra:
        print(f"\n-- EXTRA (first 15 of {len(extra)}): live signals with no backtest trade --")
        for k in extra[:15]:
            s = live[k]
            print(f"   {k}  {s['side']:5} entry={s['entry']} stop={s['stop']} tgt={s['target']} liq={s['liq']}")
    if field_mismatch:
        print(f"\n-- FIELD MISMATCH (first 15 of {len(field_mismatch)}) --")
        for k, diffs in field_mismatch[:15]:
            print(f"   {k}: " + "; ".join(diffs))

    # persist full detail
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out_parity.csv")
    rows = []
    for k in sorted(ref_keys | live_keys):
        r = ref_map.get(k); s = live.get(k)
        rows.append(dict(key=k,
                         in_bt=r is not None, in_live=s is not None,
                         bt_dir=r["direction"] if r is not None else "",
                         live_dir=s["side"] if s is not None else "",
                         bt_entry=r["entry"] if r is not None else np.nan,
                         live_entry=s["entry"] if s is not None else np.nan,
                         bt_stop=r["stop"] if r is not None else np.nan,
                         live_stop=s["stop"] if s is not None else np.nan,
                         bt_target=r["target"] if r is not None else np.nan,
                         live_target=s["target"] if s is not None else np.nan))
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"detail -> {out}")
    return total_signal_diff


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
