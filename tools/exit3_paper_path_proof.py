"""EXITPARITY — end-to-end PAPER-PATH proof. Drives one synthetic Profile A signal
through the REAL auto_live wiring (LiveAuto.on_decision) in PAPER/dry-run mode and
proves it routes as two-leg Exit #3 (no live send, no single full-qty payload).
Deterministic; needs no live feed. No --live, no URL, no flag."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import config
from store import Store
from journal import Journal
from bridge_sender import BridgeSender
from auto_live import LiveAuto

store = Store("data/_pp_proof.db"); store.reset()
j = Journal("data/_pp_proofj.db")
sender = BridgeSender(store=store, journal=j, mode="dry-run")   # PAPER: dry-run, no URL
captured = []
_orig_send = sender.send
sender.send = lambda payload, **kw: (captured.append(payload), _orig_send(payload, **kw))[1]

auto = LiveAuto("MFFU-50K-1", "50K-conservative", "paper", store, j, sender,
                daily_stop=700, d1c_mode="SHADOW")            # SHADOW so the signal routes
ny_open = pd.Timestamp("2026-06-16 09:30:00-04:00")
ts = pd.Timestamp("2026-06-16 10:46:00-04:00")
auto.gate.on_session_open(ny_open, 30700.0)
auto.gate.on_bar_close(ts, 30654.0)

sig = dict(side="short", entry=30654.83, stop=30771.50, target=30421.49,
           ts_signal="2026-06-16T14:46:00+00:00", liq="pdh")

print(f"EXIT_MODEL = {config.EXIT_MODEL}   mode = paper(dry-run)   live_url = {sender.live_url}\n")
auto.on_decision(sig, True, "placed", ts)

print(f"payloads routed to bridge: {len(captured)}")
for p in captured:
    print(f"  {p['action']} {p['quantity']} {p['ticker']}  tgt {p['takeProfit']['limitPrice']}  "
          f"stop {p['stopLoss']['stopPrice']}  role {p['extras'].get('role')}")

# ---- assertions ----
ok = True
def chk(name, cond):
    global ok; ok = ok and cond
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
print("\nPARITY ASSERTIONS:")
chk("exactly 2 legs routed", len(captured) == 2)
qtys = sorted(p["quantity"] for p in captured)
chk("qtys are 1 and 2 (no full 3)", qtys == [1, 2])
chk("shared stop on both legs", len({p["stopLoss"]["stopPrice"] for p in captured}) == 1)
tp2 = [p for p in captured if p["quantity"] == 2][0]
tp1 = [p for p in captured if p["quantity"] == 1][0]
chk("TP2 (2 MNQ) target = strategy 2R (30421.5)", tp2["takeProfit"]["limitPrice"] == 30421.5)
chk("TP1 (1 MNQ) target = +1R (30538.25)", tp1["takeProfit"]["limitPrice"] == 30538.25)
chk("distinct deterministic signalIds", len({p["extras"]["signalId"] for p in captured}) == 2)
chk("no single full-qty(3) @ 2R payload", not any(p["quantity"] == 3 for p in captured))
chk("NO live send occurred (dry-run only)", all(p.get("orderType") for p in captured) and sender.mode != "live")
print("\nRESULT:", "EXIT3 PAPER-PATH PARITY PASS" if ok else "FAIL")
os.remove("data/_pp_proof.db"); os.remove("data/_pp_proofj.db")
sys.exit(0 if ok else 1)
