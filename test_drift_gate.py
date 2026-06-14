"""Tests for drift_gate.py (D1c gate, default OFF, fail-closed)."""
import pandas as pd
from drift_gate import DriftGate


def T(h, m, s=0):
    return pd.Timestamp(2026, 6, 12, h, m, s)


def make_gate(enabled=True):
    g = DriftGate(enabled=enabled)
    g.on_session_open(T(9, 30), 24000.0)
    return g


def test_disabled_gate_always_allows():
    g = make_gate(enabled=False)
    assert g.allows("long", T(9, 31)) is True
    assert g.allows("short", T(9, 31)) is True
    assert g.heimdall_status() == "OFF"


def test_agreement_logic():
    g = make_gate()
    g.on_bar_close(T(9, 59), 24050.0)          # drift +50
    assert g.allows("long", T(10, 0)) is True
    assert g.allows("short", T(10, 0)) is False
    g.on_bar_close(T(10, 14), 23980.0)         # drift -20
    assert g.allows("long", T(10, 15)) is False
    assert g.allows("short", T(10, 15)) is True


def test_zero_drift_fails_closed():
    g = make_gate()
    g.on_bar_close(T(9, 59), 24000.0)          # drift == 0
    assert g.allows("long", T(10, 0)) is False
    assert g.allows("short", T(10, 0)) is False


def test_missing_session_open_fails_closed():
    g = DriftGate(enabled=True)
    g.on_bar_close(T(9, 59), 24050.0)          # no session open recorded
    assert g.allows("long", T(10, 0)) is False


def test_stale_feed_fails_closed():
    g = make_gate()
    g.on_bar_close(T(9, 59), 24050.0)
    assert g.allows("long", T(10, 0)) is True
    assert g.allows("long", T(10, 5)) is False  # 1m feed silent for 5 min -> suspend


def test_new_session_resets_state():
    g = make_gate()
    g.on_bar_close(T(9, 59), 24050.0)
    g.on_session_open(T(9, 30) + pd.Timedelta(days=1), 24100.0)
    assert g.drift() is None                    # yesterday's close must not leak
    assert g.allows("long", T(9, 31) + pd.Timedelta(days=1)) is False


def test_bar_from_wrong_day_ignored():
    g = make_gate()
    g.on_bar_close(T(9, 59) - pd.Timedelta(days=1), 25000.0)
    assert g.drift() is None


def test_feed_disconnect_then_late_reconnect_resumes():
    g = make_gate()
    g.on_bar_close(T(9, 59), 24050.0)
    assert g.allows("long", T(10, 0)) is True
    # disconnect: no bars 10:00-10:20 -> fail closed
    assert g.allows("long", T(10, 20)) is False
    # late reconnect: fresh bar arrives -> resumes with current drift
    g.on_bar_close(T(10, 20), 23950.0)          # drift now -50
    assert g.allows("long", T(10, 21)) is False
    assert g.allows("short", T(10, 21)) is True


def test_mid_session_bar_gap_fails_closed_within_gap():
    g = make_gate()
    g.on_bar_close(T(10, 0), 24060.0)
    # 4-minute hole in the 1m feed: stale (>120s+60s grace) at 10:04
    assert g.allows("long", T(10, 4)) is False
    g.on_bar_close(T(10, 4), 24070.0)
    assert g.allows("long", T(10, 5)) is True


def test_drift_unavailable_before_first_bar():
    g = make_gate()                              # session open known, no bar closed yet
    assert g.drift() is None
    assert g.allows("long", T(9, 31)) is False


def test_keep_rate_monitor():
    g = make_gate()
    g.on_bar_close(T(9, 59), 24050.0)          # drift +50
    for i in range(40):
        g.allows("long", T(10, 0))             # all kept
    assert g.keep_rate() == 1.0
    assert g.heimdall_status() == "YELLOW"     # 100% keep-rate is suspicious -> YELLOW
    for i in range(60):
        g.allows("short", T(10, 0))            # all suspended
    kr = g.keep_rate()
    # 90-decision window holds the last 30 keeps + 60 suspends -> 1/3
    assert kr is not None and 0.30 <= kr <= 0.37
    assert g.heimdall_status() == "YELLOW"     # below 45% band -> alert
