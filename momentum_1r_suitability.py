"""Is 1RR (single +1R exit) suitable for the CONTINUATION (Momentum) model? Real Databento ~5y.
Momentum is a POSITION strategy: no bracket, no target — it rides the trend until the signal flips /
flattens / EOD, with a wide 120pt catastrophic stop. So 1RR (a fixed +1R take-profit bracket) has no
bracket to attach to. This quantifies WHY you wouldn't want to: the edge is right-tail trend days that
run FAR past +1R; a +1R cap truncates exactly those. 1R analog = the 120pt catastrophic stop."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB

STOP_PTS = 120.0                       # momentum catastrophic stop -> the 1R risk unit


def main():
    print("loading real Databento…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    R = STOP_PTS * H.DPP               # 1R in $ at size 1 (120pt * $2)
    ev = H.m_events(df5)              # daily momentum P&L, mfe=intraday peak, mae=intraday trough
    pnl = np.array([e["pnl"] for e in ev]); mfe = np.array([e["mfe"] for e in ev])
    tot = pnl.sum(); wins = pnl[pnl > 0]

    print(f"\n  momentum days {len(ev)} · 1R = {STOP_PTS:.0f}pt = ${R:,.0f} (size 1)\n")
    print("========  NATURAL momentum (current signal-driven exit)  ========")
    print(f"  total P&L        : ${tot:,.0f}")
    print(f"  win days         : {100*len(wins)/len(ev):.0f}%   avg win ${wins.mean():,.0f}   best day ${pnl.max():,.0f}")

    # right-tail concentration: how much profit comes from days that ran past +1R intraday
    ran_past_1R = mfe >= R
    print(f"\n  days whose intraday PEAK ran past +1R : {100*ran_past_1R.mean():.0f}% of days")
    prof_from_runners = pnl[ran_past_1R & (pnl > 0)].sum()
    gross_profit = wins.sum()
    print(f"  share of gross profit from >+1R days  : {100*prof_from_runners/gross_profit:.0f}%")

    # +1R cap sim: if the day hit +1R intraday, a +1R target exits there (=+1R); else natural close
    capped = np.where(mfe >= R, R, pnl)
    print(f"\n========  +1R-CAPPED momentum (hypothetical single +1R exit)  ========")
    print(f"  total P&L        : ${capped.sum():,.0f}")
    print(f"  vs natural       : {100*(capped.sum()-tot)/abs(tot):+.0f}%   (${capped.sum()-tot:,.0f})")
    print(f"\n  [1RR truncates the trend-day right tail that IS the momentum edge -> total collapses.]")
    print(f"  [Architecturally: momentum has no bracket/target; 1RR is a bracket exit — not applicable.]")


if __name__ == "__main__":
    main()
