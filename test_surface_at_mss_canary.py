"""SURFACE-AT-MSS emission-mode canary (reports/fork_a/03_build_report.md).

Scope: signal DELIVERY only, for EMISSION_MODE_SURFACE_AT_MSS. Guarantees (permanent regression):
  * default / certified_gate path NEVER routes through the surface path and never imports it;
  * surface_at_mss mode emits the resting-limit entry/stop/target for a setup whose MSS confirmed
    on the most-recent bar, derives the emit instant ONLY from feats.index[-1], dedups via acted_ts,
    and returns None when there is no fresh MSS-confirmed setup.
detection math is not exercised here (surface_at_mss delegates it to the frozen model01._detect;
the real-data causal canary + 581 parity live in research/fork_a/build_surface_mss_verify.py).
"""
import pandas as pd
import pytest

import strategy_engine_profileA as SEP
from strategy_engine_profileA import (
    ProfileAEngine,
    EMISSION_MODE_CERTIFIED_GATE,
    EMISSION_MODE_SURFACE_AT_MSS,
)

NY = SEP.NY
STRAT = {"nyam_start_min": 570, "nyam_end_min": 690, "flat_min": 870}


def _engine(mode, last_ts="2024-06-03 10:00", buf_len=2500):
    eng = ProfileAEngine(STRAT, emission_mode=mode)
    recent = pd.Timestamp(last_ts, tz=NY)
    eng.buf = pd.DataFrame(
        {"Open": 0.0, "High": 0.0, "Low": 0.0, "Close": 0.0, "Volume": 0.0},
        index=pd.date_range(end=recent, periods=buf_len, freq="5min", tz=NY),
    )
    feats = pd.DataFrame(index=eng.buf.index.copy())   # last row = ny_am 10:00 ET
    feats.index.name = "timestamp"
    eng._features = lambda: feats
    return eng, feats


_EMIS = dict(direction="long", entry=100.0, stop=99.0, target=102.0, rr=2.0,
             liq_swept="pdl", sweep_bar=2498, mss_bar=2499, session="ny_am")


@pytest.fixture(autouse=True)
def _restore():
    import surface_at_mss as SM
    orig = SM.latest_mss_emission
    yield
    SM.latest_mss_emission = orig


def test_default_mode_never_calls_surface():
    """certified_gate (default) must not route to the surface path even if surface would emit."""
    import surface_at_mss as SM
    SM.latest_mss_emission = lambda *a, **k: (_ for _ in ()).throw(AssertionError("surface called on default path"))
    eng, _ = _engine(EMISSION_MODE_CERTIFIED_GATE)
    # default path uses model01.run(); with a warmup-sized zero buffer it simply returns None,
    # and must NEVER have touched surface_at_mss.
    assert eng.latest_signal() is None


def test_surface_mode_emits_at_mss_bar():
    import surface_at_mss as SM
    SM.latest_mss_emission = lambda feats, params: dict(_EMIS)
    eng, feats = _engine(EMISSION_MODE_SURFACE_AT_MSS)
    sig = eng.latest_signal()
    assert sig is not None
    assert sig["side"] == "long" and sig["entry"] == 100.0 and sig["stop"] == 99.0 and sig["target"] == 102.0
    assert sig["emission_mode"] == EMISSION_MODE_SURFACE_AT_MSS
    # emit instant derived ONLY from the last (MSS) bar
    assert sig["ts_signal"] == feats.index[-1].isoformat()


def test_surface_mode_dedupes():
    import surface_at_mss as SM
    SM.latest_mss_emission = lambda feats, params: dict(_EMIS)
    eng, _ = _engine(EMISSION_MODE_SURFACE_AT_MSS)
    assert eng.latest_signal() is not None
    assert eng.latest_signal() is None          # same MSS bar already acted


def test_surface_mode_none_when_no_setup():
    import surface_at_mss as SM
    SM.latest_mss_emission = lambda feats, params: None
    eng, _ = _engine(EMISSION_MODE_SURFACE_AT_MSS)
    assert eng.latest_signal() is None


def test_surface_mode_warmup_guard():
    import surface_at_mss as SM
    SM.latest_mss_emission = lambda feats, params: dict(_EMIS)
    eng, _ = _engine(EMISSION_MODE_SURFACE_AT_MSS, buf_len=100)   # < 2000 warmup
    assert eng.latest_signal() is None


def test_surface_mode_detection_error_fails_closed():
    import surface_at_mss as SM
    SM.latest_mss_emission = lambda feats, params: (_ for _ in ()).throw(RuntimeError("boom"))
    eng, _ = _engine(EMISSION_MODE_SURFACE_AT_MSS)
    assert eng.latest_signal() is None          # detection error -> no signal, no crash
