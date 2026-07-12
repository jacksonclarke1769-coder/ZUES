"""test_vpc_trail_manager.py — VpcTrailManager cancel-replace machinery: never-naked ordering,
rate-limiting (1 replace / 1m bar), and the cancel-replace TIMEOUT fail-safe (keep the last resting
stop, alert, stand down). The manager drives the CANONICAL vpc_trail.VpcTrail, so trail math parity
is covered by the ARM A/B canaries — these tests target the ORDER-MANAGEMENT layer."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vpc_trail_manager import VpcTrailManager


class FakeSender:
    def __init__(self, accept=True):
        self.accept = accept
        self.sent = []

    def send(self, payload):
        self.sent.append(payload)
        ok = self.accept(payload) if callable(self.accept) else self.accept
        return {"sent": ok}


def _mgr(**over):
    kw = dict(account="T", signal_ts="ts", side="long", qty=1, entry=100.0,
              init_stop_dist=5.0, trail_atr=2.0, send_fn=FakeSender().send)
    kw.update(over)
    return VpcTrailManager(**kw)


def test_construction_fail_closed():
    with pytest.raises(ValueError):
        _mgr(side="up")
    with pytest.raises(ValueError):
        _mgr(qty=0)
    with pytest.raises(ValueError):
        _mgr(init_stop_dist=0)


def test_ratchet_issues_replace_and_advances_resting_stop():
    """A profitable long ratchets the trail; the manager issues a cancel-replace and the resting
    stop moves toward price. The initial resting stop = entry - init_stop_dist."""
    sender = FakeSender(accept=True)
    m = _mgr(send_fn=sender.send)
    assert m.resting_stop == 95.0
    # bar drives close up so peak - 2*atr(1.0) = close-2 > 95 -> ratchet
    res, level = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)
    assert res == "replace"
    assert level > 95.0
    assert m.resting_stop == level
    # payloads: a stop order + a cancel (never-naked pair). Stop sent BEFORE cancel.
    kinds = [p.get("action") for p in sender.sent]
    assert kinds == ["stop", "cancel"], f"expected stop-then-cancel, got {kinds}"


def test_never_naked_on_failed_new_stop():
    """If the NEW stop send is rejected, the manager keeps the LAST resting stop and does NOT send
    the cancel — the position is never left without protection."""
    sender = FakeSender(accept=False)          # broker rejects every send
    m = _mgr(send_fn=sender.send)
    start = m.resting_stop
    res, level = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)
    assert res == "hold"
    assert m.resting_stop == start             # unchanged — old stop still working
    # only the (failed) new-stop send was attempted; NO cancel of the still-needed old stop
    kinds = [p.get("action") for p in sender.sent]
    assert kinds == ["stop"], f"cancel must NOT be sent when new stop failed, got {kinds}"
    assert m.replaces_failed == 1


def test_rate_limit_one_replace_per_bar():
    """At most one replace per 1m bar id (bounds watchdog trail-churn)."""
    sender = FakeSender(accept=True)
    m = _mgr(send_fn=sender.send)
    r1, _ = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)
    assert r1 == "replace"
    # SAME bar id again, price ratchets further -> must be rate-limited to hold
    r2, _ = m.on_1m_bar(1, 100.0, 103.0, 102.5, 1.0)
    assert r2 == "hold"
    # a NEW bar id may replace again
    r3, _ = m.on_1m_bar(2, 100.0, 104.0, 103.5, 1.0)
    assert r3 == "replace"


def test_cancel_replace_timeout_stands_down_and_keeps_last_resting():
    """A replace that a readback never confirms within timeout_s triggers stand-down: the manager
    keeps the LAST confirmed resting stop, alerts, and stops issuing replaces (never naked)."""
    clock = {"t": 0.0}
    alerts = []
    sender = FakeSender(accept=True)
    # confirm_fn never confirms -> the in-flight replace times out
    m = VpcTrailManager(account="T", signal_ts="ts", side="long", qty=1, entry=100.0,
                        init_stop_dist=5.0, trail_atr=2.0, send_fn=sender.send,
                        alert_fn=lambda ev, **k: alerts.append((ev, k)),
                        clock_fn=lambda: clock["t"], confirm_fn=lambda stop: False, timeout_s=5.0)
    res, level = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0, now_ts=0.0)
    assert res == "replace"
    resting_at_replace = m.resting_stop        # readback path: resting stays at the OLD (working) stop
    assert m.pending is not None
    # F1: the OLD stop must NOT have been cancelled — no cancel payload sent while unconfirmed
    assert m.cancelled_stops == []
    assert [p.get("action") for p in sender.sent] == ["stop"]
    # advance the clock past the timeout; next bar's timeout check must stand down
    clock["t"] = 10.0
    res2, level2 = m.on_1m_bar(2, 100.0, 104.0, 103.5, 1.0, now_ts=10.0)
    assert m.stood_down is True
    assert any(ev == "vpc_trail_timeout" for ev, _ in alerts)
    # stood down -> no further replaces; resting stop is the OLD stop, which was NEVER cancelled ->
    # genuinely still working (the F1 fix: not a cancelled order held under a false belief)
    assert res2 == "hold"
    assert m.resting_stop == resting_at_replace
    assert m.resting_stop not in m.cancelled_stops
    assert m.cancelled_stops == []             # old stop never cancelled on timeout
    assert m.pending is None


def test_confirm_advances_resting_stop():
    """With a readback that confirms, the resting stop advances to the confirmed level."""
    confirmed = {"stop": None}
    sender = FakeSender(accept=True)
    m = VpcTrailManager(account="T", signal_ts="ts", side="long", qty=1, entry=100.0,
                        init_stop_dist=5.0, trail_atr=2.0, send_fn=sender.send,
                        clock_fn=lambda: 0.0,
                        confirm_fn=lambda stop: confirmed["stop"] == stop, timeout_s=5.0)
    res, level = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)
    assert res == "replace"
    # F1: BEFORE confirmation, the old stop is NOT cancelled (confirm-then-cancel)
    assert m.cancelled_stops == []
    old_resting = m.resting_stop               # still the OLD stop while unconfirmed
    confirmed["stop"] = level                  # readback now sees the new stop resting
    # next bar's timeout check confirms it -> old stop cancelled, THEN resting advances, no stand-down
    m.on_1m_bar(2, 100.0, 100.6, 100.2, 1.0)   # small bar, no new ratchet
    assert m.stood_down is False
    assert m.resting_stop == level
    assert m.cancelled_stops == [old_resting]  # old stop cancelled ONLY after confirmation
    assert m.resting_stop not in m.cancelled_stops


def test_readback_confirm_rejection_keeps_old_and_stands_down():
    """F1: if confirm_fn reports the new stop was REJECTED downstream, the manager keeps the OLD
    (never-cancelled, still-working) stop, alerts, and stands down — never naked, never a phantom."""
    alerts = []
    sender = FakeSender(accept=True)
    m = VpcTrailManager(account="T", signal_ts="ts", side="long", qty=1, entry=100.0,
                        init_stop_dist=5.0, trail_atr=2.0, send_fn=sender.send,
                        alert_fn=lambda ev, **k: alerts.append(ev),
                        clock_fn=lambda: 0.0, confirm_fn=lambda stop: "rejected", timeout_s=5.0)
    res, level = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)
    assert res == "replace"
    old_resting = m.resting_stop
    m.on_1m_bar(2, 100.0, 100.6, 100.2, 1.0)   # confirm check sees "rejected"
    assert m.stood_down is True
    assert "vpc_trail_replace_rejected" in alerts
    assert m.resting_stop == old_resting
    assert m.cancelled_stops == []             # old stop never cancelled -> genuinely protected
    assert m.pending is None


def test_resting_stop_never_cancelled_invariant():
    """F1 core invariant across a ratcheting sequence (readback path, always confirming): at EVERY
    step the manager's believed-resting stop is never an order it has already cancelled."""
    confirmed = {"stop": None}
    sender = FakeSender(accept=True)
    m = VpcTrailManager(account="T", signal_ts="ts", side="long", qty=1, entry=100.0,
                        init_stop_dist=5.0, trail_atr=2.0, send_fn=sender.send,
                        clock_fn=lambda: 0.0,
                        confirm_fn=lambda stop: confirmed["stop"] == stop, timeout_s=5.0)
    # a rising sequence -> repeated ratchets; confirm each replace on the following bar
    bars = [(99.0, 101.0, 100.6), (100.0, 102.0, 101.6), (101.0, 103.0, 102.6),
            (102.0, 104.0, 103.6), (103.0, 105.0, 104.6)]
    for i, (lo, hi, cl) in enumerate(bars, start=1):
        res, level = m.on_1m_bar(i, lo, hi, cl, 1.0)
        assert m.resting_stop not in m.cancelled_stops     # invariant holds at every step
        if res == "replace":
            confirmed["stop"] = level                       # readback confirms it before the next bar
    assert m.replaces_sent >= 2                              # the sequence actually ratcheted
    assert m.resting_stop not in m.cancelled_stops


def test_out_of_order_stale_bar_rejected():
    """F2: a reconnect-replayed / out-of-order stale bar (bar_id <= last processed) must NOT re-step
    the trail — the audit's reproduced phantom exit must no longer reproduce."""
    sender = FakeSender(accept=True)
    m = _mgr(send_fn=sender.send)
    r1, _ = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)
    assert r1 == "replace"
    r2, _ = m.on_1m_bar(2, 100.0, 103.0, 102.5, 1.0)       # ratchets internal trail toward 100.5
    assert r2 == "replace"
    # AUDIT REPRODUCTION: re-deliver stale bar id 1 (low 99 < the ratcheted internal stop) — under
    # the old == guard this fired a PHANTOM exit. Monotonic guard now rejects it as a no-op hold.
    r3, level3 = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)
    assert r3 == "hold"
    assert not m.exited
    assert level3 == m.resting_stop


def test_same_timestamp_repoll_rejected():
    """F2: a same-timestamp re-poll (bar_id == last processed) is a no-op hold, no re-step."""
    sender = FakeSender(accept=True)
    m = _mgr(send_fn=sender.send)
    r1, _ = m.on_1m_bar(5, 99.0, 101.0, 100.5, 1.0)
    assert r1 == "replace"
    before = m.trail.stop
    r2, _ = m.on_1m_bar(5, 100.0, 103.0, 102.5, 1.0)       # same id re-poll
    assert r2 == "hold"
    assert m.trail.stop == before                           # canonical trail did NOT advance


def test_stop_hit_exits_at_resting_stop():
    """When the bar takes out the resting stop, the manager reports exit at the resting level."""
    sender = FakeSender(accept=True)
    m = _mgr(send_fn=sender.send)              # resting stop 95.0
    res, level = m.on_1m_bar(1, 94.0, 96.0, 94.5, 1.0)   # low 94 < 95 -> stop hit
    assert res == "exit"
    assert level == 95.0
    # once exited, further bars keep reporting exit (idempotent)
    res2, _ = m.on_1m_bar(2, 90.0, 92.0, 91.0, 1.0)
    assert res2 == "exit"
