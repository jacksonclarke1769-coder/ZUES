"""Pre-open feed-readiness guard tests — proves it alerts EARLY when the feed isn't GREEN before the
09:30 ET open (the Friday 06-26 late-feed failure that killed the ORB + Momentum), confirms a ready feed,
escalates, flags a late open once, and never fires on weekends / outside the window."""
import pandas as pd

from preopen_guard import PreopenGuard


def et(s):
    return pd.Timestamp(s, tz="America/New_York")


def test_too_early_is_silent():
    g = PreopenGuard(lead_min=10)
    assert g.evaluate(et("2026-06-26 09:00"), "RED") is None       # before 09:20 lead-start


def test_ready_before_open_confirms_once():
    g = PreopenGuard(lead_min=10)
    a = g.evaluate(et("2026-06-26 09:22"), "GREEN")
    assert a["kind"] == "ready"
    assert g.evaluate(et("2026-06-26 09:25"), "GREEN") is None     # confirmed -> silent after


def test_not_ready_alerts_then_throttles_then_escalates():
    g = PreopenGuard(lead_min=10, realert_s=120)
    a = g.evaluate(et("2026-06-26 09:21"), "RED")
    assert a["kind"] == "not_ready" and "09:30" in a["msg"]
    assert g.evaluate(et("2026-06-26 09:22"), "RED") is None       # <120s since last alert -> throttled
    b = g.evaluate(et("2026-06-26 09:24"), "RED")                  # >=120s -> re-alert (escalate)
    assert b["kind"] == "not_ready"


def test_recovered_before_open():
    g = PreopenGuard(lead_min=10)
    assert g.evaluate(et("2026-06-26 09:21"), "RED")["kind"] == "not_ready"
    r = g.evaluate(et("2026-06-26 09:27"), "GREEN")
    assert r["kind"] == "recovered"
    assert g.evaluate(et("2026-06-26 09:29"), "GREEN") is None     # only once


def test_late_open_flagged_once_when_still_red():
    g = PreopenGuard(lead_min=10)
    g.evaluate(et("2026-06-26 09:21"), "RED")                      # pre-open alert
    a = g.evaluate(et("2026-06-26 09:31"), "RED")                  # open passed, still not ready
    assert a["kind"] == "late_open"
    assert g.evaluate(et("2026-06-26 09:33"), "RED") is None       # flagged once only


def test_late_open_when_green_arrives_after_open():
    g = PreopenGuard(lead_min=10)
    g.evaluate(et("2026-06-26 09:21"), "RED")                      # alerted pre-open
    a = g.evaluate(et("2026-06-26 09:40"), "GREEN")               # exactly Friday: GREEN only at 09:40
    assert a["kind"] == "late_open"


def test_clean_open_no_late_flag():
    g = PreopenGuard(lead_min=10)
    assert g.evaluate(et("2026-06-26 09:25"), "GREEN")["kind"] == "ready"
    assert g.evaluate(et("2026-06-26 09:31"), "GREEN") is None     # was ready -> no late-open warning


def test_past_grace_is_silent():
    g = PreopenGuard(lead_min=10, open_grace_min=15)
    assert g.evaluate(et("2026-06-26 10:00"), "RED") is None       # >09:45, midday is feed_watch's job


def test_weekend_never_alerts():
    g = PreopenGuard(lead_min=10)
    assert g.evaluate(et("2026-06-27 09:25"), "RED") is None       # Saturday
    assert g.evaluate(et("2026-06-28 09:25"), "RED") is None       # Sunday


def test_new_day_resets_state():
    g = PreopenGuard(lead_min=10)
    g.evaluate(et("2026-06-25 09:21"), "RED")
    g.evaluate(et("2026-06-25 09:31"), "RED")                      # late_open flagged on the 25th
    a = g.evaluate(et("2026-06-26 09:21"), "RED")                  # next day -> fresh alert
    assert a["kind"] == "not_ready"
