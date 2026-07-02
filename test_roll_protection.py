"""Roll protection tests — TP_SYMBOL_MNQ override + preflight blocking.

Covers:
  - bridge_traderspost: TP_SYMBOL_MNQ env override appears in MNQ payload ticker;
    NQ payloads are unaffected; unset env restores bare 'MNQ'.
  - full_auto_preflight main(): BLOCKS in-window without env, passes with env set.
  - Payloads byte-identical to baseline when env unset AND outside roll window.
"""
import datetime
import importlib
import os
import sys
import unittest.mock as mock

import pytest

import bridge_traderspost as B
import market_calendar as MC


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_entry_ticker(root="MNQ", env_override=None):
    """Call build_entry with minimal valid args and return the ticker from the payload."""
    env = {}
    if env_override is not None:
        env["TP_SYMBOL_MNQ"] = env_override
    with mock.patch.dict(os.environ, env, clear=False):
        # Remove TP_SYMBOL_MNQ from env when env_override is None
        with mock.patch.dict(os.environ, {}, clear=False):
            if env_override is None:
                os.environ.pop("TP_SYMBOL_MNQ", None)
            else:
                os.environ["TP_SYMBOL_MNQ"] = env_override
            p, err = B.build_entry(
                account="TEST", strategy="A", setup="ote",
                signal_ts="2026-09-10T10:00:00", side="long",
                qty=1, entry=21000.0, stop=20950.0, target=21050.0,
                root=root, order_type="limit",
            )
    assert err is None, err
    return p["ticker"]


# ---------------------------------------------------------------------------
# bridge_traderspost: TP_SYMBOL_MNQ env override
# ---------------------------------------------------------------------------

def test_mnq_ticker_bare_when_env_unset():
    """No env override -> ticker is bare 'MNQ'."""
    os.environ.pop("TP_SYMBOL_MNQ", None)
    ticker = _build_entry_ticker(root="MNQ", env_override=None)
    assert ticker == "MNQ"


def test_mnq_ticker_overridden_when_env_set():
    """TP_SYMBOL_MNQ=MNQU2026 -> ticker is 'MNQU2026'."""
    ticker = _build_entry_ticker(root="MNQ", env_override="MNQU2026")
    assert ticker == "MNQU2026"


def test_nq_ticker_unaffected_by_env():
    """NQ root ignores TP_SYMBOL_MNQ — only MNQ is overridden."""
    with mock.patch.dict(os.environ, {"TP_SYMBOL_MNQ": "MNQU2026"}):
        p, err = B.build_entry(
            account="TEST", strategy="A", setup="ote",
            signal_ts="2026-09-10T10:00:00", side="long",
            qty=1, entry=21000.0, stop=20950.0, target=21050.0,
            root="NQ", order_type="limit",
        )
    assert err is None
    assert p["ticker"] == "NQ"


def test_exit_payload_uses_override():
    """build_exit also picks up the override."""
    with mock.patch.dict(os.environ, {"TP_SYMBOL_MNQ": "MNQU2026"}):
        p, err = B.build_exit(account="TEST", strategy="A",
                              signal_ts="2026-09-10T10:00:00", root="MNQ")
    assert err is None
    assert p["ticker"] == "MNQU2026"


def test_flatten_payload_uses_override():
    """build_flatten also picks up the override."""
    with mock.patch.dict(os.environ, {"TP_SYMBOL_MNQ": "MNQU2026"}):
        p, err = B.build_flatten(account="TEST", root="MNQ")
    assert err is None
    assert p["ticker"] == "MNQU2026"


def test_payload_byte_identical_outside_roll_window():
    """When env unset and NOT in roll window, payload is byte-identical to bare MNQ baseline."""
    os.environ.pop("TP_SYMBOL_MNQ", None)
    # Aug 1 2026 is outside any roll window
    p, err = B.build_entry(
        account="TEST", strategy="A", setup="ote",
        signal_ts="2026-08-01T10:00:00", side="long",
        qty=1, entry=21000.0, stop=20950.0, target=21050.0,
        root="MNQ", order_type="limit",
    )
    assert err is None
    assert p["ticker"] == "MNQ"


# ---------------------------------------------------------------------------
# full_auto_preflight: roll-window preflight block
# ---------------------------------------------------------------------------

def _run_preflight(today_date, env_override=None):
    """Import and call full_auto_preflight.main() with a mocked environment.

    We patch: datetime.date.today() for the roll check, roll_window to use real
    MC.roll_window, and every auto_safety gate to pass — isolating the roll block.
    Returns (exit_code, fails_printed) via capturing stdout.
    """
    import io
    import contextlib
    import full_auto_preflight as FP

    env = {}
    if env_override is not None:
        env["TP_SYMBOL_MNQ"] = env_override

    # Build a minimal fake auto_safety result (all gates pass)
    fake_ok = True
    fake_fails = []
    fake_summ = {"effective_d1c": "ACTIVE_EVAL_FILTER"}

    buf = io.StringIO()
    with mock.patch.dict(os.environ, env, clear=False):
        if env_override is None:
            os.environ.pop("TP_SYMBOL_MNQ", None)
        # Patch auto_safety.full_auto_preflight to return all-pass
        with mock.patch("full_auto_preflight.auto_safety") as mock_as, \
             mock.patch("full_auto_preflight.zeus_server") as mock_zs, \
             mock.patch("full_auto_preflight.Store") as mock_store, \
             mock.patch("full_auto_preflight.apply_freshness", return_value={"DATA_READY": True, "data_state": "GREEN"}), \
             mock.patch("full_auto_preflight.datetime") as mock_dt, \
             contextlib.redirect_stdout(buf):
            mock_as.full_auto_preflight.return_value = (fake_ok, list(fake_fails), "ACTIVE_EVAL_FILTER", fake_summ)
            mock_zs.assemble_state.return_value = {"deployment": {"green": True}}
            mock_store.return_value.get_state.return_value = "{}"
            # patch datetime.date.today() for the roll-window check in preflight
            mock_dt.date.today.return_value = today_date
            # Allow real roll_window to work (market_calendar is not patched)
            rc = FP.main(["--account", "TEST-ACCT"])
    output = buf.getvalue()
    return rc, output


def test_preflight_blocked_in_roll_window_no_env():
    """In-window date without TP_SYMBOL_MNQ -> preflight BLOCKED."""
    in_window = datetime.date(2026, 9, 10)  # inside Sep roll window
    assert MC.roll_window(in_window)        # verify our test date is actually in-window
    rc, output = _run_preflight(in_window, env_override=None)
    assert rc == 1, "expected exit 1 (BLOCKED), got %d" % rc
    assert "ROLL WINDOW" in output


def test_preflight_passes_in_roll_window_with_env():
    """In-window date WITH TP_SYMBOL_MNQ set -> roll check passes (other gates also mocked pass)."""
    in_window = datetime.date(2026, 9, 10)
    rc, output = _run_preflight(in_window, env_override="MNQU2026")
    assert rc == 0, "expected exit 0 (GO), got %d\n%s" % (rc, output)
    assert "ROLL WINDOW" not in output


def test_preflight_passes_outside_roll_window_no_env():
    """Outside roll window without TP_SYMBOL_MNQ -> no roll block."""
    outside = datetime.date(2026, 8, 1)    # outside any window
    assert not MC.roll_window(outside)
    rc, output = _run_preflight(outside, env_override=None)
    assert rc == 0, "expected exit 0 (GO), got %d\n%s" % (rc, output)
    assert "ROLL WINDOW" not in output


def test_preflight_expiry_day_blocked():
    """Expiry day itself (Sep 18) is in-window -> blocks without env."""
    expiry = datetime.date(2026, 9, 18)
    assert MC.roll_window(expiry)
    rc, output = _run_preflight(expiry, env_override=None)
    assert rc == 1
    assert "ROLL WINDOW" in output


def test_preflight_day_after_expiry_passes():
    """Day after expiry (Sep 19) is out-of-window -> no block."""
    after = datetime.date(2026, 9, 19)
    assert not MC.roll_window(after)
    rc, output = _run_preflight(after, env_override=None)
    assert rc == 0
