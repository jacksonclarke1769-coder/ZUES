"""Full Apex cash-flow timeline (EOD + Databento): eval-start -> PASS -> +$2.6k LOCK -> FIRST PAYOUT.
Reports median/mean CALENDAR days for each leg (success paths), with the success probabilities."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod as EOD
import apex_eval_eod_databento as DB
import funded_rules as FR

SPEC = FR.APEX_ACCOUNTS["50K"]
START, TRAIL, LOCK_EOD, FLOOR = 50_000.0, 2_500.0, 52_600.0, 50_100.0
SAFETY, CAP_FIRST, CAP_LATER, N_CAPPED, MIN_PAYOUT = 52_100.0, 2_000.0, 4_000.0, 5, 500.0
HORIZON_DAYS, DAILY_STOP = 18 * 30, -550.0
PRE = {"A": 4, "B": 2}; POST = {"A": 6, "B": 3}
TD = 5.0 / 7.0          # calendar->trading-day rough factor


def funded_timeline(ev, start, pre):
    """Returns days-to-lock and days-to-first-payout (from funded start), or None if bust/never.
    `pre` = grind (pre-lock) sizing; POST (A6/B3) is used after the floor locks."""
    thr = START - TRAIL; bal = START; peak = START; locked = False; d2l = None; d2pay = None
    npay = 0; t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0; cmonth = None
    tdays = set()
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if (ts - t0).days > HORIZON_DAYS:
            break
        if cur is None:
            cur = day
        if day != cur:
            peak = max(peak, bal)
            if not locked:
                if peak >= LOCK_EOD:
                    thr = FLOOR; locked = True; d2l = (ts - t0).days
                else:
                    thr = max(thr, peak - TRAIL)
            cur = day; dreal = 0.0
        m = (ts.year, ts.month)
        if cmonth is None:
            cmonth = m
        if m != cmonth:                                   # monthly payout window
            if locked and bal > SAFETY and len(tdays) >= 8:    # Apex: >=8 trading days before 1st payout
                cap = CAP_FIRST if npay < N_CAPPED else CAP_LATER
                w = min(bal - SAFETY, cap)
                if w >= MIN_PAYOUT:
                    bal -= w; npay += 1
                    if d2pay is None:
                        d2pay = (ts - t0).days
            cmonth = m
        if dreal <= DAILY_STOP:
            continue
        sc = (POST if locked else pre)[e["src"]]
        if bal + min(0.0, e["mae"]) * sc <= thr:
            return d2l, d2pay          # preserve lock/payout that ALREADY happened before this bust
        bal += e["pnl"] * sc; dreal += e["pnl"] * sc; tdays.add(day)
    return d2l, d2pay


def med_mean(x):
    return (np.median(x), np.mean(x)) if x else (float("nan"), float("nan"))


def main():
    print("loading Databento + building streams…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    A, B, M = H.a_events(df5), H.b_events(df5), H.m_events(df5)

    # ---- EVAL leg: days to PASS (deployed 10/5/6) ----
    sc = {"A": 10, "B": 5, "M": 6}
    eev = H.apply_daily_stop([dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*sc[e["src"]],
                                   mfe=e["mfe"]*sc[e["src"]], mae=e["mae"]*sc[e["src"]]) for e in A+B+M])
    est = EOD.day_starts(eev)
    eres = [EOD.eval_eod(eev, s, SPEC) for s in est]
    pass_days = [r[1] for r in eres if r[0] == "PASS"]
    p_pass = 100 * len(pass_days) / len(eres)
    ep_med, ep_mean = med_mean(pass_days)

    # ---- FUNDED legs: pass->lock and lock->payout (deployed A4/B2 -> A6/B3) ----
    fev = sorted(A + B, key=lambda e: e["ts"])
    last = pd.Timestamp(fev[-1]["ts"]); seen, fst = set(), []
    for i, e in enumerate(fev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days >= 270:
            fst.append(i)
    def line(lbl, med, mean, prob=None):
        pr = f"   (reached by {prob:.0f}%)" if prob is not None else ""
        return (f"  {lbl:<34}: {med:>5.0f} cal-days (~{med*TD:>4.0f} trading)   mean {mean:>5.0f}{pr}")

    print(f"\n================ APEX 50K PIPELINE TIMING · EOD · real Databento ================")
    print(f"  medians for the SUCCESS path at each stage. Eval = deployed A10/B5/mm6 (same for both).\n")
    print(line("eval start -> PASS", ep_med, ep_mean, p_pass))

    for label, pre in [("A4/B2  (deployed grind)", {"A": 4, "B": 2}),
                       ("A3/B2  (balanced grind)", {"A": 3, "B": 2}),
                       ("A2/B1  (max-survival grind)", {"A": 2, "B": 1})]:
        tl = [funded_timeline(fev, s, pre) for s in fst]
        d2l = [a for a, _ in tl if a is not None]
        paid = [(a, b) for a, b in tl if a is not None and b is not None]
        p_lock = 100 * len(d2l) / len(tl)
        p_pay = 100 * len(paid) / len(tl)
        l_med, l_mean = med_mean(d2l)
        lp_med, lp_mean = med_mean([b - a for a, b in paid])
        tot_med, tot_mean = med_mean([b for a, b in paid])
        print(f"\n  ---- funded grind {label}  ->  A6/B3 post-lock ----")
        print(line("funded start -> +$2.6k LOCK", l_med, l_mean, p_lock))
        print(line("LOCK -> first PAYOUT", lp_med, lp_mean))
        print(line("funded start -> first PAYOUT", tot_med, tot_mean, p_pay))
        print(f"  END-TO-END eval-buy -> first cash (median): ~{ep_med + tot_med:.0f} cal-days "
              f"(~{(ep_med+tot_med)/30.4:.1f}mo)  ·  P(eval+lock+pay) ≈ {p_pass/100*p_pay/100*100:.0f}% per eval")
    print("\n  [note] calendar days; monthly payout cadence + Apex 8-trading-day-min modelled. EOD + Databento.")


if __name__ == "__main__":
    main()
