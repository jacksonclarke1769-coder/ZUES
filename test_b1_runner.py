"""B1 runner battery — proves the live execution lifecycle against SimBroker,
offline, credential-free. Every B1_DESIGN invariant and every THOR/LOKI order
risk that B1 owns has a test here. When TradovateBrokerView replaces SimBroker
(post A3 spike) this same battery is the acceptance gate.
"""
import pytest

from journal import Journal
from store import Store
from sim_broker import SimBroker
from b1_runner import B1Runner
from flatten import EmergencyFlatten

ACCT = "MFFU-50K-1"
SIG = dict(side="long", entry=21000.0, stop=20980.0, target=21040.0,
           ts_signal="2026-06-22T13:45:00+00:00")


def _stack(tmp_path, accounts=(ACCT,)):
    j = Journal(str(tmp_path / "journal.db"))
    st = Store(str(tmp_path / "store.db"))
    b = SimBroker(list(accounts))
    em = EmergencyFlatten(j, b, st)
    r = B1Runner(j, b, st, accounts=list(accounts), emergency=em)
    return j, st, b, em, r


# ----------------------------- clean path -----------------------------
def test_clean_path_full_lifecycle(tmp_path):
    j, st, b, em, r = _stack(tmp_path)
    res = r.on_signal(ACCT, SIG, qty=2)
    assert res["action"] == "acked"
    cl = res["cl"]
    assert j.status(cl) == "working"

    b.fill_entry(cl)                       # broker fills the entry
    s = r.poll()
    assert (cl, "FILL", 2) in s["fills"]
    assert cl in s["bracket_confirmed"]    # I3: stop WORKING == filled qty
    assert j.status(cl) == "open"
    assert j.has_event(cl, "BRACKET_CONFIRMED")

    b.fill_target(cl)                      # take profit
    s = r.poll()
    assert any(f[0] == cl and f[1] == "EXIT" for f in s["fills"])
    assert j.status(cl) == "closed"
    assert not em.locked()                 # clean book, no incident


# ------------------------- I1/I2 no resend ----------------------------
def test_timeout_is_sent_unknown_and_never_resends(tmp_path):
    j, st, b, em, r = _stack(tmp_path)
    b.disconnect()                         # send will raise (timeout)
    res = r.on_signal(ACCT, SIG, qty=2)
    assert res["action"] == "sent_unknown"
    cl = res["cl"]
    assert j.status(cl) == "sent_unknown"
    assert j.has_event(cl, "SEND") and not j.has_event(cl, "ACK")
    # I6 local: the account is now no-new-entries until the slot resolves
    ok, why = r.can_trade(ACCT)
    assert not ok and why == "unresolved_send_on_account"
    # I2: even re-submitting the SAME signal must NOT transmit again
    res2 = r.on_signal(ACCT, SIG, qty=2)
    assert res2["action"] in ("blocked", "duplicate")
    assert sum(1 for e in j.events(cl) if e["event_type"] == "SEND") == 1


def test_startup_recovery_resolves_unknown_send_from_broker_truth(tmp_path):
    j, st, b, em, r = _stack(tmp_path)
    # Simulate: SEND journaled, order actually reached the broker, ACK lost.
    cl = j.intent(ACCT, "profileA", "A", SIG["ts_signal"], "entry",
                  payload=dict(side="Buy", qty=2, entry=SIG["entry"],
                               stop=SIG["stop"], target=SIG["target"]))
    j.append("SEND", ACCT, cl, payload=dict(qty=2))
    b.place_oso(cl, ACCT, "Buy", 2, SIG["entry"], SIG["stop"], SIG["target"])
    assert j.status(cl) == "sent_unknown"

    rep = r.startup()                      # recovery from broker truth (Part 1F)
    assert j.status(cl) == "working"       # resolved to ACK(source=recovery)
    assert rep["ready"] is True
    ok, _ = r.can_trade(ACCT)
    assert ok                               # account un-halted once resolved


# --------------------------- partial fills ----------------------------
def test_partial_fill_tracks_bracket_to_filled_qty(tmp_path):
    j, st, b, em, r = _stack(tmp_path)
    cl = r.on_signal(ACCT, SIG, qty=4)["cl"]
    b.partial_fill_entry(cl, qty=2)        # only 2 of 4 fill
    s = r.poll()
    assert (cl, "PARTIAL_FILL", 2) in s["fills"]
    assert j.status(cl) == "partial"
    assert cl in s["bracket_confirmed"]    # protective stop sized to the 2 filled
    # the rest fills later -> FILL, still one open lifecycle
    b.partial_fill_entry(cl, qty=2)
    s = r.poll()
    assert (cl, "FILL", 2) in s["fills"]
    assert j.status(cl) == "open"


# ------------------------------ rejects -------------------------------
def test_reject_is_terminal_and_slot_is_dead(tmp_path):
    j, st, b, em, r = _stack(tmp_path)
    b.reject_next_send(reason="margin")
    res = r.on_signal(ACCT, SIG, qty=2)
    assert res["action"] == "rejected"
    cl = res["cl"]
    assert j.status(cl) == "rejected"
    # a re-fire of the same slot is refused by the deterministic cl_ord_id
    res2 = r.on_signal(ACCT, SIG, qty=2)
    assert res2["action"] == "duplicate"


# ---------------- recon BLACK -> emergency flatten --------------------
def test_recon_black_routes_to_emergency_flatten_and_locks(tmp_path):
    j, st, b, em, r = _stack(tmp_path)
    # Broker shows a position the ledger never authorised (CHECK1 mismatch / CHECK3).
    b.position[ACCT] = 3
    b._fill_seq += 1
    b.fills.append(dict(account_id=ACCT, broker_order_id="X-1", cl_ord_id=None,
                        fill_id=b._fill_seq, qty=3, px=21000.0, ts_utc=None,
                        leg="entry", closes_cl=None))
    s1 = r.poll()                          # cycle 1: within grace, not yet confirmed
    s2 = r.poll()                          # cycle 2: confirmed BLACK
    assert s2["flattened"] is True
    assert em.locked()
    assert b.position[ACCT] == 0           # flattened to truth-flat
    # I6: locked book takes no new entries
    ok, why = r.can_trade(ACCT)
    assert not ok and why == "emergency_lockout"


def test_fail_closed_when_locked(tmp_path):
    j, st, b, em, r = _stack(tmp_path)
    em.trigger("manual_test", account_id="ALL")
    res = r.on_signal(ACCT, SIG, qty=2)
    assert res["action"] == "blocked"
    assert res["reason"] == "emergency_lockout"


# ----------------------- declared manual flatten ----------------------
def test_declared_flatten_exits_without_lockout(tmp_path):
    j, st, b, em, r = _stack(tmp_path)
    cl = r.on_signal(ACCT, SIG, qty=2)["cl"]
    b.fill_entry(cl); r.poll()
    out = r.flatten_account(ACCT, reason="operator_eod")
    assert cl in out["exited"]
    assert j.status(cl) == "closed"
    assert b.position[ACCT] == 0
    assert not em.locked()                 # declared != emergency


# --------------------------- idempotency ------------------------------
def test_poll_is_idempotent_on_fills(tmp_path):
    j, st, b, em, r = _stack(tmp_path)
    cl = r.on_signal(ACCT, SIG, qty=2)["cl"]
    b.fill_entry(cl)
    r.poll()
    s = r.poll()                           # cursor advanced -> no re-record
    assert s["fills"] == []
    fills = [e for e in j.events(cl) if e["event_type"] in ("FILL", "PARTIAL_FILL")]
    assert len(fills) == 1


def test_account_isolation(tmp_path):
    a2 = "MFFU-50K-2"
    j, st, b, em, r = _stack(tmp_path, accounts=(ACCT, a2))
    b.disconnect()
    r.on_signal(ACCT, SIG, qty=2)          # acct1 now has an unresolved send
    b.reconnect()
    # acct2 is independent and must still be tradeable (I5)
    ok, _ = r.can_trade(a2)
    assert ok
    ok1, why1 = r.can_trade(ACCT)
    assert not ok1 and why1 == "unresolved_send_on_account"
