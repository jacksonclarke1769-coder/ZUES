"""
Q — positive fill confirmation + order TTL tests.

Covers the four success criteria from docs/tickets/Q-fill-confirm-ttl.md:

  1. on_missing fires ONCE after missing_confirm consecutive MISSING polls; resets so a second
     episode can fire again.
  2. FILL_CONFIRMED journaled once when broker matches expected (no on_missing).
  3. MISSING still ORANGE, never halts (existing contract preserved).
  4. auto_live cancel guard: skips cancel when another lane reports an open position.
"""
import pytest
from live_readback import ReadbackSentinel, ORANGE


ACCT = "APEX-50K-test"


class FakeJournal:
    def __init__(self):
        self.events = []

    def append(self, event_type, account_id, payload=None, **_kw):
        self.events.append((event_type, account_id, payload))


class FakeBrokerView:
    def __init__(self, net=None, bal=100_000.0):
        self._net = net or {}
        self._bal = bal

    def net_by_account(self):
        return dict(self._net)

    def balance(self, account_id):
        return self._bal


def _poll_n(sent, broker, n):
    out = []
    for _ in range(n):
        out = sent.poll(broker)
    return out


# ---------------------------------------------------------------------------
# Test 1: on_missing fires once after N confirmed polls; second episode fires again
# ---------------------------------------------------------------------------
def test_on_missing_fires_once_then_rearms():
    """Expected=+10, broker flat for missing_confirm polls → on_missing fired exactly once
    with the expected qty; a second independent episode can fire again."""
    fired = []
    j = FakeJournal()
    s = ReadbackSentinel(ACCT, floor=None, journal=j,
                         on_missing=lambda qty: fired.append(qty),
                         missing_confirm=3)   # small N for test speed
    s.on_entry("long", 10)
    broker_flat = FakeBrokerView(net={})

    # poll 1, 2: below missing_confirm threshold — not yet fired
    s.poll(broker_flat)
    s.poll(broker_flat)
    assert fired == [], "on_missing must not fire before missing_confirm polls"

    # poll 3: hits threshold — fires exactly once
    s.poll(broker_flat)
    assert fired == [10], "on_missing must fire once with expected qty"

    # poll 4: still MISSING — callback must NOT re-fire this episode
    s.poll(broker_flat)
    assert fired == [10], "on_missing must not fire twice in the same episode"

    # ---- second episode: condition clears, then re-enters MISSING ----
    s.on_flat()                          # position resolved (e.g. via on_missing handler calling on_flat)
    broker_match = FakeBrokerView(net={ACCT: 5})
    s.on_entry("long", 5)
    s.poll(broker_match)                 # healed: _missing_consec resets to 0, _missing_fired resets
    # drive the second episode: broker goes flat again
    s.on_flat()
    s.on_entry("long", 5)
    broker_flat2 = FakeBrokerView(net={})
    s.poll(broker_flat2)
    s.poll(broker_flat2)
    assert fired == [10], "no second fire yet (only 2 polls)"
    s.poll(broker_flat2)
    assert fired == [10, 5], "second episode must re-arm and fire with new expected qty"


# ---------------------------------------------------------------------------
# Test 2: broker matches expected → FILL_CONFIRMED journaled once; no on_missing
# ---------------------------------------------------------------------------
def test_fill_confirmed_journaled_once_on_match():
    """Bot expects +10, broker shows +10 → FILL_CONFIRMED journaled once; on_missing NOT fired."""
    fired = []
    j = FakeJournal()
    s = ReadbackSentinel(ACCT, floor=None, journal=j,
                         on_missing=lambda qty: fired.append(qty),
                         missing_confirm=3)
    s.on_entry("long", 10)
    broker_match = FakeBrokerView(net={ACCT: 10})

    s.poll(broker_match)
    conf_events = [e for e in j.events if e[0] == "FILL_CONFIRMED"]
    assert len(conf_events) == 1, "FILL_CONFIRMED must be journaled on the first matching poll"
    assert conf_events[0][2]["expected"] == 10
    assert conf_events[0][2]["broker"] == 10

    # subsequent polls: no duplicate journal entry
    s.poll(broker_match)
    s.poll(broker_match)
    assert len([e for e in j.events if e[0] == "FILL_CONFIRMED"]) == 1, \
        "FILL_CONFIRMED must not journal more than once per entry episode"

    # on_missing never fires (broker position matches)
    assert fired == [], "on_missing must not fire when broker matches expected"
    assert not s.halted, "a matched position must not halt"


def test_fill_confirmed_rearms_on_new_entry():
    """FILL_CONFIRMED re-arms after on_entry so a second entry episode journals again."""
    j = FakeJournal()
    s = ReadbackSentinel(ACCT, floor=None, journal=j)
    s.on_entry("long", 3)
    FakeBrokerView(net={ACCT: 3})
    s.poll(FakeBrokerView(net={ACCT: 3}))
    assert len([e for e in j.events if e[0] == "FILL_CONFIRMED"]) == 1

    s.on_flat()
    s.on_entry("short", 2)
    s.poll(FakeBrokerView(net={ACCT: -2}))
    assert len([e for e in j.events if e[0] == "FILL_CONFIRMED"]) == 2, \
        "second entry episode must journal FILL_CONFIRMED again"


# ---------------------------------------------------------------------------
# Test 3: MISSING is still ORANGE, never halts (existing contract unchanged)
# ---------------------------------------------------------------------------
def test_missing_is_still_orange_never_halts():
    """Ticket constraint: adding on_missing must NOT change MISSING_POSITION tier semantics."""
    fired = []
    s = ReadbackSentinel(ACCT, floor=None,
                         on_missing=lambda qty: fired.append(qty),
                         missing_confirm=1)   # fire immediately (worst case for halt risk)
    s.on_entry("long", 5)
    b = FakeBrokerView(net={})

    # drive enough polls to fire on_missing
    for _ in range(3):
        conf = s.poll(b)

    assert not s.halted, "MISSING_POSITION is ORANGE — must NEVER halt"
    assert fired, "on_missing must have fired"
    assert all(c[1] == ORANGE for c in conf if c[0] == "MISSING_POSITION"), \
        "MISSING_POSITION tier must remain ORANGE after on_missing fires"


# ---------------------------------------------------------------------------
# Test 4: cancel guard — skip cancel when another lane reports an open position
# ---------------------------------------------------------------------------
def test_cancel_guard_skips_when_b_lane_open():
    """auto_live._on_missing_cancel_is_safe returns False when B lane has an open position,
    preventing a cancel that would affect B's working orders."""
    from auto_live import _on_missing_cancel_is_safe

    class MockBTracker:
        open = [{"side": "long", "qty": 2, "entry": 21000}]

    class MockAutoWithB:
        open_risk = {"B": 600.0}
        b_tracker = MockBTracker()

    safe, reason = _on_missing_cancel_is_safe(MockAutoWithB())
    assert not safe, "cancel must be blocked when B lane open"
    assert "B lane" in reason


def test_cancel_guard_allows_when_a_only():
    """Cancel is safe when no other lane is open (single-lane A-only selected machine)."""
    from auto_live import _on_missing_cancel_is_safe

    class MockBTracker:
        open = []   # B flat

    class MockAutoAOnly:
        open_risk = {}   # only A risk (or nothing)
        b_tracker = MockBTracker()

    safe, reason = _on_missing_cancel_is_safe(MockAutoAOnly())
    assert safe, "cancel must be allowed when A is the only open lane"
    assert "single-lane" in reason


def test_cancel_guard_checks_open_risk_b_even_if_tracker_empty():
    """open_risk['B'] alone (e.g. signal sent but tracker not yet updated) also blocks cancel."""
    from auto_live import _on_missing_cancel_is_safe

    class MockBTracker:
        open = []

    class MockAutoRiskB:
        open_risk = {"B": 400.0}   # B entry sent but tracker not yet updated
        b_tracker = MockBTracker()

    safe, _ = _on_missing_cancel_is_safe(MockAutoRiskB())
    assert not safe, "open_risk['B'] alone must block cancel"
