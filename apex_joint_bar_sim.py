"""JOINT bar-by-bar Apex sim — removes the per-trade give-back proxy's optimism.

Instead of marking each trade's drawdown in isolation (sequential), this tracks every leg's OPEN
position per 5m bar and marks the COMBINED intraday equity (realized + all open legs' unrealized,
each at its bar-adverse extreme). That's a PESSIMISTIC bound (assumes all legs hit their worst at once);
the per-trade proxy is the OPTIMISTIC bound. The truth is between -> this brackets the real numbers.

Pressure-tests the softest claims: eval 57.5%, funded reach-lock 68% (mm0) and 79.8% (mm2 grind).
Single sizing per precompute (lock happens during the pre-lock grind, so reach-lock needs only pre-size).
EOD drawdown rule + real Databento.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
from collections import defaultdict
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import strategy_engine_profileA as E
import model01_sweep_mss_fvg as M1
import config
import apex_eval_eod_databento as DB
from profile_momentum_engine import ProfileMomentumEngine as PME

NY = "America/New_York"
TRAIL, LOCK_EOD, FLOOR = 2500.0, 52_600.0, 50_100.0
DAILY_STOP, EXPIRE_DAYS = -550.0, 30
B_COST = 0.75


def build_legs(feats):
    """A legs (model01) + B legs (ORB) as (fill_i, exit_i, dir, entry, realized_unit_$) on feats positions,
    and momentum position-per-bar (unit contracts) on feats positions."""
    H = feats.High.values; L = feats.Low.values; C = feats.Close.values; idx = feats.index; n = len(C)
    # --- A ---
    trA = M1.run(feats, "NQ", {**E.PROFILE_A, "slip_ticks": 8})
    trA = trA[trA.session == "ny_am"]
    A = []
    for _, t in trA.iterrows():
        risk = abs(float(t.entry) - float(t.stop))
        if risk <= 0:
            continue
        fb, xb = int(t.fill_bar), int(t.exit_bar)
        if not (0 <= fb < n and fb <= xb < n):
            continue
        d = 1 if t.direction == "long" else -1
        A.append((fb, xb, d, float(t.entry), float(t.r_result) * risk * 2.0))
    # --- B (ORB) on feats ---
    et = idx.tz_convert(NY); mins = (et.hour * 60 + et.minute).values
    rth = (mins >= 570) & (mins < 960)
    day = et.normalize().tz_localize(None).values
    pc = feats.Close.shift(1)
    trng = pd.concat([feats.High - feats.Low, (feats.High - pc).abs(), (feats.Low - pc).abs()], axis=1).max(axis=1)
    atr = trng.rolling(14).mean().values
    B = []
    for d0 in pd.unique(day):
        di = np.where((day == d0) & rth)[0]
        if len(di) < 20:
            continue
        o_end = idx[di[0]] + pd.Timedelta(minutes=15)
        org = [j for j in di if idx[j] < o_end]
        if len(org) < 2:
            continue
        orh = max(H[j] for j in org); orl = min(L[j] for j in org)
        atr0 = atr[org[-1]]
        if not atr0 or np.isnan(atr0):
            continue
        broke = False
        for j in di:
            if idx[j] < o_end or broke:
                continue
            for dd, lvl in ((1, orh), (-1, orl)):
                if (C[j] > lvl) if dd > 0 else (C[j] < lvl):
                    broke = True
                    fill = next((x for x in range(j + 1, min(j + 7, n)) if L[x] <= lvl <= H[x]), None)
                    if fill is None:
                        break
                    stop = lvl - dd * 1.0 * atr0; tgt = lvl + dd * 1.5 * atr0
                    ex = None; xb = fill
                    for x in range(fill, min(fill + 24, n)):
                        xb = x
                        if dd > 0:
                            if L[x] <= stop: ex = stop; break
                            if H[x] >= tgt: ex = tgt; break
                        else:
                            if H[x] >= stop: ex = stop; break
                            if L[x] <= tgt: ex = tgt; break
                        if not rth[x] and x > fill: ex = C[x]; break
                    if ex is None: ex = C[min(fill + 24, n) - 1]
                    B.append((fill, xb, dd, float(lvl), ((ex - lvl) * dd - B_COST) * 2.0))
                    break
    # --- momentum position per feats bar ---
    dd = feats[rth].copy()
    dd["date"] = dd.index.tz_convert(NY).normalize().tz_localize(None)
    dd["slot"] = ((dd.index.tz_convert(NY).hour * 60 + dd.index.tz_convert(NY).minute) - 570) // 5
    mp_rth = PME.compute(dd[["date", "slot", "Open", "High", "Low", "Close"]].assign(Volume=0))
    mompos = np.zeros(n); mompos[np.where(rth)[0]] = mp_rth
    return A, B, mompos, day, rth, H, L, C


def precompute(A, B, mompos, day, rth, H, L, C, a_sz, b_sz, m_sz):
    """Per-bar realized increment and per-bar combined open-adverse unrealized ($), at the given sizing,
    with the $550 daily stop blocking NEW legs once the day's realized <= -550."""
    n = len(C)
    by_fill = defaultdict(list)
    for (fb, xb, d, ent, ru) in A:
        by_fill[fb].append((xb, d, ent, a_sz, ru * a_sz))
    for (fb, xb, d, ent, ru) in B:
        by_fill[fb].append((xb, d, ent, b_sz, ru * b_sz))
    realized = np.zeros(n); open_adv = np.zeros(n)
    open_legs = []; curday = None; dayreal = 0.0; stopped = False
    for i in range(n):
        if day[i] != curday:
            curday = day[i]; dayreal = 0.0; stopped = False; open_legs = [l for l in open_legs if l[0] >= i]
        if not stopped:
            for leg in by_fill.get(i, []):
                open_legs.append(leg)
        mp = mompos[i - 1] if i > 0 else 0.0          # position held into bar i
        if stopped:
            mp = 0.0
        adv = 0.0
        for (xb, d, ent, sz, ru) in open_legs:
            ext = L[i] if d > 0 else H[i]
            adv += d * (ext - ent) * sz * 2.0
        if mp != 0.0 and i > 0:
            mext = L[i] if mp > 0 else H[i]
            adv += mp * (mext - C[i - 1]) * m_sz * 2.0
        open_adv[i] = min(0.0, adv)
        rinc = 0.0; still = []
        for leg in open_legs:
            if leg[0] == i: rinc += leg[4]
            else: still.append(leg)
        open_legs = still
        if mp != 0.0 and i > 0:
            rinc += mp * (C[i] - C[i - 1]) * m_sz * 2.0
        realized[i] = rinc; dayreal += rinc
        if dayreal <= DAILY_STOP: stopped = True
    return realized, open_adv


def day_first_bars(day):
    out = []; prev = None
    for i, d in enumerate(day):
        if d != prev: out.append(i); prev = d
    return out


def run_eod(realized, open_adv, day, start, target, until_lock=False):
    """EOD drawdown walk from bar `start`. until_lock=True -> returns LOCK/BUST/NOLOCK (funded reach-lock);
    else PASS/BUST/EXPIRE (eval target)."""
    bal = 50000.0; thr = bal - TRAIL; peak = bal; locked = False
    d0 = day[start]; cur = None; days = 0
    for i in range(start, len(realized)):
        if day[i] != cur:
            if cur is not None:
                days = (pd.Timestamp(day[i]) - pd.Timestamp(d0)).days
                if not until_lock and days > EXPIRE_DAYS:
                    return "EXPIRE"
                if until_lock and days > 18 * 30:
                    return "NOLOCK"
                peak = max(peak, bal)
                if not locked:
                    thr = max(thr, peak - TRAIL)
                    if peak >= LOCK_EOD:
                        if until_lock: return "LOCK"
                        thr = FLOOR; locked = True
            cur = day[i]
        if bal + open_adv[i] <= thr:
            return "BUST"
        bal += realized[i]
        if not until_lock and bal >= 50000.0 + target:
            return "PASS"
    return "NOLOCK" if until_lock else "INCOMPLETE"


def pct(results, key):
    return 100 * sum(1 for r in results if r == key) / len(results)


def main():
    print("loading Databento + building features/legs (one-time)…", flush=True)
    df5 = DB.load_databento_5m()
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    feats = eng._features()
    A, B, mompos, day, rth, H, L, C = build_legs(feats)
    print(f"  A legs={len(A)}  B legs={len(B)}  momentum bars≠0={int((mompos!=0).sum())}", flush=True)
    dfb = day_first_bars(day)
    starts = [b for b in dfb if (pd.Timestamp(day[-1]) - pd.Timestamp(day[b])).days > EXPIRE_DAYS]
    fstarts = [b for b in dfb if (pd.Timestamp(day[-1]) - pd.Timestamp(day[b])).days >= 270]

    print(f"\n  === JOINT (pessimistic) vs PROXY (optimistic) — EOD + Databento ===")
    # EVAL deployed 10/5/6
    rz, oa = precompute(A, B, mompos, day, rth, H, L, C, 10, 5, 6)
    res = [run_eod(rz, oa, day, s, 3000.0) for s in starts]
    print(f"  EVAL  A10/B5/mm6   JOINT pass {pct(res,'PASS'):.1f}%  bust {pct(res,'BUST'):.1f}%  "
          f"exp {pct(res,'EXPIRE'):.1f}%   (proxy 57.5%)")
    # FUNDED reach-lock A4/B2 mm0
    rz, oa = precompute(A, B, mompos, day, rth, H, L, C, 4, 2, 0)
    res = [run_eod(rz, oa, day, s, 0, until_lock=True) for s in fstarts]
    print(f"  FUND  A4/B2 mm0    JOINT lock {pct(res,'LOCK'):.1f}%  bust {pct(res,'BUST'):.1f}%   (proxy 68.8%)")
    # FUNDED reach-lock A4/B2 mm2 (the soft momentum-grind claim)
    rz, oa = precompute(A, B, mompos, day, rth, H, L, C, 4, 2, 2)
    res = [run_eod(rz, oa, day, s, 0, until_lock=True) for s in fstarts]
    print(f"  FUND  A4/B2 mm2    JOINT lock {pct(res,'LOCK'):.1f}%  bust {pct(res,'BUST'):.1f}%   (proxy 79.8%)")
    print("\n  [note] JOINT marks all legs' combined intraday adverse at once (pessimistic bound);")
    print("         real number sits between JOINT and the per-trade PROXY. EOD + real Databento.")


if __name__ == "__main__":
    main()
