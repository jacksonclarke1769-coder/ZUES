"""MONTE CARLO on the 5yr fleet — turns the single $2.37M path into a DISTRIBUTION.
Block-bootstrap the daily P&L (contiguous ~21-day blocks) to build synthetic 5yr histories that PRESERVE
within-month regime correlation (so the correlation-1 bust-clustering tail is kept, not averaged away),
then run the capped weekly-buy fleet on each. Reports median / P10-P90 / worst, the honest accuracy read."""
import os, sys, warnings; warnings.filterwarnings("ignore")
from collections import defaultdict
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB

START, TRAIL, LOCK_EOD, FLOOR = 50_000.0, 2_500.0, 52_600.0, 50_100.0
SAFETY, CF, CL, NC, MINP = 52_100.0, 2_000.0, 4_000.0, 5, 500.0
DAILY_STOP = -550.0
EVAL_COST, ACTIVATION, EVAL_PASS, MAX_ACTIVE = 45.0, 130.0, 0.575, 20
N_ITERS, BLOCK = 400, 63   # quarter-length blocks: preserve multi-month regime persistence (the tail)
np.random.seed(7)


def daily_series(df5):
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    A, B, M = H.a_events(df5), H.b_events(df5), H.m_events(df5)
    ar = defaultdict(float); am = defaultdict(float); br = defaultdict(float); bm = defaultdict(float)
    mr = defaultdict(float); mm = defaultdict(float)
    nz = lambda e: pd.Timestamp(e["ts"]).normalize().tz_localize(None)   # tz-naive to match bdate_range keys
    for e in A:
        d = nz(e); ar[d] += e["pnl"]; am[d] += min(0.0, e["mae"])
    for e in B:
        d = nz(e); br[d] += e["pnl"]; bm[d] += min(0.0, e["mae"])
    for e in M:
        d = nz(e); mr[d] += e["pnl"]; mm[d] += min(0.0, e["mae"])
    days = pd.bdate_range(df5.index.min().normalize().tz_localize(None), df5.index.max().normalize().tz_localize(None))
    rows = []
    for d in days:
        d = pd.Timestamp(d)
        rows.append((ar[d], br[d], mr[d], am[d], bm[d], mm[d]))
    return np.array(rows, dtype=float)               # (n_days, 6): a_r b_r m_r a_mae b_mae m_mae


def synth(series):
    n = len(series); out = []
    while len(out) < n:
        s = np.random.randint(0, n - BLOCK)
        out.extend(series[s:s + BLOCK])
    return np.array(out[:n])


def run_acct(series, dates, start, pre, post, brake):
    bal = START; thr = bal - TRAIL; peak = bal; locked = False
    payout = 0.0; npay = 0; cmonth = None
    pa, pb, pm = pre; qa, qb, qm = post
    for i in range(start, len(series)):
        ar, brr, mr, am, bm, mm = series[i]
        m = (dates[i].year, dates[i].month)
        if cmonth is None:
            cmonth = m
        if m != cmonth:
            if locked and bal > SAFETY:
                cap = CF if npay < NC else CL
                w = min(bal - SAFETY, cap)
                if w >= MINP:
                    bal -= w; payout += w; npay += 1
            cmonth = m
        peak = max(peak, bal)
        if not locked:
            thr = max(thr, peak - TRAIL)
            if peak >= LOCK_EOD:
                thr = FLOOR; locked = True
        asz, bsz, msz = (qa, qb, qm) if locked else (pa, pb, pm)
        if brake and (bal - thr) < brake[0]:
            asz *= brake[1]; bsz *= brake[1]; msz *= brake[1]
        if bal + asz * am + bsz * bm + msz * mm <= thr:
            return True, i, payout
        dreal = asz * ar + bsz * brr + msz * mr
        if dreal < DAILY_STOP:
            dreal = DAILY_STOP
        bal += dreal
    return False, len(series), payout


def one_fleet(series, dates, pre, post, brake):
    weeks = range(0, len(series) - 5, 5)
    active = []; n = 0; busted = 0; payouts = 0.0
    for w in weeks:
        active = [b for b in active if b > w]
        if len(active) < MAX_ACTIVE:
            bu, endi, pay = run_acct(series, dates, w, pre, post, brake)
            n += 1; payouts += pay
            if bu:
                busted += 1; active.append(endi)
            else:
                active.append(len(series) + 1)
    active_end = len([b for b in active if b > len(series)])
    spend = n / EVAL_PASS * EVAL_COST + n * ACTIVATION
    return payouts - spend, payouts, busted, active_end, n


def main():
    print("loading Databento + building daily series…", flush=True)
    df5 = DB.load_databento_5m()
    series = daily_series(df5)
    dates = pd.bdate_range("2021-06-23", periods=len(series))
    nzdays = int((np.abs(series).sum(axis=1) > 0).sum())
    print(f"  {len(series)} trading days ({nzdays} with P&L) · unit daily net ${series[:,:3].sum():,.0f} "
          f"· {N_ITERS} block-bootstrap paths (block {BLOCK}d)", flush=True)
    assert nzdays > 100, "series is empty — tz/key bug"

    for label, pre, post, brake in [
        ("OPTIMISED A4/B2/mm2+brake -> A6/B3/mm6", (4, 2, 2), (6, 3, 6), (1000, 0.5)),
        ("DEPLOYED  A4/B2 mm0 -> A6/B3 mm0", (4, 2, 0), (6, 3, 0), None)]:
        nets = []; pays = []; busts = []; act = []
        for _ in range(N_ITERS):
            s = synth(series)
            net, pay, bu, ae, nn = one_fleet(s, dates, pre, post, brake)
            nets.append(net); pays.append(pay); busts.append(bu); act.append(ae)
        nets = np.array(nets) / 1e6
        q = lambda p: np.percentile(nets, p)
        print(f"\n  ===== {label} =====")
        print(f"  NET over 5yr ($M):  median {np.median(nets):.2f}   mean {nets.mean():.2f}")
        print(f"    P10 {q(10):.2f}   P25 {q(25):.2f}   P75 {q(75):.2f}   P90 {q(90):.2f}")
        print(f"    worst {nets.min():.2f}   best {nets.max():.2f}   "
              f"% paths <$0: {100*(nets<0).mean():.0f}%   <$0.5M: {100*(nets<0.5).mean():.0f}%")
        print(f"  busts/path  median {int(np.median(busts))}   active-at-end median {int(np.median(act))}")
        print(f"  single real-data path was: $2.37M (optimised) / $1.66M (deployed)")
    print("\n  [note] block bootstrap preserves regime clustering (the correlation-1 tail). Daily-grain")
    print("         approx + modeled costs/payout rules. Compare median+P10 to the single-path number.")


if __name__ == "__main__":
    main()
