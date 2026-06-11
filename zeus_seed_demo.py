"""Seed the ZEUS demo preview (data/zeus_demo_*.db). SIMULATED data only —
production journal/store are never touched. Deterministic (seeded RNG).
Run: python3 zeus_seed_demo.py && python3 zeus_server.py --demo
"""
import json
import os
import random
from datetime import datetime, timedelta, timezone

from journal import Journal
from store import Store

random.seed(7)
JP, SP = "data/zeus_demo_journal.db", "data/zeus_demo_store.db"
for p in (JP, SP):
    if os.path.exists(p):
        os.remove(p)
j, store = Journal(JP), Store(SP)

ACCTS = [
    dict(firm="MFFU", name="MFFU-PRO-1", size=150_000, phase="FUNDED", dd=4500,
         alloc_a=4, alloc_b=2, paid=6_643.0),
    dict(firm="MFFU", name="MFFU-PRO-2", size=150_000, phase="FUNDED", dd=4500,
         alloc_a=4, alloc_b=2, paid=11_327.0),
    dict(firm="MFFU", name="MFFU-PRO-3", size=150_000, phase="FUNDED", dd=4500,
         alloc_a=4, alloc_b=2, paid=8_596.0),
    dict(firm="Topstep", name="TS-XFA-1", size=150_000, phase="FUNDED", dd=4500,
         alloc_a=4, alloc_b=2, paid=6_222.0),
    dict(firm="Topstep", name="TS-XFA-2", size=150_000, phase="EVAL", dd=4500,
         alloc_a=4, alloc_b=2, paid=0.0),
]

now = datetime.now(timezone.utc)
t = now - timedelta(days=28)
sig_n = 0
bal = {a["name"]: float(a["size"]) + random.uniform(1500, 4500) for a in ACCTS}

while t < now - timedelta(hours=4):
    if t.weekday() < 5 and random.random() < 0.62:           # a trading day with signals
        for strat, prob, qty_per in (("A", 0.55, 4), ("B", 0.72, 2)):
            if random.random() > prob:
                continue
            sig_n += 1
            side = random.choice(["Buy", "Sell"])
            base_px = 24200 + random.uniform(-300, 300)
            stop_off = random.uniform(45, 70) if strat == "A" else random.uniform(18, 30)
            win = random.random() < (0.47 if strat == "A" else 0.52)
            ts = t.replace(hour=random.choice((13, 14, 15)),
                           minute=random.randint(0, 59), second=0)
            for acc in ACCTS:
                qty = qty_per if strat == "A" else acc["alloc_b"]
                cl = j.intent(acc["name"], strat, strat,
                              ts.isoformat() + f"-{sig_n}", "entry",
                              dict(side=side, qty=qty, entry=round(base_px, 2),
                                   stop=round(base_px - stop_off if side == "Buy"
                                              else base_px + stop_off, 2),
                                   target=round(base_px + 2 * stop_off if side == "Buy"
                                                else base_px - 2 * stop_off, 2)))
                if cl is None:
                    continue
                iso = ts.isoformat()
                j.append("SEND", acc["name"], cl, ts=iso)
                j.append("ACK", acc["name"], cl, payload=dict(broker_order_id=sig_n * 10),
                         ts=iso)
                fill_px = base_px + random.uniform(-0.75, 0.75)
                j.append("FILL", acc["name"], cl,
                         payload=dict(qty=qty, side=side, px=round(fill_px, 2),
                                      fill_id=f"d{sig_n}-{acc['name']}"), ts=iso)
                j.append("BRACKET_SENT", acc["name"], cl, ts=iso)
                j.append("BRACKET_CONFIRMED", acc["name"], cl,
                         payload=dict(broker_order_id=sig_n * 10 + 1), ts=iso)
                if win:
                    move = stop_off * (2 if random.random() < 0.55 else 1.2)
                else:
                    move = -stop_off
                exit_px = fill_px + (move if side == "Buy" else -move)
                xts = (ts + timedelta(minutes=random.randint(8, 150))).isoformat()
                j.append("EXIT", acc["name"], cl,
                         payload=dict(px=round(exit_px, 2),
                                      reason=("target" if win else "stop"),
                                      slip=round(abs(random.gauss(1.2, 0.6)), 2)),
                         ts=xts)
                bal[acc["name"]] += move * 2.0 * qty
    t += timedelta(days=1)

# one drill RECON_ALERT + one P3 episode marker for realism
j.append("RECON_ALERT", "TS-XFA-1", payload=dict(
    check="CHECK2_NAKED_POSITION", tier="BLACK", detail=dict(drill=True),
    note="Gate-5 forced drill — resolved in 41s"), ts=(now - timedelta(days=6)).isoformat())

accounts_state = []
for a in ACCTS:
    b = round(bal[a["name"]], 2)
    floor = (a["size"] - a["dd"]) if a["phase"] == "EVAL" else a["size"] + 100
    accounts_state.append(dict(
        a, balance=b, floor=floor, open_qty=0,
        p3_braked=(b - floor) < 0.4 * a["dd"],
        daily_loss_used=round(random.uniform(0, 320), 2), trades_today=0,
        open_position=None, working_stop=None, working_target=None,
        last_recon="clean", last_payout=("2026-06-02" if a["paid"] else None),
        next_payout_eligible="2026-06-16"))
store.set_state(zeus_accounts=json.dumps(accounts_state),
                heartbeat_ts=(now - timedelta(seconds=22)).isoformat(),
                feed_last_bar_ts=(now - timedelta(seconds=31)).isoformat(),
                broker_sync_ts=(now - timedelta(seconds=19)).isoformat(),
                recon_ts=(now - timedelta(seconds=19)).isoformat())
n = j.con.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
print(f"demo seeded: {n} journal events · {len(ACCTS)} accounts · balances "
      + ", ".join(f"{k}={v:,.0f}" for k, v in bal.items()))
