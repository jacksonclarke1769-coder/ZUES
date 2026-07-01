"""TradingView read-back parsing + fail-closed, with a mock CDP (no live connection needed).
Proves the sentinel interface (net_by_account/balance) and the phantom-killer (order_filled), and that an
unconfigured panel RAISES (fail-closed) so build_readback returns None and the bot stays stood down."""
import pytest
from readback_tradingview import TradingViewBrokerView, TradingViewReadbackUnconfigured


class MockCDP:
    def __init__(self, payload):
        self.payload = payload
    def eval(self, expr, await_promise=False):
        return self.payload


def test_net_by_account_signs_and_aggregates():
    cdp = MockCDP({"positions": [{"account": "APX1", "symbol": "NQ", "qty": 2, "side": "long"},
                                 {"account": "APX1", "symbol": "NQ", "qty": 1, "side": "short"},
                                 {"account": "APX2", "symbol": "NQ", "qty": 3, "side": "short"}],
                   "balances": [], "orders": []})
    assert TradingViewBrokerView(cdp=cdp).net_by_account() == {"APX1": 1, "APX2": -3}


def test_balance_lookup():
    cdp = MockCDP({"positions": [], "balances": [{"account": "APX1", "equity": 50123.5}], "orders": []})
    bv = TradingViewBrokerView(cdp=cdp)
    assert bv.balance("APX1") == 50123.5
    assert bv.balance("OTHER") is None                       # unknown account -> None (not a guess)


def test_order_filled_only_true_on_fill():
    cdp = MockCDP({"positions": [], "balances": [],
                   "orders": [{"account": "APX1", "signal": "sig-1", "status": "filled"},
                              {"account": "APX1", "signal": "sig-2", "status": "working"}]})
    bv = TradingViewBrokerView(cdp=cdp)
    assert bv.order_filled("sig-1") is True
    assert bv.order_filled("sig-2") is False                 # 'working' != fill (the 06-30 phantom case)
    assert bv.order_filled("sig-x") is None                  # not found -> unknown


def test_fail_closed_when_unconfigured():
    bv = TradingViewBrokerView(cdp=MockCDP({"__unconfigured__": True}))
    with pytest.raises(TradingViewReadbackUnconfigured):
        bv.net_by_account()
    with pytest.raises(TradingViewReadbackUnconfigured):
        bv.balance("APX1")


def test_empty_panel_is_flat_not_error():
    bv = TradingViewBrokerView(cdp=MockCDP({"positions": [], "balances": [], "orders": []}))
    assert bv.net_by_account() == {}                         # connected + genuinely flat
    assert bv.balance("APX1") is None
    assert bv.order_filled("sig") is None
