"""DEFINITIVE Apex eval pass-rate — EOD drawdown rule, REAL DATABENTO data.

Resolves the residual gap: apex_eval_eod.py used the Dukascopy proxy (pessimistic for Profile A:
PF 1.17 proxy vs 1.46 real). This rebuilds A/B/momentum from real Databento CME 1m (the 2026-06-24
revalidation source, run_d1c_real.load_1m) and reruns the EOD harness. Operator-confirmed: eval = EOD.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))

import apex_eval_deployed as H            # stream generators (a_events/b_events/m_events, apply_daily_stop, eval_from)
import apex_eval_eod as EOD               # eval_eod, eval_eod_closeonly, day_starts, summarize
import funded_rules as FR
import run_d1c_real as RD                 # real Databento NQ 1m loader

SPEC = FR.APEX_ACCOUNTS["50K"]
NY = "America/New_York"
CONFIGS = [(14, 7, 8), (12, 6, 7), (10, 5, 6), (8, 4, 5), (6, 3, 4),
           (5, 3, 3), (4, 2, 2), (4, 2, 0)]


def load_databento_5m():
    d1 = RD.load_1m()
    ag = lambda c, h: getattr(d1[c].resample("5min", label="left", closed="left"), h)()
    df5 = pd.DataFrame({"Open": ag("open", "first"), "High": ag("high", "max"),
                        "Low": ag("low", "min"), "Close": ag("close", "last"),
                        "Volume": ag("volume", "sum")}).dropna(subset=["Open"])
    idx = df5.index
    df5.index = idx.tz_localize(NY) if idx.tz is None else idx.tz_convert(NY)
    df5 = df5[~df5.index.duplicated(keep="last")].sort_index()
    df5.index.name = None                       # so m_events' reset_index()->"index" rename works
    return df5


def main():
    print("loading real Databento NQ 1m -> 5m…", flush=True)
    df5 = load_databento_5m()
    print(f"  bars {df5.index.min().date()} -> {df5.index.max().date()}  ({len(df5):,})", flush=True)

    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    print("building A/B/momentum streams on real data…", flush=True)
    base = H.a_events(df5) + H.b_events(df5) + H.m_events(df5)
    nA = sum(1 for e in base if e["src"] == "A"); nB = sum(1 for e in base if e["src"] == "B")
    nM = sum(1 for e in base if e["src"] == "M")
    print(f"  events: A={nA} B={nB} mm-days={nM}", flush=True)

    print(f"\n  Apex 50K EOD · $2.5k trail / $3k target · $550 stop · 30-day clock · REAL DATABENTO")
    print(f"  {'A/B/mm':>10}{'MNQ':>5}  |  {'EOD-real PASS%':>16}{'BUST%':>7}{'EXP%':>6}{'med':>5}  |  {'(intraday)':>11}{'(pure-EOD)':>11}")
    print("  " + "-" * 80)
    rows = []
    for (a, b, m) in CONFIGS:
        sc = {"A": a, "B": b, "M": m}
        ev = [dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*sc[e["src"]],
                   mfe=e["mfe"]*sc[e["src"]], mae=e["mae"]*sc[e["src"]]) for e in base if sc[e["src"]] > 0]
        ev = H.apply_daily_stop(ev)
        starts = EOD.day_starts(ev)
        ep, eb, ex, emd = EOD.summarize([EOD.eval_eod(ev, s, SPEC) for s in starts])
        ip, _, _, _ = EOD.summarize([H.eval_from(ev, s, SPEC) for s in starts])
        cp, _, _, _ = EOD.summarize([EOD.eval_eod_closeonly(ev, s, SPEC) for s in starts])
        star = " <-DEPLOYED" if (a, b, m) == (10, 5, 6) else ""
        rows.append((a, b, m, ep))
        print(f"  {f'{a}/{b}/{m}':>10}{a+b+m:>5}  |  {ep:>16.1f}{eb:>7.1f}{ex:>6.1f}{emd or 0:>5}  |  "
              f"{ip:>11.1f}{cp:>11.1f}{star}")
    dep = next((r for r in rows if (r[0], r[1], r[2]) == (10, 5, 6)), None)
    if dep:
        print(f"\n  DEPLOYED A10/B5/mm6 on real Databento, EOD rule: {dep[3]:.1f}% pass")
    print("  [note] real CME data + EOD rule = the trustworthy number. Per-trade give-back proxy on the")
    print("         intraday-liquidation leg is slightly optimistic; verify size/rules vs your Apex contract.")


if __name__ == "__main__":
    main()
