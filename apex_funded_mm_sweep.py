"""Sweep the FUNDED momentum (continuation) size — EOD + Databento. Funded base A4/B2 grind -> A6/B3
post-lock. Pass 1: hold grind mm=0, sweep POST-LOCK mm (clean income win). Pass 2: at the best post-lock
mm, sweep GRIND mm. Rank by E[payout|funded] while watching lock% (survival) and income/mo."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB
import apex_funded_momentum_test as MT

POST_MM = [0, 2, 3, 4, 5, 6, 8]
GRIND_MM = [0, 1, 2, 3, 4, 5]


def evaluate(ev, fst, pre, post):
    out = [MT.life(ev, s, pre, post) for s in fst]
    n = len(out); lk = [o for o in out if o["locked"]]
    p_lock = 100 * len(lk) / n
    pay_all = np.mean([o["payout"] for o in out])
    pay_lk = np.mean([o["payout"] for o in lk]) if lk else 0.0
    mo = np.mean([o["months"] for o in lk]) if lk else 0.0
    inc = pay_lk / mo if mo else 0.0
    return p_lock, inc, pay_all


def main():
    print("loading Databento + A/B/Momentum streams…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5) + H.m_events(df5), key=lambda e: e["ts"])
    last = pd.Timestamp(ev[-1]["ts"]); seen, fst = set(), []
    for i, e in enumerate(ev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days >= 270:
            fst.append(i)

    print(f"\n  ===== PASS 1 · POST-LOCK momentum size (grind mm=0, base A6/B3) =====")
    print(f"  {'post mm':>8}{'lock%':>8}{'income/mo':>12}{'E[payout]':>12}")
    best_post, best_pay = 0, -1
    for x in POST_MM:
        lk, inc, pay = evaluate(ev, fst, {"A": 4, "B": 2, "M": 0}, {"A": 6, "B": 3, "M": x})
        star = "  <-current" if x == 0 else ""
        print(f"  {x:>8}{lk:>8.1f}{inc:>12,.0f}{pay:>12,.0f}{star}")
        if pay > best_pay:
            best_pay, best_post = pay, x
    print(f"  -> best POST-LOCK mm = {best_post} (E[payout] ${best_pay:,.0f})")

    print(f"\n  ===== PASS 2 · GRIND momentum size (post-lock mm={best_post}, base A4/B2) =====")
    print(f"  {'grind mm':>8}{'lock%':>8}{'income/mo':>12}{'E[payout]':>12}")
    best_grind, best_pay2 = 0, -1
    for y in GRIND_MM:
        lk, inc, pay = evaluate(ev, fst, {"A": 4, "B": 2, "M": y}, {"A": 6, "B": 3, "M": best_post})
        star = "  <-current(0)" if y == 0 else ""
        print(f"  {y:>8}{lk:>8.1f}{inc:>12,.0f}{pay:>12,.0f}{star}")
        if pay > best_pay2:
            best_pay2, best_grind = pay, y
    print(f"  -> best GRIND mm = {best_grind} (E[payout] ${best_pay2:,.0f})")

    lk0, inc0, pay0 = evaluate(ev, fst, {"A": 4, "B": 2, "M": 0}, {"A": 6, "B": 3, "M": 0})
    print(f"\n  ===== RECOMMENDED funded momentum: grind mm{best_grind} / post-lock mm{best_post} =====")
    lkb, incb, payb = evaluate(ev, fst, {"A": 4, "B": 2, "M": best_grind}, {"A": 6, "B": 3, "M": best_post})
    print(f"  current (mm off): lock {lk0:.1f}% · ${inc0:,.0f}/mo · E[payout] ${pay0:,.0f}")
    print(f"  optimised       : lock {lkb:.1f}% · ${incb:,.0f}/mo · E[payout] ${payb:,.0f}  "
          f"(+{100*(payb-pay0)/pay0:.0f}% payout, {lkb-lk0:+.1f}pt lock)")
    print("\n  [note] EOD + Databento; momentum daily-aggregate proxy; ranked by E[payout|funded].")


if __name__ == "__main__":
    main()
