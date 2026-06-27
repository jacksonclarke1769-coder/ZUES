"""Beyond sizing: can a tighter DAILY STOP or a CUSHION BRAKE raise eval pass / funded reach-lock?
EOD rule + real Databento. daily stop tuning caps bad days (fewer trail breaches); cushion brake trades
small when the cushion (bal - threshold) is thin (early, where most busts happen) then full once banked."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB

TRAIL, LOCK_EOD, FLOOR, EXPIRE = 2500.0, 52_600.0, 50_100.0, 30


def walk(ev, start, sizing, daily_stop, target, until_lock, brake=None):
    sb = 50000.0; thr = sb - TRAIL; bal = sb; peak = sb; locked = False
    t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0
    for i in range(start, len(ev)):
        e = ev[i]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if day != cur:
            if cur is not None:
                dd = (ts - t0).days
                if not until_lock and dd > EXPIRE:
                    return "EXPIRE"
                if until_lock and dd > 18 * 30:
                    return "NOLOCK"
                peak = max(peak, bal)
                if not locked:
                    thr = max(thr, peak - TRAIL)
                    if peak >= LOCK_EOD:
                        if until_lock:
                            return "LOCK"
                        thr = FLOOR; locked = True
            cur = day; dreal = 0.0
        if dreal <= daily_stop:
            continue
        s = sizing.get(e["src"], 0)
        if s == 0:
            continue
        if brake and (bal - thr) < brake[0]:
            s *= brake[1]
        if bal + min(0.0, e["mae"]) * s <= thr:
            return "BUST"
        bal += e["pnl"] * s; dreal += e["pnl"] * s
        if not until_lock and bal >= sb + target:
            return "PASS"
    return "NOLOCK" if until_lock else "INCOMPLETE"


def starts_for(ev, runway):
    seen, out = set(), []; last = pd.Timestamp(ev[-1]["ts"])
    for i, e in enumerate(ev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days >= runway:
            out.append(i)
    return out


def rate(ev, st, sizing, ds, target, until_lock, key, brake=None):
    r = [walk(ev, s, sizing, ds, target, until_lock, brake) for s in st]
    return 100 * sum(1 for x in r if x == key) / len(r)


def main():
    print("loading Databento + streams…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5) + H.m_events(df5), key=lambda e: e["ts"])
    est = starts_for(ev, EXPIRE); fst = starts_for(ev, 270)
    EVAL = {"A": 10, "B": 5, "M": 6}
    F0 = {"A": 4, "B": 2, "M": 0}; F2 = {"A": 4, "B": 2, "M": 2}

    print(f"\n  === LEVER 1 · DAILY-STOP sweep (EOD + Databento) ===")
    print(f"  {'daily stop':>11}{'eval PASS%':>12}{'fund lock A4/B2':>17}{'fund lock A4/B2+mm2':>21}")
    for ds in (-250, -350, -450, -550, -700, -900):
        ep = rate(ev, est, EVAL, ds, 3000, False, "PASS")
        f0 = rate(ev, fst, F0, ds, 0, True, "LOCK")
        f2 = rate(ev, fst, F2, ds, 0, True, "LOCK")
        star = "  <-current" if ds == -550 else ""
        print(f"  ${ds:>9,.0f}{ep:>12.1f}{f0:>17.1f}{f2:>21.1f}{star}")

    print(f"\n  === LEVER 2 · CUSHION BRAKE (size×factor when cushion < level), $550 stop ===")
    print(f"  {'brake':>22}{'eval PASS%':>12}{'fund lock A4/B2+mm2':>21}")
    ep0 = rate(ev, est, EVAL, -550, 3000, False, "PASS")
    f20 = rate(ev, fst, F2, -550, 0, True, "LOCK")
    print(f"  {'none (baseline)':>22}{ep0:>12.1f}{f20:>21.1f}")
    for lvl, fac in [(1000, 0.5), (1500, 0.5), (1500, 0.33), (2000, 0.5), (2000, 0.33)]:
        ep = rate(ev, est, EVAL, -550, 3000, False, "PASS", brake=(lvl, fac))
        f2 = rate(ev, fst, F2, -550, 0, True, "LOCK", brake=(lvl, fac))
        print(f"  {f'cushion<${lvl:,} ×{fac}':>22}{ep:>12.1f}{f2:>21.1f}")
    print("\n  [note] EOD + Databento, proxy engine (validated within 1pt of joint sim).")


if __name__ == "__main__":
    main()
