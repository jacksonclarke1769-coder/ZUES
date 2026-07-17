"""WP-E baseline-feature-set B (PREREG_PHASE3.md v1.0 §2) + outcome arithmetic
(§2 "Outcomes"), computed independently of the engines over the bar array itself
(numpy, causal single forward pass -- never peeks ahead). B is "the ICT-free
control, fixed": time-of-day slot (30-min bucket), day-of-week, ATR20 percentile
(vs trailing 60 sessions), sigma_TOD-relative realized vol of last 12 bars, signed
12-bar return in ATR units, overnight gap in ATR units. "Nothing else enters B."

Documented operational choices (none in PREREG's own prose, each a straightforward,
conservative reading -- flagged here the same way WP-B/C/D flag their own
interpretive calls):

  * ATR20: the SAME causal, current-bar-inclusive convention every WP-B/C engine
    already uses (`engines/_util.py::ATR`, mirrors the oracle's own
    `atr_arr = rolling(14/20).mean()` non-shifted convention) -- reused verbatim, not
    reimplemented, so Phase-3's ATR normalization is bit-for-bit consistent with the
    certified engines' own ATR-based math (e.g. `displacement.py`'s `range_vs_atr`).
  * "ATR20 percentile vs trailing 60 sessions": percentile rank of ATR20(t0) within
    the distribution of EOD ATR20 snapshots (the ATR20 value at each trade_date's
    LAST seen bar) over the trailing <=60 COMPLETED trade_dates strictly before
    today's (still in-progress) session -- never includes today's own EOD value.
  * "sigma_TOD-relative realized vol of last 12 bars": realized_vol_12 (population
    std of the 12 bar-to-bar close differences ending at t0, inclusive) divided by
    sigma_TOD(t0) -- REUSED verbatim from `engines/displacement.py`'s own emitted
    `DISPLACEMENT_COMPONENTS`/`DISPLACEMENT_WARMUP` events (median |body| for this
    bar's time-of-day slot over the trailing 20 occurrences), not reimplemented, so
    the TOD-normalization matches the certified engine's own sigma_TOD exactly.
    `None` while sigma_TOD is in warmup (recorded as a null, never fabricated, same
    convention `displacement.py` itself uses).
  * "signed 12-bar return in ATR units": (close(t0) - close(t0-12 bars)) / ATR20(t0).
  * "overnight gap in ATR units": the MOST RECENTLY COMPLETED overnight gap known as
    of t0 -- (RTH 09:30 open of the current/most-recent trading day) minus (the
    immediately preceding trading day's final RTH print, i.e. the last bar seen
    while `session=="ny_pm"`), divided by ATR20(t0). Held constant (carried forward)
    from the instant the 09:30 bar is processed until the next trade_date's own
    09:30 bar -- so asia/london/overnight bars before a trade_date's own RTH open
    correctly see YESTERDAY's gap (today's hasn't formed yet), never a forward peek.

All four B components are asserted knowable (`confirmed_at <= t0`) BY CONSTRUCTION:
every value at bar index i is computed from bars[0..i] only, in a single forward
Python loop that never reads bars[j] for j > i.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..core.clock import NY as CLOCK_NY
from ..core.clock import SessionEngine
from ..engines._util import ATR
from ..parity.model01_canary import _Bar

EOD_ATR_TRAILING_SESSIONS = 60
RET_LOOKBACK_BARS = 12
REALIZED_VOL_LOOKBACK_BARS = 12


@dataclass
class BarArrays:
    n: int
    close_time: List[datetime]
    open_: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    atr20: np.ndarray  # inclusive-of-current-bar convention (engines/_util.py::ATR)
    session: List[str]
    trade_date: List
    tod_slot_30: List[str]
    day_of_week: np.ndarray
    ret_12bar_atr: np.ndarray
    realized_vol_12: np.ndarray
    overnight_gap_atr: np.ndarray
    atr20_percentile_60sess: np.ndarray
    index_by_close_time: Dict[datetime, int]


def _tod_slot_30(ts_ny: datetime) -> str:
    floored_minute = 0 if ts_ny.minute < 30 else 30
    return f"{ts_ny.hour:02d}:{floored_minute:02d}"


def build_bar_arrays(bars: List[_Bar]) -> BarArrays:
    n = len(bars)
    close_time = [b.close_time for b in bars]
    open_ = np.array([b.open for b in bars], dtype=float)
    high = np.array([b.high for b in bars], dtype=float)
    low = np.array([b.low for b in bars], dtype=float)
    close = np.array([b.close for b in bars], dtype=float)
    volume = np.array([b.volume for b in bars], dtype=float)

    atr20 = np.full(n, np.nan)
    session = [""] * n
    trade_date: List = [None] * n
    tod_slot_30 = [""] * n
    day_of_week = np.full(n, -1, dtype=int)
    ret_12bar_atr = np.full(n, np.nan)
    realized_vol_12 = np.full(n, np.nan)
    overnight_gap_atr = np.full(n, np.nan)
    atr20_percentile_60sess = np.full(n, np.nan)
    index_by_close_time: Dict[datetime, int] = {}

    sessions = SessionEngine()
    atr_calc = ATR(20)

    # -- overnight-gap tracking (causal, single forward pass) --------------------
    last_rth_close_price: Optional[float] = None  # last bar seen while session=="ny_pm"
    gap_pts_current: Optional[float] = None  # most recently KNOWN overnight gap, points
    gap_updated_dates: set = set()

    # -- EOD-ATR trailing-60-session percentile tracking --------------------------
    eod_atr_history: List[float] = []  # trailing <=60 COMPLETED trade_dates' EOD ATR20
    cur_td = None
    last_atr20_for_cur_td: Optional[float] = None

    for i, b in enumerate(bars):
        index_by_close_time[b.close_time] = i
        ny_ts = b.close_time.astimezone(CLOCK_NY)
        td = sessions.trade_date(b.close_time)
        label = sessions.session(b.close_time)
        session[i] = label
        trade_date[i] = td
        tod_slot_30[i] = _tod_slot_30(ny_ts)
        day_of_week[i] = ny_ts.weekday()

        a = atr_calc.update(b.high, b.low, b.close)
        atr20[i] = a if a is not None else np.nan

        if i >= RET_LOOKBACK_BARS:
            prior_close = close[i - RET_LOOKBACK_BARS]
            if a not in (None, 0):
                ret_12bar_atr[i] = (b.close - prior_close) / a

        if i >= REALIZED_VOL_LOOKBACK_BARS:
            window_closes = close[i - REALIZED_VOL_LOOKBACK_BARS : i + 1]
            diffs = np.diff(window_closes)
            realized_vol_12[i] = float(np.std(diffs))

        # -- trade_date transition: finalize the OUTGOING date's EOD ATR into history
        if cur_td is None:
            cur_td = td
        elif td != cur_td:
            if last_atr20_for_cur_td is not None:
                eod_atr_history.append(last_atr20_for_cur_td)
                if len(eod_atr_history) > EOD_ATR_TRAILING_SESSIONS:
                    eod_atr_history.pop(0)
            cur_td = td
            last_atr20_for_cur_td = None
        if a is not None:
            last_atr20_for_cur_td = a

        # percentile of THIS bar's atr20 within the trailing <=60 COMPLETED sessions
        # (never includes today's own still-in-progress EOD snapshot)
        if a is not None and len(eod_atr_history) > 0:
            le = sum(1 for v in eod_atr_history if v <= a)
            atr20_percentile_60sess[i] = 100.0 * le / len(eod_atr_history)

        # -- overnight gap: update the instant we cross into a NEW date's ny_am ------
        if label == "ny_am" and td not in gap_updated_dates:
            gap_updated_dates.add(td)
            if last_rth_close_price is not None:
                gap_pts_current = b.open - last_rth_close_price
        if label == "ny_pm":
            last_rth_close_price = b.close
        if gap_pts_current is not None and a not in (None, 0):
            overnight_gap_atr[i] = gap_pts_current / a

    return BarArrays(
        n=n,
        close_time=close_time,
        open_=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        atr20=atr20,
        session=session,
        trade_date=trade_date,
        tod_slot_30=tod_slot_30,
        day_of_week=day_of_week,
        ret_12bar_atr=ret_12bar_atr,
        realized_vol_12=realized_vol_12,
        overnight_gap_atr=overnight_gap_atr,
        atr20_percentile_60sess=atr20_percentile_60sess,
        index_by_close_time=index_by_close_time,
    )


# --- outcomes (PREREG §2) -----------------------------------------------------------

OUTCOME_HORIZONS: Tuple[int, ...] = (12, 24, 48)


def raw_outcomes_at(arrays: BarArrays, i0: int, horizons: Tuple[int, ...] = OUTCOME_HORIZONS) -> Dict[str, float]:
    """Raw (unadjusted, signed) forward-path measures from bar index i0, in ATR20(t0)
    units. `fwd_raw_h` = signed close-to-close return; `maxfav_raw_h` = best-case
    (upside) excursion; `maxadv_raw_h` = worst-case (downside) excursion magnitude
    (positive number). NaN if the horizon runs past the end of the data (no lookahead
    substitute is ever fabricated)."""
    out: Dict[str, float] = {}
    atr0 = arrays.atr20[i0]
    c0 = arrays.close[i0]
    for h in horizons:
        j = i0 + h
        if atr0 is None or np.isnan(atr0) or atr0 == 0 or j >= arrays.n:
            out[f"fwd_raw_{h}"] = np.nan
            out[f"maxfav_raw_{h}"] = np.nan
            out[f"maxadv_raw_{h}"] = np.nan
            continue
        out[f"fwd_raw_{h}"] = (arrays.close[j] - c0) / atr0
        window_high = arrays.high[i0 + 1 : j + 1]
        window_low = arrays.low[i0 + 1 : j + 1]
        out[f"maxfav_raw_{h}"] = (float(np.max(window_high)) - c0) / atr0
        out[f"maxadv_raw_{h}"] = (c0 - float(np.min(window_low))) / atr0
    return out


def direction_adjust(raw: Dict[str, float], direction: Optional[str], horizons: Tuple[int, ...] = OUTCOME_HORIZONS) -> Dict[str, float]:
    """Direction-adjusted outcome columns (PREREG §2: "direction-adjusted where the
    event has a direction"). `direction` in {"up","down",None}. NaN where direction
    is None (the raw columns remain the source of truth for those events)."""
    sign = 1.0 if direction == "up" else (-1.0 if direction == "down" else None)
    out: Dict[str, float] = {}
    for h in horizons:
        fr = raw.get(f"fwd_raw_{h}", np.nan)
        mf = raw.get(f"maxfav_raw_{h}", np.nan)
        ma = raw.get(f"maxadv_raw_{h}", np.nan)
        if sign is None:
            out[f"fwd_{h}"] = np.nan
            out[f"maxcont_{h}"] = np.nan
            out[f"maxrev_{h}"] = np.nan
        else:
            out[f"fwd_{h}"] = fr * sign
            out[f"maxcont_{h}"] = mf if sign == 1.0 else ma
            out[f"maxrev_{h}"] = ma if sign == 1.0 else mf
    fwd24 = out.get("fwd_24", np.nan)
    out["rev24"] = (1 if fwd24 < 0 else 0) if not (isinstance(fwd24, float) and np.isnan(fwd24)) else np.nan
    out["direction"] = direction
    return out


def rolling_forward_max(a: np.ndarray, h: int) -> np.ndarray:
    """`out[i] = max(a[i+1 .. i+h])` (the h bars strictly after i), NaN where the full
    forward window runs past the end. Vectorized via `sliding_window_view` -- computed
    ONCE over the whole bar array, then indexed at event positions (replaces the
    per-event `np.max(high[i0+1:i0+h+1])` slice that dominated the slow path)."""
    from numpy.lib.stride_tricks import sliding_window_view

    n = len(a)
    out = np.full(n, np.nan)
    if n >= h:
        swv = sliding_window_view(a, h)  # shape (n-h+1, h); swv[k] = a[k .. k+h-1]
        wmax = swv.max(axis=1)  # wmax[k] = max(a[k .. k+h-1])
        if n - h > 0:
            valid_i = np.arange(0, n - h)  # i in [0, n-h-1] -> window [i+1, i+h] = swv[i+1]
            out[valid_i] = wmax[valid_i + 1]
    return out


def rolling_forward_min(a: np.ndarray, h: int) -> np.ndarray:
    """Mirror of `rolling_forward_max` for the minimum."""
    from numpy.lib.stride_tricks import sliding_window_view

    n = len(a)
    out = np.full(n, np.nan)
    if n >= h:
        swv = sliding_window_view(a, h)
        wmin = swv.min(axis=1)
        if n - h > 0:
            valid_i = np.arange(0, n - h)
            out[valid_i] = wmin[valid_i + 1]
    return out


@dataclass
class OutcomeArrays:
    """Full-bar-length (indexed by bar position i0) vectorized raw outcomes, in
    ATR20(t0) units. Bit-for-bit identical to `raw_outcomes_at` (the slow per-event
    reference) -- proven by the conformance check in `extract.py` before any real
    extraction runs. Knowability preserved BY CONSTRUCTION: `fwd_raw[h][i]` reads
    close[i+h]/high/low STRICTLY AFTER i0 (these are OUTCOMES, computed from the
    future relative to t0 on purpose, exactly as the prereg §2 outcome definitions
    require) -- they are never fed back as a FEATURE; features only ever read bars
    <= t0."""

    horizons: Tuple[int, ...]
    fwd_raw: Dict[int, np.ndarray]
    maxfav_raw: Dict[int, np.ndarray]
    maxadv_raw: Dict[int, np.ndarray]


def build_outcome_arrays(arrays: BarArrays, horizons: Tuple[int, ...] = OUTCOME_HORIZONS) -> OutcomeArrays:
    n = arrays.n
    close = arrays.close
    high = arrays.high
    low = arrays.low
    atr = arrays.atr20
    idx = np.arange(n)
    fwd_raw: Dict[int, np.ndarray] = {}
    maxfav_raw: Dict[int, np.ndarray] = {}
    maxadv_raw: Dict[int, np.ndarray] = {}
    atr_ok = np.isfinite(atr) & (atr != 0)
    for h in horizons:
        j = idx + h
        valid = (j < n) & atr_ok
        fwd = np.full(n, np.nan)
        mfav = np.full(n, np.nan)
        madv = np.full(n, np.nan)
        vi = idx[valid]
        jj = vi + h
        fwd[vi] = (close[jj] - close[vi]) / atr[vi]
        fmax = rolling_forward_max(high, h)
        fmin = rolling_forward_min(low, h)
        mfav[vi] = (fmax[vi] - close[vi]) / atr[vi]
        madv[vi] = (close[vi] - fmin[vi]) / atr[vi]
        fwd_raw[h] = fwd
        maxfav_raw[h] = mfav
        maxadv_raw[h] = madv
    return OutcomeArrays(horizons=tuple(horizons), fwd_raw=fwd_raw, maxfav_raw=maxfav_raw, maxadv_raw=maxadv_raw)


def efficiency_trailing_12(arrays: BarArrays, i0: int) -> float:
    """|net move| / sum(|bar moves|) over the trailing 12 bars ENDING at t0 (PREREG
    §3 F5). NaN if fewer than 12 prior bars exist. SLOW per-event reference (kept for
    the conformance check); the real run uses `build_efficiency_array`."""
    if i0 < 12:
        return np.nan
    window_closes = arrays.close[i0 - 12 : i0 + 1]
    diffs = np.diff(window_closes)
    denom = float(np.sum(np.abs(diffs)))
    if denom == 0:
        return np.nan
    net = float(window_closes[-1] - window_closes[0])
    return abs(net) / denom


def build_efficiency_array(arrays: BarArrays) -> np.ndarray:
    """Vectorized full-bar-length trailing-12 efficiency (feature, bars <= t0 only).
    Bit-for-bit identical to `efficiency_trailing_12` -- proven by the conformance
    check. `eff[i] = |close[i]-close[i-12]| / sum_{m=i-11..i} |close[m]-close[m-1]|`,
    NaN for i<12 or a zero denominator."""
    n = arrays.n
    close = arrays.close
    out = np.full(n, np.nan)
    if n < 13:
        return out
    d = np.zeros(n)
    d[1:] = np.abs(np.diff(close))  # d[m] = |close[m]-close[m-1]|
    cs = np.cumsum(d)
    i = np.arange(12, n)
    denom = cs[i] - cs[i - 12]  # sum over m = i-11..i (12 terms)
    net = np.abs(close[i] - close[i - 12])
    with np.errstate(divide="ignore", invalid="ignore"):
        eff = np.where(denom > 0, net / denom, np.nan)
    out[i] = eff
    return out
