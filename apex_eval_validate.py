"""VALIDATION: reproduce apex_sim.py's result with apex_eval_deployed's engine.
If I get ~90.3% PASS / median ~41 trades for A-only @ 3 MNQ with NO clock and rolling-every-trade,
the harness engine is trustworthy and the deployed-config 43% number stands."""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import apex_eval_deployed as H
import funded_rules as FR

H.A_SIZE = 3                      # match apex_sim baseline

df5 = H.load_bars()
A = H.a_events(df5)               # A-only @ 3 MNQ
print(f"A-only @3MNQ events: {len(A)}")
events = sorted(A, key=lambda e: e["ts"])

def eval_no_clock(events, start, spec):
    a = FR.ApexAcct(spec)
    for k in range(start, len(events)):
        e = events[k]
        a.apply_trade(e["pnl"], mfe=max(0.0, e["mfe"]), mae=min(0.0, e["mae"]))
        if a.passed: return "PASS", k - start + 1
        if a.breached: return "BUST", k - start + 1
    return "INCOMPLETE", len(events) - start

spec = FR.APEX_ACCOUNTS["50K"]
starts = range(0, max(1, len(events) - 10))         # rolling at every trade, like apex_sim
out = [eval_no_clock(events, s, spec) for s in starts]
n = len(out)
npass = sum(1 for o in out if o[0] == "PASS")
nbust = sum(1 for o in out if o[0] == "BUST")
med = int(np.median([o[1] for o in out if o[0] == "PASS"])) if npass else None
print(f"my engine, A-only @3MNQ, no clock, rolling-every-trade:")
print(f"  PASS {100*npass/n:.1f}%   BUST {100*nbust/n:.1f}%   median {med} trades to pass")
print(f"  apex_sim.py reported:  PASS 90.3%   median 41 trades  ->  {'MATCH (engine trustworthy)' if npass and abs(100*npass/n-90.3)<6 and med and abs(med-41)<8 else 'MISMATCH (investigate)'}")
