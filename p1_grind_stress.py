"""ADVERSARIAL stress test of A3/B1/mm0 (cand) vs A4/B2/mm2 (incumbent) phase-1 grind.
Reuses validated life() lifecycle (apex_funded_momentum_test) + cached unit event stream.
Tests: (1) per-calendar-year funded-start P(lock); (2) cost/slippage sensitivity; (3) worst
rolling window of funded starts; (4) OOS independence (effective N)."""
import os, sys, pickle, copy, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
import apex_funded_momentum_test as MT

CACHE = os.path.expanduser("~/trading-team/bot/nq-liq-bot/.cache_p1_events.pkl")
POST = {"A": 6, "B": 3, "M": 6}
CANDS = {"A3/B1/mm0": {"A": 3, "B": 1, "M": 0}, "A4/B2/mm2": {"A": 4, "B": 2, "M": 2}}
INC = "A4/B2/mm2"; CAND = "A3/B1/mm0"

START,TRAIL,LOCK_EOD,FLOOR = MT.START,MT.TRAIL,MT.LOCK_EOD,MT.FLOOR
SAFETY,CAP_FIRST,CAP_LATER,N_CAPPED,MIN_PAYOUT = MT.SAFETY,MT.CAP_FIRST,MT.CAP_LATER,MT.N_CAPPED,MT.MIN_PAYOUT
HOR,DAILY_STOP = MT.HORIZON_DAYS,MT.DAILY_STOP

def life_d2l(ev, start, pre, post):
    thr=START-TRAIL; bal=START; peak=START; locked=False; d2l=None
    payout=0.0; npay=0; t0=pd.Timestamp(ev[start]["ts"]); cur=None; dreal=0.0; cmonth=None; last=t0
    for k in range(start,len(ev)):
        e=ev[k]; ts=pd.Timestamp(e["ts"]); day=ts.normalize(); last=ts
        if (ts-t0).days>HOR: break
        if cur is None: cur=day
        if day!=cur:
            peak=max(peak,bal)
            if not locked:
                if peak>=LOCK_EOD: thr=FLOOR; locked=True; d2l=(ts-t0).days
                else: thr=max(thr,peak-TRAIL)
            cur=day; dreal=0.0
        m=(ts.year,ts.month)
        if cmonth is None: cmonth=m
        if m!=cmonth:
            if locked and bal>SAFETY:
                cap=CAP_FIRST if npay<N_CAPPED else CAP_LATER
                w=min(bal-SAFETY,cap)
                if w>=MIN_PAYOUT: bal-=w; payout+=w; npay+=1
            cmonth=m
        if dreal<=DAILY_STOP: continue
        s=(post if locked else pre).get(e["src"],0)
        if s==0: continue
        if bal+min(0.0,e["mae"])*s<=thr:
            return dict(locked=locked,payout=payout,d2l=d2l)
        bal+=e["pnl"]*s; dreal+=e["pnl"]*s
    return dict(locked=locked,payout=payout,d2l=d2l)

def funded_starts(ev):
    last=pd.Timestamp(ev[-1]["ts"]); seen=set(); fst=[]
    for i,e in enumerate(ev):
        d=pd.Timestamp(e["ts"]).normalize()
        if d in seen: continue
        seen.add(d)
        if (last-pd.Timestamp(e["ts"])).days>=270: fst.append(i)
    return fst

def lockpct(ev,fst,pre):
    o=[life_d2l(ev,s,pre,POST) for s in fst]
    return 100*sum(x["locked"] for x in o)/len(o) if o else float("nan"), len(o)

def apply_cost(ev, c_ab, c_m):
    """Return a copy with per-trade cost (per-1-contract $) baked into pnl AND mae (worse fill)."""
    out=[]
    for e in ev:
        c = c_m if e["src"]=="M" else c_ab
        out.append(dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]-c, mfe=e["mfe"], mae=e["mae"]-c))
    return out

def main():
    ev=pickle.load(open(CACHE,"rb"))
    fst=funded_starts(ev)
    print(f"events {len(ev)} starts {len(fst)} span {pd.Timestamp(ev[0]['ts']).date()}..{pd.Timestamp(ev[-1]['ts']).date()}\n")

    # ---- 1. PER-CALENDAR-YEAR funded-start P(lock) ----
    print("==== 1. PER-CALENDAR-YEAR funded-start P(lock)  (does cand LOSE any year?) ====")
    print(f"  {'year':>6}{'N':>6}{'  cand':>9}{'  inc':>9}{'  delta':>9}")
    for y in range(2021,2027):
        sub=[s for s in fst if pd.Timestamp(ev[s]["ts"]).year==y]
        if not sub: continue
        lc,_=lockpct(ev,sub,CANDS[CAND]); li,_=lockpct(ev,sub,CANDS[INC])
        flag=" <-- CAND LOSES" if lc<li-1e-9 else ("  tie" if abs(lc-li)<1e-9 else "")
        print(f"  {y:>6}{len(sub):>6}{lc:>8.1f}%{li:>8.1f}%{lc-li:>+8.1f}{flag}")

    # ---- 2. COST / SLIPPAGE SENSITIVITY ----
    print("\n==== 2. COST/SLIPPAGE SENSITIVITY (per-1-contract $ added to A/B trades; M = daily) ====")
    print("  scenarios: NQ tick=0.25pt=$0.50/MNQ; MNQ commission RT ~ $1.04")
    scen=[("baseline",0.0,0.0),("+1tick $0.50",0.50,0.0),("+commission $1.04",1.04,0.0),
          ("+1tick+comm $1.54",1.54,0.50),("harsh +2tick+comm $2.04",2.04,1.0)]
    print(f"  {'scenario':<24}{'cand lock':>11}{'inc lock':>11}{'delta':>9}")
    base=None
    for name,c_ab,c_m in scen:
        evc=apply_cost(ev,c_ab,c_m)
        lc,_=lockpct(evc,fst,CANDS[CAND]); li,_=lockpct(evc,fst,CANDS[INC])
        if base is None: base=(lc,li)
        print(f"  {name:<24}{lc:>10.1f}%{li:>10.1f}%{lc-li:>+8.1f}")

    # ---- 3. WORST ROLLING WINDOW of funded starts ----
    print("\n==== 3. WORST ROLLING WINDOW (W consecutive funded starts; min delta & min cand-lock) ====")
    # precompute per-start lock booleans
    lc_b=np.array([life_d2l(ev,s,CANDS[CAND],POST)["locked"] for s in fst],float)
    li_b=np.array([life_d2l(ev,s,CANDS[INC],POST)["locked"] for s in fst],float)
    for W in (100,150,200):
        if W>len(fst): continue
        cs_c=np.convolve(lc_b,np.ones(W),"valid")/W*100
        cs_i=np.convolve(li_b,np.ones(W),"valid")/W*100
        d=cs_c-cs_i
        jmin=int(np.argmin(d)); jclo=int(np.argmin(cs_c))
        ds=lambda j:pd.Timestamp(ev[fst[j]]["ts"]).date()
        print(f"  W={W}: worst-DELTA window starts {ds(jmin)} cand {cs_c[jmin]:.1f}% inc {cs_i[jmin]:.1f}% Δ{d[jmin]:+.1f}"
              f" | min cand-lock {cs_c[jclo]:.1f}% (inc {cs_i[jclo]:.1f}%) @ {ds(jclo)}")
        print(f"        windows where cand<inc: {100*np.mean(d<0):.1f}%  (Δ p5 {np.percentile(d,5):+.1f}, median {np.median(d):+.1f})")

    # ---- 4. OOS INDEPENDENCE (effective N behind OOS=100%) ----
    print("\n==== 4. OOS INDEPENDENCE — how many INDEPENDENT 18mo accounts back the OOS=100%? ====")
    for lo,hi,lbl in [(2025,2026,"split1 OOS 2025-26"),(2024,2026,"split2 OOS 2024-26")]:
        sub=[s for s in fst if lo<=pd.Timestamp(ev[s]["ts"]).year<=hi]
        if not sub: continue
        t_first=pd.Timestamp(ev[sub[0]]["ts"]); t_last=pd.Timestamp(ev[sub[-1]]["ts"])
        span_d=(t_last-t_first).days
        # non-overlapping 18mo (HOR) accounts that fit in the OOS start-window
        eff=max(1, span_d/HOR + 1)
        # also: greedily count non-overlapping starts spaced >= HOR apart
        chosen=[]; cutoff=None
        for s in sub:
            ts=pd.Timestamp(ev[s]["ts"])
            if cutoff is None or ts>=cutoff:
                chosen.append(s); cutoff=ts+pd.Timedelta(days=HOR)
        lc,_=lockpct(ev,sub,CANDS[CAND]); li,_=lockpct(ev,sub,CANDS[INC])
        print(f"  {lbl}: start-window span {span_d}d, HOR {HOR}d -> ~{eff:.1f} non-overlapping accts;"
              f" greedy non-overlap N={len(chosen)}")
        print(f"        OOS starts={len(sub)} (overlapping), cand lock {lc:.1f}% inc {li:.1f}%"
              f"  => OOS=100% rests on ~{len(chosen)} independent path(s)")

if __name__=="__main__":
    main()
