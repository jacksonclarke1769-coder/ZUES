"""APEX FUNDED-side survival sim — the piece the eval sweep can't answer.

A passed eval becomes a PA (funded) account: start $50k, the $2,500 trailing drawdown STILL LIVE,
size A4/B2 (momentum OFF on funded per the tier). Two phases:
  PHASE 1 (grind to lock): trade A4/B2; the trail can still bust you (same trap, smaller size).
     The floor LOCKS at $50,100 once the unrealized peak hits $52,600 (banked ~+$2.6k) -> near-unbustable.
  PHASE 2 (income): scale to A6/B3; draw monthly payouts down to a $52,100 safety net (first 5 capped
     $2k, then $4k); the account dies only if balance gives back to the locked $50,100 floor.

Engine = the validated ApexAcct (reproduces apex_sim exactly). Streams generated ONCE at size 1, rescaled
per phase. The $550 daily stop applies on funded too. Outputs P(reach lock), survival, and the expected
LIFETIME PAYOUT per funded account — which, combined with the sweep's $/funded, gives true spray EV.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import apex_eval_deployed as H
import funded_rules as FR

SPEC = FR.APEX_ACCOUNTS["50K"]            # start 50k, trailing 2500
FLOOR = SPEC["start"] + 100               # 50,100 — locked threshold
LOCK_PEAK = SPEC["start"] + SPEC["trailing"] + 100   # 52,600 -> lock
SAFETY = 52_100                           # withdraw down to here
CAP_FIRST, CAP_LATER, N_CAPPED = 2_000.0, 4_000.0, 5
MIN_PAYOUT = 500.0
HORIZON_DAYS = 18 * 30                    # value each account over ~18 months
DAILY_STOP = -550.0
PRE = {"A": 4, "B": 2}                    # phase 1
POST = {"A": 6, "B": 3}                   # phase 2 (post-lock scale)


def lifecycle(ev, start):
    a = FR.ApexAcct(SPEC)
    t0 = pd.Timestamp(ev[start]["ts"])
    locked = False; days_to_lock = None
    payout = 0.0; n_pay = 0
    cur_month = None; day = None; day_real = 0.0
    last_ts = t0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); last_ts = ts
        if (ts - t0).days > HORIZON_DAYS:
            break
        d = ts.normalize()
        if d != day:
            day = d; day_real = 0.0
        m = (ts.year, ts.month)
        if cur_month is None:
            cur_month = m
        if m != cur_month:                                  # month rollover -> payout sweep
            if locked and a.bal > SAFETY:
                cap = CAP_FIRST if n_pay < N_CAPPED else CAP_LATER
                w = min(a.bal - SAFETY, cap)
                if w >= MIN_PAYOUT:
                    a.bal -= w; payout += w; n_pay += 1
            cur_month = m
        if day_real <= DAILY_STOP:                          # $550 daily stop: no new entries
            continue
        sc = (POST if locked else PRE)[e["src"]]
        a.apply_trade(e["pnl"] * sc, mfe=max(0.0, e["mfe"]) * sc, mae=min(0.0, e["mae"]) * sc)
        day_real += e["pnl"] * sc
        if not locked and a.locked:
            locked = True; days_to_lock = (ts - t0).days
        if a.breached:
            return dict(locked=locked, days_to_lock=days_to_lock, payout=payout,
                        bust="prelock" if days_to_lock is None else "postlock",
                        months=max(1e-6, (ts - t0).days) / 30.0)
    return dict(locked=locked, days_to_lock=days_to_lock, payout=payout,
                bust=None, months=max(1e-6, (last_ts - t0).days) / 30.0)


def main():
    print("generating unit A/B streams (funded = momentum OFF)…", flush=True)
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    df5 = H.load_bars()
    print(f"  bars {df5.index.min().date()} -> {df5.index.max().date()}", flush=True)
    A, B = H.a_events(df5), H.b_events(df5)
    ev = sorted(A + B, key=lambda e: e["ts"])
    print(f"  unit events A+B: {len(ev)}", flush=True)

    last = pd.Timestamp(ev[-1]["ts"])
    seen, starts = set(), []
    for i, e in enumerate(ev):
        dd = pd.Timestamp(e["ts"]).normalize()
        if dd in seen:
            continue
        seen.add(dd)
        if (last - pd.Timestamp(e["ts"])).days >= 270:      # need >=9mo of runway to value the account
            starts.append(i)
    out = [lifecycle(ev, s) for s in starts]
    n = len(out)
    locked = [o for o in out if o["locked"]]
    bust_pre = sum(1 for o in out if o["bust"] == "prelock")
    bust_post = sum(1 for o in out if o["bust"] == "postlock")
    p_lock = len(locked) / n
    d2l = [o["days_to_lock"] for o in locked if o["days_to_lock"] is not None]
    med_lock = int(np.median(d2l)) if d2l else None
    payout_all = np.mean([o["payout"] for o in out])                 # per funded account STARTED (bust=~0)
    payout_locked = np.mean([o["payout"] for o in locked]) if locked else 0.0
    mo_locked = np.mean([o["months"] for o in locked]) if locked else 0.0
    permonth = (payout_locked / mo_locked) if mo_locked else 0.0

    print(f"\n================ APEX 50K FUNDED SURVIVAL (A4/B2 -> lock -> A6/B3) ================")
    print(f"  funded accounts simulated (rolling start): {n}   horizon {HORIZON_DAYS//30}mo")
    print(f"  P(reach lock)        : {100*p_lock:5.1f}%   (median {med_lock} days to lock)")
    print(f"  bust BEFORE lock     : {100*bust_pre/n:5.1f}%   (eval fee wasted, $0 income)")
    print(f"  bust AFTER lock      : {100*bust_post/n:5.1f}%   (kept payouts banked before bust)")
    print(f"  survived horizon     : {100*(n-bust_pre-bust_post)/n:5.1f}%")
    print(f"  income | locked acct : ${permonth:,.0f}/mo   over ~{mo_locked:.0f} mo observed")
    print(f"  E[payout | LOCKED]   : ${payout_locked:,.0f}   (lifetime, {HORIZON_DAYS//30}mo horizon)")
    print(f"  E[payout | per funded account started] : ${payout_all:,.0f}   <-- value of one passed eval")

    print(f"\n  --- END-TO-END spray EV (E[payout|funded] vs eval cost to produce one) ---")
    print(f"  {'eval sizing':>12}{'$/funded':>10}{'E[payout]':>11}{'net EV/funded':>15}")
    for tag, cpf in [("6/3/4 (13MNQ)", 69), ("8/4/5 (17MNQ)", 73), ("10/5/6 DEPLOYED", 82), ("14/7/8 (29MNQ)", 88)]:
        print(f"  {tag:>12}{cpf:>10}{payout_all:>11,.0f}{payout_all-cpf:>15,.0f}")
    print("\n  [note] per-trade give-back (slightly optimistic); Dukascopy proxy; payouts = monthly sweep")
    print("         above $52,100 safety net (first 5 capped $2k, then $4k); 18-mo horizon caps lifetime value.")


if __name__ == "__main__":
    main()
