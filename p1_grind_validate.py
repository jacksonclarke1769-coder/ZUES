"""PHASE-1 GRIND validation: A3/B1/mm0 vs DEPLOYED A4/B2/mm2 vs A2/B1/mm0.
Reuses validated funded lifecycle (apex_funded_momentum_test.life: EOD drawdown + REAL Databento,
A/B/M unit streams from apex_eval_deployed). POST (phase-2) held at deployed A6/B3/mm6.

Validation per method spec:
  (1) IS vs OOS by funded-START year: split-1 IS 2021-24 / OOS 2025-26; split-2 IS 2021-23 / OOS 2024-26.
  (2) BLOCK-BOOTSTRAP MC: each replicate = ONE synthetic ~18mo forward funded account built by resampling
      contiguous 20-business-day blocks of the real day-event stream; run life() once from day 0.
      Paired across configs (same synthetic stream). R replicates -> distribution of P(lock), E[payout],
      days-to-lock. p5 of the PAIRED difference (candidate - incumbent) decides 'beats at MC p5'.
Metrics: P(reach lock), E[payout|funded started], median days-to-lock.
"""
import os, sys, pickle, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB
import apex_funded_momentum_test as MT   # life(ev,start,pre,post)

POST = {"A": 6, "B": 3, "M": 6}          # deployed phase-2, held fixed
CANDS = {
    "A2/B1/mm0": {"A": 2, "B": 1, "M": 0},
    "A3/B1/mm0": {"A": 3, "B": 1, "M": 0},
    "A4/B2/mm2": {"A": 4, "B": 2, "M": 2},   # DEPLOYED phase-1
}
INCUMBENT = "A4/B2/mm2"
HORIZON_DAYS = MT.HORIZON_DAYS
CACHE = os.path.expanduser("~/trading-team/bot/nq-liq-bot/.cache_p1_events.pkl")


def build_events():
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as f:
            return pickle.load(f)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5) + H.m_events(df5), key=lambda e: e["ts"])
    with open(CACHE, "wb") as f:
        pickle.dump(ev, f)
    return ev


def funded_starts(ev):
    last = pd.Timestamp(ev[-1]["ts"]); seen, fst = set(), []
    for i, e in enumerate(ev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days >= 270:
            fst.append(i)
    return fst


def stats(outcomes):
    n = len(outcomes)
    lk = [o for o in outcomes if o["locked"]]
    p_lock = 100 * len(lk) / n if n else 0.0
    pay_all = float(np.mean([o["payout"] for o in outcomes])) if n else 0.0
    d2l = [o["d2l"] for o in lk if o.get("d2l") is not None]
    med_d2l = float(np.median(d2l)) if d2l else None
    return dict(n=n, p_lock=p_lock, pay_all=pay_all, med_d2l=med_d2l)


# life() in MT doesn't return d2l; wrap to capture it via a patched copy.
def life_d2l(ev, start, pre, post):
    """Re-implements MT.life but also returns days-to-lock (d2l). Logic identical to source."""
    START, TRAIL, LOCK_EOD, FLOOR = MT.START, MT.TRAIL, MT.LOCK_EOD, MT.FLOOR
    SAFETY, CAP_FIRST, CAP_LATER, N_CAPPED, MIN_PAYOUT = MT.SAFETY, MT.CAP_FIRST, MT.CAP_LATER, MT.N_CAPPED, MT.MIN_PAYOUT
    HOR, DAILY_STOP = MT.HORIZON_DAYS, MT.DAILY_STOP
    thr = START - TRAIL; bal = START; peak = START; locked = False; d2l = None
    payout = 0.0; npay = 0; t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0; cmonth = None
    last = t0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize(); last = ts
        if (ts - t0).days > HOR:
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
        if m != cmonth:
            if locked and bal > SAFETY:
                cap = CAP_FIRST if npay < N_CAPPED else CAP_LATER
                w = min(bal - SAFETY, cap)
                if w >= MIN_PAYOUT:
                    bal -= w; payout += w; npay += 1
            cmonth = m
        if dreal <= DAILY_STOP:
            continue
        s = (post if locked else pre).get(e["src"], 0)
        if s == 0:
            continue
        if bal + min(0.0, e["mae"]) * s <= thr:
            return dict(locked=locked, payout=payout, d2l=d2l, months=max(1e-6, (ts - t0).days) / 30.0)
        bal += e["pnl"] * s; dreal += e["pnl"] * s
    return dict(locked=locked, payout=payout, d2l=d2l, months=max(1e-6, (last - t0).days) / 30.0)


def run_split(ev, fst, lo_year, hi_year):
    """Return per-config stats for starts whose year in [lo_year, hi_year]."""
    sub = [s for s in fst if lo_year <= pd.Timestamp(ev[s]["ts"]).year <= hi_year]
    res = {}
    for lbl, pre in CANDS.items():
        res[lbl] = stats([life_d2l(ev, s, pre, POST) for s in sub])
    return res, len(sub)


# ---------------- block-bootstrap synthetic forward account ----------------
def day_blocks(ev):
    """Group unit events into ordered per-trading-day buckets."""
    by = {}
    for e in ev:
        d = pd.Timestamp(e["ts"]).normalize()
        by.setdefault(d, []).append(e)
    days = sorted(by)
    return [by[d] for d in days]              # list of day-event-lists, chronological


def synth_stream(blocks, rng, n_bus_days, block_len=20):
    """Build a synthetic event stream of ~n_bus_days business days by tiling resampled
    contiguous block_len-day blocks, reassigning consecutive business-day calendar dates
    (preserving intraday time-of-day) so day-rollover / monthly-payout / horizon logic works."""
    nb = len(blocks)
    out_days = []
    while len(out_days) < n_bus_days:
        st = rng.integers(0, nb - block_len) if nb > block_len else 0
        out_days.extend(blocks[st:st + block_len])
    out_days = out_days[:n_bus_days]
    cal = pd.bdate_range("2021-01-04", periods=n_bus_days)
    ev = []
    for di, dayev in enumerate(out_days):
        base = cal[di]
        for e in dayev:
            t = pd.Timestamp(e["ts"])
            ts = base + pd.Timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
            ev.append(dict(ts=ts, src=e["src"], pnl=e["pnl"], mfe=e["mfe"], mae=e["mae"]))
    return ev


def mc(ev, R=2000, seed=7):
    rng = np.random.default_rng(seed)
    blocks = day_blocks(ev)
    # synthetic stream length = full horizon + slack so the account runs its whole 18mo window
    n_bus = int(HORIZON_DAYS / 7 * 5) + 60       # ~ business days spanning HORIZON_DAYS calendar + slack
    rec = {lbl: dict(lock=[], payout=[], d2l=[]) for lbl in CANDS}
    for r in range(R):
        stream = synth_stream(blocks, rng, n_bus)
        for lbl, pre in CANDS.items():
            o = life_d2l(stream, 0, pre, POST)
            rec[lbl]["lock"].append(1 if o["locked"] else 0)
            rec[lbl]["payout"].append(o["payout"])
            rec[lbl]["d2l"].append(o["d2l"] if o["d2l"] is not None else np.nan)
    return rec


def pct(a, q):
    a = np.asarray(a, float); a = a[~np.isnan(a)]
    return float(np.percentile(a, q)) if len(a) else float("nan")


def main():
    print("building events (cached)…", flush=True)
    ev = build_events()
    print(f"  unit A+B+M events: {len(ev)}  span {pd.Timestamp(ev[0]['ts']).date()}..{pd.Timestamp(ev[-1]['ts']).date()}", flush=True)
    fst = funded_starts(ev)
    print(f"  funded starts (>=270d remaining): {len(fst)}\n", flush=True)

    # ---- FULL history point estimate ----
    print("==== FULL HISTORY (all funded starts) ====")
    full = {}
    for lbl, pre in CANDS.items():
        full[lbl] = stats([life_d2l(ev, s, pre, POST) for s in fst])
        m = full[lbl]
        print(f"  {lbl:<11} lock {m['p_lock']:5.1f}%   E[payout|funded] ${m['pay_all']:>7,.0f}   med-d2l {m['med_d2l']}")

    # ---- IS/OOS split 1: 2021-24 / 2025-26 ----
    print("\n==== SPLIT 1  IS 2021-2024  /  OOS 2025-2026  (by start year) ====")
    is1, nis1 = run_split(ev, fst, 2021, 2024)
    oos1, noos1 = run_split(ev, fst, 2025, 2026)
    print(f"  IS starts {nis1}   OOS starts {noos1}")
    for lbl in CANDS:
        print(f"  {lbl:<11} IS lock {is1[lbl]['p_lock']:5.1f}% pay ${is1[lbl]['pay_all']:>6,.0f}  |  "
              f"OOS lock {oos1[lbl]['p_lock']:5.1f}% pay ${oos1[lbl]['pay_all']:>6,.0f} med-d2l {oos1[lbl]['med_d2l']}")

    # ---- IS/OOS split 2: 2021-23 / 2024-26 ----
    print("\n==== SPLIT 2  IS 2021-2023  /  OOS 2024-2026  (stability check) ====")
    is2, nis2 = run_split(ev, fst, 2021, 2023)
    oos2, noos2 = run_split(ev, fst, 2024, 2026)
    print(f"  IS starts {nis2}   OOS starts {noos2}")
    for lbl in CANDS:
        print(f"  {lbl:<11} IS lock {is2[lbl]['p_lock']:5.1f}% pay ${is2[lbl]['pay_all']:>6,.0f}  |  "
              f"OOS lock {oos2[lbl]['p_lock']:5.1f}% pay ${oos2[lbl]['pay_all']:>6,.0f} med-d2l {oos2[lbl]['med_d2l']}")

    # ---- BLOCK-BOOTSTRAP MC ----
    R = 2000
    print(f"\n==== BLOCK-BOOTSTRAP MC  ({R} synthetic 18mo accounts, 20-bday blocks, paired) ====", flush=True)
    rec = mc(ev, R=R)
    inc = rec[INCUMBENT]
    print(f"  {'config':<11}{'P(lock)':>9}{'lock p5':>9}{'lock p95':>10}   "
          f"{'E[pay]':>9}{'pay p5':>9}{'pay p50':>9}{'pay p95':>10}{'med-d2l':>9}")
    for lbl in CANDS:
        rc = rec[lbl]
        plock = 100 * np.mean(rc["lock"])
        # bootstrap CI for P(lock)
        lk = np.array(rc["lock"]); bs = [100*np.mean(rng_choice(lk)) for _ in range(800)]
        med_d2l = pct(rc["d2l"], 50)
        print(f"  {lbl:<11}{plock:>8.1f}%{np.percentile(bs,5):>8.1f}%{np.percentile(bs,95):>9.1f}%   "
              f"${np.mean(rc['payout']):>7,.0f}{pct(rc['payout'],5):>9,.0f}{pct(rc['payout'],50):>9,.0f}"
              f"{pct(rc['payout'],95):>10,.0f}{med_d2l:>9.0f}")

    # ---- paired differences candidate vs incumbent ----
    print(f"\n  ---- paired diff vs incumbent ({INCUMBENT}); p5 of (cand - incumbent) ----")
    incl = np.array(inc["lock"]); incp = np.array(inc["payout"])
    for lbl in CANDS:
        if lbl == INCUMBENT:
            continue
        dl = np.array(rec[lbl]["lock"]) - incl       # per-account lock diff (binary)
        dp = np.array(rec[lbl]["payout"]) - incp
        # bootstrap mean-difference distribution
        idx = np.arange(len(dl))
        rng = np.random.default_rng(11)
        mdl = []; mdp = []
        for _ in range(2000):
            j = rng.integers(0, len(idx), len(idx))
            mdl.append(100*np.mean(dl[j])); mdp.append(np.mean(dp[j]))
        mdl = np.array(mdl); mdp = np.array(mdp)
        print(f"  {lbl:<11} ΔP(lock) mean {mdl.mean():+5.1f}pt  p5 {np.percentile(mdl,5):+5.1f}pt  p95 {np.percentile(mdl,95):+5.1f}pt   "
              f"| ΔE[pay] mean ${mdp.mean():+6,.0f}  p5 ${np.percentile(mdp,5):+6,.0f}  p95 ${np.percentile(mdp,95):+6,.0f}")
    print("\n[note] EOD rule; funded has NO 30-day clock (horizon 18mo). POST fixed A6/B3/mm6. Per-trade proxy.")


_RNG = np.random.default_rng(99)
def rng_choice(a):
    return a[_RNG.integers(0, len(a), len(a))]


if __name__ == "__main__":
    main()
