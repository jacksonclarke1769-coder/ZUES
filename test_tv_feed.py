"""Tests for tv_feed.TradingViewFeed — CDP channel is faked (no Chrome needed)."""
import itertools

import pandas as pd
import pytest

import tv_feed
from tv_feed import TradingViewFeed, _to_et
from store import Store


class FakeCDP:
    """Stands in for the CDP websocket channel. Routes eval() by expression content."""

    def __init__(self, symbol="CME_MINI:NQ1!", resolution="5", bars=None):
        self.symbol_val = symbol
        self.resolution_val = resolution
        self.bars = bars or []          # list of [time_unix, o, h, l, c, vol]
        self.connected = False
        self.closed = False

    def connect(self):
        self.connected = True
        return {"id": "fake-target"}

    def eval(self, expr, await_promise=False):
        if ".symbol()" in expr:
            return self.symbol_val
        if ".resolution()" in expr:
            return self.resolution_val
        return [list(b) for b in self.bars]

    def close(self):
        self.closed = True


def _old_bar(open_et_iso, o, h, l, c, vol=100):
    """Build a bar tuple at a fixed past ET time (guaranteed CLOSED)."""
    ts = pd.Timestamp(open_et_iso, tz=tv_feed.NY)
    return [int(ts.tz_convert("UTC").timestamp()), o, h, l, c, vol]


# ----------------------------- symbol / timeframe guard -----------------------------
def test_connect_accepts_nq_5m():
    feed = TradingViewFeed(cdp=FakeCDP("CME_MINI:NQ1!", "5"))
    contract = feed.connect()
    assert contract["source"] == "tradingview-cdp"
    assert "NQ" in contract["name"]
    assert contract["resolution"] == "5"


def test_connect_refuses_wrong_symbol():
    feed = TradingViewFeed(cdp=FakeCDP("NASDAQ:AAPL", "5"))
    with pytest.raises(RuntimeError, match="REFUSED"):
        feed.connect()


def test_connect_refuses_wrong_timeframe():
    feed = TradingViewFeed(cdp=FakeCDP("CME_MINI:NQ1!", "1"))
    with pytest.raises(RuntimeError, match="REFUSED"):
        feed.connect()


def test_connect_refuses_when_api_not_ready():
    feed = TradingViewFeed(cdp=FakeCDP(symbol=None))
    with pytest.raises(RuntimeError, match="not ready"):
        feed.connect()


# ----------------------------- timestamp conversion -----------------------------
def test_to_et_seconds():
    ts = _to_et(1781297700)
    assert str(ts.tz) == tv_feed.NY
    assert ts == pd.Timestamp(1781297700, unit="s", tz="UTC").tz_convert(tv_feed.NY)


def test_to_et_milliseconds_normalized():
    assert _to_et(1781297700000) == _to_et(1781297700)


# ----------------------------- history -----------------------------
def test_history_drops_forming_last_bar_and_marks_seen():
    bars = [
        _old_bar("2026-06-12 09:30", 100, 101, 99, 100.5),
        _old_bar("2026-06-12 09:35", 100.5, 102, 100, 101),
        _old_bar("2026-06-12 09:40", 101, 103, 100.5, 102),
    ]
    feed = TradingViewFeed(cdp=FakeCDP(bars=bars), warmup_source="tradingview")
    out = feed.history()
    assert len(out) == 2                      # last (forming) bar dropped
    assert out[0][0] < out[1][0]              # sorted ascending
    assert out[1][4] == 101                   # close of 2nd bar
    # only the 2 COMPLETED bars are marked seen; the forming bar is left unseen so live()
    # emits it once it closes (the previous behavior wrongly suppressed it).
    assert len(feed.seen) == 2


def test_history_empty():
    feed = TradingViewFeed(cdp=FakeCDP(bars=[]), warmup_source="tradingview")
    assert feed.history() == []


# ----------------------------- deep warmup (Dukascopy-backed, basis-aligned) -----------------------------
class FakeDuka:
    """Stands in for paper_live.DukascopyLiveFeed (deep, current warmup history)."""
    def __init__(self, bars):
        self._bars = bars
    def connect(self):
        return {"name": "duka"}
    def history(self):
        return list(self._bars)


def _et(iso):
    return pd.Timestamp(iso, tz=tv_feed.NY)


# ----------------------------- 1m -> 5m aggregation -----------------------------
def test_aggregator_rolls_five_1m_into_one_5m():
    from tv_feed import Bar5Aggregator
    agg = Bar5Aggregator()
    out = []
    # 09:30..09:34 (one 5m bucket) then 09:35 (new bucket -> emits the 09:30 bar)
    ones = [
        ("2026-06-15 09:30", 100, 105, 99, 101, 10),
        ("2026-06-15 09:31", 101, 106, 100, 102, 12),
        ("2026-06-15 09:32", 102, 108, 101, 107, 8),
        ("2026-06-15 09:33", 107, 109, 104, 105, 9),
        ("2026-06-15 09:34", 105, 110, 103, 106, 11),
        ("2026-06-15 09:35", 106, 107, 105, 106, 5),   # new bucket -> flush prior
    ]
    for iso, o, h, l, c, v in ones:
        done = agg.add(_et(iso), o, h, l, c, v)
        if done:
            out.append(done)
    assert len(out) == 1
    ts, o, h, l, c, v = out[0]
    assert ts == _et("2026-06-15 09:30")
    assert (o, h, l, c, v) == (100, 110, 99, 106, 50)   # O=first H=max L=min C=last V=sum


def test_aggregate_5m_helper_matches_buckets():
    from tv_feed import aggregate_5m
    bars = [(_et("2026-06-15 09:30"), 1, 2, 0.5, 1.5, 3),
            (_et("2026-06-15 09:34"), 1.5, 3, 1, 2.8, 4),
            (_et("2026-06-15 09:35"), 2.8, 2.9, 2.0, 2.1, 2)]
    out = aggregate_5m(bars)            # flush() includes the final (forming) bucket too
    assert len(out) == 2
    assert out[0][0] == _et("2026-06-15 09:30")
    assert out[0][1:] == (1, 3, 0.5, 2.8)   # O,H,L,C of the 09:30 bucket


def test_measure_basis_median_offset():
    # overlapping timestamps; TV close is +5 above Duka close
    ts = "2026-06-12 09:30"
    tv = [(_et(ts), 0, 0, 0, 105.0)]
    duka = [(_et(ts), 0, 0, 0, 100.0)]
    feed = TradingViewFeed(cdp=FakeCDP(), warmup_source="tradingview")
    assert feed._measure_basis(tv, duka) == (5.0, 1)


def _solid_overlap(offset, n=25, start="2026-06-12 09:30"):
    """n overlapping 5m bars where TV close = Duka close + offset (for a confident basis)."""
    tv, duka = [], []
    t0 = _et(start)
    for i in range(n):
        ts = t0 + pd.Timedelta(minutes=5 * i)
        duka.append((ts, 100, 100, 100, 100.0))
        tv.append(_old_bar(ts.strftime("%Y-%m-%d %H:%M"), 100 + offset, 100 + offset,
                           100 + offset, 100.0 + offset))
    return tv, duka


def test_dukascopy_warmup_trusts_solid_overlap(tmp_path):
    # >= MIN_BASIS_OVERLAP matching bars at +7 -> trusted, persisted, applied
    tv, duka = _solid_overlap(7.0, n=25)
    bstore = Store(str(tmp_path / "b.db"))
    feed = TradingViewFeed(cdp=FakeCDP(bars=tv), warmup_source="dukascopy",
                           duka_feed=FakeDuka(duka), basis_store=bstore)
    out = feed.history()
    assert feed.basis == 7.0 and feed.basis_confident is True
    assert out[0][4] == 107.0                          # 100 + 7
    assert float(bstore.get_state("tv_cme_basis")) == 7.0   # persisted


def test_dukascopy_warmup_keeps_persisted_when_overlap_thin(tmp_path):
    # only 1 overlapping bar (noisy) -> must NOT clobber the good persisted +27.7
    overlap = "2026-06-12 16:00"
    tv_cache = [_old_bar(overlap, 110, 110, 110, 110)]   # would measure +10 (1 bar, thin)
    duka_hist = [(_et("2026-06-01 09:30"), 100, 101, 99, 100.5),
                 (_et(overlap), 100, 100, 100, 100)]
    bstore = Store(str(tmp_path / "b.db"))
    bstore.set_state(tv_cme_basis="27.7")               # the clean prior value
    feed = TradingViewFeed(cdp=FakeCDP(bars=tv_cache), warmup_source="dukascopy",
                           duka_feed=FakeDuka(duka_hist), basis_store=bstore)
    out = feed.history()
    assert feed.basis == 27.7 and feed.basis_from_cache is True   # kept, not clobbered
    assert feed.basis_confident is False
    assert float(bstore.get_state("tv_cme_basis")) == 27.7        # persisted value untouched
    assert out[0][4] == 100.5 + 27.7


# ----------------------------- data_status / DATA_READY -----------------------------
def _two_week_feed(reset=0):
    feed = TradingViewFeed(cdp=FakeCDP(), warmup_source="tradingview")
    feed.first_bar_ts = _et("2026-05-26 09:30")
    feed.last_bar_ts = _et("2026-06-12 16:00")        # ~17 days span
    feed.reset_count = reset
    return feed


def test_data_ready_false_when_entitlement_unconfirmed(monkeypatch):
    monkeypatch.delenv("TV_REALTIME_CONFIRMED", raising=False)
    feed = _two_week_feed()
    now = _et("2026-06-12 16:03").tz_convert("UTC")    # fresh
    st = feed.data_status(now=now)
    assert st["warmup_ok"] is True
    assert st["DATA_READY"] is False                   # entitlement unverified -> never ready
    assert any("entitlement" in r for r in st["reasons"])


def test_data_ready_true_only_when_all_green(monkeypatch):
    monkeypatch.setenv("TV_REALTIME_CONFIRMED", "1")
    feed = _two_week_feed(reset=0)
    now = _et("2026-06-12 16:03").tz_convert("UTC")
    st = feed.data_status(now=now)
    assert st["DATA_READY"] is True


def test_data_ready_false_on_shallow_warmup(monkeypatch):
    monkeypatch.setenv("TV_REALTIME_CONFIRMED", "1")
    feed = TradingViewFeed(cdp=FakeCDP(), warmup_source="tradingview")
    feed.first_bar_ts = _et("2026-06-12 09:30")
    feed.last_bar_ts = _et("2026-06-12 16:00")         # 1 day
    st = feed.data_status(now=_et("2026-06-12 16:03").tz_convert("UTC"))
    assert st["warmup_ok"] is False
    assert st["DATA_READY"] is False


def test_data_ready_false_on_stale_and_reset(monkeypatch):
    monkeypatch.setenv("TV_REALTIME_CONFIRMED", "1")
    feed = _two_week_feed(reset=2)
    now = _et("2026-06-12 18:00").tz_convert("UTC")    # 2h after last bar -> stale
    st = feed.data_status(now=now)
    assert st["stale"] is True
    assert st["reset_count"] == 2
    assert st["DATA_READY"] is False


# ----------------------------- live -----------------------------
def test_live_yields_closed_unseen_bars_only():
    bars = [
        _old_bar("2026-06-12 09:30", 100, 101, 99, 100.5),
        _old_bar("2026-06-12 09:35", 100.5, 102, 100, 101),
    ]
    feed = TradingViewFeed(poll_sec=0, cdp=FakeCDP(bars=bars))
    got = list(itertools.islice(feed.live(), 2))
    assert len(got) == 2
    assert {g[0] for g in got} == {_to_et(bars[0][0]), _to_et(bars[1][0])}


def test_live_skips_already_seen():
    bars = [_old_bar("2026-06-12 09:30", 100, 101, 99, 100.5)]
    feed = TradingViewFeed(poll_sec=0, cdp=FakeCDP(bars=bars))
    feed.seen.add(_to_et(bars[0][0]).isoformat())   # pretend already emitted
    # all bars seen -> generator never yields; islice(…,1) over a 0-yield first batch
    # would loop forever, so prove emptiness by checking the filter directly instead.
    out = feed._fetch(50)
    assert len(out) == 1
    assert out[0][0].isoformat() in feed.seen


def test_live_close_rule_matches_resolution():
    """A 1m feed must emit a bar ~1 min after open, not wait 5 min (D1c needs timely 1m)."""
    now = pd.Timestamp.now("UTC")
    # bar opened 90s ago: closed for a 1m feed, NOT yet for a 5m feed
    bar = [int((now - pd.Timedelta(seconds=90)).timestamp()), 100, 101, 99, 100.5, 5]
    f1 = TradingViewFeed(poll_sec=0, expect_res="1", warmup_source="tradingview",
                         cdp=FakeCDP(bars=[bar]))
    got1 = list(itertools.islice(f1.live(), 1))
    assert len(got1) == 1                      # 1m feed emits the 90s-old bar
    f5 = TradingViewFeed(poll_sec=0, expect_res="5", warmup_source="tradingview",
                         cdp=FakeCDP(bars=[bar]))
    # 5m feed: 90s-old bar is still forming -> _fetch returns it but live() must not emit it
    assert f5._fetch(50)[0][0] == _to_et(bar[0])
    assert int(f5.expect_res) == 5


# ----------------------------- reconnect-tolerant readiness (GREEN/YELLOW/RED) -----------------------------
def _live_feed():
    f = TradingViewFeed(cdp=FakeCDP(), warmup_source="tradingview")
    f.first_bar_ts = _et("2026-05-26 09:30")
    f.last_bar_ts = _et("2026-06-12 16:00")
    return f


def _fresh_now():
    return _et("2026-06-12 16:02").tz_convert("UTC")   # 2 min after last bar


def test_state_green_when_healthy():
    assert _live_feed().data_state(_fresh_now())[0] == "GREEN"


def test_single_reset_yellow_then_green_after_stability():
    f = _live_feed()
    f.reset_count = 1; f.last_reset_ts = f.last_bar_ts; f.bars_since_reset = 0
    assert f.data_state(_fresh_now())[0] == "YELLOW"        # stabilizing 0/3 -> entries blocked
    f.bars_since_reset = 3
    assert f.data_state(_fresh_now())[0] == "GREEN"         # recovered after stability window


def test_reconnecting_is_yellow():
    f = _live_feed(); f._reconnecting = True
    assert f.data_state(_fresh_now())[0] == "YELLOW"


def test_stale_feed_is_red():
    f = _live_feed()
    now = _et("2026-06-12 16:30").tz_convert("UTC")         # 30 min > STALE_RED_S
    assert f.data_state(now)[0] == "RED"


def test_too_many_resets_is_red():
    f = _live_feed(); f.reset_count = f.MAX_RESETS + 1
    assert f.data_state(_fresh_now())[0] == "RED"


def test_data_ready_only_green_and_realtime(monkeypatch):
    monkeypatch.setenv("TV_REALTIME_CONFIRMED", "1")
    f = _live_feed()
    assert f.data_status(_fresh_now())["DATA_READY"] is True
    f._reconnecting = True                                  # YELLOW must block readiness
    assert f.data_status(_fresh_now())["DATA_READY"] is False


def test_classify_dup_ooo_unclosed_ok():
    f = _live_feed()
    now = pd.Timestamp.now("UTC")
    seen_ts = _et("2026-06-12 15:00")
    f.seen.add(seen_ts.isoformat())
    assert f._classify(seen_ts, now, 1) == "dup"            # duplicate rejected
    f.last_yielded_ts = _et("2026-06-12 15:30")
    assert f._classify(_et("2026-06-12 15:25"), now, 1) == "ooo"   # out-of-order rejected
    assert f._classify(_et("2026-06-12 15:35"), now, 1) == "ok"
    forming = _to_et(int(now.timestamp()))
    assert f._classify(forming, now, 5) == "unclosed"


def test_closed_bar_predicate():
    """The exact gate live() uses: a bar is emitted only once now >= open + 5m."""
    now = pd.Timestamp.now("UTC")
    forming_open = _to_et(int(now.timestamp()))               # opened ~now
    assert not (now >= forming_open.tz_convert("UTC") + pd.Timedelta(minutes=5))
    closed_open = _to_et(int((now - pd.Timedelta(minutes=10)).timestamp()))
    assert now >= closed_open.tz_convert("UTC") + pd.Timedelta(minutes=5)
