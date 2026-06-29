"""Conditional eval pass-rate: P(pass | the eval LOSES its first N trades), last 12 months.

Uses the VALIDATED EOD harness + real Databento, deployed config A10/B5/mm6. Mirrors EOD.eval_eod
exactly but TRACES the taken-trade pnls so we can condition on the first-N outcomes. Reports, for
N = 0(baseline)/1/2/3/4 opening losses: how often it happens, the pass rate, and the median
days-to-pass (and how much longer than baseline).
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
EXPIRE_DAYS, DAILY_STOP, NY = EOD.EXPIRE_DAYS, EOD.DAILY_STOP, "America/New_York"


def load_databento_5m():
    d1 = RD.load_1m()
    ag = lambda c, h: getattr(d1[c].resample("5min", label="left", closed="left"), h)()
    df5 = pd.DataFrame({"Open": ag("open","first"),"High": ag("high","max"),"Low": ag("low","min"),
                        "Close": ag("close","last"),"Volume": ag("volume","sum")}).dropna(subset=["Open"])
    idx = df5.index
    df5.index = idx.tz_localize(NY) if idx.tz is None else idx.tz_convert(NY)
    df5 = df5[~df5.index.duplicated(keep="last")].sort_index(); df5.index.name = None
    return df5


def eval_eod_traced(ev, start, spec):
    """EXACT mirror of EOD.eval_eod, additionally returning the list of TAKEN-trade pnls."""
    sb, tr, tg = spec["start"], spec["trailing"], spec["target"]
    lock = sb + 100.0
    thr = sb - tr; bal = sb; peak_eod = sb; locked = False
    t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0; taken = []
    for i in range(start, len(ev)):
        e = ev[i]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if (ts - t0).days > EXPIRE_DAYS:
            return "EXPIRE", EXPIRE_DAYS, taken
        if cur is None:
            cur = day
        if day != cur:
            peak_eod = max(peak_eod, bal)
            if not locked:
                thr = max(thr, peak_eod - tr)
                if peak_eod - tr >= lock:
                    thr = lock; locked = True
            cur = day; dreal = 0.0
        if dreal <= DAILY_STOP:
            continue
        if bal + min(0.0, e["mae"]) <= thr:
            return "BUST", (ts - t0).days, taken
        bal += e["pnl"]; dreal += e["pnl"]; taken.append(e["pnl"])
        if bal >= sb + tg:
            return "PASS", (ts - t0).days, taken
    return "INCOMPLETE", None, taken


def main():
    full = "full" in sys.argv
    print("loading real Databento NQ 1m -> 5m…", flush=True)
    df5 = load_databento_5m()
    if not full:
        end = df5.index.max(); df5 = df5[df5.index >= end - pd.Timedelta(days=365)]
    span_days = (df5.index.max() - df5.index.min()).days
    print(f"  window {df5.index.min().date()} -> {df5.index.max().date()}  "
          f"({len(df5):,} 5m bars, ~{span_days/365:.1f}y) [{'FULL HISTORY' if full else 'last 12 months'}]\n", flush=True)

    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    base = H.a_events(df5) + H.b_events(df5) + H.m_events(df5)
    sc = {"A": 10, "B": 5, "M": 6}
    ev = [dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*sc[e["src"]],
               mfe=e["mfe"]*sc[e["src"]], mae=e["mae"]*sc[e["src"]]) for e in base if sc[e["src"]] > 0]
    ev = H.apply_daily_stop(ev)

    all_starts = EOD.day_starts(ev)
    # weekly = first eligible start in each ISO (year, week)
    wk, weekly = set(), []
    for s in all_starts:
        k = pd.Timestamp(ev[s]["ts"]).isocalendar()[:2]
        if k not in wk:
            wk.add(k); weekly.append(s)

    for label, starts in [("WEEKLY starts (one eval/week, as asked)", weekly),
                          ("ALL daily starts (max sample, robust probabilities)", all_starts)]:
        res = [eval_eod_traced(ev, s, SPEC) for s in starts]
        base_pass = [r for r in res if r[0] == "PASS"]
        base_rate = 100*len(base_pass)/len(res)
        base_med = int(np.median([r[1] for r in base_pass])) if base_pass else None
        print(f"=== {label} ===")
        print(f"  N evals: {len(res)}  |  baseline PASS {base_rate:.1f}%  |  median days-to-pass {base_med}")
        print(f"  {'opening':>16}{'# evals':>9}{'% of all':>9}{'PASS%':>8}{'med days':>9}{'Δ vs base':>10}")
        # first trade WON (contrast)
        won1 = [r for r in res if len(r[2]) >= 1 and r[2][0] > 0]
        wp = [r for r in won1 if r[0]=="PASS"]
        wmed = int(np.median([r[1] for r in wp])) if wp else None
        print(f"  {'won 1st trade':>16}{len(won1):>9}{100*len(won1)/len(res):>8.1f}%"
              f"{(100*len(wp)/len(won1) if won1 else 0):>7.1f}%{str(wmed):>9}"
              f"{(f'{wmed-base_med:+d}' if (wmed and base_med) else '—'):>10}")
        for n in (1, 2, 3, 4):
            # "lost first n trades" = at least n trades taken AND first n all < 0
            cond = [r for r in res if len(r[2]) >= n and all(p < 0 for p in r[2][:n])]
            if not cond:
                print(f"  {'lost first '+str(n):>16}{0:>9}{0:>8.1f}%{'—':>8}{'—':>9}{'—':>10}"); continue
            cp = [r for r in cond if r[0] == "PASS"]
            cmed = int(np.median([r[1] for r in cp])) if cp else None
            dlt = (f"{cmed-base_med:+d}" if (cmed and base_med) else "—")
            print(f"  {'lost first '+str(n):>16}{len(cond):>9}{100*len(cond)/len(res):>8.1f}%"
                  f"{(100*len(cp)/len(cond)):>7.1f}%{str(cmed):>9}{dlt:>10}")
        print()


if __name__ == "__main__":
    main()
