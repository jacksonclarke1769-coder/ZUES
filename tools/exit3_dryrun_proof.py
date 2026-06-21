"""EXITFORGE Phase 10 — dry-run payload proof. Builds (does NOT send) the two Exit #3
bracket legs for one Profile A signal and prints them. No webhook, no live. Run:
    python3 tools/exit3_dryrun_proof.py
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bridge_traderspost as BP
from runtime_config import resolve_exit_model

# one representative A3 Profile A short (the reported trade)
SIG = dict(side="short", entry=30654.83, stop=30771.50, target=30421.49)
ACC, QTY = "MFFU-50K-1", 3

print(f"EXIT_MODEL = {resolve_exit_model('research')}   account = {ACC}   qty = {QTY} MNQ   (DRY-RUN — no sends)\n")
legs, err = BP.build_entry_exit3(account=ACC, strategy="A", setup="sweep-OTE",
                                 signal_ts="2026-06-16T13:46:00+00:00", side=SIG["side"],
                                 qty=QTY, entry=SIG["entry"], stop=SIG["stop"], target=SIG["target"])
if err:
    print("BUILD FAILED (fail-closed):", err); sys.exit(1)
for L in legs:
    p = L["payload"]
    print(f"--- {L['role'].upper()} ({'CORE, sent first' if L['role']=='entry_tp2' else 'scalp, sent second'}) ---")
    print(f"  {p['action']} {p['quantity']} {p['ticker']}  +{int(L['r_target'])}R target")
    print(f"  limit  {p['limitPrice']}")
    print(f"  stop   {p['stopLoss']['stopPrice']}   (shared protective stop)")
    print(f"  target {p['takeProfit']['limitPrice']}")
    print(f"  signalId {p['extras']['signalId']}")
    print()
stops = {L['payload']['stopLoss']['stopPrice'] for L in legs}
qtys = sum(L['payload']['quantity'] for L in legs)
print(f"INTEGRITY: legs={len(legs)}  total_qty={qtys}  shared_stop={'YES' if len(stops)==1 else 'NO!'}  "
      f"distinct_ids={'YES' if len({L['payload']['extras']['signalId'] for L in legs})==len(legs) else 'NO!'}")
print("NO single full-qty @ 2R payload was built (Exit #3 split only).")
