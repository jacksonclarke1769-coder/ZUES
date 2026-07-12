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


def test_ratchet_issues_single_call_replace_and_advances_resting_stop():
    """D6: a profitable long ratchets the trail; the manager issues ONE bundled cancel-replace call
    (new stop + cancel:true) and the resting stop moves toward price. No separate client cancel."""
    sender = FakeSender(accept=True)
    m = _mgr(send_fn=sender.send)
    assert m.resting_stop == 95.0
    # bar drives close up so peak - 2*atr(1.0) = close-2 > 95 -> ratchet
    res, level = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)
    assert res == "replace"
    assert level > 95.0
    assert m.resting_stop == level
    # EXACTLY ONE payload — the bundled cancel-replace. No client-side cancel action is ever sent.
    assert len(sender.sent) == 1, f"expected a single bundled call, got {len(sender.sent)}"
    only = sender.sent[0]
    assert only["action"] == "sell"            # protective stop for a long = a resting sell-stop
    assert only["orderType"] == "stop"
    assert only["cancel"] is True              # bundled server-side cancel of the prior stop
    assert m.cancelled_stops == []             # the manager issued NO client-side cancel
    assert m.live_stops() == {m.resting_stop}  # never two live stops


def test_never_naked_on_failed_bundled_replace():
    """D6: if the bundled cancel-replace send is rejected, it FAILS-WHOLE — the manager keeps the
    LAST resting stop unchanged (old stop stands). The position is never left without protection,
    and there is never a two-stops window."""
    sender = FakeSender(accept=False)          # broker rejects every send
    m = _mgr(send_fn=sender.send)
    start = m.resting_stop
    res, level = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)
    assert res == "hold"
    assert m.resting_stop == start             # unchanged — old stop still working
    assert len(sender.sent) == 1               # ONE attempt (the bundled call); nothing else sent
    assert m.cancelled_stops == []             # nothing cancelled -> old stop genuinely still working
    assert m.live_stops() == {start}
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
    # D6: the OLD stop is NOT cancelled by us — the bundled replace is one server-sequenced call.
    assert m.cancelled_stops == []
    assert len(sender.sent) == 1               # a single bundled cancel-replace call
    assert sender.sent[0]["cancel"] is True
    assert m.live_stops() == {resting_at_replace}   # still exactly one live stop while in flight
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
    """With a readback that confirms the bundled replace landed, the resting stop advances to the
    confirmed level — with NO separate client-side cancel (the cancel was bundled server-side)."""
    confirmed = {"stop": None}
    sender = FakeSender(accept=True)
    m = VpcTrailManager(account="T", signal_ts="ts", side="long", qty=1, entry=100.0,
                        init_stop_dist=5.0, trail_atr=2.0, send_fn=sender.send,
                        clock_fn=lambda: 0.0,
                        confirm_fn=lambda stop: confirmed["stop"] == stop, timeout_s=5.0)
    res, level = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)
    assert res == "replace"
    # BEFORE confirmation, resting stays OLD and nothing is client-cancelled
    assert m.cancelled_stops == []
    old_resting = m.resting_stop               # still the OLD stop while unconfirmed
    assert m.live_stops() == {old_resting}
    confirmed["stop"] = level                  # readback now sees the new stop resting
    # next bar's timeout check confirms it -> resting advances; STILL no client-side cancel
    m.on_1m_bar(2, 100.0, 100.6, 100.2, 1.0)   # small bar, no new ratchet
    assert m.stood_down is False
    assert m.resting_stop == level
    assert m.cancelled_stops == []             # single-call model: no client cancel, ever
    assert m.live_stops() == {level}


def test_readback_confirm_rejection_keeps_old_and_stands_down():
    """D6: if confirm_fn reports the bundled replace failed-whole (REJECTED), the manager keeps the
    OLD (unchanged, working) stop, alerts, and stands down — never naked, never two live stops."""
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


def test_no_two_live_stops_invariant_across_ratchet():
    """D6 core invariant: at NO point does the manager's model contain two live protective stops.
    Across a ratcheting sequence with an in-flight readback confirm, live_stops() is always exactly
    one level (the bundled replace either fully lands or fully fails)."""
    confirmed = {"stop": None}
    sender = FakeSender(accept=True)
    m = VpcTrailManager(account="T", signal_ts="ts", side="long", qty=1, entry=100.0,
                        init_stop_dist=5.0, trail_atr=2.0, send_fn=sender.send,
                        clock_fn=lambda: 0.0,
                        confirm_fn=lambda stop: confirmed["stop"] == stop, timeout_s=5.0)
    bars = [(99.0, 101.0, 100.6), (100.0, 102.0, 101.6), (101.0, 103.0, 102.6),
            (102.0, 104.0, 103.6), (103.0, 105.0, 104.6)]
    for i, (lo, hi, cl) in enumerate(bars, start=1):
        res, level = m.on_1m_bar(i, lo, hi, cl, 1.0)
        assert len(m.live_stops()) == 1                     # NEVER two live stops — even mid-confirm
        assert m.cancelled_stops == []                      # no client-side cancel is ever issued
        if res == "replace":
            confirmed["stop"] = level                       # readback confirms it before the next bar
    assert m.replaces_sent >= 2                              # the sequence actually ratcheted


def test_resting_stop_never_cancelled_invariant():
    """Core never-naked invariant across a ratcheting sequence: at EVERY step the manager's
    believed-resting stop is never an order it has already cancelled (in the single-call model it
    cancels nothing client-side while the position is open, so this holds trivially)."""
    confirmed = {"stop": None}
    sender = FakeSender(accept=True)
    m = VpcTrailManager(account="T", signal_ts="ts", side="long", qty=1, entry=100.0,
                        init_stop_dist=5.0, trail_atr=2.0, send_fn=sender.send,
                        clock_fn=lambda: 0.0,
                        confirm_fn=lambda stop: confirmed["stop"] == stop, timeout_s=5.0)
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


# ==================================================================================================
# D3 — KILL/FLATTEN semantics for an in-flight trail (Phase-4 DEC, single-call model)
# ==================================================================================================
def test_kill_during_pending_confirm_never_cancels_resting_stop():
    """D3: a kill arriving WHILE a cancel-replace readback confirm is pending must NOT cancel the
    believed-resting stop first. It market-flattens and leaves the OLD stop working; the resting
    stop is cleaned up only after flat is confirmed."""
    flat_calls = []
    sender = FakeSender(accept=True)
    m = VpcTrailManager(account="T", signal_ts="ts", side="long", qty=1, entry=100.0,
                        init_stop_dist=5.0, trail_atr=2.0, send_fn=sender.send,
                        clock_fn=lambda: 0.0, confirm_fn=lambda stop: False, timeout_s=99.0)
    res, level = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0, now_ts=0.0)
    assert res == "replace"
    assert m.pending is not None               # a readback replace is in flight
    old_resting = m.resting_stop
    # KILL arrives mid-confirm
    out = m.kill_flatten("operator kill", flatten_fn=lambda r: flat_calls.append(r) or {"flat": True})
    assert out == {"flat": True}               # a MARKET-FLATTEN was issued
    assert flat_calls == ["operator kill"]
    assert m.killed is True
    assert m.pending is None                   # in-flight replace abandoned (nothing cancelled)
    assert m.resting_stop == old_resting       # OLD stop UNCHANGED and still working (never naked)
    assert m.cancelled_stops == []             # nothing cancelled while still holding the position
    assert m.awaiting_flat is True
    assert m.live_stops() == {old_resting}     # position still protected by exactly one stop
    # further bars issue NO replaces while killed
    r2, _ = m.on_1m_bar(2, 101.0, 103.0, 102.5, 1.0)
    assert r2 == "hold"
    assert m.replaces_sent == 1                # no new replace after kill
    # NOW confirm the position is flat -> only now is the resting stop cleaned up
    cancel_calls = []
    m.on_flat_confirmed(cancel_fn=lambda lvl: cancel_calls.append(lvl))
    assert cancel_calls == [old_resting]       # resting stop cancelled ONLY after flat-confirm
    assert m.cancelled_stops == [old_resting]
    assert m.awaiting_flat is False
    assert m.live_stops() == set()             # flat + cleaned up -> no live stops


def test_kill_during_ratchet_market_flattens_and_halts_replaces():
    """D3: a kill during a normal holding/ratcheting trail market-flattens, keeps the resting stop
    working, and stops all further replaces."""
    flat_calls = []
    sender = FakeSender(accept=True)
    m = _mgr(send_fn=sender.send)
    r1, _ = m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)   # ratchet -> resting advanced
    assert r1 == "replace"
    resting = m.resting_stop
    m.kill_flatten("EOD flatten", flatten_fn=lambda r: flat_calls.append(r) or {"flat": True})
    assert flat_calls == ["EOD flatten"]
    assert m.killed is True
    assert m.resting_stop == resting           # resting stop unchanged, still working
    assert m.cancelled_stops == []             # not cancelled while position open
    # subsequent ratchet-worthy bars do nothing
    r2, _ = m.on_1m_bar(2, 101.0, 104.0, 103.5, 1.0)
    assert r2 == "hold"
    assert m.replaces_sent == 1


def test_kill_naked_impossible_no_cancel_before_flat_confirm():
    """D3 naked-impossible assertion: between kill and flat-confirm there is NEVER a moment where the
    position is open AND its protective stop has been cancelled. The resting stop appears in
    cancelled_stops only AFTER on_flat_confirmed() (position already flat)."""
    sender = FakeSender(accept=True)
    m = _mgr(send_fn=sender.send)
    m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)
    resting = m.resting_stop
    m.kill_flatten("kill", flatten_fn=lambda r: {"flat": True})
    # position is being flattened but NOT yet confirmed flat -> stop must still be live/uncancelled
    assert m.awaiting_flat is True
    assert resting not in m.cancelled_stops     # NOT cancelled while open (naked-impossible)
    assert m.live_stops() == {resting}
    # idempotent flat-confirm cleanup
    m.on_flat_confirmed(cancel_fn=lambda lvl: None)
    assert resting in m.cancelled_stops
    assert m.on_flat_confirmed(cancel_fn=lambda lvl: None) is None   # idempotent no-op


def test_kill_flatten_idempotent():
    """A second kill_flatten does not re-issue the market-flatten."""
    n = {"c": 0}
    sender = FakeSender(accept=True)
    m = _mgr(send_fn=sender.send)
    m.on_1m_bar(1, 99.0, 101.0, 100.5, 1.0)
    m.kill_flatten("kill", flatten_fn=lambda r: n.__setitem__("c", n["c"] + 1))
    m.kill_flatten("kill again", flatten_fn=lambda r: n.__setitem__("c", n["c"] + 1))
    assert n["c"] == 1                          # flatten issued exactly once
