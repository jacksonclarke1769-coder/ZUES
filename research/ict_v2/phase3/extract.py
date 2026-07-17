"""WP-E main extraction pipeline (PREREG_PHASE3.md v1.0 + Amendment v1.1, git hash
cd652ea81093, prereg §8): runs the certified event engines (`research/ict_v2/engines/`,
read-only, the ONLY event source -- no re-implemented detection anywhere here) over the
roll-adjusted 5m frame, extracts the prereg's 6 event UNITS (which together cover all
17 §3 cells), computes the §2 baseline set B + per-family features (asserted knowable,
`confirmed_at <= t0`) and outcomes (fwd/maxcont/maxrev/rev24, direction-adjusted where
the event has a direction), splits IS/HOLDOUT by t0, and writes them to SEPARATE
parquet files.

PERFORMANCE (v2, after the 5h-line stop): the hot path is now VECTORIZED. Two costs
dominated the naive per-event loop and are removed:
  1. `prior_test_count` was O(episodes x tests-on-that-level) with per-pair pandas
     Timestamp comparisons -- quadratic on heavily-tested levels (round numbers /
     PDH). Now: per-level sorted int64 test-time arrays + `np.searchsorted` (O(log n)
     per episode, integer compares).
  2. `fwd/maxcont/maxrev` and `efficiency_12` were per-event numpy window slices.
     Now: computed ONCE over the whole bar array (`baseline.build_outcome_arrays` /
     `build_efficiency_array`, `sliding_window_view` + `cumsum`) and indexed at event
     bar positions; direction-adjustment and the baseline B columns are attached
     vectorized from full-bar arrays via each event's bar index.

KNOWABILITY GUARANTEE SURVIVES (PREREG §2): every FEATURE value at t0 reads only bars
<= t0. Outcomes read bars > t0 by definition (they are forward-path measures, prereg
§2) and are never fed back as features. The equivalence of the fast vectorized path to
the slow per-event reference is PROVEN, not assumed: `run_conformance_checks()` runs at
the START of every real extraction (not a skippable separate script) and asserts, for a
deterministic >=200-event sample per family, that every fast feature/outcome value
equals its slow-path value EXACTLY -- the run aborts before writing any parquet on the
first mismatch.

AMD is excluded (prereg ban); `opening_range`/`overnight`/`ranges`/`swings_b`/
`swings_c` engines are not registered -- no prereg cell names an event type from any of
them (baseline B's "overnight gap"/"ATR20 percentile" are computed independently from
the bar array itself, `baseline.py`, NOT read from those engines' events -- consistent
with `core/runner.py`'s own "engines never share state" convention).
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Mapping, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ..core.events import CausalEvent, EventStore
from ..engines.displacement import DisplacementEngine
from ..engines.levels import LevelRegistry
from ..engines.structure import StructureEngine
from ..engines.sweeps import _AMBIDEXTROUS_KINDS, _HIGH_KINDS, _LOW_KINDS, SweepEngine
from ..engines.zones import ZonesEngine
from ..parity.model01_canary import _Bar
from .baseline import (
    OUTCOME_HORIZONS,
    BarArrays,
    OutcomeArrays,
    build_bar_arrays,
    build_efficiency_array,
    build_outcome_arrays,
    efficiency_trailing_12,
    raw_outcomes_at,
)
from .frame import build_bars

BOT_REPO = os.path.expanduser("~/trading-team/bot/nq-liq-bot")
DATA_DIR = os.path.join(BOT_REPO, "research", "ict_v2", "phase3", "data")

NY = "America/New_York"
_NY_ZONE = ZoneInfo("America/New_York")
IS_START = pd.Timestamp("2021-06-22", tz=NY)
IS_END_EXCLUSIVE = pd.Timestamp("2025-06-22", tz=NY)  # IS: 2021-06-22 -> 2025-06-21 inclusive
HOLDOUT_START = pd.Timestamp("2025-06-22", tz=NY)
HOLDOUT_END_EXCLUSIVE = pd.Timestamp("2026-06-23", tz=NY)  # HOLDOUT: 2025-06-22 -> 2026-06-22 inclusive

ENGINE_PROGRESS_EVERY = 20_000  # bars
ROW_PROGRESS_EVERY = 250_000  # events
CONFORMANCE_SAMPLE = 250  # >= prereg-mandated 200 per family

# -- knowability-assertion counter (module-level; incremented by assert_knowable) ---
_KNOWABILITY_CHECKS = 0
_KNOWABILITY_VIOLATIONS = 0


def _log(msg: str) -> None:
    print(f"[wp-e {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def assert_knowable(bar_indices: np.ndarray, i0: int, context: str = "") -> None:
    """Structural knowability proof (PREREG §2). `bar_indices` is the array of bar
    positions of the events feeding a feature at t0 (bar index i0); every one must be
    <= i0 (bar close_times are strictly increasing, so bar-index <= i0 is exactly
    `confirmed_at <= t0`). Vectorized (was a per-event pandas Timestamp loop). Raises
    immediately on any violation (fail-closed)."""
    global _KNOWABILITY_CHECKS, _KNOWABILITY_VIOLATIONS
    _KNOWABILITY_CHECKS += int(bar_indices.size)
    if bar_indices.size and int(bar_indices.max()) > i0:
        n_bad = int((bar_indices > i0).sum())
        _KNOWABILITY_VIOLATIONS += n_bad
        raise AssertionError(
            f"knowability violated ({context}): {n_bad} event(s) with bar_index > i0={i0}"
        )


def split_label(t0) -> Optional[str]:
    if IS_START <= t0 < IS_END_EXCLUSIVE:
        return "IS"
    if HOLDOUT_START <= t0 < HOLDOUT_END_EXCLUSIVE:
        return "HOLDOUT"
    return None


def _year_of(t0) -> int:
    return t0.astimezone(_NY_ZONE).year


# --- engine run (local runner with progress logging; functionally identical to
# core/runner.py::BatchRunner.run -- same bar-then-engine iteration order, so
# determinism/prefix-invariance are preserved; we do NOT edit the certified runner) ---


def run_engines(bars: List[_Bar]) -> Dict[str, EventStore]:
    engines = {
        "levels": LevelRegistry(),
        "sweeps": SweepEngine(),
        "structure": StructureEngine(),
        "displacement": DisplacementEngine(),
        "zones": ZonesEngine(),
    }
    stores = {name: EventStore() for name in engines}
    n = len(bars)
    t0 = time.time()
    for k, bar in enumerate(bars):
        for name, eng in engines.items():
            evs = eng.on_bar(bar)
            if evs:
                stores[name].extend(evs)
        if (k + 1) % ENGINE_PROGRESS_EVERY == 0:
            rate = (k + 1) / (time.time() - t0)
            eta = (n - (k + 1)) / rate if rate else float("nan")
            _log(f"engines: {k + 1:,}/{n:,} bars ({rate:,.0f} bars/s, ETA {eta:,.0f}s)")
    _log(f"engines: done {n:,} bars in {time.time() - t0:,.1f}s")
    return stores


# --- derived per-bar arrays (all O(bars), single forward pass; not the bottleneck) ---


def build_displacement_component_index(disp_store: EventStore) -> Dict[Any, Mapping]:
    idx: Dict[Any, Any] = {}
    for ev in disp_store.by_type("DISPLACEMENT_COMPONENTS"):
        idx[ev.confirmed_at] = ev.attributes
    for ev in disp_store.by_type("DISPLACEMENT_WARMUP"):
        idx.setdefault(ev.confirmed_at, ev.attributes)
    return idx


def build_component_arrays(arrays: BarArrays, disp_index: Dict[Any, Any]) -> Dict[str, np.ndarray]:
    """Per-bar arrays for the displacement component snapshot (body_vs_tod, volume_z,
    close_location, sigma_tod) joined by close_time, plus sigma_tod-relative realized
    vol (PREREG §2 B). All values are known AT that bar's close (confirmed_at == t0),
    so they are legitimate features."""
    n = arrays.n
    body_vs_tod = np.full(n, np.nan)
    volume_z = np.full(n, np.nan)
    close_location = np.full(n, np.nan)
    sigma_tod = np.full(n, np.nan)
    sigma_rel_vol12 = np.full(n, np.nan)
    for i, t in enumerate(arrays.close_time):
        comp = disp_index.get(t)
        if comp is None:
            continue
        bvt = comp.get("body_vs_tod")
        if bvt is not None:
            body_vs_tod[i] = bvt
        vz = comp.get("volume_z")
        if vz is not None:
            volume_z[i] = vz
        cl = comp.get("close_location")
        if cl is not None:
            close_location[i] = cl
        st = comp.get("sigma_tod")
        if st not in (None, 0):
            sigma_tod[i] = st
            rv = arrays.realized_vol_12[i]
            if not np.isnan(rv):
                sigma_rel_vol12[i] = rv / st
    return {
        "body_vs_tod": body_vs_tod,
        "volume_z": volume_z,
        "close_location": close_location,
        "sigma_tod": sigma_tod,
        "sigma_tod_relative_vol_12": sigma_rel_vol12,
    }


def build_ny_am_session_range_consumed(arrays: BarArrays) -> np.ndarray:
    """(session H-L so far at t0) / (median full-session ny_am range, trailing <=20
    COMPLETED ny_am sessions) -- PREREG §3 F6. Causal single forward pass."""
    n = arrays.n
    out = np.full(n, np.nan)
    completed_ranges: List[float] = []
    cur_td = None
    session_hi = session_lo = None
    for i in range(n):
        if arrays.session[i] != "ny_am":
            continue
        td = arrays.trade_date[i]
        if td != cur_td:
            if cur_td is not None and session_hi is not None:
                completed_ranges.append(session_hi - session_lo)
                if len(completed_ranges) > 20:
                    completed_ranges.pop(0)
            cur_td = td
            session_hi = arrays.high[i]
            session_lo = arrays.low[i]
        else:
            session_hi = max(session_hi, arrays.high[i])
            session_lo = min(session_lo, arrays.low[i])
        if completed_ranges:
            median_range = float(np.median(completed_ranges))
            if median_range > 0:
                out[i] = (session_hi - session_lo) / median_range
    return out


def build_level_test_baridx_index(levels_store: EventStore, index_by_close_time: Dict[Any, int]) -> Dict[str, np.ndarray]:
    """level_id -> sorted int array of its LEVEL_TESTED bar POSITIONS.
    `np.searchsorted(arr, i0, side='left')` then counts tests STRICTLY before bar i0
    in O(log n) integer compares -- the vectorized replacement for the old per-episode
    `[e for e in tests if e.confirmed_at < t0]` quadratic pandas-Timestamp scan. Bar
    positions are used (not ns) because a plain python datetime has no `.value`; the
    bar index is an exact, injective, order-preserving key for the strictly-increasing
    5m close_time grid."""
    raw: Dict[str, List[int]] = {}
    for ev in levels_store.by_type("LEVEL_TESTED"):
        bi = index_by_close_time.get(ev.confirmed_at)
        if bi is not None:
            raw.setdefault(ev.source_event_ids[0], []).append(bi)
    return {lid: np.array(sorted(v), dtype=np.int64) for lid, v in raw.items()}


# --- vectorized column attachment ---------------------------------------------------


def _obj_index(pylist: List[Any], i0: np.ndarray) -> np.ndarray:
    return np.array(pylist, dtype=object)[i0]


def attach_baseline_columns(df: pd.DataFrame, arrays: BarArrays, comp_arrays: Dict[str, np.ndarray]) -> None:
    """Attach the PREREG §2 baseline set B columns (+ session) to `df` in place,
    vectorized via each row's `_i0` bar index. B = {tod_slot_30, day_of_week,
    ATR20-percentile-60sess, sigma_TOD-relative realized vol (12), signed 12-bar
    return in ATR, overnight gap in ATR}; atr20 and session carried alongside."""
    i0 = df["_i0"].to_numpy()
    df["tod_slot_30"] = _obj_index(arrays.tod_slot_30, i0)
    df["day_of_week"] = arrays.day_of_week[i0]
    df["atr20"] = arrays.atr20[i0]
    df["atr20_percentile_60sess"] = arrays.atr20_percentile_60sess[i0]
    df["sigma_tod_relative_vol_12"] = comp_arrays["sigma_tod_relative_vol_12"][i0]
    df["ret_12bar_atr"] = arrays.ret_12bar_atr[i0]
    df["overnight_gap_atr"] = arrays.overnight_gap_atr[i0]
    df["session"] = _obj_index(arrays.session, i0)


def attach_raw_outcomes(df: pd.DataFrame, outcomes: OutcomeArrays) -> None:
    i0 = df["_i0"].to_numpy()
    for h in outcomes.horizons:
        df[f"fwd_raw_{h}"] = outcomes.fwd_raw[h][i0]
        df[f"maxfav_raw_{h}"] = outcomes.maxfav_raw[h][i0]
        df[f"maxadv_raw_{h}"] = outcomes.maxadv_raw[h][i0]


def attach_direction_adjusted(df: pd.DataFrame, outcomes: OutcomeArrays) -> None:
    """Direction-adjusted outcome columns (PREREG §2) vectorized from raw + the
    per-row `direction` column ('up'/'down'/None)."""
    d = df["direction"].to_numpy()
    sign = np.where(d == "up", 1.0, np.where(d == "down", -1.0, np.nan))
    for h in outcomes.horizons:
        fr = df[f"fwd_raw_{h}"].to_numpy()
        mf = df[f"maxfav_raw_{h}"].to_numpy()
        ma = df[f"maxadv_raw_{h}"].to_numpy()
        df[f"fwd_{h}"] = fr * sign
        df[f"maxcont_{h}"] = np.where(sign == 1.0, mf, np.where(sign == -1.0, ma, np.nan))
        df[f"maxrev_{h}"] = np.where(sign == 1.0, ma, np.where(sign == -1.0, mf, np.nan))
    fwd24 = df["fwd_24"].to_numpy()
    df["rev24"] = np.where(np.isnan(fwd24), np.nan, (fwd24 < 0).astype(float))


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Common tail: split/year columns + drop the internal `_i0` helper."""
    df["split"] = df["t0"].map(split_label)
    df["year"] = df["t0"].map(_year_of)
    return df.drop(columns=["_i0"])


def level_direction_for_kind(kind: str) -> Optional[str]:
    if kind in _HIGH_KINDS:
        return "down"  # a bounce AWAY from a HIGH-type level tested from below = down
    if kind in _LOW_KINDS:
        return "up"
    return None  # ambidextrous (round numbers) -- no defined approach side


# --- per-unit extraction (row loop = engine attributes only; everything else
# attached vectorized afterward) -----------------------------------------------------


def extract_excursion_episodes(
    sweeps_store: EventStore,
    arrays: BarArrays,
    comp_arrays: Dict[str, np.ndarray],
    outcomes: OutcomeArrays,
    level_test_baridx: Dict[str, np.ndarray],
) -> pd.DataFrame:
    t = time.time()
    open_events = sweeps_store.by_type("EXCURSION_OPEN")
    total = len(open_events)
    _log(f"excursion_episodes: {total:,} EXCURSION_OPEN events")

    terminal_by_open: Dict[str, CausalEvent] = {}
    for et in ("SWEEP_CONFIRMED", "ACCEPTED_BREAKOUT", "EXCURSION_TIMEOUT"):
        for ev in sweeps_store.by_type(et):
            terminal_by_open[ev.source_event_ids[0]] = ev

    tick = 0.25
    body_vs_tod_arr = comp_arrays["body_vs_tod"]
    volume_z_arr = comp_arrays["volume_z"]
    rows: List[Dict[str, Any]] = []
    for k, ev in enumerate(open_events):
        t0 = ev.confirmed_at
        i0 = arrays.index_by_close_time.get(t0)
        if i0 is None:
            continue
        attrs = ev.attributes
        level_id = attrs["level_id"]
        side = attrs["side"]
        level_price = attrs["level_price"]
        breach_price = attrs["breach_price"]
        depth_pts = abs(breach_price - level_price)
        atr0 = arrays.atr20[i0]
        depth_atr = depth_pts / atr0 if (np.isfinite(atr0) and atr0 != 0) else np.nan

        # prior test_count (F1b): searchsorted STRICTLY before bar i0, O(log n) integer.
        test_arr = level_test_baridx.get(level_id)
        if test_arr is not None and test_arr.size:
            prior_ct = int(np.searchsorted(test_arr, i0, side="left"))
            assert_knowable(test_arr[:prior_ct], i0, "F1b prior_test_count")
        else:
            prior_ct = 0

        prom_above = attrs.get("level_prominence_above_pts")
        prom_below = attrs.get("level_prominence_below_pts")
        prominence_relevant = prom_above if side == "buy" else prom_below

        h, l, c = arrays.high[i0], arrays.low[i0], arrays.close[i0]
        close_loc_t0 = (c - l) / (h - l) if h > l else np.nan

        terminal = terminal_by_open.get(ev.event_id)
        if terminal is not None and terminal.confirmed_at < t0:
            raise AssertionError("terminal event precedes its own EXCURSION_OPEN (impossible)")

        equality_count = attrs.get("level_equality_count") or 1
        roundness_major = bool(attrs.get("level_roundness_major"))
        roundness_minor = bool(attrs.get("level_roundness_minor"))
        bvt = body_vs_tod_arr[i0]
        vz = volume_z_arr[i0]

        rows.append(
            {
                "_i0": i0,
                "t0": t0,
                "level_id": level_id,
                "level_kind": attrs.get("level_kind"),
                "side": side,
                "level_timeframe_class": attrs.get("level_timeframe_class"),
                "level_price": level_price,
                "breach_price": breach_price,
                "excursion_depth_pts_t0": depth_pts,
                "excursion_depth_ticks_t0": depth_pts / tick,
                "excursion_depth_atr_t0": depth_atr,
                "t0_close_location": close_loc_t0,
                "body_vs_tod_t0": bvt if np.isfinite(bvt) else np.nan,
                "volume_z_t0": vz if np.isfinite(vz) else np.nan,
                "prominence_above_pts": prom_above,
                "prominence_below_pts": prom_below,
                "prominence_pts_relevant": prominence_relevant,
                "roundness_major": roundness_major,
                "roundness_minor": roundness_minor,
                "equality_count": equality_count,
                "equality_flag": equality_count >= 2,
                "roundness_flag": roundness_major or roundness_minor,
                "prior_test_count": prior_ct,
                "h_bars": attrs.get("h_bars"),
                "terminal_event_type": terminal.event_type if terminal else "UNRESOLVED_AT_DATA_END",
                "terminal_confirmed_at": terminal.confirmed_at if terminal else pd.NaT,
                "reclaim_speed_bars": terminal.attributes.get("reclaim_speed_bars") if terminal else None,
                "duration_bars": terminal.attributes.get("duration_bars") if terminal else None,
                "excursion_depth_ticks_final": terminal.attributes.get("excursion_depth_ticks") if terminal else None,
            }
        )
        if (k + 1) % ROW_PROGRESS_EVERY == 0:
            _log(f"excursion_episodes: {k + 1:,}/{total:,} ({time.time() - t:,.1f}s)")

    df = pd.DataFrame(rows)
    attach_baseline_columns(df, arrays, comp_arrays)
    attach_raw_outcomes(df, outcomes)  # excursion outcomes stay RAW (no single event direction)
    df = _finalize(df)
    _log(f"excursion_episodes: built {len(df):,} rows in {time.time() - t:,.1f}s")
    return df


def _simple_family(events, name, arrays, comp_arrays, outcomes, row_builder, directional: bool) -> pd.DataFrame:
    t = time.time()
    total = len(events)
    _log(f"{name}: {total:,} events")
    rows: List[Dict[str, Any]] = []
    for k, ev in enumerate(events):
        t0 = ev.confirmed_at
        i0 = arrays.index_by_close_time.get(t0)
        if i0 is None:
            continue
        row = row_builder(ev, i0)
        row["_i0"] = i0
        row["t0"] = t0
        rows.append(row)
        if (k + 1) % ROW_PROGRESS_EVERY == 0:
            _log(f"{name}: {k + 1:,}/{total:,} ({time.time() - t:,.1f}s)")
    df = pd.DataFrame(rows)
    attach_baseline_columns(df, arrays, comp_arrays)
    attach_raw_outcomes(df, outcomes)
    if directional:
        attach_direction_adjusted(df, outcomes)
    df = _finalize(df)
    _log(f"{name}: built {len(df):,} rows in {time.time() - t:,.1f}s")
    return df


def extract_sweep_confirmed(sweeps_store, arrays, comp_arrays, outcomes, eff_arr, ny_am_src) -> pd.DataFrame:
    def build(ev, i0):
        a = ev.attributes
        side = a["side"]
        session = arrays.session[i0]
        return {
            "level_id": a.get("level_id"),
            "level_kind": a.get("level_kind"),
            "side": side,
            "direction": "down" if side == "buy" else "up",
            "reclaim_speed_bars": a.get("reclaim_speed_bars"),
            "duration_bars": a.get("duration_bars"),
            "excursion_depth_ticks": a.get("excursion_depth_ticks"),
            "level_timeframe_class": a.get("level_timeframe_class"),
            "prominence_above_pts": a.get("level_prominence_above_pts"),
            "prominence_below_pts": a.get("level_prominence_below_pts"),
            "roundness_major": a.get("level_roundness_major"),
            "roundness_minor": a.get("level_roundness_minor"),
            "equality_count": a.get("level_equality_count"),
            "session_range_consumed": ny_am_src[i0] if session == "ny_am" else np.nan,
        }

    return _simple_family(sweeps_store.by_type("SWEEP_CONFIRMED"), "sweep_confirmed", arrays, comp_arrays, outcomes, build, directional=True)


def extract_displacement_qualified(disp_store, arrays, comp_arrays, outcomes, eff_arr) -> pd.DataFrame:
    bvt_arr = comp_arrays["body_vs_tod"]
    cl_arr = comp_arrays["close_location"]
    vz_arr = comp_arrays["volume_z"]

    def build(ev, i0):
        a = ev.attributes
        bvt = bvt_arr[i0]
        cl = cl_arr[i0]
        vz = vz_arr[i0]
        eff = eff_arr[i0]
        return {
            "direction": "up" if a["direction"] == "bullish" else "down",
            "body": a.get("body"),
            "mean20_body": a.get("mean20_body"),
            "ratio": a.get("ratio"),
            "body_vs_tod_magnitude": abs(bvt) if np.isfinite(bvt) else np.nan,
            "close_location": cl if np.isfinite(cl) else np.nan,
            "volume_z": vz if np.isfinite(vz) else np.nan,
            "efficiency_12": eff if np.isfinite(eff) else np.nan,
        }

    return _simple_family(disp_store.by_type("DISPLACEMENT_QUALIFIED"), "displacement_qualified", arrays, comp_arrays, outcomes, build, directional=True)


def extract_mss(structure_store, arrays, comp_arrays, outcomes, eff_arr, ny_am_src) -> pd.DataFrame:
    def build(ev, i0):
        a = ev.attributes
        session = arrays.session[i0]
        eff = eff_arr[i0]
        return {
            "direction": "up" if a["direction"] == "bullish" else "down",
            "choch_bars_elapsed": a.get("choch_bars_elapsed"),
            "efficiency_12": eff if np.isfinite(eff) else np.nan,
            "session_range_consumed": ny_am_src[i0] if session == "ny_am" else np.nan,
        }

    return _simple_family(structure_store.by_type("MSS"), "mss", arrays, comp_arrays, outcomes, build, directional=True)


def extract_level_tested(levels_store, arrays, comp_arrays, outcomes) -> pd.DataFrame:
    def build(ev, i0):
        a = ev.attributes
        kind = a.get("kind")
        tc = a.get("test_count")
        return {
            "level_kind": kind,
            "test_count": tc,
            "test_number_ge2": (tc is not None and tc >= 2),
            "age_seconds": a.get("age_seconds"),
            "direction": level_direction_for_kind(kind),
        }

    return _simple_family(levels_store.by_type("LEVEL_TESTED"), "level_tested", arrays, comp_arrays, outcomes, build, directional=True)


def extract_fvg_tested(zones_store, arrays, comp_arrays, outcomes) -> pd.DataFrame:
    def build(ev, i0):
        a = ev.attributes
        fdir = a.get("direction")
        tc = a.get("test_count")
        return {
            "fvg_direction": fdir,
            "test_count": tc,
            "test_number_ge2": (tc is not None and tc >= 2),
            "impulse_id": a.get("impulse_id"),
            "direction": "up" if fdir == "bullish" else ("down" if fdir == "bearish" else None),
        }

    return _simple_family(zones_store.by_type("FVG_TESTED"), "fvg_tested", arrays, comp_arrays, outcomes, build, directional=True)


# --- conformance check (fast vectorized == slow per-event reference) ------------------


def _nan_eq(a: float, b: float) -> bool:
    if isinstance(a, float) and isinstance(b, float) and np.isnan(a) and np.isnan(b):
        return True
    return a == b


def _sample_positions(total: int, k: int = CONFORMANCE_SAMPLE) -> List[int]:
    if total <= k:
        return list(range(total))
    return sorted(set(np.linspace(0, total - 1, k).astype(int).tolist()))


def run_conformance_checks(stores, arrays, outcomes, eff_arr, level_test_baridx, levels_store) -> Dict[str, int]:
    """Proves the fast vectorized path == the slow per-event reference on a
    deterministic >=200-event sample per family. Aborts (AssertionError) on the first
    mismatch, BEFORE any real extraction/parquet write. PREREG §2 knowability + fast/
    slow fidelity guard."""
    _log("conformance: proving fast vectorized path == slow per-event reference...")
    checked: Dict[str, int] = {}

    families = {
        "excursion_episodes": stores["sweeps"].by_type("EXCURSION_OPEN"),
        "sweep_confirmed": stores["sweeps"].by_type("SWEEP_CONFIRMED"),
        "displacement_qualified": stores["displacement"].by_type("DISPLACEMENT_QUALIFIED"),
        "mss": stores["structure"].by_type("MSS"),
        "level_tested": stores["levels"].by_type("LEVEL_TESTED"),
        "fvg_tested": stores["zones"].by_type("FVG_TESTED"),
    }

    # (a) outcomes -- every family uses the same OutcomeArrays.
    n_out = 0
    for fam, events in families.items():
        for p in _sample_positions(len(events)):
            ev = events[p]
            i0 = arrays.index_by_close_time.get(ev.confirmed_at)
            if i0 is None:
                continue
            slow = raw_outcomes_at(arrays, i0)
            for h in outcomes.horizons:
                for fast_v, slow_v in (
                    (outcomes.fwd_raw[h][i0], slow[f"fwd_raw_{h}"]),
                    (outcomes.maxfav_raw[h][i0], slow[f"maxfav_raw_{h}"]),
                    (outcomes.maxadv_raw[h][i0], slow[f"maxadv_raw_{h}"]),
                ):
                    if not _nan_eq(float(fast_v), float(slow_v)):
                        raise AssertionError(
                            f"CONFORMANCE FAIL outcomes {fam} pos={p} i0={i0} h={h}: fast={fast_v} slow={slow_v}"
                        )
                    n_out += 1
    checked["outcome_value_comparisons"] = n_out

    # (b) efficiency_12 -- displacement + mss.
    n_eff = 0
    for fam in ("displacement_qualified", "mss"):
        for p in _sample_positions(len(families[fam])):
            ev = families[fam][p]
            i0 = arrays.index_by_close_time.get(ev.confirmed_at)
            if i0 is None:
                continue
            slow_v = efficiency_trailing_12(arrays, i0)
            fast_v = eff_arr[i0]
            if not _nan_eq(float(fast_v), float(slow_v)):
                raise AssertionError(f"CONFORMANCE FAIL efficiency_12 {fam} pos={p} i0={i0}: fast={fast_v} slow={slow_v}")
            n_eff += 1
    checked["efficiency_value_comparisons"] = n_eff

    # (c) prior_test_count -- excursion (the quadratic feature we vectorized). Slow =
    # the literal list-filter the naive path used; fast = searchsorted.
    tests_by_level: Dict[str, List[CausalEvent]] = {}
    for ev in levels_store.by_type("LEVEL_TESTED"):
        tests_by_level.setdefault(ev.source_event_ids[0], []).append(ev)
    for lst in tests_by_level.values():
        lst.sort(key=lambda e: e.confirmed_at)
    open_events = stores["sweeps"].by_type("EXCURSION_OPEN")
    n_ptc = 0
    for p in _sample_positions(len(open_events)):
        ev = open_events[p]
        t0 = ev.confirmed_at
        i0 = arrays.index_by_close_time.get(t0)
        level_id = ev.attributes["level_id"]
        slow_ct = len([e for e in tests_by_level.get(level_id, []) if e.confirmed_at < t0])
        arr = level_test_baridx.get(level_id)
        fast_ct = int(np.searchsorted(arr, i0, side="left")) if (arr is not None and arr.size) else 0
        if slow_ct != fast_ct:
            raise AssertionError(f"CONFORMANCE FAIL prior_test_count pos={p} level={level_id}: fast={fast_ct} slow={slow_ct}")
        n_ptc += 1
    checked["prior_test_count_comparisons"] = n_ptc

    _log(f"conformance: PASSED — {checked}")
    return checked


# --- top-level pipeline ---------------------------------------------------------------


def run_extraction() -> Dict[str, Any]:
    t_start = time.time()
    timings: Dict[str, float] = {}

    t = time.time()
    bars = build_bars()
    timings["frame_build_s"] = round(time.time() - t, 2)
    _log(f"frame built: {len(bars):,} bars ({timings['frame_build_s']}s)")

    t = time.time()
    arrays = build_bar_arrays(bars)
    timings["baseline_arrays_s"] = round(time.time() - t, 2)
    _log(f"baseline arrays built ({timings['baseline_arrays_s']}s)")

    t = time.time()
    stores = run_engines(bars)
    timings["engines_run_s"] = round(time.time() - t, 2)

    t = time.time()
    disp_index = build_displacement_component_index(stores["displacement"])
    comp_arrays = build_component_arrays(arrays, disp_index)
    outcomes = build_outcome_arrays(arrays)
    eff_arr = build_efficiency_array(arrays)
    ny_am_src = build_ny_am_session_range_consumed(arrays)
    level_test_baridx = build_level_test_baridx_index(stores["levels"], arrays.index_by_close_time)
    timings["derived_arrays_s"] = round(time.time() - t, 2)
    _log(f"derived arrays built ({timings['derived_arrays_s']}s)")

    t = time.time()
    conformance = run_conformance_checks(stores, arrays, outcomes, eff_arr, level_test_baridx, stores["levels"])
    timings["conformance_s"] = round(time.time() - t, 2)

    t = time.time()
    dfs: Dict[str, pd.DataFrame] = {}
    dfs["excursion_episodes"] = extract_excursion_episodes(stores["sweeps"], arrays, comp_arrays, outcomes, level_test_baridx)
    dfs["sweep_confirmed"] = extract_sweep_confirmed(stores["sweeps"], arrays, comp_arrays, outcomes, eff_arr, ny_am_src)
    dfs["displacement_qualified"] = extract_displacement_qualified(stores["displacement"], arrays, comp_arrays, outcomes, eff_arr)
    dfs["mss"] = extract_mss(stores["structure"], arrays, comp_arrays, outcomes, eff_arr, ny_am_src)
    dfs["level_tested"] = extract_level_tested(stores["levels"], arrays, comp_arrays, outcomes)
    dfs["fvg_tested"] = extract_fvg_tested(stores["zones"], arrays, comp_arrays, outcomes)
    timings["feature_extraction_s"] = round(time.time() - t, 2)

    unsplit_counts = {name: int(df["split"].isna().sum()) for name, df in dfs.items()}

    os.makedirs(DATA_DIR, exist_ok=True)
    t = time.time()
    for name, df in dfs.items():
        is_df = df[df["split"] == "IS"].drop(columns=["split"]).reset_index(drop=True)
        holdout_df = df[df["split"] == "HOLDOUT"].drop(columns=["split"]).reset_index(drop=True)
        is_df.to_parquet(os.path.join(DATA_DIR, f"{name}_is.parquet"), index=False)
        holdout_df.to_parquet(os.path.join(DATA_DIR, f"{name}_holdout.parquet"), index=False)
        _log(f"wrote {name}: IS={len(is_df):,} HOLDOUT={len(holdout_df):,}")
    timings["parquet_write_s"] = round(time.time() - t, 2)

    per_engine_event_counts = {name: {et: len(store.by_type(et)) for et in _event_types(store)} for name, store in stores.items()}
    timings["total_s"] = round(time.time() - t_start, 2)

    return {
        "dfs": dfs,
        "timings": timings,
        "unsplit_counts": unsplit_counts,
        "per_engine_event_counts": per_engine_event_counts,
        "knowability_checks": _KNOWABILITY_CHECKS,
        "knowability_violations": _KNOWABILITY_VIOLATIONS,
        "conformance": conformance,
        "n_bars": arrays.n,
    }


def _event_types(store: EventStore) -> List[str]:
    seen: List[str] = []
    for ev in store.all:
        if ev.event_type not in seen:
            seen.append(ev.event_type)
    return seen


if __name__ == "__main__":
    result = run_extraction()
    print("timings:", result["timings"])
    print("knowability_checks:", result["knowability_checks"], "violations:", result["knowability_violations"])
    for name, df in result["dfs"].items():
        print(name, len(df), "IS:", int((df["split"] == "IS").sum()), "HOLDOUT:", int((df["split"] == "HOLDOUT").sum()))
