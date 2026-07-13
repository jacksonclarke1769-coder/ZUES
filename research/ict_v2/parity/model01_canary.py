"""WP-D parity canary (SPEC.md "Parity canary"): the dual-implementation gate.

Reproduces the certified Profile-A 581-signal set (sweep_bar, mss_bar, direction,
entry, stop, target) through an INDEPENDENT V2-composed pipeline and compares it,
signal-for-signal, against the frozen oracle (`model01_sweep_mss_fvg.py`, run over
the same certified dataset via the framework's own loaders).

READ-ONLY imports only, never edited, never monkeypatched:
  * `~/trading-team/backtests/ict-nq-framework/models/model01_sweep_mss_fvg.py` (M1) --
    frozen oracle `_detect`/`run`.
  * `~/trading-team/backtests/ict-nq-framework/engine/primitives.py` (P) -- used ONLY
    by the oracle-regeneration side and by the (separate, offline) validation notes in
    this docstring; the V2 side never imports it.
  * `~/trading-team/backtests/ict-nq-framework/run_d1c_real.py` (RD) -- 1m loader +
    `attach_drift` (the D1c live-executability gate).
  * bot-repo-root production modules (`apex_eval_eod_databento.py`,
    `strategy_engine_profileA.py`, `config.py`, `tools_1m_truth_recert.py`) -- the SAME
    certified data loaders + params the 581-signal reference artifact was built from.
  * `reports/inc_20260707_recert/emission_replay_raw_full.csv` -- the FROZEN
    emission-replay artifact (a ~3.1h live-poll replay; per PAE-001's own documented
    precedent it is READ, never re-run, here).

WHAT "581 CERTIFIED SIGNALS" MEANS (verified by regenerating it from scratch, not by
trusting the static CSV): `model01.run()` over the full certified 5m dataset with
`A_PARAMS["exit3"]` params produces 2,359 raw candidate trades; filtered to
`session(mss_bar) == "ny_am"` -> 705; filtered to the D1c live-executability gate
(`attach_drift`, real 1m drift-direction agreement at fill) -> 583; joined against the
frozen emission-replay artifact and 5-way classified (PAE-001's `classify_signals.py`
logic, reproduced here) -> 394 FULLY-AVAILABLE + 187 DELAYED + 1 UNREACHABLE + 1
POST-ENTRY-DEPENDENT. The target population is FULLY-AVAILABLE + DELAYED = 581 (matches
`reports/fork_a/04_causal_anchor_parity_summary.json`'s `n=581` and
`research/atlas/profile_a_edge/outputs/signals_583_classified.csv` exactly).

SCOPE BOUNDARY (flagged for Fable's review, non-blocking): the ny_am-session filter,
the D1c drift gate, and the emission-replay classification are LIVE-EXECUTABILITY
selection layers, not "signal DETECTION" (SPEC.md's V2-composition list names only
levels/sweep/MSS/displacement/OTE). They are deterministic functions of
(direction, fill instant) and externally-frozen artifacts (real 1m data; the
emission-replay CSV) -- applying the IDENTICAL functions to both the oracle's raw
candidate list and the V2 pipeline's raw candidate list is fair (neither side is
special-cased) and isolates the actual detection-math comparison to what SPEC asks
for. This module does NOT re-derive the emission-replay artifact (out of scope,
~3.1h, PAE-001's own precedent) or re-verify the D1c drift-gate's own correctness
(already validated in `run_d1c_real.py`'s own report).

V2 COMPOSITION -- which building blocks are reused vs. which are hand-composed here,
and why (every "why" is a documented divergence-bridge SPEC.md pre-authorizes):

  * Swings (5m 3/3, opposing-swing lookup for MSS; 1h 2/2, for the h1_sh/h1_sl level
    tier): `engines/swings.py::SwingMethodA`, REUSED UNMODIFIED, parameterized
    left=right=3 (5m) and left=right=2 (1h, fed 1h-resampled bars -- HTF swings are not
    a Phase-2 engine SPEC.md itemizes; composing SwingMethodA over a different bar
    aggregation is not an edit to `swings.py`). Verified bit-for-bit against
    `primitives.py::last_known_swings` on the FULL real certified dataset (0/353,952
    bar mismatches, both timeframes) via `selfcheck_building_blocks_against_production`,
    called by `run_full_parity` and recorded in the summary JSON's
    `building_block_selfcheck_mismatches`.
  * Displacement qualification (`disp != 0` in oracle's window scan):
    `engines/displacement.py::DisplacementEngine`'s `DISPLACEMENT_QUALIFIED` event,
    REUSED UNMODIFIED (`displacement_body_mult=1.5` is exactly oracle's
    `body_ratio >= 1.5` threshold; `RollingMean`'s shift-by-one convention is exactly
    `primitives.py::body_ratio`'s). Verified bit-for-bit (0/353,952 mismatches on the
    qualified-bar set + direction).
  * PDH/PDL/PWH/PWL/session-H-L (asia, london): hand-composed from
    `engines/_util.py::BucketHL` (the SAME shared primitive `engines/levels.py` and
    `engines/ranges.py` themselves use) + `core/clock.py::SessionEngine` (SAME
    session/trade-date logic `levels.py` uses). NOT via `engines/levels.py::
    LevelRegistry` directly: LevelRegistry's `active_from`-gate (one-bar visibility
    lag by design, appropriate for its own lifecycle-event semantics) and its
    unbounded-list `_active` scan (round numbers/equal-highs/OR/overnight kinds this
    canary doesn't need) are both real, but ORTHOGONAL, engineering choices that would
    either shift the sweep-window comparison by a bar or make a 353,952-bar /
    multi-year run computationally impractical for a single-purpose canary. Composing
    directly from `BucketHL`+`SessionEngine` avoids both without touching
    `levels.py`. Verified bit-for-bit against `strategy_engine_profileA.py`'s own
    production feature columns (0/353,952 mismatches on all 8 series).
  * Sweep detection / MSS window / OTE entry-stop-target arithmetic: HAND-COMPOSED
    in this module (`_detect_v2`), a direct line-for-line port of the oracle's own
    `model01_sweep_mss_fvg.py::_detect()` formulas, operating on the V2-built level/
    swing arrays above (NOT on model01's own feature columns). SPEC.md explicitly
    pre-flags this as a documented, expected divergence-bridge: `engines/sweeps.py`'s
    FSM is `>=`-vs-oracle's-strict-`>` on excursion-open AND (found during this
    build) can preempt a later in-window reclaim via its `consecutive_beyond>=2`
    ACCEPTED_BREAKOUT rule in a way the oracle's pure 3-bar trailing-window reclaim
    check never does (a real, structural FSM-semantics difference, not a param);
    `engines/structure.py`'s MSS is CHoCH-state-anchored, oracle's is
    sweep-bar-anchored (re-evaluates the CURRENT most-recent opposing swing fresh at
    every candidate sweep, independent of any BOS/CHoCH state machine). Neither
    module is edited; this parity layer is exactly SPEC.md's "compose around the
    divergence" instruction.
  * "No overlap" candidate-selection walk (oracle's `i = exit_i + 1` after a trade is
    registered, so the next scan resumes past the open position): a MECHANICAL,
    NEVER-STORED, NEVER-REPORTED bar-index walk (`_mechanical_exit_bar`) -- first bar
    where the FIXED stop or FIXED target is touched, or `MAX_HOLD` elapses, or a
    >`gap_min`-minute data gap is hit (PROFILE_A's exit3 params disable breakeven/
    partial-driven-stop-move/trail, so `cur_stop`/`cur_target` are fixed for the
    whole hold -- the walk needs no R/PF bookkeeping at all to reproduce which bar
    the position structurally closes on). This is NOT a performance statistic
    (SPEC.md's PF/WR/expectancy ban): no R, no win/loss tag, no PF-adjacent quantity
    is computed, stored, or reported anywhere -- `_mechanical_exit_bar` returns only
    an integer bar index used purely as the next scan cursor, exactly mirroring what
    the oracle's own `i = exit_i + 1` line does structurally. Flagged for Fable's
    review as a documented boundary judgment call (same class as WP-B/C's own flagged
    calls), non-blocking.

COMPARISON: per-signal exact match on (sweep_bar, mss_bar, direction, entry, stop,
target) to the cent, using the SAME rounding convention the oracle itself uses
(`round()` dispatched on a `numpy.float64` -- NOT `round(float(x), 2)`, which can
disagree with numpy's rounding at an exact binary-representation boundary; see
`_round_cent`). Discovered and fixed during this build: an early comparison harness
that called `float(x)` before rounding produced 44 spurious "mismatches" that were
purely this rounding-function discrepancy, not detection differences -- all 44
resolved to exact matches once compared with numpy's own rounding on both sides.

FULL RESULT (`--full`, real certified dataset, run once and recorded in
`reports/ict_v2/parity_canary_summary.json`): 581/581 exact match.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..core.clock import SessionEngine
from ..core.events import CausalEvent, EventStore
from ..engines._util import BucketHL, trade_week_key
from ..engines.displacement import DisplacementEngine
from ..engines.swings import SwingMethodA

BOT_REPO = os.path.expanduser("~/trading-team/bot/nq-liq-bot")
FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
_PATHS = (
    os.path.expanduser("~/trading-team/backtests"),
    FW,
    os.path.join(FW, "engine"),
    os.path.join(FW, "models"),
    BOT_REPO,
)


def _ensure_readonly_imports_on_path() -> None:
    """Adds the frozen framework + bot-repo-root read-only import paths. Only ever
    APPENDS to sys.path; never writes to any of those locations."""
    for p in _PATHS:
        if p not in sys.path:
            sys.path.insert(0, p)


# --- minimal local Bar (mirrors tests/helpers.py::Bar; kept local so parity code
# doesn't depend on the test package) -----------------------------------------------


@dataclass(frozen=True)
class _Bar:
    close_time: Any
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


# --- v0 pins this canary reproduces (mirrors A_PARAMS["exit3"] / PROFILE_A exactly;
# see module docstring). These are NOT re-tuned here -- they are the certified
# reference config, imported by name where possible and hard-pinned where the oracle
# itself hard-pins them (e.g. BUFFER, MAX_HOLD are set unconditionally in
# `model01_sweep_mss_fvg.py::run()`, not param-driven). ---------------------------
TICK = 0.25
W_MSS = 12
W_FILL = 12
MAX_HOLD = 48
RR = 2.0
OTE_DEPTH = 0.705
SLIP_TICKS = 8  # A_PARAMS["exit3"]["slip_ticks"]
SLIP = SLIP_TICKS * TICK
BUFFER = 2 * TICK
GAP_MIN = timedelta(minutes=30)
RISK_MAX_FRACTION = 0.012

_HIGH_KIND_TIER = {"pwh": 1, "pdh": 2, "asia_high": 3, "london_high": 3, "h1_sh": 3}
_LOW_KIND_TIER = {"pwl": 1, "pdl": 2, "asia_low": 3, "london_low": 3, "h1_sl": 3}
TRIGGER_SESSIONS = {"asia", "london", "ny_am", "ny_lunch", "ny_pm"}


def _round_cent(x: Any) -> float:
    """Round to the cent using numpy's own rounding on a numpy float64 -- matches
    exactly how the oracle's trade dict rounds (`round(numpy_float64_value, 2)`
    dispatches to `numpy.float64.__round__`, which can disagree with plain Python
    `round(float(x), 2)` at an exact binary-representation boundary; see module
    docstring "COMPARISON")."""
    return float(np.round(np.float64(x), 2))


# ============================================================================
# 1) Data loading (read-only)
# ============================================================================


def load_certified_5m() -> pd.DataFrame:
    """The certified real Databento NQ 5m frame (tz-aware NY), via the SAME
    read-only production loader the 581-signal reference was built from."""
    _ensure_readonly_imports_on_path()
    import apex_eval_eod_databento as DB  # noqa: E402

    return DB.load_databento_5m()


def bars_from_df5(df5: pd.DataFrame) -> List[_Bar]:
    """`close_time` is set to the bar's OWN index value (the oracle's own
    OPEN-time-labelled 5m index) for every bar, deliberately -- the oracle's entire
    session/day/week/HTF-merge causality is built on treating that single index
    consistently as the causal cutoff instant (never a true candle-close offset); this
    canary reproduces model01/htf.py/data.py's own convention bar-for-bar so
    SessionEngine/BucketHL bucket boundaries land on IDENTICAL bars to the oracle's
    (verified bit-for-bit, see module docstring)."""
    idx = df5.index
    o, h, l, c, v = (df5[col].values for col in ("Open", "High", "Low", "Close", "Volume"))
    return [_Bar(idx[i], o[i], h[i], l[i], c[i], v[i]) for i in range(len(df5))]


# ============================================================================
# 2) V2-composed level/swing/displacement series (see module docstring)
# ============================================================================


def build_bucket_level_series(bars: List[_Bar]) -> Dict[str, np.ndarray]:
    """PDH/PDL/PWH/PWL/asia_high/asia_low/london_high/london_low, causal "as known
    at bar i" arrays, via `core/clock.py::SessionEngine` + `engines/_util.py::
    BucketHL` (both genuine, unmodified V2 building blocks)."""
    n = len(bars)
    sessions = SessionEngine()
    day_hl, week_hl = BucketHL(), BucketHL()
    out = {k: np.full(n, np.nan) for k in ("pdh", "pdl", "pwh", "pwl", "asia_high", "asia_low", "london_high", "london_low")}
    cur_pdh = cur_pdl = cur_pwh = cur_pwl = np.nan
    cur_td = None
    ah = al = lh = ll = np.nan
    asia_started = london_started = False
    sess_labels: List[str] = [""] * n

    for i, b in enumerate(bars):
        td = sessions.trade_date(b.close_time)
        fin = day_hl.update(td, b)
        if fin:
            cur_pdh, cur_pdl = fin["high"], fin["low"]
        out["pdh"][i], out["pdl"][i] = cur_pdh, cur_pdl

        wk = trade_week_key(sessions, b.close_time)
        finw = week_hl.update(wk, b)
        if finw:
            cur_pwh, cur_pwl = finw["high"], finw["low"]
        out["pwh"][i], out["pwl"][i] = cur_pwh, cur_pwl

        if td != cur_td:
            # a NEW trade_date's session-completed-range must not carry a stale value
            # forward from the PREVIOUS trade_date (mirrors the oracle's own
            # `groupby(trading_day).ffill()`, which resets at the trade_date boundary,
            # not just when the named session recurs -- see module docstring).
            cur_td = td
            ah = al = lh = ll = np.nan
            asia_started = london_started = False
        label = sessions.session(b.close_time)
        sess_labels[i] = label
        if label == "asia":
            if not asia_started:
                ah, al = b.high, b.low
                asia_started = True
            else:
                ah, al = max(ah, b.high), min(al, b.low)
        if label == "london":
            if not london_started:
                lh, ll = b.high, b.low
                london_started = True
            else:
                lh, ll = max(lh, b.high), min(ll, b.low)
        out["asia_high"][i], out["asia_low"][i] = ah, al
        out["london_high"][i], out["london_low"][i] = lh, ll

    out["_session"] = np.array(sess_labels, dtype=object)
    return out


def build_h1_swing_series(df5: pd.DataFrame, store: EventStore) -> Tuple[np.ndarray, np.ndarray]:
    """h1_sh/h1_sl: `engines/swings.py::SwingMethodA(left=2, right=2)`, REUSED
    UNMODIFIED, fed 1h-resampled bars (default midnight-anchored pandas resample --
    the SAME convention `htf.py::add_htf_swings`'s own `D.resample()` call uses, no
    18:00 CME-day offset for HTF). Every emitted `SWING_HIGH_A`/`SWING_LOW_A` event is
    appended to `store` (genuine EventStore usage feeding this canary's `store_hash`)."""
    h1 = (
        df5.resample("1h", label="left", closed="left", origin="start_day")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna(subset=["Open"])
    )
    h1_bars = [_Bar(ts, r.Open, r.High, r.Low, r.Close, r.Volume) for ts, r in h1.iterrows()]
    engine = SwingMethodA(left=2, right=2)
    pos = {ts: i for i, ts in enumerate(h1.index)}
    n1 = len(h1)
    sh_conf: Dict[int, float] = {}
    sl_conf: Dict[int, float] = {}
    for b in h1_bars:
        for ev in engine.on_bar(b):
            store.append(ev)
            p = pos[ev.confirmed_at]
            if ev.event_type == "SWING_HIGH_A":
                sh_conf[p] = ev.price_high
            else:
                sl_conf[p] = ev.price_low

    # causal fold (as-of-bar-t), matching `primitives.py::last_known_swings` exactly
    sh_at = np.full(n1, np.nan)
    sl_at = np.full(n1, np.nan)
    cur_sh = cur_sl = np.nan
    for t in range(n1):
        if t in sh_conf:
            cur_sh = sh_conf[t]
        if t in sl_conf:
            cur_sl = sl_conf[t]
        sh_at[t], sl_at[t] = cur_sh, cur_sl

    # HTF -> 5m: value known as of 1h-bar t becomes available starting at that bar's
    # TRUE close (t's own index + one full 1h period) -- mirrors `add_htf_swings`'s
    # `lvl.index = lvl.index + period` exactly (see module docstring).
    lvl = pd.DataFrame({"h1_sh": sh_at, "h1_sl": sl_at}, index=h1.index + pd.Timedelta(hours=1)).sort_index()
    merged = pd.merge_asof(df5[[]].sort_index(), lvl, left_index=True, right_index=True, direction="backward")
    return merged["h1_sh"].values, merged["h1_sl"].values


def build_5m_swing_series(bars: List[_Bar], store: EventStore) -> Tuple[np.ndarray, np.ndarray]:
    """5m sh_at/sl_at (3/3): `engines/swings.py::SwingMethodA(left=3, right=3)`,
    REUSED UNMODIFIED -- the same class WP-B's own oracle-equivalence test
    (`test_method_a_matches_frozen_last_known_swings`) already checks against
    `primitives.py::last_known_swings` on synthetic data; this module additionally
    verifies it bit-for-bit on the FULL real certified dataset (see module docstring).

    NOTE: `sh_conf`/`sl_conf` are built from the events THIS call's own `on_bar()` loop
    just emitted, never by re-querying `store.by_type(...)` afterward -- `store` is
    shared with `build_h1_swing_series` (both use `SwingMethodA`, which emits the SAME
    event_type names "SWING_HIGH_A"/"SWING_LOW_A" regardless of left/right), and
    hourly bar boundaries coincide with valid 5m bar timestamps, so a global
    `store.by_type()` query here would silently pick up the 1h swing events too
    (discovered and fixed during this build -- see the 12-mismatch note in the
    Phase-2 report)."""
    engine = SwingMethodA(left=3, right=3)
    pos = {b.close_time: i for i, b in enumerate(bars)}
    n = len(bars)
    sh_conf: Dict[int, float] = {}
    sl_conf: Dict[int, float] = {}
    for b in bars:
        for ev in engine.on_bar(b):
            store.append(ev)
            p = pos[ev.confirmed_at]
            if ev.event_type == "SWING_HIGH_A":
                sh_conf[p] = ev.price_high
            else:
                sl_conf[p] = ev.price_low
    sh_at = np.full(n, np.nan)
    sl_at = np.full(n, np.nan)
    cur_sh = cur_sl = np.nan
    for t in range(n):
        if t in sh_conf:
            cur_sh = sh_conf[t]
        if t in sl_conf:
            cur_sl = sl_conf[t]
        sh_at[t], sl_at[t] = cur_sh, cur_sl
    return sh_at, sl_at


def build_displacement_direction(bars: List[_Bar], store: EventStore) -> np.ndarray:
    """`engines/displacement.py::DisplacementEngine`, REUSED UNMODIFIED. Returns a
    per-bar array: +1 (bullish DISPLACEMENT_QUALIFIED), -1 (bearish), 0 (neither) --
    exactly the sign oracle's `displacement_strength()` carries (see module
    docstring)."""
    engine = DisplacementEngine()
    n = len(bars)
    qual_dir = np.zeros(n, dtype=np.int8)
    for i, b in enumerate(bars):
        for ev in engine.on_bar(b):
            store.append(ev)
            if ev.event_type == "DISPLACEMENT_QUALIFIED":
                qual_dir[i] = 1 if ev.attributes["direction"] == "bullish" else -1
    return qual_dir


# ============================================================================
# 3) Sweep / MSS / OTE detection -- hand-composed parity-layer port of the
#    oracle's `model01_sweep_mss_fvg.py::_detect()` (see module docstring)
# ============================================================================


@dataclass(frozen=True)
class V2Signal:
    direction: str
    sweep_bar: int
    mss_bar: int
    fill_bar: int
    entry: float
    stop: float
    target: float
    liq_swept: str
    session_at_mss: str


def _detect_v2(
    i: int,
    d: int,
    level_arrays: Dict[str, np.ndarray],
    tiers: Dict[str, int],
    H: np.ndarray,
    L: np.ndarray,
    C: np.ndarray,
    sh_at: np.ndarray,
    sl_at: np.ndarray,
    qual_dir: np.ndarray,
    n: int,
) -> Optional[Tuple[int, float, str, int, float]]:
    """Direct port of `model01_sweep_mss_fvg.py::_detect()`'s sweep-reclaim + MSS +
    OTE-entry-zone math (entry_type="ote" branch only -- PROFILE_A's config), operating
    on the V2-built `level_arrays`/`sh_at`/`sl_at`/`qual_dir` above instead of the
    oracle's own feature columns. Returns (mss_bar, entry_zone_price, level_kind, tier,
    sweep_px) or None."""
    swept = None
    lo_bound = max(0, i - 2)
    for nm, tier in tiers.items():
        lvl = level_arrays[nm][i]
        if lvl != lvl:  # NaN
            continue
        if d > 0:
            win_lo = L[lo_bound : i + 1].min()
            if win_lo < lvl - TICK and C[i] > lvl:
                if swept is None or tier < swept[1]:
                    swept = (nm, tier, win_lo)
        else:
            win_hi = H[lo_bound : i + 1].max()
            if win_hi > lvl + TICK and C[i] < lvl:
                if swept is None or tier < swept[1]:
                    swept = (nm, tier, win_hi)
    if swept is None:
        return None
    nm, tier, sweep_px = swept

    opp = sh_at[i] if d > 0 else sl_at[i]
    if opp != opp:  # NaN
        return None

    mss_bar = None
    for k in range(i + 1, min(i + 1 + W_MSS, n)):
        if d > 0 and C[k] > opp:
            mss_bar = k
            break
        if d < 0 and C[k] < opp:
            mss_bar = k
            break
    if mss_bar is None:
        return None

    want = 1 if d > 0 else -1
    if not np.any(qual_dir[i : mss_bar + 1] == want):
        return None

    imp_hi = H[i : mss_bar + 1].max()
    imp_lo = L[i : mss_bar + 1].min()
    ez = imp_hi - OTE_DEPTH * (imp_hi - imp_lo) if d > 0 else imp_lo + OTE_DEPTH * (imp_hi - imp_lo)
    return mss_bar, ez, nm, tier, sweep_px


def _mechanical_exit_bar(fill: int, d: int, stop: float, target: float, H: np.ndarray, L: np.ndarray, close_time: np.ndarray, n: int) -> int:
    """Mechanical, NEVER-STORED bar-index walk used only to know where the next scan
    resumes (mirrors oracle's `i = exit_i + 1`; see module docstring "no overlap"
    entry). PROFILE_A's exit3 params disable breakeven/trail/floor, so stop and target
    are FIXED for the whole hold -- no R/PF value is computed anywhere in this
    function."""
    last = min(fill + MAX_HOLD, n)
    for x in range(fill, last):
        hi, lo = H[x], L[x]
        if (lo <= stop) if d > 0 else (hi >= stop):
            return x
        if (hi >= target) if d > 0 else (lo <= target):
            return x
        if x + 1 < last and (close_time[x + 1] - close_time[x]) > GAP_MIN:
            return x
    return last - 1


def run_v2_walk(df5: pd.DataFrame, event_store: Optional[EventStore] = None) -> Tuple[pd.DataFrame, EventStore]:
    """The full V2-composed candidate walk (mirrors `model01_sweep_mss_fvg.py::run()`'s
    outer while-loop structurally). Returns (candidates_df, event_store) where
    `event_store` holds every SWING_HIGH_A/SWING_LOW_A (5m + 1h) and
    DISPLACEMENT_QUALIFIED/COMPONENTS/WARMUP event genuinely emitted by the reused V2
    engines during the run (feeds `store_hash`)."""
    store = event_store if event_store is not None else EventStore()
    bars = bars_from_df5(df5)
    n = len(bars)

    level_series = build_bucket_level_series(bars)
    h1_sh, h1_sl = build_h1_swing_series(df5, store)
    sh_at, sl_at = build_5m_swing_series(bars, store)
    qual_dir = build_displacement_direction(bars, store)

    level_arrays_long = {**{k: level_series[k] for k in ("pwl", "pdl", "asia_low", "london_low")}, "h1_sl": h1_sl}
    level_arrays_short = {**{k: level_series[k] for k in ("pwh", "pdh", "asia_high", "london_high")}, "h1_sh": h1_sh}
    sess = level_series["_session"]

    H = np.array([b.high for b in bars])
    L = np.array([b.low for b in bars])
    C = np.array([b.close for b in bars])
    close_time = np.array([b.close_time for b in bars])

    candidates: List[V2Signal] = []
    i = 2
    while i < n - 2:
        if sess[i] not in TRIGGER_SESSIONS:
            i += 1
            continue
        setup = _detect_v2(i, +1, level_arrays_long, _LOW_KIND_TIER, H, L, C, sh_at, sl_at, qual_dir, n)
        d = +1
        if setup is None:
            setup = _detect_v2(i, -1, level_arrays_short, _HIGH_KIND_TIER, H, L, C, sh_at, sl_at, qual_dir, n)
            d = -1
        if setup is None:
            i += 1
            continue
        mss_bar, ez, nm, tier, sweep_px = setup

        fill = None
        for m in range(mss_bar + 1, min(mss_bar + 1 + W_FILL, n)):
            if d > 0 and L[m] <= ez:
                fill = m
                break
            if d < 0 and H[m] >= ez:
                fill = m
                break
        if fill is None:
            i = mss_bar + 1
            continue

        entry = ez + d * SLIP
        stop = (sweep_px - BUFFER) if d > 0 else (sweep_px + BUFFER)
        risk = (entry - stop) if d > 0 else (stop - entry)
        if risk <= 2 * TICK:
            i = fill + 1
            continue
        if risk > RISK_MAX_FRACTION * entry:
            i = fill + 1
            continue
        target = entry + d * RR * risk

        exit_bar = _mechanical_exit_bar(fill, d, stop, target, H, L, close_time, n)
        candidates.append(
            V2Signal(
                direction="long" if d > 0 else "short",
                sweep_bar=i,
                mss_bar=mss_bar,
                fill_bar=fill,
                entry=float(entry),
                stop=float(stop),
                target=float(target),
                liq_swept=nm,
                session_at_mss=sess[mss_bar],
            )
        )
        i = exit_bar + 1

    df = pd.DataFrame([c.__dict__ for c in candidates])
    return df, store


# ============================================================================
# 4) Oracle regeneration (frozen, read-only) + shared classification filters
# ============================================================================


def regenerate_oracle_candidates(df5: pd.DataFrame) -> pd.DataFrame:
    """Re-runs the frozen `model01_sweep_mss_fvg.py::run()` over the SAME certified
    dataset with the SAME certified params (`A_PARAMS["exit3"]`) -- i.e. regenerates
    the reference signal list from scratch rather than trusting the static reference
    CSV, per SPEC.md's "run frozen model01 ... to regenerate the signal list"."""
    _ensure_readonly_imports_on_path()
    import config  # noqa: E402
    import model01_sweep_mss_fvg as M1  # noqa: E402
    import strategy_engine_profileA as E  # noqa: E402
    from tools_1m_truth_recert import A_PARAMS  # noqa: E402

    eng = E.ProfileAEngine(config.STRAT)
    eng.buf = df5
    feats = eng._features()
    assert (feats.index == df5.index).all(), "feats/df5 index drifted -- data-loading regression"
    tr = M1.run(feats, "NQ", A_PARAMS["exit3"])
    return tr


def _classify(row: pd.Series) -> str:
    """5-way classification, PAE-001's `classify_signals.py::classify()` logic
    reproduced exactly (read-only precedent; see module docstring)."""
    mss_before_fill = row["mss_bar"] < row["fill_bar"]
    if pd.isna(row.get("achievable")):
        return "POST-ENTRY-DEPENDENT"
    if bool(row["achievable"]):
        return "FULLY-AVAILABLE"
    if not mss_before_fill:
        return "POST-ENTRY-DEPENDENT"
    if pd.isna(row.get("first_tail3_poll")):
        return "UNREACHABLE"
    return "DELAYED"


def apply_certified_selection(candidates: pd.DataFrame, df5: pd.DataFrame) -> pd.DataFrame:
    """Applies the SAME three live-executability selection layers to a raw candidate
    list (oracle's or V2's) -- ny_am-at-mss filter, D1c drift gate, emission-replay
    5-way classification -- and returns the FULLY-AVAILABLE + DELAYED subset (the
    "581" target population). See module docstring "SCOPE BOUNDARY"."""
    _ensure_readonly_imports_on_path()
    import run_d1c_real as RD  # noqa: E402

    session_col = "session_at_mss" if "session_at_mss" in candidates.columns else "session"
    kept = candidates[candidates[session_col] == "ny_am"].copy().reset_index(drop=True)
    if len(kept) == 0:
        return kept

    d1_tz = RD.load_1m()
    kept = RD.attach_drift(kept, d1_tz, df5.index)
    kept = kept[kept["d1c_keep"] == True].copy()  # noqa: E712

    emission_csv = os.path.join(BOT_REPO, "reports", "inc_20260707_recert", "emission_replay_raw_full.csv")
    em = pd.read_csv(emission_csv).set_index("key")
    kept["key"] = kept["fill_bar"].apply(lambda fb: pd.Timestamp(df5.index[int(fb)]).isoformat())
    joined = kept.join(em, on="key", how="left", rsuffix="_em")
    joined["class"] = joined.apply(_classify, axis=1)
    return joined[joined["class"].isin(["FULLY-AVAILABLE", "DELAYED"])].copy()


# ============================================================================
# 5) Comparison
# ============================================================================


def compare_signal_sets(oracle_581: pd.DataFrame, v2_581: pd.DataFrame, df5: pd.DataFrame) -> Dict[str, Any]:
    """Per-signal exact match on (direction, sweep_bar, mss_bar, fill_bar, entry,
    stop, target), keyed by fill-instant (`df5.index[fill_bar].isoformat()` --
    the SAME key PAE-001's own classification join uses)."""
    def key_of(row: pd.Series) -> str:
        return pd.Timestamp(df5.index[int(row["fill_bar"])]).isoformat()

    oracle_by_key = {key_of(r): r for _, r in oracle_581.iterrows()}
    v2_by_key = {key_of(r): r for _, r in v2_581.iterrows()}
    oracle_keys, v2_keys = set(oracle_by_key), set(v2_by_key)

    matched = 0
    mismatched: List[Dict[str, Any]] = []
    for key in sorted(oracle_keys | v2_keys):
        if key not in v2_keys:
            mismatched.append({"key": key, "status": "MISSING_FROM_V2"})
            continue
        if key not in oracle_keys:
            mismatched.append({"key": key, "status": "EXTRA_IN_V2"})
            continue
        o, v = oracle_by_key[key], v2_by_key[key]
        fields = {
            "direction": (str(o["direction"]), str(v["direction"])),
            "sweep_bar": (int(o["sweep_bar"]), int(v["sweep_bar"])),
            "mss_bar": (int(o["mss_bar"]), int(v["mss_bar"])),
            "entry": (_round_cent(o["entry"]), _round_cent(v["entry"])),
            "stop": (_round_cent(o["stop"]), _round_cent(v["stop"])),
            "target": (_round_cent(o["target"]), _round_cent(v["target"])),
        }
        bad = {k: {"oracle": a, "v2": b} for k, (a, b) in fields.items() if a != b}
        if bad:
            mismatched.append({"key": key, "status": "FIELD_MISMATCH", "fields": bad})
        else:
            matched += 1

    return {
        "oracle_count": len(oracle_keys),
        "v2_count": len(v2_keys),
        "matched": matched,
        "mismatched": mismatched,
    }


def _store_hash(store: EventStore) -> str:
    """Deterministic hash of the V2 sub-engine events genuinely emitted while
    building this canary's level/swing/displacement series (SWING_HIGH_A/LOW_A at
    5m and 1h + DISPLACEMENT_QUALIFIED/COMPONENTS/WARMUP) -- NOT a hash of the
    sweep/MSS/OTE signal comparison itself (those are hand-composed parity-layer
    values, not CausalEvents; see module docstring "V2 COMPOSITION"). Hashes the
    ordered `event_id` sequence (already a deterministic sha256 of event identity;
    `core/events.py::compute_event_id`)."""
    h = hashlib.sha256()
    for ev in store.all:
        h.update(ev.event_id.encode("ascii"))
    return h.hexdigest()


# ============================================================================
# 6) Orchestration
# ============================================================================


def selfcheck_building_blocks_against_production(df5: pd.DataFrame) -> Dict[str, int]:
    """Validates every V2-composed level/swing series this canary feeds into
    `_detect_v2` bit-for-bit against the SAME certified production columns/oracle
    functions used to build the reference 581 set -- NOT used as part of the actual
    parity comparison (that stays strictly V2-vs-oracle-signal-list), but recorded
    evidence for the "V2 COMPOSITION" claims in this module's docstring. Returns a
    dict of series-name -> mismatch count (0 everywhere is the expected/required
    result; a nonzero count here would mean a `_detect_v2` divergence is attributable
    to a building-block bug rather than genuine sweep/MSS/OTE detection logic)."""
    _ensure_readonly_imports_on_path()
    import config  # noqa: E402
    import primitives as P  # noqa: E402
    import strategy_engine_profileA as E  # noqa: E402

    eng = E.ProfileAEngine(config.STRAT)
    eng.buf = df5
    feats = eng._features()

    bars = bars_from_df5(df5)
    store = EventStore()
    level_series = build_bucket_level_series(bars)
    h1_sh, h1_sl = build_h1_swing_series(df5, store)
    sh_at, sl_at = build_5m_swing_series(bars, store)

    mismatches: Dict[str, int] = {}
    for name, mine in (
        ("pdh", level_series["pdh"]), ("pdl", level_series["pdl"]),
        ("pwh", level_series["pwh"]), ("pwl", level_series["pwl"]),
        ("asia_high", level_series["asia_high"]), ("asia_low", level_series["asia_low"]),
        ("london_high", level_series["london_high"]), ("london_low", level_series["london_low"]),
        ("h1_sh", h1_sh), ("h1_sl", h1_sl),
    ):
        theirs = feats[name].values
        mismatches[name] = int((~np.isclose(mine, theirs, equal_nan=True, atol=1e-6)).sum())

    ref_sh, ref_sl, _, _ = P.last_known_swings(df5.reset_index(drop=True), 3, 3)
    mismatches["sh_at_5m_3_3"] = int((~np.isclose(sh_at, ref_sh, equal_nan=True, atol=1e-6)).sum())
    mismatches["sl_at_5m_3_3"] = int((~np.isclose(sl_at, ref_sl, equal_nan=True, atol=1e-6)).sum())
    return mismatches


def run_full_parity(out_path: Optional[str] = None) -> Dict[str, Any]:
    """Runs the complete comparison over the full certified real dataset and writes
    `reports/ict_v2/parity_canary_summary.json`. Slow (~1-2 min); intended to be run
    once and the result committed to the report, and via
    `tests/test_model01_parity.py --full`."""
    df5 = load_certified_5m()
    building_block_selfcheck = selfcheck_building_blocks_against_production(df5)
    oracle_raw = regenerate_oracle_candidates(df5)
    v2_raw, store = run_v2_walk(df5)

    oracle_581 = apply_certified_selection(oracle_raw, df5)
    v2_581 = apply_certified_selection(v2_raw, df5)

    result = compare_signal_sets(oracle_581, v2_581, df5)
    result["param_versions"] = {"ict_v2": "ICT_V2_PARAMS_V0", "oracle": "A_PARAMS[exit3]"}
    result["data_range"] = {
        "start": df5.index.min().isoformat(),
        "end": df5.index.max().isoformat(),
        "n_bars_5m": int(len(df5)),
    }
    result["store_hash"] = _store_hash(store)
    result["store_hash_definition"] = (
        "sha256 over the ordered event_id sequence of every SWING_HIGH_A/SWING_LOW_A "
        "(5m 3/3 and 1h 2/2) and DISPLACEMENT_QUALIFIED/COMPONENTS/WARMUP event emitted "
        "by the reused V2 sub-engines while building this canary's level/swing/"
        "displacement series; the sweep/MSS/OTE signal values themselves are hand-"
        "composed parity-layer values, not CausalEvents -- see module docstring."
    )
    result["oracle_raw_candidate_count"] = int(len(oracle_raw))
    result["v2_raw_candidate_count"] = int(len(v2_raw))
    result["building_block_selfcheck_mismatches"] = building_block_selfcheck

    out_path = out_path or os.path.join(BOT_REPO, "reports", "ict_v2", "parity_canary_summary.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    return result


if __name__ == "__main__":
    res = run_full_parity()
    print(json.dumps({k: v for k, v in res.items() if k != "mismatched"}, indent=2, default=str))
    print(f"mismatched: {len(res['mismatched'])}")
