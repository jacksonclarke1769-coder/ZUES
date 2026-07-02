"""
Stage B battery — BREAK the read-back sentinel.
  * coherent world stays SILENT across many polls (no false halts)
  * every injected failure (orphan / direction / floor / read-fail) is CONFIRMED after grace
  * grace: a one-poll blip does NOT halt; persistence does
  * healing resets the counter (no latched false alarm)
  * critical action fires ONCE; entry gate goes fail-closed
  * a broker that cannot be read fails CLOSED
"""
import pytest
from live_readback import ReadbackSentinel, TradovateBrokerView, BLACK, ORANGE

ACCT = "MFFU1"


class FakeBrokerView:
    def __init__(self, net=None, bal=100_000.0, raise_on_read=False):
        self._net = net or {}
        self._bal = bal
        self.raise_on_read = raise_on_read

    def net_by_account(self):
        if self.raise_on_read:
            raise ConnectionError("broker unreachable")
        return dict(self._net)

    def balance(self, account_id):
        if self.raise_on_read:
            raise ConnectionError("broker unreachable")
        return self._bal


class FakeJournal:
    def __init__(self):
        self.events = []

    def append(self, event_type, account_id, payload=None):
        self.events.append((event_type, account_id, payload))


def _poll_n(sent, broker, n):
    out = []
    for _ in range(n):
        out = sent.poll(broker)
    return out


# --------------------------------------------------------------------------
def test_coherent_world_stays_silent():
    """Bot flat + broker flat, then bot long 3 + broker long 3 — no critical alerts ever.
    Updated Q-fill-confirm-ttl: FILL_CONFIRMED is now journaled on the first matching poll
    (positive audit trail — not a discrepancy). Only RECON_ALERT indicates a problem."""
    j = FakeJournal()
    s = ReadbackSentinel(ACCT, floor=48_000.0, journal=j)
    b = FakeBrokerView(net={}, bal=100_000.0)
    assert _poll_n(s, b, 5) == []
    s.on_entry("long", 3)                      # bot opens 3
    b._net = {ACCT: 3}                          # broker agrees
    assert _poll_n(s, b, 5) == []
    s.on_flat(); b._net = {}                    # both flat
    assert _poll_n(s, b, 5) == []
    assert not s.halted
    # FILL_CONFIRMED is expected — it is the positive fill-confirmation audit trail, not an error.
    crit = [e for e in j.events if e[0] == "RECON_ALERT"]
    assert crit == [], f"no critical alerts expected in a coherent world; got {crit}"


def test_orphan_position_confirmed_black_and_halts():
    """Bot believes FLAT but broker shows a position -> BLACK, halt, alert, callback once."""
    j = FakeJournal(); fired = []
    s = ReadbackSentinel(ACCT, floor=48_000.0, journal=j, on_critical=lambda r: fired.append(r))
    b = FakeBrokerView(net={ACCT: 2}, bal=100_000.0)
    assert s.poll(b) == []                      # cycle 1: within grace, not yet confirmed
    conf = s.poll(b)                            # cycle 2: confirmed
    assert any(c[0] == "ORPHAN_POSITION" and c[1] == BLACK for c in conf)
    assert s.halted and len(fired) == 1
    ok, why = s.ready(); assert not ok and "HALT" in why
    s.poll(b)                                   # still halted, callback does NOT re-fire
    assert len(fired) == 1
    assert any(e[0] == "RECON_ALERT" for e in j.events)


def test_direction_mismatch_black():
    s = ReadbackSentinel(ACCT, floor=None)
    s.on_entry("long", 3)                        # bot expects +3
    b = FakeBrokerView(net={ACCT: -3})           # broker is SHORT 3
    assert s.poll(b) == []
    conf = s.poll(b)
    assert any(c[0] == "DIRECTION_MISMATCH" and c[1] == BLACK for c in conf)
    assert s.halted


def test_missing_position_is_orange_not_halt():
    """Bot expects a position, broker flat -> ORANGE (entry didn't fill); does NOT halt."""
    s = ReadbackSentinel(ACCT, floor=None)
    s.on_entry("long", 3)
    b = FakeBrokerView(net={})
    conf = _poll_n(s, b, 3)
    assert any(c[0] == "MISSING_POSITION" and c[1] == ORANGE for c in conf)
    assert not s.halted                          # ORANGE alone never halts


def test_balance_floor_black_halts():
    s = ReadbackSentinel(ACCT, floor=48_000.0)
    b = FakeBrokerView(net={}, bal=47_900.0)     # below the MFFU floor
    assert s.poll(b) == []
    conf = s.poll(b)
    assert any(c[0] == "BALANCE_FLOOR" and c[1] == BLACK for c in conf)
    assert s.halted


def test_grace_blip_does_not_halt():
    """A single-poll discrepancy that heals next poll must NOT confirm."""
    s = ReadbackSentinel(ACCT, floor=None)
    b = FakeBrokerView(net={ACCT: 2})            # transient orphan (e.g. in-flight fill)
    assert s.poll(b) == []                        # cycle 1
    b._net = {}                                    # healed before cycle 2
    assert s.poll(b) == []                        # counter reset, no confirm
    assert not s.halted


def test_broker_read_fail_fails_closed():
    """Repeated read failures escalate ORANGE->BLACK and halt (can't verify = fail closed)."""
    s = ReadbackSentinel(ACCT, floor=None)
    b = FakeBrokerView(raise_on_read=True)
    s.poll(b); s.poll(b)                          # 2 fails: ORANGE
    assert not s.halted
    conf = s.poll(b)                              # 3rd fail: BLACK
    assert any(c[0] == "BROKER_READ_FAIL" and c[1] == BLACK for c in conf)
    assert s.halted


def test_tradovate_view_adapts_position_and_balance():
    """The Tradovate adapter sums netPos by account and builds equity from the snapshot."""
    class FakeClient:
        def positions(self):
            return [dict(accountId=ACCT, netPos=2, contractId=1),
                    dict(accountId=ACCT, netPos=1, contractId=1)]
        def account_snapshot(self):
            return dict(cashBalance=50_000.0, openPnL=-250.0)
    v = TradovateBrokerView(FakeClient())
    assert v.net_by_account() == {ACCT: 3}
    assert v.balance(ACCT) == pytest.approx(49_750.0)


def test_expected_position_tracking():
    s = ReadbackSentinel(ACCT)
    s.on_entry("long", 3); assert s.expected == 3
    s.on_partial_or_exit(-1); assert s.expected == 2     # TP1 banks 1
    s.on_flat(); assert s.expected == 0
    s.on_entry("short", 2); assert s.expected == -2
