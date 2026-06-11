"""W7 — Reconciliation battery. Goal: BREAK the reconciler.
Detection completeness: every injected discrepancy class must be confirmed.
False-positive freedom: a coherent world must stay silent through many cycles.
Robustness: corrupted ledger payloads and degenerate broker data must not crash it.
"""
import json
import random
import pytest
from journal import Journal
from recon import Reconciler
from test_b0_thor_battery import FakeBroker

ACCT = "A1"


def coherent_world(tmp_path, name="w"):
    """Ledger and broker in perfect agreement: open 4-lot, stop working, balance sane."""
    j = Journal(str(tmp_path / f"{name}.db"))
    b = FakeBroker()
    cl = j.intent(ACCT, "A", "A", "sig", "entry", dict(side="Buy", qty=4))
    j.append("SEND", ACCT, cl)
    j.append("ACK", ACCT, cl, payload=dict(broker_order_id=100))
    j.append("FILL", ACCT, cl, payload=dict(qty=4, side="Buy", fill_id="f1",
                                            broker_order_id=100))
    j.append("BRACKET_SENT", ACCT, cl, payload=dict(stop=21950.0))
    j.append("BRACKET_CONFIRMED", ACCT, cl, payload=dict(broker_order_id=101))
    b._positions = [dict(account_id=ACCT, qty=4, contract="MNQ")]
    b._orders = [dict(account_id=ACCT, broker_order_id=101, order_type="Stop",
                      action="Sell", qty=4, cl_ord_id=cl)]
    b._fills = [dict(account_id=ACCT, broker_order_id=100, fill_id="f1", qty=4,
                     px=22000.0, ts_utc="t", cl_ord_id=cl)]
    b._accounts[ACCT] = dict(balance=150_000.0)
    sv = {ACCT: dict(balance=150_000.0, floor=145_500.0, p3_braked=False)}
    p3 = {ACCT: dict(dd=4_500)}
    return j, b, cl, sv, p3


def confirmed(j, b, sv=None, p3=None, cycles=2):
    rec = Reconciler(j, b)
    out = []
    for _ in range(cycles):
        out = rec.run(state_view=sv, p3_params=p3)
    return out


MUTATIONS = {
    "CHECK1_POSITION_MISMATCH": lambda j, b, cl, sv: b._positions.clear(),
    "CHECK2_NAKED_POSITION": lambda j, b, cl, sv: b._orders.clear(),
    "CHECK3_UNKNOWN_FILL": lambda j, b, cl, sv: b._fills.append(
        dict(account_id=ACCT, broker_order_id=999, fill_id="fx", qty=2, px=1.0, ts_utc="t")),
    "CHECK4_UNKNOWN_ORDER": lambda j, b, cl, sv: b._orders.append(
        dict(account_id=ACCT, broker_order_id=888, order_type="Limit", action="Buy", qty=4)),
    "CHECK5_STATE_DIVERGENCE": lambda j, b, cl, sv: sv[ACCT].update(balance=152_000.0),
    "CHECK5_P3_SHOULD_BE_ON": lambda j, b, cl, sv: (
        b._accounts.__setitem__(ACCT, dict(balance=146_000.0)),
        sv[ACCT].update(balance=146_000.0)),
}


def test_zero_false_positives_coherent_world(tmp_path):
    j, b, cl, sv, p3 = coherent_world(tmp_path)
    rec = Reconciler(j, b)
    for _ in range(50):                              # 50 quiet cycles
        assert rec.run(state_view=sv, p3_params=p3) == []


@pytest.mark.parametrize("check", list(MUTATIONS))
def test_every_injected_class_detected(tmp_path, check):
    j, b, cl, sv, p3 = coherent_world(tmp_path, check[:6])
    MUTATIONS[check](j, b, cl, sv)
    out = confirmed(j, b, sv, p3)
    assert any(d["check"] == check for d in out), (check, out)
    # and it is journaled, not silently handled
    n = j.con.execute("SELECT COUNT(*) FROM ledger WHERE event_type='RECON_ALERT'"
                      " AND payload_json LIKE ?", (f"%{check}%",)).fetchone()[0]
    assert n >= 1


def test_multi_injection_all_detected(tmp_path):
    j, b, cl, sv, p3 = coherent_world(tmp_path, "multi")
    for m in ("CHECK2_NAKED_POSITION", "CHECK3_UNKNOWN_FILL", "CHECK4_UNKNOWN_ORDER"):
        MUTATIONS[m](j, b, cl, sv)
    found = {d["check"] for d in confirmed(j, b, sv, p3)}
    assert {"CHECK2_NAKED_POSITION", "CHECK3_UNKNOWN_FILL",
            "CHECK4_UNKNOWN_ORDER"} <= found


def test_qty_mutation_detected(tmp_path):
    """Broker says 6, ledger says 4 — the 2-lot ghost must surface (CHECK1)."""
    j, b, cl, sv, p3 = coherent_world(tmp_path, "qty")
    b._positions[0]["qty"] = 6
    out = confirmed(j, b, sv, p3)
    assert any(d["check"] == "CHECK1_POSITION_MISMATCH"
               and d["detail"]["broker_net"] == 6 for d in out)


def test_corrupted_ledger_payload_does_not_crash(tmp_path):
    j, b, cl, sv, p3 = coherent_world(tmp_path, "corrupt")
    # raw insert of a syntactically-valid but semantically-garbage event
    j.con.execute("INSERT INTO ledger(ts_utc, account_id, event_type, cl_ord_id,"
                  " payload_json) VALUES ('t', ?, 'STATE_ASSERT', NULL, ?)",
                  (ACCT, json.dumps({"qty": "not_a_number", "side": None})))
    j.con.commit()
    assert confirmed(j, b, sv, p3) == []             # quiet AND alive


def test_degenerate_broker_rows_do_not_crash(tmp_path):
    j, b, cl, sv, p3 = coherent_world(tmp_path, "degen")
    b._orders.append(dict(account_id=ACCT, broker_order_id=101, order_type="Stop",
                          action="Sell", qty=4, cl_ord_id=cl))   # exact duplicate row
    b._fills.append(dict(account_id=ACCT, broker_order_id=100, fill_id="f1", qty=4,
                         px=22000.0, ts_utc="t", cl_ord_id=cl))  # duplicate fill replay
    out = confirmed(j, b, sv, p3)
    assert all(d["check"] != "CHECK3_UNKNOWN_FILL" for d in out)  # replay != unknown


def test_grace_suppresses_transient_blip(tmp_path):
    """A one-cycle transient (in-flight modify) must NOT confirm."""
    j, b, cl, sv, p3 = coherent_world(tmp_path, "blip")
    rec = Reconciler(j, b)
    saved = list(b._orders)
    b._orders = []                                   # transient: stop invisible 1 cycle
    assert rec.run(state_view=sv, p3_params=p3) == []
    b._orders = saved                                # heals before cycle 2
    assert rec.run(state_view=sv, p3_params=p3) == []


def test_randomized_mutation_storm(tmp_path):
    """200 seeded rounds of 1-3 random mutations: every applied class must be found."""
    rng = random.Random(7)
    names = list(MUTATIONS)
    misses = []
    for i in range(200):
        j, b, cl, sv, p3 = coherent_world(tmp_path, f"storm{i}")
        applied = rng.sample(names, rng.randint(1, 3))
        # CHECK5 mutations conflict with each other — keep at most one
        c5 = [a for a in applied if a.startswith("CHECK5")]
        for extra in c5[1:]:
            applied.remove(extra)
        # canonical order: destructive clears FIRST so additive mutations survive
        # (CHECK2 clears b._orders and would otherwise delete CHECK4's ghost)
        applied.sort(key=lambda a: 0 if a in ("CHECK2_NAKED_POSITION",
                                              "CHECK1_POSITION_MISMATCH") else 1)
        for a in applied:
            MUTATIONS[a](j, b, cl, sv)
        found = {d["check"] for d in confirmed(j, b, sv, p3)}
        # position-clear can also legitimately surface CHECK2 etc. — require superset
        missing = set(applied) - found
        # CHECK1-mutation hides the position, which ALSO makes CHECK2 not applicable;
        # accept the documented coupled cases:
        if "CHECK1_POSITION_MISMATCH" in applied:
            missing.discard("CHECK2_NAKED_POSITION")
        if missing:
            misses.append((i, applied, found))
        j.con.close()
    assert not misses, f"{len(misses)} undetected, first: {misses[:3]}"
