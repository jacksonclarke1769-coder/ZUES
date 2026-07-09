"""Stress part 2: (a) 2021 failure mechanism (bust vs never-lock); (b) MC paired ΔP(lock)
under LONGER blocks that preserve regime clustering (the harness used 20d which the author
flags as breaking the long 2021 drawdown)."""
import os, sys, pickle, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
import apex_funded_momentum_test as MT

CACHE=os.path.expanduser("~/trading-team/bot/nq-liq-bot/.cache_p1_events.pkl")
POST={"A":6,"B":3,"M":6}
CANDS={"A3/B1/mm0":{"A":3,"B":1,"M":0},"A4/B2/mm2":{"A":4,"B":2,"M":2}}
CAND="A3/B1/mm0"; INC="A4/B2/mm2"
START,TRAIL,LOCK_EOD,FLOOR=MT.START,MT.TRAIL,MT.LOCK_EOD,MT.FLOOR
SAFETY,CAP_FIRST,CAP_LATER,N_CAPPED,MIN_PAYOUT=MT.SAFETY,MT.CAP_FIRST,MT.CAP_LATER,MT.N_CAPPED,MT.MIN_PAYOUT
HOR,DAILY_STOP=MT.HORIZON_DAYS,MT.DAILY_STOP

def life(ev,start,pre,post):
    thr=START-TRAIL; bal=START; peak=START; locked=False; d2l=None
    payout=0.0; npay=0; t0=pd.Timestamp(ev[start]["ts"]); cur=None; dreal=0.0; cmonth=None; last=t0; busted=False
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
            busted=True
            return dict(locked=locked,payout=payout,busted=busted)
        bal+=e["pnl"]*s; dreal+=e["pnl"]*s
    return dict(locked=locked,payout=payout,busted=busted)

def funded_starts(ev):
    last=pd.Timestamp(ev[-1]["ts"]); seen=set(); fst=[]
    for i,e in enumerate(ev):
        d=pd.Timestamp(e["ts"]).normalize()
        if d in seen: continue
        seen.add(d)
        if (last-pd.Timestamp(e["ts"])).days>=270: fst.append(i)
    return fst

def day_blocks(ev):
    by={}
    for e in ev: by.setdefault(pd.Timestamp(e["ts"]).normalize(),[]).append(e)
    return [by[d] for d in sorted(by)]

def synth(blocks,rng,n_bus,block_len):
    nb=len(blocks); out=[]
    while len(out)<n_bus:
        st=rng.integers(0,nb-block_len) if nb>block_len else 0
        out.extend(blocks[st:st+block_len])
    out=out[:n_bus]; cal=pd.bdate_range("2021-01-04",periods=n_bus); ev=[]
    for di,dayev in enumerate(out):
        base=cal[di]
        for e in dayev:
            t=pd.Timestamp(e["ts"])
            ev.append(dict(ts=base+pd.Timedelta(hours=t.hour,minutes=t.minute,seconds=t.second),
                           src=e["src"],pnl=e["pnl"],mfe=e["mfe"],mae=e["mae"]))
    return ev

def main():
    ev=pickle.load(open(CACHE,"rb")); fst=funded_starts(ev)
    # (a) 2021 mechanism
    print("==== (a) 2021 funded-start failure mechanism ====")
    sub=[s for s in fst if pd.Timestamp(ev[s]["ts"]).year==2021]
    for lbl in (CAND,INC):
        o=[life(ev,s,CANDS[lbl],POST) for s in sub]
        nlock=sum(x["locked"] for x in o); nbust=sum(x["busted"] for x in o)
        ninc=len(o)-nlock-sum(1 for x in o if x["busted"] and not x["locked"])
        # never-lock-never-bust = ran to horizon flat
        nflat=sum(1 for x in o if (not x["locked"]) and (not x["busted"]))
        print(f"  {lbl:<11} N={len(o)} lock {100*nlock/len(o):.1f}%  busted {100*nbust/len(o):.1f}%  ran-to-horizon-unlocked {100*nflat/len(o):.1f}%")
    print("  (smaller size can't reach +$2,600 lock in the 2021->22 adverse regime; trail stays live -> bust)")

    # (b) MC paired diff under longer blocks
    print("\n==== (b) MC paired ΔP(lock) cand-inc by BLOCK LENGTH (preserve regime clustering) ====")
    blocks=day_blocks(ev); n_bus=int(HOR/7*5)+60
    print(f"  {'block_len':>10}{'cand P(lock)':>14}{'inc P(lock)':>13}{'Δmean':>8}{'Δp5':>8}{'Δp95':>8}")
    for BL in (20,40,60,120):
        rng=np.random.default_rng(7); R=1500
        lc=np.zeros(R); li=np.zeros(R)
        for r in range(R):
            st=synth(blocks,rng,n_bus,BL)
            lc[r]=life(st,0,CANDS[CAND],POST)["locked"]
            li[r]=life(st,0,CANDS[INC],POST)["locked"]
        d=(lc-li)*100
        # paired bootstrap of the mean diff
        rb=np.random.default_rng(11); ms=[]
        for _ in range(2000):
            j=rb.integers(0,R,R); ms.append(d[j].mean())
        ms=np.array(ms)
        print(f"  {BL:>10}{100*lc.mean():>13.1f}%{100*li.mean():>12.1f}%{ms.mean():>+8.1f}{np.percentile(ms,5):>+8.1f}{np.percentile(ms,95):>+8.1f}")
    print("  (if Δp5 collapses toward/below 0 as blocks lengthen, the +3.4pt edge was a block-shuffle artifact)")

if __name__=="__main__":
    main()
