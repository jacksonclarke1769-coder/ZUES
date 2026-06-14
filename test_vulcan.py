"""PROJECT VULCAN — war-game tests for the phases not covered by existing batteries.
P8 bad data · P9 dashboard truth · P11 account safety · P12 live-permission safety.
(P2-P7, P10 are covered by THOR / recovery / recon / lock / scheduler / flatten / mffu
batteries — mapped in the VULCAN report.)"""
import json
import os

import pandas as pd
import pytest

from tradovate_client import TradovateClient, TradovateError


# ---------------------------------------------------------------- P11 account safety
def _client(spec):
    cli = TradovateClient({"env": "demo", "account_spec": spec},
                          {"demo": {"rest": "x", "ws": "y"}, "live": {"rest": "x", "ws": "y"}})
    cli._get = lambda path, **k: [{"name": "MFFU-EVAL-1", "id": 111},
                                  {"name": "MFFU-EVAL-2", "id": 222}]
    return cli


def test_missing_account_spec_blocks():
    with pytest.raises(TradovateError, match="account_spec is required"):
        _client(None)._resolve_account()
    with pytest.raises(TradovateError, match="account_spec is required"):
        _client("")._resolve_account()


def test_placeholder_account_spec_blocks():
    with pytest.raises(TradovateError, match="account_spec is required"):
        _client("YOUR_MFFU_ACCOUNT")._resolve_account()


def test_mismatched_account_spec_blocks_no_first_account_fallback():
    cli = _client("MFFU-EVAL-9")          # typo / wrong env
    with pytest.raises(TradovateError, match="refusing first-account fallback"):
        cli._resolve_account()
    assert cli.account_id is None


def test_explicit_account_match_by_name_and_id():
    cli = _client("MFFU-EVAL-2"); cli._resolve_account(); assert cli.account_id == 222
    cli = _client("111"); cli._resolve_account(); assert cli.account_id == 111


# ---------------------------------------------------------------- P12 live permission
def test_live_orders_disabled_by_code_constant():
    import tradovate_client as tc
    assert tc.LIVE_ORDERS_ENABLED is False           # hard latch in source
    cli = _client("MFFU-EVAL-1")
    with pytest.raises(TradovateError, match="DISABLED"):
        cli._guard_live()


def test_config_default_posture_is_paper():
    import config
    assert config.TRADOVATE.get("env", "demo") == "demo"
    assert config.SAFETY["enabled"] is False
    assert config.SAFETY.get("paper", True) is True


def test_d1c_production_gate_off():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "out", "d1c_shadow", "trial_state.json")
    st = json.load(open(p))
    assert st["production_gate_enabled"] is False


# ---------------------------------------------------------------- P8 bad data
def _mk_bot(tmp_path):
    from store import Store
    from bot import SimBot
    st = Store(str(tmp_path / "v.db"))
    return SimBot(st)


def _bars(n=40, start="2026-03-02 09:30", px=20000.0):
    ts = pd.date_range(start, periods=n, freq="5min", tz="America/New_York")
    return [(t, px + i, px + i + 5, px + i - 5, px + i + 1) for i, t in enumerate(ts)]


def test_duplicate_bar_is_ignored(tmp_path):
    b = _mk_bot(tmp_path)
    bars = _bars()
    for t, o, h, l, c in bars[:10]:
        b.process_bar(t, o, h, l, c)
    state_ts = b.last_bar_ts
    b.process_bar(*bars[9])                          # exact duplicate
    assert b.last_bar_ts == state_ts                 # not re-processed


def test_out_of_order_bar_is_ignored(tmp_path):
    b = _mk_bot(tmp_path)
    bars = _bars()
    for t, o, h, l, c in bars[:10]:
        b.process_bar(t, o, h, l, c)
    b.process_bar(*bars[3])                          # stale bar arrives late
    assert b.last_bar_ts == bars[9][0]


def test_zero_range_and_large_tick_bars_do_not_crash(tmp_path):
    b = _mk_bot(tmp_path)
    t0 = pd.Timestamp("2026-03-02 09:30", tz="America/New_York")
    b.process_bar(t0, 20000.0, 20000.0, 20000.0, 20000.0)            # zero-range
    b.process_bar(t0 + pd.Timedelta(minutes=5), 20000, 21500, 19000, 20007)  # absurd tick
    b.process_bar(t0 + pd.Timedelta(minutes=10), 20007, 20010, 20003, 20005)
    assert b.last_bar_ts is not None


def test_timestamp_gap_session_roll_does_not_crash(tmp_path):
    b = _mk_bot(tmp_path)
    t0 = pd.Timestamp("2026-03-06 15:50", tz="America/New_York")     # Fri afternoon
    b.process_bar(t0, 20000, 20010, 19990, 20005)
    t1 = pd.Timestamp("2026-03-09 09:30", tz="America/New_York")     # Mon after DST!
    b.process_bar(t1, 20050, 20060, 20040, 20055)
    assert b.cur_day == t1.date()                    # day rolled, no crash across gap+DST


# ---------------------------------------------------------------- P9 dashboard truth
def test_dashboard_regime_block_mirrors_source_files_exactly():
    import zeus_server as zs
    rm = zs._regime_monitor()
    for key, path in (("regime", zs.REGIME_JSON), ("d1c_shadow", zs.D1C_SHADOW_JSON)):
        if os.path.exists(path):
            assert rm[key] == json.load(open(path))   # pass-through, no reinterpretation
        else:
            assert rm[key] is None                    # absent -> null, never fake green


def test_dashboard_d1c_block_carries_trial_truth():
    import zeus_server as zs
    rm = zs._regime_monitor()
    if rm["d1c_shadow"] is not None:
        s = rm["d1c_shadow"]
        assert s["production_gate_enabled"] is False
        assert s["official_forward_count"] == 0       # current trial state
        assert "REHEARSAL ONLY" in s["replay_note"]
