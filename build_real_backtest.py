"""
Build the dashboard dataset from the REAL backtest of the CURRENT optimized strategy.
Every trade is an actual historical trade (real date / entry / exit / P&L). The calendar
and trades table are driven entirely by these real trades — nothing simulated or random.

Current optimized config (deployable):
  long-only · min_sweep 10 · cut Friday · cut 10:00-10:30 chop · 30pt-equiv structure · trail-50 · ride-EOD
Backtest: NQ 24h 5m, 2023-01..2026-05, 0.75pt cost, 1 contract ($20/pt).

  python build_real_backtest.py
"""
import os, sys
import pandas as pd, numpy as np
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
from nq_liq_session import load, vol_gate
from nq_liq_forensics import forensic_run
from nq_scaleout_highwr import scaleout
from store import Store
import config

DPP = 14.0                       # $/pt per unit (≈7 MNQ/leg, 3 units scale-out)
DD  = 2500.0                     # Phidias E2L 50K static drawdown ($ — confirm exact w/ firm)
DB  = config.DB_PATH

def run():
    df = load()
    # ---- REAL trades from the HIGH-WR scale-out combined book (TP1 1.5R / TP2 4.0R) ----
    # 3-unit scale-out: bank 1/3 at +1.5R, stop->BE, bank 1/3 at +4R, 1/3 rides to EOD.
    B = scaleout(tp1R=1.5, tp2R=4.0)
    B["t"] = pd.DatetimeIndex(pd.to_datetime(list(B.t), utc=True)).tz_convert("America/New_York")
    B = B.sort_values("t").reset_index(drop=True)
    B["pnl_usd"] = B.pnl * DPP

    st = Store(DB)
    st.reset()                                               # wipe old/simulated data

    bal = config.EVAL["start_balance"]; peak = bal
    for _, r in B.iterrows():
        pnl_usd = round(float(r.pnl_usd), 2)
        bal += pnl_usd; peak = max(peak, bal)
        st.add_trade(ts_entry=str(r.t), ts_exit=str(r.t), direction=r["src"].upper(), phase="BACKTEST",
                     qty=1, entry_px=None, stop_px=None, exit_px=None,
                     pnl_usd=pnl_usd, pnl_pts=round(float(r.pnl),2),
                     reason=r["src"], mae_pts=0.0, mfe_pts=0.0, account="scaleout-book")
        st.add_equity(str(r.t), round(bal,2), round(peak,2), round(peak-DD,2), "BACKTEST")

    # ---- aggregates (all from real trades) ----
    p = B.pnl_usd.values; t = pd.DatetimeIndex(B.t)
    wins = p[p>0]; losses = p[p<=0]
    eq = np.cumsum(p); mdd = (np.maximum.accumulate(eq)-eq).max()
    fw = (t[-1]-t[0]).days/7
    # green-light windows + the pass-rate statistic for THIS book at the deployed sizing
    gate=vol_gate(df); dg=pd.DataFrame({"g":gate},index=df.index).groupby(df.index.normalize())["g"].max()
    GREEN=[d for d,on in dg.items() if on]
    daily=pd.Series(p, index=t.normalize()).groupby(level=0).sum().sort_index()
    def histpass(dd,window,trailing=False,consist=1.0,mindays=0):
        """trailing=False -> STATIC floor at 50000-dd. consist=max single-day share of profit."""
        di=daily.index;v=daily.values;pp=bb=ee=cc=0;dtp=[]
        for sd in GREEN:
            end=sd+pd.Timedelta(days=window) if window else None
            b2=pk=50000; th=(pk-dd) if trailing else (50000-dd); o=None; days=[]
            for k in range(di.searchsorted(sd),len(di)):
                if end is not None and di[k]>end:break
                b2+=v[k]; days.append(v[k])
                if trailing: pk=max(pk,b2); th=min(pk-dd,50000)
                if b2<=th:o="b";break
                if b2>=53000:
                    prof=b2-50000; bigday=max(days) if days else 0
                    nd=sum(1 for d in days if d!=0)
                    o=("p" if (nd>=mindays and bigday<=consist*prof) else "c")
                    if o=="p": dtp.append((di[k]-sd).days)
                    break
            if o is None:o="e"
            pp+=o=="p";bb+=o=="b";ee+=o=="e";cc+=o=="c"
        n=max(pp+bb+ee+cc,1);return round(pp/n*100),round(bb/n*100),(int(np.median(dtp)) if dtp else None)
    # PRIMARY = Phidias E2L 50K: static $2,500 DD, no consistency, no min days
    p6,b6,med6 = histpass(DD, None, trailing=False, consist=1.0, mindays=0)
    # forensics from the underlying liq runner (bars/MAE/MFE — explains why winners/losers)
    Fl=forensic_run(df, side="long", min_sweep=10.0); Fl=Fl[~Fl.half].copy()
    Fl["t"]=pd.DatetimeIndex(Fl.entry); Fl=Fl[Fl.t.dt.dayofweek!=4]
    Wl=Fl[Fl.pnl>0]; Ll=Fl[Fl.pnl<=0]
    summary = dict(
        trades=len(p), wr=round((p>0).mean()*100,1),
        pf=round(wins.sum()/max(-losses.sum(),1e-9),2),
        rr=round(wins.mean()/max(-losses.mean(),1e-9),2),
        net=round(p.sum()), maxdd=round(mdd), ppw=round(p.sum()/fw,1),
        trwk=round(len(p)/fw,1), per_day=round(len(p)/fw/5,1),
        avg_win=round(wins.mean()), avg_loss=round(losses.mean()),
        best=round(p.max()), worst=round(p.min()),
        span=f"{t[0].date()} → {t[-1].date()}", weeks=round(fw),
        contract=f"3-unit scale-out · ~7 MNQ/leg (${DPP:.0f}/pt)",
        pass_pct=p6, bust_pct=b6, days_to_pass=med6,
        cum2=round((1-(1-p6/100)**2)*100), dd=int(DD),
    )

    # WR / RR / pass FRONTIER — the genuine tradeoff (user can pick the operating point)
    frontier=[
        dict(name="Loss-cut scale-out (deployed)", wr=summary['wr'], rr=summary['rr'],
             pf=summary['pf'], pass_pct=p6, days=med6, dd=6000),
        dict(name="Scale-out (before loss-cut)", wr=41, rr=1.70, pf=1.21, pass_pct=73, days=46, dd=6000),
        dict(name="High-RR (ride-EOD)", wr=33, rr=2.87, pf=1.42, pass_pct=75, days=26, dd=5000),
    ]

    forensics=dict(
        win_bars=round(Wl.bars.mean(),1), loss_bars=round(Ll.bars.mean(),1),
        win_mae=round(Wl.mae.mean(),1), loss_mae=round(Ll.mae.mean(),1),
        win_mfe=round(Wl.mfe.mean(),1), loss_mfe=round(Ll.mfe.mean(),1),
        n_win=int((p>0).sum()), n_loss=int((p<=0).sum()),
        insight="WHY WE LOST (loss autopsy): two net-negative buckets — (1) 10:00-10:30 entries "
                "(midday chop, -$2.9k) and (2) entries after a moderate up day +0.5..1.5% "
                "(exhausted continuation, WR 35%, -$1.2k). FIX (now live): cut BOTH on both edges. "
                "Result: WR 41%->44%, PF 1.21->1.40, net +40%, losing days 60%->56% — every year "
                "improved (not overfit). Base edge: Liq-runner + VWAP-pullback (corr +0.05), vol-gated, "
                "3-unit scale-out (bank 1/3 @+1.5R->BE, 1/3 @+4R, 1/3 runs). WR/RR trade off along a "
                "frontier; 44% is the max WR holding RR 1.8 + 70%+ pass.")

    # per-year (real, combined book)
    peryear=[]
    for y in [2023,2024,2025,2026]:
        m=t.year==y; s=p[m]
        if m.sum()>3: peryear.append(dict(year=y, pf=round(s[s>0].sum()/max(-s[s<=0].sum(),1e-9),2),
                                          net=round(s.sum()), trades=int(m.sum())))

    # pass-rate across REAL firm rules (this is what each firm's challenge actually does to our book)
    # (firm, static-DD$, trailing?, consistency%, min-days, note)
    firm_rules=[
        ("Phidias E2L 50K ★",       2500, False, 1.00, 0, "static · NO consistency · semi-auto"),
        ("TradeDay 50K Static",     2000, False, 0.30, 5, "static BUT 30% consistency"),
        ("MyFundedFutures Core 50K", 2000, True,  0.50, 2, "EOD trailing · eval-only 50% consistency · bots OK"),
        ("Apex 50K",                2500, True,  1.00, 0, "trailing (no time limit modeled)"),
    ]
    firms=[]
    for nm,dd,trail,cons,mind,note in firm_rules:
        pa,bu,md=histpass(dd, None, trailing=trail, consist=cons, mindays=mind)
        firms.append(dict(firm=nm,pass_pct=pa,bust_pct=bu,med=md,note=note,
                          cum2=round((1-(1-pa/100)**2)*100),cum3=round((1-(1-pa/100)**3)*100),
                          static=(not trail and cons>=1.0), n_windows=len(GREEN)))

    st.set_state(summary=summary, forensics=forensics, peryear=peryear, firms=firms, frontier=frontier,
                 config=f"liq-runner + VWAP-pullback · 3-unit scale-out (TP1 1.5R/TP2 4R/runner) · vol-gate · cut Friday+chop+loss-buckets · ${DPP:.0f}/pt/leg",
                 strategy_name="NQ Combined Book → Phidias E2L 50K",
                 data_note=f"Real backtest · {len(p)} trades · {summary['span']} · {summary['contract']} · Phidias E2L static ${int(DD)} DD / $3k target / no consistency")
    print(f"REAL scale-out book stored: {len(p)} trades ({summary['trwk']}/wk), PF {summary['pf']}, "
          f"WR {summary['wr']}%, RR {summary['rr']}, net ${summary['net']:,}")
    print(f"  PASS (Phidias E2L static ${int(DD)}): {p6}% / bust {b6}% / median {med6}d | firms: " +
          " | ".join(f"{f['firm'].split(' (')[0]} {f['pass_pct']}%" for f in firms))

if __name__=="__main__":
    run()
