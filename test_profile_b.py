"""Profile B engine — ORB break detection, stop/target geometry, one-per-day,
D1c exemption (via permission). Streaming logic mirrors b_entries/b_exits."""
import pandas as pd
from strategy_engine_profileB import ProfileBEngine
from d1c_filter import profile_b_permission


def _feed_day(eng, day="2026-06-22", or_high=110.0, or_low=100.0, break_close=113.0,
              warmup=20):
    # warmup bars (pre-market) to seed ATR(14): TR ~10 each
    t = pd.Timestamp(f"{day} 07:00")
    for _ in range(warmup):
        eng.add_bar(t, 100, 105, 95, 100); t += pd.Timedelta(minutes=5)
    # opening range 09:30-09:45 (3x 5m bars) establishing OR high/low
    for ts, h, l in [("09:30", or_high, or_low), ("09:35", or_high - 1, or_low + 1),
                     ("09:40", or_high - 2, or_low + 2)]:
        eng.add_bar(pd.Timestamp(f"{day} {ts}"), 105, h, l, 105)
    # 09:45 break bar — close beyond OR high -> long
    eng.add_bar(pd.Timestamp(f"{day} 09:45"), 108, break_close + 1, 107, break_close)


def test_long_break_emits_signal_with_geometry():
    eng = ProfileBEngine()
    _feed_day(eng)
    s = eng.latest_signal()
    assert s is not None
    assert s["side"] == "long" and s["profile"] == "B" and s["liq"] == "orb"
    assert s["entry"] == 110.0                        # OR high level
    assert s["stop"] < s["entry"] < s["target"]
    rr = (s["target"] - s["entry"]) / (s["entry"] - s["stop"])
    assert round(rr, 2) == 1.5                          # 1.5R target / 1R stop


def test_short_break_emits_short():
    eng = ProfileBEngine()
    # break BELOW OR low
    t = pd.Timestamp("2026-06-22 07:00")
    for _ in range(20):
        eng.add_bar(t, 100, 105, 95, 100); t += pd.Timedelta(minutes=5)
    for ts, h, l in [("09:30", 110, 100), ("09:35", 109, 101), ("09:40", 108, 102)]:
        eng.add_bar(pd.Timestamp(f"2026-06-22 {ts}"), 105, h, l, 105)
    eng.add_bar(pd.Timestamp("2026-06-22 09:45"), 102, 103, 96, 97)   # close 97 < OR low 100
    s = eng.latest_signal()
    assert s is not None and s["side"] == "short" and s["entry"] == 100.0
    assert s["target"] < s["entry"] < s["stop"]


def test_one_signal_per_day():
    eng = ProfileBEngine()
    _feed_day(eng)
    assert eng.latest_signal() is not None
    # another post-OR break bar same day -> no second signal
    eng.add_bar(pd.Timestamp("2026-06-22 09:50"), 113, 120, 112, 118)
    assert eng.latest_signal() is None


def test_no_signal_without_break():
    eng = ProfileBEngine()
    t = pd.Timestamp("2026-06-22 07:00")
    for _ in range(20):
        eng.add_bar(t, 100, 105, 95, 100); t += pd.Timedelta(minutes=5)
    for ts in ["09:30", "09:35", "09:40", "09:45", "09:50"]:
        eng.add_bar(pd.Timestamp(f"2026-06-22 {ts}"), 105, 108, 102, 105)  # stays inside OR
    assert eng.latest_signal() is None


def test_profile_b_never_consults_d1c():
    # permission is identical to non-D1c logic; blocked only by daily stop / P3
    assert profile_b_permission(signal_present=True, daily_stopped=False, p3_blocked=False)["permit"]
    assert not profile_b_permission(signal_present=True, daily_stopped=False, p3_blocked=True)["permit"]
    assert not profile_b_permission(signal_present=True, daily_stopped=True, p3_blocked=False)["permit"]
    assert not profile_b_permission(signal_present=False, daily_stopped=False, p3_blocked=False)["permit"]
