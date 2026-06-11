"""W6 — Recovery battery. Goal: DESTROY recovery logic.
Randomized crash-stage × broker-outcome matrix (2,000+ seeded scenarios) + directed
edge cases. Invariants for EVERY scenario:
  I-1 no unresolved (ambiguous) SENDs survive recovery
  I-2 idempotency: a second recover() appends no new lifecycle events
  I-3 convergence-or-alarm: ledger net == broker net, OR a discrepancy is REPORTED
  I-4 directed status expectations for every well-defined (stage, outcome) pair
"""
import pytest
import random
from journal import Journal
from recovery import recover
from test_b0_thor_battery import FakeBroker

ACCT = "A1"
STAGES = ("INTENT", "SEND", "ACK", "PARTIAL", "FILL_NO_BRACKET", "BRACKET_OK",
          "CANCEL_SENT", "MODIFY_SENT")
OUTCOMES = ("absent", "working", "filled_partial", "filled_full", "closed_gone")


def build(j, b, stage, outcome, stop_present, sig):
    """Construct ledger cut at `stage` and broker reality `outcome`. Returns cl."""
    cl = j.intent(ACCT, "A", "A", f"s{sig}", "entry", dict(side="Buy", qty=4))
    led_filled = 0
    if stage != "INTENT":
        j.append("SEND", ACCT, cl)
    if stage in ("ACK", "PARTIAL", "FILL_NO_BRACKET", "BRACKET_OK",
                 "CANCEL_SENT", "MODIFY_SENT"):
        j.append("ACK", ACCT, cl, payload=dict(broker_order_id=100))
    if stage in ("PARTIAL", "MODIFY_SENT"):
        j.append("PARTIAL_FILL", ACCT, cl,
                 payload=dict(qty=2, side="Buy", fill_id="f1", broker_order_id=100))
        led_filled = 2
    if stage in ("FILL_NO_BRACKET", "BRACKET_OK"):
        j.append("PARTIAL_FILL", ACCT, cl,
                 payload=dict(qty=2, side="Buy", fill_id="f1", broker_order_id=100))
        j.append("FILL", ACCT, cl,
                 payload=dict(qty=2, side="Buy", fill_id="f2", broker_order_id=100))
        led_filled = 4
    if stage == "BRACKET_OK":
        j.append("BRACKET_SENT", ACCT, cl, payload=dict(stop=21950.0))
        j.append("BRACKET_CONFIRMED", ACCT, cl, payload=dict(broker_order_id=101))
    if stage == "CANCEL_SENT":
        j.append("CANCEL_SENT", ACCT, cl)
    if stage == "MODIFY_SENT":
        j.append("MODIFY_SENT", ACCT, cl, payload=dict(qty=2))

    # broker reality
    brk_filled = dict(absent=0, working=0, filled_partial=2, filled_full=4,
                      closed_gone=4)[outcome]
    if outcome == "working":
        b._orders.append(dict(account_id=ACCT, broker_order_id=100, order_type="Limit",
                              action="Buy", qty=4 - led_filled, cl_ord_id=cl))
    if brk_filled >= 2:
        b._fills.append(dict(account_id=ACCT, broker_order_id=100, fill_id="f1",
                             qty=2, px=22000.0, ts_utc="t", cl_ord_id=cl))
    if brk_filled == 4:
        b._fills.append(dict(account_id=ACCT, broker_order_id=100, fill_id="f2",
                             qty=2, px=22000.5, ts_utc="t", cl_ord_id=cl))
    if outcome == "closed_gone":
        b._fills.append(dict(account_id=ACCT, broker_order_id=101, fill_id="f3",
                             qty=4, px=22050.0, ts_utc="t", closes_cl=cl))
    else:
        if brk_filled:
            b._positions.append(dict(account_id=ACCT, qty=brk_filled, contract="MNQ"))
        if brk_filled and stop_present:
            b._orders.append(dict(account_id=ACCT, broker_order_id=101,
                                  order_type="Stop", action="Sell", qty=brk_filled,
                                  cl_ord_id=cl))
    return cl


def lifecycle_count(j):
    return j.con.execute(
        "SELECT COUNT(*) FROM ledger WHERE event_type != 'RECON_ALERT'").fetchone()[0]


def ledger_net(j):
    return sum(p["qty"] for p in j.open_positions().values())


def broker_net(b):
    return sum(p["qty"] for p in b.positions())


def run_invariants(j, b, n_recovers):
    rep = recover(j, b)
    assert j.unresolved_sends() == []                                   # I-1
    before = lifecycle_count(j)
    for _ in range(n_recovers - 1):
        recover(j, b)
    assert lifecycle_count(j) == before, "recovery not idempotent"      # I-2
    if ledger_net(j) != broker_net(b):                                  # I-3
        assert rep["discrepancies"] or recover(j, b)["discrepancies"], \
            f"silent divergence: ledger {ledger_net(j)} vs broker {broker_net(b)}"
    return rep


def test_randomized_matrix_2000(tmp_path):
    rng = random.Random(42)
    fails = []
    for i in range(2000):
        j = Journal(str(tmp_path / f"j{i % 8}_{i}.db"))
        b = FakeBroker()
        stage = rng.choice(STAGES)
        outcome = rng.choice(OUTCOMES)
        stop = rng.random() < 0.5
        try:
            build(j, b, stage, outcome, stop, sig=i)
            run_invariants(j, b, n_recovers=rng.choice((2, 3)))
        except AssertionError as e:
            fails.append((i, stage, outcome, stop, str(e)))
        j.con.close()
    assert not fails, f"{len(fails)} scenario failures, first: {fails[:3]}"


@pytest.mark.parametrize("stage,outcome,expected", [
    ("INTENT", "absent", "pending_send"),
    ("SEND", "absent", "rejected"),
    ("SEND", "working", "working"),
    ("SEND", "filled_full", "open"),
    ("SEND", "filled_partial", "partial"),
    ("PARTIAL", "filled_full", "open"),
    ("FILL_NO_BRACKET", "filled_full", "open"),
    ("CANCEL_SENT", "absent", "cancelled"),
    ("CANCEL_SENT", "working", "working"),
    ("BRACKET_OK", "closed_gone", "closed"),
])
def test_directed_status_convergence(tmp_path, stage, outcome, expected):
    j = Journal(str(tmp_path / "j.db"))
    b = FakeBroker()
    cl = build(j, b, stage, outcome, stop_present=True, sig=99)
    recover(j, b)
    assert j.status(cl) == expected                                     # I-4


def test_modify_sent_confirmed_on_qty_match(tmp_path):
    j = Journal(str(tmp_path / "j.db"))
    b = FakeBroker()
    cl = build(j, b, "MODIFY_SENT", "working", stop_present=True, sig=7)
    # broker shows working order already at requested qty 2
    b._orders = [dict(account_id=ACCT, broker_order_id=100, order_type="Limit",
                      action="Buy", qty=2, cl_ord_id=cl)]
    recover(j, b)
    assert j.has_event(cl, "MODIFY_CONFIRMED")


def test_fill_sweep_dedupes_by_fill_id(tmp_path):
    """Broker re-delivers f1 (officially expected duplicate) — must not double-count."""
    j = Journal(str(tmp_path / "j.db"))
    b = FakeBroker()
    cl = build(j, b, "PARTIAL", "filled_partial", stop_present=True, sig=5)
    recover(j, b)
    assert j.status(cl) == "partial"
    pos = j.open_positions()[(ACCT, cl)]
    assert pos["qty"] == 2                          # f1 NOT double-counted
    recover(j, b)
    assert j.open_positions()[(ACCT, cl)]["qty"] == 2


def test_crash_chain_multiple_restarts(tmp_path):
    """Crash, recover, crash again mid-day, recover, recover — one final state."""
    j = Journal(str(tmp_path / "j.db"))
    b = FakeBroker()
    cl = build(j, b, "SEND", "filled_full", stop_present=False, sig=11)
    r1 = recover(j, b)
    assert j.status(cl) == "open"
    assert any(d["check"] == "CHECK2_NAKED_POSITION" for d in r1["discrepancies"])
    n = lifecycle_count(j)
    for _ in range(3):
        recover(j, b)
    assert lifecycle_count(j) == n and j.status(cl) == "open"


def test_ghost_position_no_lifecycle_is_alarmed(tmp_path):
    """Broker position with NO ledger lifecycle at all — must be reported, never adopted."""
    j = Journal(str(tmp_path / "j.db"))
    b = FakeBroker()
    b._positions = [dict(account_id=ACCT, qty=4, contract="MNQ")]
    rep = recover(j, b)
    assert any(d["check"] == "CHECK1_POSITION_MISMATCH" for d in rep["discrepancies"])
    assert j.open_positions() == {}                 # never silently adopted
