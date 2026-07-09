"""OPTIMALITY audit — profile mix & filters on the DEPLOYED EOD eval harness, REAL Databento.

Reuses the validated engines ONLY:
  * apex_eval_deployed (H)  -> a_events / b_events / m_events generators, apply_daily_stop
  * apex_eval_eod (EOD)     -> eval_eod (real EOD-drawdown rule), day_starts, summarize
  * run_d1c_real (RD)       -> real Databento NQ 1m
  * funded_rules.APEX_ACCOUNTS["50K"]

Nothing about signal generation is changed. Filters are pure post-hoc transforms on the
unit-size event stream (drop events that fail a gate), then re-scaled and re-run through the
SAME eval_eod. Mixes are the same generators with some legs zeroed / re-sized.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))

import apex_eval_deployed as H
import apex_eval_eod as EOD
import funded_rules as FR
import run_d1c_real as RD

SPEC = FR.APEX_ACCOUNTS["50K"]
NY = "America/New_York"


def load_databento_5m():
    d1 = RD.load_1m()
    ag = lambda c, h: getattr(d1[c].resample("5min", label="left", closed="left"), h)()
    df5 = pd.DataFrame({"Open": ag("open", "first"), "High": ag("high", "max"),
                        "Low": ag("low", "min"), "Close": ag("close", "last"),
                        "Volume": ag("volume", "sum")}).dropna(subset=["Open"])
    idx = df5.index
    df5.index = idx.tz_localize(NY) if idx.tz is None else idx.tz_convert(NY)
    df5 = df5[~df5.index.duplicated(keep="last")].sort_index()
    df5.index.name = None
    return df5


def eval_mix(base, scale):
    """Scale unit events by per-src size, apply $550 daily stop, run EOD eval over rolling starts."""
    ev = [dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*scale[e["src"]],
               mfe=e["mfe"]*scale[e["src"]], mae=e["mae"]*scale[e["src"]])
          for e in base if scale.get(e["src"], 0) > 0]
    if not ev:
        return (0.0, 0.0, 0.0, None, 0)
    ev = H.apply_daily_stop(ev)
    starts = EOD.day_starts(ev)
    out = [EOD.eval_eod(ev, s, SPEC) for s in starts]
    ep, eb, ex, emd = EOD.summarize(out)
    return (ep, eb, ex, emd, len(starts))


def eval_events(ev_unit, scale):
    """Same as eval_mix but takes an already-filtered unit event list."""
    ev = [dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*scale[e["src"]],
               mfe=e["mfe"]*scale[e["src"]], mae=e["mae"]*scale[e["src"]])
          for e in ev_unit if scale.get(e["src"], 0) > 0]
    if not ev:
        return (0.0, 0.0, 0.0, None, 0)
    ev = H.apply_daily_stop(ev)
    starts = EOD.day_starts(ev)
    out = [EOD.eval_eod(ev, s, SPEC) for s in starts]
    return EOD.summarize(out) + (len(starts),)


def main():
    print("loading real Databento NQ 1m -> 5m…", flush=True)
    df5 = load_databento_5m()
    print(f"  bars {df5.index.min().date()} -> {df5.index.max().date()}  ({len(df5):,})", flush=True)

    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    A = H.a_events(df5); B = H.b_events(df5); M = H.m_events(df5)
    base = A + B + M
    print(f"  unit events: A={len(A)} B={len(B)} mm-days={len(M)}", flush=True)

    DEP = {"A": 10, "B": 5, "M": 6}
    dep = eval_mix(base, DEP)
    print(f"\n=== BASELINE deployed A10/B5/mm6: PASS {dep[0]:.1f}  BUST {dep[1]:.1f}  EXP {dep[2]:.1f}  med {dep[3]}  N={dep[4]}")

    # -------------------------------------------------------------------
    # PART 1 — PROFILE MIX at matched TOTAL CONTRACTS (fair throughput compare)
    # For each mix, sweep a size ladder; report each total-size's pass/bust/exp.
    # -------------------------------------------------------------------
    print("\n" + "="*78)
    print("PART 1 — PROFILE MIX  (EOD rule, $550 stop, 30d clock)")
    print("="*78)
    mixes = {
        "A-only":   lambda k: {"A": k},
        "A+B (2:1)":lambda k: {"A": 2*k, "B": k},
        "A+B+M(deployed-ratio 10:5:6 ~ 2:1:1.2)": lambda k: {"A": 2*k, "B": k, "M": max(1, round(1.2*k))},
    }
    for name, mk in mixes.items():
        print(f"\n  {name}")
        print(f"    {'k':>3}{'tot':>5}  {'A/B/M':>10}  | {'PASS%':>6}{'BUST%':>6}{'EXP%':>6}{'med':>5}")
        for k in range(1, 12):
            sc = mk(k)
            tot = sum(sc.values())
            if tot > 40:
                break
            ep, eb, ex, emd, n = eval_mix(base, sc)
            tag = f"{sc.get('A',0)}/{sc.get('B',0)}/{sc.get('M',0)}"
            print(f"    {k:>3}{tot:>5}  {tag:>10}  | {ep:>6.1f}{eb:>6.1f}{ex:>6.1f}{(emd or 0):>5}")

    # head-to-head at the deployed total (21 contracts) — best allocation of 21
    print("\n  HEAD-TO-HEAD near 21 total contracts:")
    cands = {
        "A21 (A-only)":              {"A": 21},
        "A14/B7 (A+B)":              {"A": 14, "B": 7},
        "A10/B5/M6 (DEPLOYED)":      {"A": 10, "B": 5, "M": 6},
        "A12/B6/M3":                 {"A": 12, "B": 6, "M": 3},
        "A8/B4/M8 (more momentum)":  {"A": 8, "B": 4, "M": 8},
    }
    print(f"    {'config':>26}  | {'PASS%':>6}{'BUST%':>6}{'EXP%':>6}{'med':>5}")
    for nm, sc in cands.items():
        ep, eb, ex, emd, n = eval_mix(base, sc)
        print(f"    {nm:>26}  | {ep:>6.1f}{eb:>6.1f}{ex:>6.1f}{(emd or 0):>5}")

    # -------------------------------------------------------------------
    # PART 2 — FILTERS on the DEPLOYED mix (A10/B5/mm6)
    # Each filter drops unit events failing a gate, then re-run EOD eval @ deployed sizing.
    # -------------------------------------------------------------------
    print("\n" + "="*78)
    print("PART 2 — FILTERS on DEPLOYED A10/B5/mm6  (delta vs 57.x baseline)")
    print("="*78)

    # daily context: 200d SMA regime + ATR vol percentile, keyed by NY date
    dd = df5.copy()
    daily = dd["Close"].resample("1D").last().dropna()
    sma200 = daily.rolling(200).mean()
    above = (daily > sma200)                          # regime: price above 200d SMA
    above_map = {d.date(): bool(v) for d, v in above.items()}
    # ATR(14) daily on 5m -> daily realized range proxy. Drop weekend/holiday NaN rows FIRST
    # (resample('1D') injects empty calendar days as NaN; leaving them poisons the rolling window).
    rng = (dd["High"].resample("1D").max() - dd["Low"].resample("1D").min()).dropna()
    atr = rng.rolling(14).mean()
    atr_pct = atr.rank(pct=True)
    vol_map = {d.date(): (float(v) if not np.isnan(v) else 0.5) for d, v in atr_pct.items()}
    nbit = sum(1 for v in vol_map.values() if v != 0.5)
    print(f"  [vol_map] {nbit}/{len(vol_map)} trading days with real ATR percentile", flush=True)

    def ev_date(e):
        return pd.Timestamp(e["ts"]).date()

    def ev_hour(e):
        t = pd.Timestamp(e["ts"]); return t.hour + t.minute/60.0

    base_pass = dep[0]

    def report(label, ev_unit):
        ep, eb, ex, emd, n = eval_events(ev_unit, DEP)
        d = ep - base_pass
        print(f"    {label:>40}  | PASS {ep:>5.1f} ({d:+5.1f})  BUST {eb:>5.1f}  EXP {ex:>5.1f}  med {emd or 0}")

    print(f"    {'baseline':>40}  | PASS {base_pass:>5.1f} ( +0.0)  BUST {dep[1]:>5.1f}  EXP {dep[2]:>5.1f}  med {dep[3]}")

    # --- 200d regime gate (direction-blind: only trade above / only below) ---
    report("regime: trade ONLY when px>200dSMA", [e for e in base if above_map.get(ev_date(e), True)])
    report("regime: trade ONLY when px<200dSMA", [e for e in base if not above_map.get(ev_date(e), False)])

    # --- vol gate (ATR percentile) ---
    for lo in (0.25, 0.33, 0.50):
        report(f"vol-gate: skip bottom {int(lo*100)}% ATR days", [e for e in base if vol_map.get(ev_date(e), 0.5) >= lo])
    report("vol-gate: skip TOP 25% ATR days", [e for e in base if vol_map.get(ev_date(e), 0.5) <= 0.75])
    report("vol-gate: mid band 25-90% ATR", [e for e in base if 0.25 <= vol_map.get(ev_date(e), 0.5) <= 0.90])

    # --- time-of-day restriction (A/B only; momentum is one EOD event, keep it) ---
    def tod_filter(ev, lo_h, hi_h):
        out = []
        for e in ev:
            if e["src"] == "M":
                out.append(e); continue
            h = ev_hour(e)
            if lo_h <= h < hi_h:
                out.append(e)
        return out
    report("time: A/B only 09:30-11:00 ET", tod_filter(base, 9.5, 11.0))
    report("time: A/B only 09:30-12:00 ET", tod_filter(base, 9.5, 12.0))
    report("time: A/B only 10:00-11:30 ET", tod_filter(base, 10.0, 11.5))

    # --- trade-count cap per day (cap total A+B+M entries per calendar day) ---
    def cap_per_day(ev, cap):
        ev_s = sorted(ev, key=lambda e: pd.Timestamp(e["ts"]))
        cnt = {}; out = []
        for e in ev_s:
            d = ev_date(e); cnt[d] = cnt.get(d, 0) + 1
            if cnt[d] <= cap:
                out.append(e)
        return out
    for cap in (2, 3, 4):
        report(f"trade-cap: max {cap} entries/day", cap_per_day(base, cap))

    # --- skip-after-N-losses (within a day: after N consecutive losers, skip rest of day) ---
    def skip_after_losses(ev, nloss):
        ev_s = sorted(ev, key=lambda e: pd.Timestamp(e["ts"]))
        out = []; streak = {}; halted = {}
        for e in ev_s:
            d = ev_date(e)
            if halted.get(d):
                continue
            out.append(e)
            if e["pnl"] < 0:
                streak[d] = streak.get(d, 0) + 1
                if streak[d] >= nloss:
                    halted[d] = True
            else:
                streak[d] = 0
        return out
    for nl in (1, 2, 3):
        report(f"skip rest of day after {nl} consec loss", skip_after_losses(base, nl))

    print("\n[note] filters are post-hoc gates on the unit event stream; signal generation unchanged.")
    print("[note] regime gate is direction-blind (suspend all trades that day), not long/short selective.")


if __name__ == "__main__":
    main()
