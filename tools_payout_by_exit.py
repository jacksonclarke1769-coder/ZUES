"""Expected monthly payout by exit model: live partial vs single@1R / @1.5R.
Runs the VALIDATED funded lifecycle (apex_funded_eod_databento: A4/B2 grind -> A6/B3 post-lock,
EOD rule, 18mo horizon, real Databento) swapping ONLY the Profile-A exit (B + sizing held constant,
so the delta is purely the exit model). Incumbent reproduces the ~$12.3k / $1,924-mo baseline."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import exit_model_validate as V
import apex_funded_eod_databento as F
import apex_eval_deployed as H
import strategy_engine_profileA as E
import config

print("loading real Databento…", flush=True)
df5 = F.DB.load_databento_5m()
H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
feats = eng._features(); fi = feats.index
Bf = H.b_events(df5)                       # funded B, held constant across all variants

variants = ["incumbent", "single1", "single15"]
lab = {"incumbent": "LIVE BOT partial", "single1": "single@1R", "single15": "single@1.5R"}

print("\n  EXPECTED PAYOUT by exit (Apex 50K FUNDED · A4/B2->A6/B3 · EOD · 18mo · real Databento)")
print(f"  {'exit':>16} | {'reach-lock%':>11} {'med d2lock':>10} | {'$/mo|locked':>12} {'E[pay|funded]':>14} {'E[pay|locked]':>14}")
print("  " + "-" * 86)
for v in variants:
    At = V.a_variant(feats, fi, v)
    Aev = [dict(ts=t["ts"], src="A", pnl=t["R"] * t["risk_usd"],
                mae=min(0.0, t["mae_r"]) * t["risk_usd"]) for t in At]
    ev = sorted(Aev + Bf, key=lambda e: pd.Timestamp(e["ts"]))
    last = pd.Timestamp(ev[-1]["ts"]); seen, starts = set(), []
    for i, e in enumerate(ev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days >= 270:
            starts.append(i)
    out = [F.lifecycle(ev, s) for s in starts]
    n = len(out)
    lk = [o for o in out if o["locked"]]
    plock = 100 * len(lk) / n
    d2l = [o["d2l"] for o in lk if o["d2l"] is not None]
    epay_all = np.mean([o["payout"] for o in out])
    epay_lk = np.mean([o["payout"] for o in lk]) if lk else 0.0
    mo_lk = np.mean([o["months"] for o in lk]) if lk else 0.0
    inc_mo = epay_lk / mo_lk if mo_lk else 0.0
    print(f"  {lab[v]:>16} | {plock:11.1f} {int(np.median(d2l)) if d2l else 0:10} | "
          f"${inc_mo:11,.0f} ${epay_all:13,.0f} ${epay_lk:13,.0f}")
print("\n  $/mo|locked = income run-rate once the floor locks · E[pay|funded] = expected total per")
print("  funded account over 18mo (incl. busts) · momentum OFF (matches the validated funded baseline).")
