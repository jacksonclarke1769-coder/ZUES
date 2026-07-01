"""Day-of-week SIZE-UP test — does weighting size toward the structurally-best days (Thu, Tue) beat
flat sizing on the Apex eval? Deployed EXIT3 config A10/B5/mm6, EOD rule, real Databento ~5y.
Reports per scheme: eval pass% / bust% / expire% / median days AND worst single-day $ (the tail the
$2k trailing floor cares about) + max contract size (Apex cap = 60 MNQ). Size-up scales pnl AND mae,
so bigger-day trades risk more against the floor — the honest tradeoff."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod as EOD
import apex_eval_eod_databento as DB
import funded_rules as FR
NY = "America/New_York"
SPEC = FR.APEX_ACCOUNTS["50K"]
EVAL = {"A": 10, "B": 5, "M": 6}

SCHEMES = {
    # ---- SIZE UP the strong days (adds tail risk) ----
    "flat (baseline)":      {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0},
    "Thu 1.5x (up)":        {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.5, 4: 1.0},
    # ---- DE-RISK the weak days (strong stay flat — reduces tail) ----
    "Mon/Wed 0.5x (trim)":  {0: 0.5, 1: 1.0, 2: 0.5, 3: 1.0, 4: 1.0},
    "skip Mon":             {0: 0.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0},
    "skip Mon+Wed":         {0: 0.0, 1: 1.0, 2: 0.0, 3: 1.0, 4: 1.0},
    "Tue+Thu ONLY":         {0: 0.0, 1: 1.0, 2: 0.0, 3: 1.0, 4: 0.0},
    "trim weak + Thu 1.25": {0: 0.5, 1: 1.0, 2: 0.5, 3: 1.25, 4: 1.0},
}


def build(base, mult):
    ev = []
    for e in base:
        dw = pd.Timestamp(e["ts"]).tz_convert(NY).dayofweek
        if dw >= 5 or mult.get(dw, 1.0) == 0.0:      # 0x = skip that weekday entirely
            continue
        s = EVAL[e["src"]] * mult.get(dw, 1.0)
        ev.append(dict(ts=e["ts"], src=e["src"], pnl=e["pnl"] * s, mae=e["mae"] * s))
    return H.apply_daily_stop(ev)


def worst_day(ev):
    by = {}
    for e in ev:
        d = pd.Timestamp(e["ts"]).tz_convert(NY).normalize()
        by[d] = by.get(d, 0.0) + e["pnl"]
    return min(by.values()) if by else 0.0


def main():
    print("loading real Databento…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    base = H.a_events(df5) + H.b_events(df5) + H.m_events(df5)
    print(f"  window {df5.index.min().date()} -> {df5.index.max().date()} · deployed A10/B5/mm6 · EOD rule\n")
    print(f"  {'scheme':>20} | {'pass%':>6} {'bust%':>6} {'exp%':>5} {'med d':>6} | {'worst day $':>11} {'max MNQ':>7}")
    print("  " + "-" * 78)
    for name, mult in SCHEMES.items():
        ev = build(base, mult)
        starts = EOD.day_starts(ev)
        p, b, x, m = EOD.summarize([EOD.eval_eod(ev, s, SPEC) for s in starts])
        wd = worst_day(ev)
        maxsz = int(max(sum(EVAL[k] * mult[dw] for k in EVAL) for dw in range(5)))  # peak day total MNQ
        print(f"  {name:>20} | {p:>6.1f} {b:>6.1f} {x:>5.1f} {str(m):>6} | ${wd:>10,.0f} {maxsz:>7}")
    print("\n  [worst day $ = deepest single-day loss (tail vs the $2k floor / $550 daily stop) · max MNQ vs Apex cap 60]")
    print("  [size-up scales BOTH wins and the single-trade MAE that can breach the trailing floor.]")


if __name__ == "__main__":
    main()
