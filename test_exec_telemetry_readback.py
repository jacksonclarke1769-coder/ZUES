"""Tests for the avg_price_by_account addition to readback_tradingview.py.

These are additive to the existing test_readback_tradingview.py tests and do not
duplicate them.  The JS _PANEL_JS change is tested indirectly via mock CDP payloads
(same as the existing test pattern).
"""
from __future__ import annotations

import pytest
from readback_tradingview import TradingViewBrokerView, TradingViewReadbackUnconfigured


class MockCDP:
    def __init__(self, payload):
        self.payload = payload

    def eval(self, expr, await_promise=False):
        return self.payload


_PANEL_WITH_AVG = {
    "positions": [
        {"account": "APX1", "symbol": "MNQ", "qty": 2, "side": "long", "avg_price": 19001.5},
        {"account": "APX2", "symbol": "MNQ", "qty": 1, "side": "short", "avg_price": None},
    ],
    "balances": [{"account": "APX1", "equity": 50000.0}],
    "orders": [],
}


def test_avg_price_returns_float_for_known_account():
    bv = TradingViewBrokerView(cdp=MockCDP(_PANEL_WITH_AVG))
    assert bv.avg_price_by_account("APX1") == pytest.approx(19001.5)


def test_avg_price_none_for_unknown_account():
    bv = TradingViewBrokerView(cdp=MockCDP(_PANEL_WITH_AVG))
    assert bv.avg_price_by_account("UNKNOWN") is None


def test_avg_price_none_when_field_null():
    """avg_price field present but None → returns None (panel readable but price absent)."""
    bv = TradingViewBrokerView(cdp=MockCDP(_PANEL_WITH_AVG))
    assert bv.avg_price_by_account("APX2") is None


def test_avg_price_none_on_unconfigured_panel():
    """Unconfigured panel → _panel() raises but avg_price_by_account catches it → None."""
    bv = TradingViewBrokerView(cdp=MockCDP({"__unconfigured__": True}))
    # Must NOT raise (method swallows exceptions and returns None)
    assert bv.avg_price_by_account("APX1") is None


def test_avg_price_none_on_empty_positions():
    bv = TradingViewBrokerView(cdp=MockCDP({"positions": [], "balances": [], "orders": []}))
    assert bv.avg_price_by_account("APX1") is None


def test_avg_price_does_not_affect_net_by_account():
    """Existing net_by_account must still work when avg_price field is present."""
    bv = TradingViewBrokerView(cdp=MockCDP(_PANEL_WITH_AVG))
    net = bv.net_by_account()
    assert net["APX1"] == 2
    assert net["APX2"] == -1
