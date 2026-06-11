"""
Simulation tests for the Profile A v2 two-leg (Exit #3) bracket. NETWORK-FREE.

Drives `TradovateClient.place_bracket_two_targets(..., dry_run=True)` and the underlying
`TwoLegBracket` state machine through every lifecycle, asserting the safety invariant
after each event. NO live orders are ever sent (dry_run only; the live path raises).

Run:   python test_two_leg_bracket.py
Exit code 0 = all pass.
"""
import sys
import tradovate_client as tc
from tradovate_client import TradovateClient, TwoLegBracket, TradovateError

# a client with dummy config — constructor does no network
CLI = TradovateClient({"env": "demo", "account_spec": None},
                      {"demo": {"rest": "x", "ws": "y"}, "live": {"rest": "x", "ws": "y"}})

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if (detail and not cond) else ""))


def invariant(b, label):
    """Stop must always exactly cover the open position; flat => nothing working."""
    op = b.open_pos()
    wo = b.working_orders()
    if op > 0:
        ok = ("STOP" in wo) and wo["STOP"]["qty"] == op
        check(f"{label}: STOP covers open pos ({op})", ok, f"working={ {k:v['qty'] for k,v in wo.items()} }")
    else:
        ok = all(not o.get("working") for o in b.orders.values())
        check(f"{label}: flat => no working orders", ok, f"working={list(wo)}")


def n_place(b, role):
    return sum(1 for a in b.actions if a["op"] == "PLACE" and a["role"] == role)


def new(action="Buy", qty=2, entry=22000.0, stop=21980.0):
    return CLI.place_bracket_two_targets("NQM6", action, qty, entry, stop, dry_run=True)


# ---------------------------------------------------------------- scenarios
def s1_tp1_then_tp2():
    print("\nScenario 1 — TP1 then TP2 (long 2):")
    b = new()
    check("entry limit placed", "ENTRY" in b.working_orders() and b.working_orders()["ENTRY"]["type"] == "Limit")
    check("no exit legs before entry fill", not any(r in b.working_orders() for r in ("STOP", "TP1", "TP2")))
    b.on_fill("ENTRY", 2)
    wo = b.working_orders()
    check("after entry: STOP=2 TP1=1 TP2=1", wo["STOP"]["qty"] == 2 and wo["TP1"]["qty"] == 1 and wo["TP2"]["qty"] == 1,
          f"{ {k:v['qty'] for k,v in wo.items()} }")
    check("TP1@+1R=22020, TP2@+2R=22040", wo["TP1"]["price"] == 22020 and wo["TP2"]["price"] == 22040)
    invariant(b, "s1 post-entry")
    b.on_fill("TP1", 1)
    check("after TP1: STOP reduced to 1", b.working_orders()["STOP"]["qty"] == 1)
    invariant(b, "s1 post-TP1")
    b.on_fill("TP2", 1)
    check("after TP2: closed & flat", b.closed and b.open_pos() == 0)
    invariant(b, "s1 post-TP2")


def s2_tp1_then_stop():
    print("\nScenario 2 — TP1 then STOP (long 2):")
    b = new(); b.on_fill("ENTRY", 2); b.on_fill("TP1", 1)
    check("STOP reduced to 1 after TP1", b.working_orders()["STOP"]["qty"] == 1)
    b.on_fill("STOP", 1)
    check("after stop: closed & flat", b.closed and b.open_pos() == 0)
    check("TP2 cancelled", not b.orders["TP2"]["working"])
    invariant(b, "s2 final")


def s3_stop_before_tp1():
    print("\nScenario 3 — STOP before any target (long 2):")
    b = new(); b.on_fill("ENTRY", 2)
    b.on_fill("STOP", 2)
    check("after full stop: closed & flat", b.closed and b.open_pos() == 0)
    check("both targets cancelled", not b.orders["TP1"]["working"] and not b.orders["TP2"]["working"])
    invariant(b, "s3 final")


def s4_entry_not_filled():
    print("\nScenario 4 — entry never fills:")
    b = new()
    check("only ENTRY working, no exits", list(b.working_orders()) == ["ENTRY"])
    check("no position", b.open_pos() == 0 and not b.closed)
    b.cancel_entry()
    check("entry cancelled, nothing working", b.closed and not b.working_orders())
    check("no exit legs were ever placed", n_place(b, "STOP") == 0 and n_place(b, "TP1") == 0 and n_place(b, "TP2") == 0)


def s5_partial_entry():
    print("\nScenario 5 — partial ENTRY fill (long 2, fills 1 then 1):")
    b = new()
    b.on_fill("ENTRY", 1)
    wo = b.working_orders()
    check("partial entry: STOP=1, no TP1 (can't split 1), TP2=1", wo["STOP"]["qty"] == 1 and "TP1" not in wo and wo["TP2"]["qty"] == 1,
          f"{ {k:v['qty'] for k,v in wo.items()} }")
    invariant(b, "s5 after 1st partial (never naked)")
    b.on_fill("ENTRY", 1)
    wo = b.working_orders()
    check("full entry: STOP=2, TP1=1, TP2=1", wo["STOP"]["qty"] == 2 and wo["TP1"]["qty"] == 1 and wo["TP2"]["qty"] == 1)
    invariant(b, "s5 after full entry")


def s5b_partial_target():
    print("\nScenario 5b — partial TARGET fill (long 4):")
    b = new(qty=4)
    b.on_fill("ENTRY", 4)
    wo = b.working_orders()
    check("entry 4: STOP=4 TP1=2 TP2=2", wo["STOP"]["qty"] == 4 and wo["TP1"]["qty"] == 2 and wo["TP2"]["qty"] == 2)
    b.on_fill("TP1", 1)                                  # partial fill of the 2-lot TP1
    wo = b.working_orders()
    check("partial TP1: STOP=3, TP1 remaining=1", wo["STOP"]["qty"] == 3 and wo["TP1"]["qty"] == 1,
          f"{ {k:v['qty'] for k,v in wo.items()} }")
    invariant(b, "s5b after partial TP1")
    b.on_fill("TP1", 1); b.on_fill("TP2", 2)
    check("all targets done -> closed & flat", b.closed and b.open_pos() == 0)
    invariant(b, "s5b final")


def s6_reconcile():
    print("\nScenario 6 — disconnect / restart reconciliation:")
    b = new(); b.on_fill("ENTRY", 2); b.on_fill("TP1", 1)   # state: open 1, STOP=1, TP2 working
    snap = b.snapshot()
    bid = b.bid
    # --- restart from snapshot, broker shows STOP+TP2 working, position 1 ---
    r = TwoLegBracket.from_snapshot(snap)
    before = len(r.actions)
    ok = r.reconcile({f"{bid}-STOP", f"{bid}-TP2"}, net_position=1)
    check("reconcile OK (pos matches)", ok)
    check("no duplicate PLACE on restart", n_place(r, "STOP") == 0 and n_place(r, "TP2") == 0)
    invariant(r, "s6 after clean restart")
    # --- broker MISSING the protective stop -> must re-place it ---
    r2 = TwoLegBracket.from_snapshot(snap)
    r2.reconcile({f"{bid}-TP2"}, net_position=1)
    check("missing STOP is re-placed", n_place(r2, "STOP") == 1)
    invariant(r2, "s6 after stop re-place")
    # --- broker position disagrees -> flatten + alert, no silent continue ---
    r3 = TwoLegBracket.from_snapshot(snap)
    ok3 = r3.reconcile({f"{bid}-STOP", f"{bid}-TP2"}, net_position=0)
    check("position mismatch -> reconcile returns False + FLATTEN intent",
          (ok3 is False) and any(a["op"] == "FLATTEN" for a in r3.actions))


def s7_no_duplicates():
    print("\nScenario 7 — duplicate-order prevention:")
    b = new()
    b.start(); b.start()                                  # repeated starts
    check("ENTRY placed once despite repeat start()", n_place(b, "ENTRY") == 1)
    b.on_fill("ENTRY", 2)
    b._reconcile(); b._reconcile()                        # repeated reconciles
    check("each exit leg placed exactly once", n_place(b, "STOP") == 1 and n_place(b, "TP1") == 1 and n_place(b, "TP2") == 1)


def s8_short_side():
    print("\nScenario 8 — SHORT side price geometry (sell 2):")
    b = new(action="Sell", entry=22000.0, stop=22020.0)  # R=20; short -> TPs below
    b.on_fill("ENTRY", 2)
    wo = b.working_orders()
    check("short TP1=21980 (+1R down), TP2=21960 (+2R down)", wo["TP1"]["price"] == 21980 and wo["TP2"]["price"] == 21960)
    check("exit legs are Buy-side", wo["STOP"]["side"] == "Buy" and wo["TP1"]["side"] == "Buy")
    invariant(b, "s8 short")


def s9_existing_single_target_intact():
    print("\nScenario 9 — single-target place_bracket(): gated by default, works only when explicitly enabled:")
    captured = {}
    CLI._post = lambda path, body: captured.update(path=path, body=body) or {"ok": True}  # monkeypatch, no network
    CLI.account_id = 999
    # default state: live orders DISABLED -> legacy order method must refuse (the gate we added)
    try:
        CLI.place_bracket("NQM6", "Buy", 2, 21980.0, 22040.0)
        check("place_bracket REFUSES when live disabled", False, "did NOT raise")
    except TradovateError:
        check("place_bracket REFUSES when live disabled (raises TradovateError)", True)
    # explicitly enable BOTH gates, then it builds + sends the OSO as before
    tc.LIVE_ORDERS_ENABLED = True; CLI.live_orders_ok = True
    try:
        resp = CLI.place_bracket("NQM6", "Buy", 2, 21980.0, 22040.0)
    finally:
        tc.LIVE_ORDERS_ENABLED = False; CLI.live_orders_ok = False   # restore safe default
    body = captured.get("body", {})
    check("OSO sent to /order/placeOSO (when enabled)", captured.get("path") == "/order/placeOSO")
    check("entry + stop bracket1 + limit bracket2 present",
          body.get("entryVersion", {}).get("orderType") == "Market"
          and body.get("bracket1", {}).get("orderType") == "Stop"
          and body.get("bracket2", {}).get("orderType") == "Limit")
    check("single-target function unchanged & callable", resp == {"ok": True})


def s10_no_live_orders():
    print("\nScenario 10 — live send path is disabled:")
    # Default (gated): _guard_live() refuses with TradovateError. If both gates were enabled it would
    # still refuse via NotImplementedError (two-leg live send is unimplemented). Either is a hard refusal.
    try:
        CLI.place_bracket_two_targets("NQM6", "Buy", 2, 22000.0, 21980.0, dry_run=False)
        check("dry_run=False refuses to send", False, "did NOT raise")
    except (TradovateError, NotImplementedError):
        check("dry_run=False refuses to send (raises)", True)


if __name__ == "__main__":
    for fn in (s1_tp1_then_tp2, s2_tp1_then_stop, s3_stop_before_tp1, s4_entry_not_filled,
               s5_partial_entry, s5b_partial_target, s6_reconcile, s7_no_duplicates,
               s8_short_side, s9_existing_single_target_intact, s10_no_live_orders):
        fn()
    print(f"\n================  {len(PASS)} passed, {len(FAIL)} failed  ================")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)
