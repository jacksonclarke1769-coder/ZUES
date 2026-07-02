"""Tests for htf_alignment.py — classifier unit, parity, and gate tests.

Unit tests use synthetic data only (no external data needed).
Parity test skips if the full research data dir is absent.
Gate tests check HTF_SKIP_ENABLED wiring into auto_live.on_decision.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from htf_alignment import compute_htf_alignment

NY = "America/New_York"


# ── helpers ──────────────────────────────────────────────────────────────────

def _trend_df(n=600, slope=1.0, start="2024-01-02 09:30", freq="5min"):
    """Synthetic 5m bars with a linear close trend."""
    idx = pd.date_range(start, periods=n, freq=freq, tz=NY)
    close = 20000.0 + slope * np.arange(n, dtype=float)
    return pd.DataFrame(
        {"Open": close, "High": close + 2, "Low": close - 2,
         "Close": close, "Volume": 100.0},
        index=idx)


# ── classifier unit tests ─────────────────────────────────────────────────────

def test_all_up_long_alignment_is_3():
    """Steady uptrend + long direction -> all three slopes +1 -> alignment +3."""
    df5 = _trend_df(n=600, slope=1.0)
    ts = df5.index[-1]
    v15, v1h, v4h, align = compute_htf_alignment(df5, ts, "long")
    assert v15 == 1.0 and v1h == 1.0 and v4h == 1.0
    assert align == 3.0


def test_all_up_short_alignment_is_minus3():
    """Steady uptrend + short direction -> all slopes +1, * -1 -> alignment -3."""
    df5 = _trend_df(n=600, slope=1.0)
    ts = df5.index[-1]
    v15, v1h, v4h, align = compute_htf_alignment(df5, ts, "short")
    assert v15 == -1.0 and v1h == -1.0 and v4h == -1.0
    assert align == -3.0


def test_all_down_short_alignment_is_3():
    """Steady downtrend + short direction -> slopes -1, * -1 -> alignment +3."""
    df5 = _trend_df(n=600, slope=-1.0)
    ts = df5.index[-1]
    v15, v1h, v4h, align = compute_htf_alignment(df5, ts, "short")
    assert v15 == 1.0 and v1h == 1.0 and v4h == 1.0
    assert align == 3.0


def test_empty_df_returns_all_nan():
    """Empty DataFrame -> all NaN (no data to classify)."""
    df5 = pd.DataFrame(
        columns=["Open", "High", "Low", "Close", "Volume"],
        index=pd.DatetimeIndex([], tz=NY))
    ts = pd.Timestamp("2024-01-03 09:35", tz=NY)
    v15, v1h, v4h, align = compute_htf_alignment(df5, ts, "long")
    assert all(np.isnan(v) for v in [v15, v1h, v4h, align])


def test_ts_before_first_bar_returns_nan():
    """Timestamp before the first bar -> i=-1 -> NaN for all timeframes."""
    df5 = _trend_df(n=100, slope=1.0)
    ts = df5.index[0] - pd.Timedelta(minutes=5)
    v15, v1h, v4h, align = compute_htf_alignment(df5, ts, "long")
    # None of the resampled bars precede ts -> all NaN
    assert all(np.isnan(v) for v in [v15, v1h, v4h, align])


def test_alignment_range_bounded():
    """Alignment is in [-3, +3] for valid data."""
    df5 = _trend_df(n=600, slope=1.0)
    ts = df5.index[-1]
    for direction in ("long", "short"):
        _, _, _, align = compute_htf_alignment(df5, ts, direction)
        assert -3.0 <= align <= 3.0


def test_direction_symmetry():
    """long+short alignments must sum to 0 for any trend (they are exact mirrors)."""
    df5 = _trend_df(n=600, slope=1.0)
    ts = df5.index[-1]
    _, _, _, a_long = compute_htf_alignment(df5, ts, "long")
    _, _, _, a_short = compute_htf_alignment(df5, ts, "short")
    assert a_long + a_short == 0.0


def test_returns_four_values():
    """Function always returns a 4-tuple."""
    df5 = _trend_df(n=60, slope=1.0)
    ts = df5.index[-1]
    result = compute_htf_alignment(df5, ts, "long")
    assert len(result) == 4


# ── gate wiring test ──────────────────────────────────────────────────────────

def test_htf_skip_disabled_by_default():
    """HTF_SKIP_ENABLED must be False in config_defaults (shadow-only; never arm without operator gate)."""
    import config_defaults as CD
    assert getattr(CD, "HTF_SKIP_ENABLED", None) is False, (
        "HTF_SKIP_ENABLED must default to False — do not arm without paper-forward gate + operator approval")


def test_htf_skip_gate_blocks_when_enabled(monkeypatch):
    """When HTF_SKIP_ENABLED=True, on_decision must block A entries with alignment <= -2."""
    import config_defaults as CD
    monkeypatch.setattr(CD, "HTF_SKIP_ENABLED", True)

    from unittest.mock import MagicMock, patch
    from store import Store
    from journal import Journal

    store = Store(":memory:")
    j = Journal()
    sender = MagicMock()
    sender.incident_blocked.return_value = False

    from auto_live import LiveAuto
    auto = LiveAuto("TEST-ACCT", "Apex-50K-eval", "paper", store, j, sender, 550)
    # Override killed() to pass all kill-switch checks
    auto.killed = lambda: None
    auto.entry_gate = None
    auto.d1c_mode = "OFF"

    # Wire buf_fn to return a downtrend (align = -3 for long direction)
    df5 = _trend_df(n=600, slope=-1.0)
    auto.buf_fn = lambda: df5

    ts = df5.index[-1]
    sig = {
        "side": "long",
        "entry": 20000.0,
        "stop": 19980.0,
        "target": 20040.0,
        "ts_signal": int(ts.timestamp()),
        "liq": "sweep-OTE",
    }

    blocked_before = auto.blocked
    auto.on_decision(sig, True, "ok", ts)
    # With HTF_SKIP_ENABLED=True and a downtrend + long direction -> align=-3 <= -2 -> blocked
    assert auto.blocked == blocked_before + 1


def test_htf_skip_gate_passes_when_alignment_above_minus2(monkeypatch):
    """When alignment > -2, the HTF gate must NOT block (even with HTF_SKIP_ENABLED=True)."""
    import config_defaults as CD
    monkeypatch.setattr(CD, "HTF_SKIP_ENABLED", True)

    from unittest.mock import MagicMock
    from store import Store
    from journal import Journal

    store = Store(":memory:")
    j = Journal()
    sender = MagicMock()
    sender.incident_blocked.return_value = False
    sender.send_exit3.return_value = {"ok": True, "reason": "paper"}
    sender.send.return_value = {"sent": True, "reason": "paper"}

    from auto_live import LiveAuto
    auto = LiveAuto("TEST-ACCT", "Apex-50K-eval", "paper", store, j, sender, 550)
    auto.killed = lambda: None
    auto.entry_gate = None
    auto.d1c_mode = "OFF"

    # Uptrend + long -> align=+3 (well above -2 threshold) -> NOT blocked
    df5 = _trend_df(n=600, slope=1.0)
    auto.buf_fn = lambda: df5

    ts = df5.index[-1]
    sig = {
        "side": "long",
        "entry": 20000.0,
        "stop": 19980.0,
        "target": 20040.0,
        "ts_signal": int(ts.timestamp()),
        "liq": "sweep-OTE",
    }

    blocked_before = auto.blocked
    sent_before = auto.sent
    auto.on_decision(sig, True, "ok", ts)
    # Should NOT be blocked by HTF gate (alignment=+3 > -2)
    assert auto.blocked == blocked_before, "HTF gate should not block alignment=+3"
    # Should have been sent (or at least not htf-blocked)
    assert auto.sent == sent_before + 1 or auto.blocked == blocked_before


# ── parity test (requires real data; skips on clean install) ─────────────────

def _have_parity_prereqs():
    if not os.path.isdir(os.path.expanduser("~/trading-team/backtests/ict-nq-framework")):
        return False
    try:
        import run_d1c_real  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _have_parity_prereqs(),
                    reason="dev-only parity (needs research data + Databento pipeline)")
def test_htf_parity_vs_research():
    """htf_alignment must reproduce tools_a_v2_score.build() slope signs 0 mismatches.

    Strategy: compute raw (unsigned) slope signs from the same df5 using both:
      (a) compute_htf_alignment with direction="long" (d=+1 -> output == raw slope sign), and
      (b) the research resampling code path directly.
    Assert they match at a representative set of timestamps.
    """
    import apex_eval_eod_databento as DB

    df5 = DB.load_databento_5m()

    # Research code path (copy from tools_a_v2_score.build())
    def _ref_slope(freq):
        c = df5["Close"].resample(freq).last().dropna()
        return np.sign(c.ewm(span=20).mean().diff())

    s15_ref = _ref_slope("15min")
    s1h_ref = _ref_slope("1h")
    s4h_ref = _ref_slope("4h")

    def _ref_lookup(series, ts):
        i = series.index.searchsorted(ts, "right") - 1
        return float(series.iloc[i]) if i >= 0 else float("nan")

    # Sample 50 evenly-spaced timestamps from RTH bars
    rth = df5.between_time("09:30", "16:00")
    step = max(1, len(rth) // 50)
    test_ts = rth.index[::step][:50]

    mismatches = 0
    for ts in test_ts:
        v15, v1h, v4h, _ = compute_htf_alignment(df5, ts, "long")
        r15 = _ref_lookup(s15_ref, ts)
        r1h = _ref_lookup(s1h_ref, ts)
        r4h = _ref_lookup(s4h_ref, ts)
        for name, live, ref in [("htf15", v15, r15), ("htf1h", v1h, r1h), ("htf4h", v4h, r4h)]:
            if not (np.isnan(live) and np.isnan(ref)):
                if live != ref:
                    mismatches += 1
                    print(f"  MISMATCH {name} ts={ts}: live={live} ref={ref}")

    assert mismatches == 0, f"HTF parity: {mismatches} mismatches (expected 0)"
