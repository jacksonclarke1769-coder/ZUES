"""Phase-1 audit fixes (2026-07-02): sentinel taxonomy/reset/balance fail-closed + prospective risk gate."""
import live_readback as LR
from live_readback import ReadbackSentinel


class _FailBroker:
    def net_by_account(self):
        raise RuntimeError("panel gone")

    def balance(self, a):
        raise RuntimeError("panel gone")


class _Broker:
    def __init__(self, net=0, bal=49_000.0):
        self._net, self._bal = net, bal

    def net_by_account(self):
        return {"ACC": self._net}

    def balance(self, a):
        return self._bal


def test_read_fail_halts_but_never_flattens():
    fired, alerts = [], []
    s = ReadbackSentinel("ACC", floor=48_000, on_critical=fired.append, on_alert=alerts.append)
    b = _FailBroker()
    for _ in range(3):
        s.poll(b)
    assert s.halted and "BROKER_READ_FAIL" in s.reason
    assert fired == []                       # READ-class BLACK must NOT market-flatten (audit T0-3)
    assert alerts                            # operator alerted (first-fail + halt)


def test_mismatch_black_still_flattens():
    fired = []
    s = ReadbackSentinel("ACC", floor=None, on_critical=fired.append)
    b = _Broker(net=5)                       # broker holds 5, bot expects flat -> ORPHAN
    s.poll(b); s.poll(b)                     # grace = 2
    assert s.halted and fired and "ORPHAN_POSITION" in fired[0]


def test_reset_clears_halt_and_counters():
    s = ReadbackSentinel("ACC", on_critical=lambda r: None)
    b = _FailBroker()
    for _ in range(3):
        s.poll(b)
    assert s.halted
    s.expected = 7
    s.reset()
    assert not s.halted and s.reason is None and s._read_fail == 0
    assert s.expected == 7                   # position belief survives re-arm
    ok, _ = s.ready()
    assert ok


def test_balance_unreadable_fails_closed_after_n():
    fired = []
    s = ReadbackSentinel("ACC", floor=48_000, on_critical=fired.append)
    b = _Broker(bal=None)
    for _ in range(LR.BAL_NONE_CONFIRM + s.grace):
        s.poll(b)
    assert s.halted and "BALANCE_UNREADABLE" in s.reason
    assert fired == []                       # READ-class: halt, no flatten


def test_equity_regex_accepts_comma_only():
    import re, readback_tradingview as RT
    m = re.search(r"Equity\s*\$?([0-9][0-9,]*(?:\.[0-9]+)?)", "Equity $52,340")
    assert m and m.group(1) == "52,340"
    assert r"(?:\.[0-9]+)?" in RT._PANEL_JS      # decimals optional in the live scrape too


def _mk_auto(cushion):
    from auto_live import LiveAuto
    a = LiveAuto.__new__(LiveAuto)
    a.open_risk, a._risk_day = {}, None
    a.cushion_fn = (lambda: (cushion, 2000.0)) if cushion is not None else None
    return a


def test_risk_gate_sizes_down_wide_stops():
    a = _mk_auto(2000.0)
    ok, why, q = a._risk_gate("A", 21000.0, 21000.0 - 137.0, 10)   # the real 06-29 137pt signal
    assert ok and q == 5                                        # $1600 budget // $274/ct = 5, not rejected
    ok, why, q = a._risk_gate("A", 21000.0, 21000.0 - 40.0, 10)   # $80/ct -> full 10 fits
    assert ok and q == 10 and why == ""


def test_risk_gate_cushion_blocks_concurrent_stack():
    a = _mk_auto(1500.0)                                        # ~real cushion today
    ok, _, q = a._risk_gate("A", 21000.0, 21000.0 - 60.0, 10)  # $120/ct -> 10 fits $1,350 headroom
    assert ok and q == 10
    a.open_risk["A"] = 1200.0
    ok, why, q = a._risk_gate("B", 21000.0, 21000.0 - 58.0, 5)  # $150 headroom left -> 1 MNQ only
    assert ok and q == 1
    a.open_risk["A"] = 1350.0
    ok, why, q = a._risk_gate("B", 21000.0, 21000.0 - 58.0, 5)  # nothing fits -> block
    assert not ok and q == 0


def test_risk_gate_new_day_clears_book():
    a = _mk_auto(1500.0)
    a.open_risk["A"] = 1200.0
    a._risk_day = None                                          # forces day-roll on next call
    ok, _, q = a._risk_gate("B", 21000.0, 21000.0 - 58.0, 5)
    assert ok and q == 5 and "A" not in a.open_risk


def test_feed_watch_holiday_closed():
    import pandas as pd
    from feed_watch import market_likely_open
    assert not market_likely_open(pd.Timestamp("2026-07-03 10:00", tz="America/New_York"))  # July 4th observed
    assert market_likely_open(pd.Timestamp("2026-07-02 10:00", tz="America/New_York"))      # normal Thursday
    assert market_likely_open(pd.Timestamp("2026-07-05 19:00", tz="America/New_York"))      # Sunday Globex
    assert not market_likely_open(pd.Timestamp("2026-11-27 14:00", tz="America/New_York"))  # half-day pm
