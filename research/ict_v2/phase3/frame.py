"""WP-E data step (PREREG_PHASE3.md Amendment v1.1): builds the 5m NQ frame from the
roll-adjusted parquet using the IDENTICAL resample recipe the certified WP-D dataset
used -- `apex_eval_eod_databento.py::load_databento_5m()` composed with
`run_d1c_real.py::load_1m()` (both read-only production modules, reproduced here
verbatim rather than imported, since they hardcode the UNADJUSTED path):

    1m parquet -> tz-convert to America/New_York, sort, dedupe (keep="first")
    -> 5min resample, label="left", closed="left", OHLCV agg (first/max/min/last/sum)
    -> dropna(subset=["Open"]) -> tz-normalize -> dedupe (keep="last"), sort.

Same date range, same IS/holdout boundaries as v1.0 (Amendment v1.1 changes only the
source parquet's prices via roll-adjustment, never bar count/timestamps -- asserted
below).
"""
from __future__ import annotations

import os
from typing import List

import pandas as pd

from ..parity.model01_canary import _Bar, bars_from_df5  # reuse verbatim, read-only

NY = "America/New_York"

ROLLADJ_PARQUET = os.path.expanduser(
    "~/trading-team/data/real_futures/NQ_databento_1m_5y_rolladj.parquet"
)

# The certified WP-D (unadjusted) frame's bar count (PREREG_PHASE3.md v1.0 §1:
# "certified NQ 5m frame ... 353,952 bars"). Amendment v1.1 only back-adjusts prices
# at 16 quarterly roll gaps -- it must NOT add or drop a single bar.
EXPECTED_BAR_COUNT = 353_952


def load_rolladj_1m() -> pd.DataFrame:
    """Mirrors `run_d1c_real.py::load_1m()` exactly, sourced from the roll-adjusted
    1m parquet instead of the unadjusted one."""
    d1 = pd.read_parquet(ROLLADJ_PARQUET)
    d1.index = d1.index.tz_convert(NY) if d1.index.tz else d1.index.tz_localize("UTC").tz_convert(NY)
    return d1.sort_index()[~d1.index.duplicated(keep="first")]


def load_rolladj_5m() -> pd.DataFrame:
    """Mirrors `apex_eval_eod_databento.py::load_databento_5m()` exactly (5min
    resample, label="left", closed="left"; OHLCV first/max/min/last/sum; dropna on
    Open; tz-normalize; dedupe keep="last"; sort), sourced from the roll-adjusted 1m
    frame."""
    d1 = load_rolladj_1m()
    ag = lambda c, h: getattr(d1[c].resample("5min", label="left", closed="left"), h)()
    df5 = pd.DataFrame(
        {
            "Open": ag("open", "first"),
            "High": ag("high", "max"),
            "Low": ag("low", "min"),
            "Close": ag("close", "last"),
            "Volume": ag("volume", "sum"),
        }
    ).dropna(subset=["Open"])
    idx = df5.index
    df5.index = idx.tz_localize(NY) if idx.tz is None else idx.tz_convert(NY)
    df5 = df5[~df5.index.duplicated(keep="last")].sort_index()
    df5.index.name = None
    return df5


def verify_against_unadjusted() -> dict:
    """Dynamically loads the certified UNADJUSTED WP-D frame (read-only,
    `apex_eval_eod_databento.py::load_databento_5m()`, same repo-root module
    `parity/model01_canary.py::load_certified_5m()` already imports) and compares it
    against the roll-adjusted frame this module builds: same bar count, IDENTICAL
    timestamp index (the adjustment must only shift prices), DIFFERENT prices
    (confirms the roll-adjustment actually changed something, i.e. we didn't
    silently load the same file twice)."""
    from ..parity.model01_canary import load_certified_5m  # read-only reuse

    unadjusted = load_certified_5m()
    adjusted = load_rolladj_5m()
    index_equal = bool((unadjusted.index == adjusted.index).all()) if len(unadjusted) == len(adjusted) else False
    prices_differ = not unadjusted["Close"].equals(adjusted["Close"])
    return {
        "unadjusted_bar_count": int(len(unadjusted)),
        "rolladj_bar_count": int(len(adjusted)),
        "bar_counts_exactly_equal": len(unadjusted) == len(adjusted),
        "timestamp_index_identical": index_equal,
        "closes_differ_as_expected": prices_differ,
        "unadjusted_range": f"{unadjusted.index.min()} -> {unadjusted.index.max()}",
        "rolladj_range": f"{adjusted.index.min()} -> {adjusted.index.max()}",
    }


def build_bars() -> List[_Bar]:
    """Loads the roll-adjusted 5m frame and asserts its bar count exactly matches the
    certified unadjusted WP-D frame (PREREG Amendment v1.1: "the adjustment only
    shifts prices" -- same date range, same bar count). Returns `_Bar` objects via
    the SAME `bars_from_df5` convention `parity/model01_canary.py` uses (close_time =
    the bar's own open-time-labelled index value)."""
    df5 = load_rolladj_5m()
    n = len(df5)
    if n != EXPECTED_BAR_COUNT:
        raise AssertionError(
            f"roll-adjusted 5m frame bar count ({n:,}) != certified unadjusted frame "
            f"count ({EXPECTED_BAR_COUNT:,}) -- Amendment v1.1 states the adjustment "
            "only shifts prices; a count mismatch means the roll-adjusted parquet has "
            "a different bar inventory and must be investigated before any extraction."
        )
    bars = bars_from_df5(df5)
    # PERFORMANCE (byte-identical, verified): feed `close_time` as a plain tz-aware
    # python `datetime` rather than a `pandas.Timestamp`. The certified engines only
    # require close_time to be a tz-aware datetime (SPEC.md core/runner.py); every
    # downstream engine timestamp (origin/observed/confirmed/actionable, expires_at,
    # active_from) is then plain-datetime arithmetic, so the per-bar level/zone-scan
    # comparisons that dominate a 5y run are datetime-vs-datetime instead of the far
    # slower pandas-Timestamp scalar compares. Event streams are IDENTICAL: whole-
    # minute 5m timestamps have zero sub-second component, so `compute_event_id`'s
    # `origin_time.astimezone(utc).isoformat()` is character-for-character the same
    # (verified: all 5 engines' full event-id hashes match Timestamp-bar output over a
    # 25k-bar slice; see the WP-E summary).
    return [
        _Bar(b.close_time.to_pydatetime(), b.open, b.high, b.low, b.close, b.volume)
        for b in bars
    ]
