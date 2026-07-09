"""Robustness of the top OPTIMALITY candidates: per-year + last-12mo, plus trade-cap decomposition."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod as EOD
import funded_rules as FR
import opt_eval_mix_filters as O

SPEC = FR.APEX_ACCOUNTS["50K"]
DEP = {"A": 10, "B": 5, "M": 6}


def run(ev_unit, scale, lo=None, hi=None):
    ev = [dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*scale[e["src"]],
               mfe=e["mfe"]*scale[e["src"]], mae=e["mae"]*scale[e["src"]])
          for e in ev_unit if scale.get(e["src"], 0) > 0]
    if lo is not None:
        ev = [e for e in ev if lo <= pd.Timestamp(e["ts"]) < hi]
    if not ev:
        return (0, 0, 0, None, 0)
    ev = H.apply_daily_stop(ev)
    starts = EOD.day_starts(ev)
    if not starts:
        return (0, 0, 0, None, 0)
    return EOD.summarize([EOD.eval_eod(ev, s, SPEC) for s in starts]) + (len(starts),)


def ev_date(e): return pd.Timestamp(e["ts"]).date()


def cap_all(ev, cap):
    s = sorted(ev, key=lambda e: pd.Timestamp(e["ts"])); cnt = {}; out = []
    for e in s:
        d = ev_date(e); cnt[d] = cnt.get(d, 0) + 1
        if cnt[d] <= cap: out.append(e)
    return out


def cap_ab_only(ev, cap):
    """Cap A/B entries per day but ALWAYS keep momentum."""
    s = sorted(ev, key=lambda e: pd.Timestamp(e["ts"])); cnt = {}; out = []
    for e in s:
        if e["src"] == "M": out.append(e); continue
        d = ev_date(e); cnt[d] = cnt.get(d, 0) + 1
        if cnt[d] <= cap: out.append(e)
    return out


def skip_after(ev, nloss):
    s = sorted(ev, key=lambda e: pd.Timestamp(e["ts"])); out = []; streak = {}; halt = {}
    for e in s:
        d = ev_date(e)
        if halt.get(d): continue
        out.append(e)
        if e["pnl"] < 0:
            streak[d] = streak.get(d, 0)+1
            if streak[d] >= nloss: halt[d] = True
        else: streak[d] = 0
    return out


def main():
    df5 = O.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    A = H.a_events(df5); B = H.b_events(df5); M = H.m_events(df5)
    base = A + B + M
    print(f"unit events A={len(A)} B={len(B)} M={len(M)}")

    # momentum survival under cap-2-all
    c2 = cap_all(base, 2)
    nM_c2 = sum(1 for e in c2 if e["src"] == "M")
    print(f"momentum events: full={len(M)}  surviving cap-2-all={nM_c2}  (dropped {len(M)-nM_c2})")

    NY = "America/New_York"
    last12_lo = pd.Timestamp("2025-06-22", tz=NY); last12_hi = pd.Timestamp("2026-06-23", tz=NY)
    years = [(pd.Timestamp(f"{y}-01-01", tz=NY), pd.Timestamp(f"{y+1}-01-01", tz=NY), str(y))
             for y in range(2022, 2026)]

    variants = {
        "DEPLOYED A10/B5/M6":        ("mix", DEP, base),
        "mix A8/B4/M8":              ("mix", {"A":8,"B":4,"M":8}, base),
        "cap-2 ALL (drops M busy)":  ("mix", DEP, cap_all(base, 2)),
        "cap-2 A/B only (keep M)":   ("mix", DEP, cap_ab_only(base, 2)),
        "cap-3 A/B only (keep M)":   ("mix", DEP, cap_ab_only(base, 3)),
        "regime px>200dSMA":         ("mix", DEP, [e for e in base if O_above(df5).get(ev_date(e), True)]),
        "skip-after-2-loss":         ("mix", DEP, skip_after(base, 2)),
        "time 09:30-11:00 A/B":      ("mix", DEP, [e for e in base if e["src"]=="M" or 9.5<=(pd.Timestamp(e['ts']).hour+pd.Timestamp(e['ts']).minute/60)<11.0]),
    }

    print(f"\n{'variant':>28} | {'FULL':>6} | {'L12mo':>6} | " + " ".join(f"{y:>5}" for *_ ,y in years))
    print("-"*90)
    for name, (_, sc, ev_unit) in variants.items():
        full = run(ev_unit, sc)[0]
        l12 = run(ev_unit, sc, last12_lo, last12_hi)[0]
        pys = [run(ev_unit, sc, a, b)[0] for a, b, _ in years]
        print(f"{name:>28} | {full:>6.1f} | {l12:>6.1f} | " + " ".join(f"{p:>5.1f}" for p in pys))


_above_cache = {}
def O_above(df5):
    if "m" in _above_cache: return _above_cache["m"]
    daily = df5["Close"].resample("1D").last().dropna()
    sma = daily.rolling(200).mean()
    m = {d.date(): bool(v) for d, v in (daily > sma).items()}
    _above_cache["m"] = m
    return m


if __name__ == "__main__":
    main()
