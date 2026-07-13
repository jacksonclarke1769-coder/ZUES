"""WP-D integration run (SPEC.md work package WP-D, item 2): the complete V2 engine
stack (every WP-B + WP-C engine, via `core.runner.BatchRunner`) over >=1 full month of
real certified 5m data. Engineering evidence only -- event counts, timestamps, a
deterministic content hash, wall-clock runtime, and prefix-invariance on a sample of
engines. NO performance/PF/WR/expectancy statistics of any kind anywhere in this
module or its output.

Month selected: **2025-03** (real Databento NQ 5m, `apex_eval_eod_databento.py`'s
certified loader) -- a full calendar month, 26 trading days, 5,868 bars, no data gaps
beyond ordinary weekend/maintenance closures, and it happens to span the 2025-03-09 US
DST spring-forward transition (a useful extra stress case for `SessionEngine`, not a
requirement).

Engines registered (every engine in `research/ict_v2/engines/`, `gated/*` excluded --
those are intentionally-inert DataGated stubs, SPEC.md "Court docket D1"):
`swings_a` (3/3), `swings_b`, `swings_c`, `structure`, `displacement`, `levels`,
`opening_range`, `overnight`, `sweeps`, `zones`, `ranges`, `amd`.

FINDING (recorded here, not fixed -- SPEC.md forbids Phase-2 param tuning): `amd`
produces ZERO events over this month (and separately verified zero over a full real
year, ~60,000 bars) -- the v0 `ACCUMULATION_ACTIVE` threshold (rolling 12-bar range <
0.6x ATR20 for >=6 consecutive bars) never triggers on real NQ 5m data in this sample
(observed minimum 12-bar-range/ATR20 ratio over a full year: 0.71, never below 0.6).
`engines/amd.py`'s own synthetic tests (`tests/test_amd.py`) confirm the FSM logic
itself is correct when the threshold IS met -- this is a v0-parameter-calibration
observation (SPEC.md: v0 pins are "RECORDED CONVENTIONS, not tuned values"), not a
code defect; flagged for Fable's review, non-blocking, no code changed here.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List

import pandas as pd

from ..core.prefix import assert_prefix_invariant
from ..core.runner import BatchRunner
from ..engines.amd import AmdEngine
from ..engines.displacement import DisplacementEngine
from ..engines.levels import LevelRegistry
from ..engines.opening_range import OpeningRangeEngine
from ..engines.overnight import OvernightEngine
from ..engines.ranges import RangesEngine
from ..engines.structure import StructureEngine
from ..engines.sweeps import SweepEngine
from ..engines.swings import SwingMethodA, SwingMethodB, SwingMethodC
from ..engines.zones import ZonesEngine
from .model01_canary import BOT_REPO, bars_from_df5, load_certified_5m

MONTH = "2025-03"

_ENGINE_FACTORIES = {
    "swings_a": lambda: SwingMethodA(),
    "swings_b": lambda: SwingMethodB(),
    "swings_c": lambda: SwingMethodC(),
    "structure": lambda: StructureEngine(),
    "displacement": lambda: DisplacementEngine(),
    "levels": lambda: LevelRegistry(),
    "opening_range": lambda: OpeningRangeEngine(),
    "overnight": lambda: OvernightEngine(),
    "sweeps": lambda: SweepEngine(),
    "zones": lambda: ZonesEngine(),
    "ranges": lambda: RangesEngine(),
    "amd": lambda: AmdEngine(),
}

# SPEC.md: "at least 3 engines (levels, sweeps, zones)"
_PREFIX_INVARIANCE_ENGINES = ("levels", "sweeps", "zones")
_PREFIX_INVARIANCE_N_CUTS = 20


def select_month(df5: pd.DataFrame, month: str = MONTH) -> pd.DataFrame:
    start = pd.Timestamp(f"{month}-01", tz="America/New_York")
    end = start + pd.offsets.MonthBegin(1)
    return df5[(df5.index >= start) & (df5.index < end)]


def _even_cuts(n_bars: int, n_cuts: int) -> List[int]:
    """`n_cuts` evenly-spaced 1-based cut positions in [1, n_bars]."""
    if n_bars <= n_cuts:
        return list(range(1, n_bars + 1))
    step = n_bars / n_cuts
    cuts = sorted({min(n_bars, max(1, round(k * step))) for k in range(1, n_cuts + 1)})
    return cuts


def run_integration(out_path: str = None) -> Dict[str, Any]:
    t_start = time.time()
    df5_full = load_certified_5m()
    df5 = select_month(df5_full, MONTH)
    bars = bars_from_df5(df5)
    n_bars = len(bars)

    runner = BatchRunner()
    for name, factory in _ENGINE_FACTORIES.items():
        runner.register(name, factory())
    stores = runner.run(bars)

    per_engine: Dict[str, Any] = {}
    all_event_ids_ordered: List[str] = []
    first_ts, last_ts = None, None
    for name in _ENGINE_FACTORIES:  # deterministic iteration order
        store = stores[name]
        by_type: Dict[str, int] = {}
        for ev in store.all:
            by_type[ev.event_type] = by_type.get(ev.event_type, 0) + 1
            all_event_ids_ordered.append(f"{name}:{ev.event_id}")
            if first_ts is None or ev.confirmed_at < first_ts:
                first_ts = ev.confirmed_at
            if last_ts is None or ev.confirmed_at > last_ts:
                last_ts = ev.confirmed_at
        per_engine[name] = {"total_events": len(store), "by_event_type": by_type}

    h = hashlib.sha256()
    for eid in all_event_ids_ordered:
        h.update(eid.encode("ascii"))
    store_hash = h.hexdigest()

    prefix_invariance_results: Dict[str, Any] = {}
    cuts = _even_cuts(n_bars, _PREFIX_INVARIANCE_N_CUTS)
    for name in _PREFIX_INVARIANCE_ENGINES:
        factory = _ENGINE_FACTORIES[name]
        try:
            assert_prefix_invariant(factory, bars, cuts=cuts)
            prefix_invariance_results[name] = {"passed": True, "cuts_checked": cuts}
        except AssertionError as exc:
            prefix_invariance_results[name] = {"passed": False, "cuts_checked": cuts, "error": str(exc)}

    wall_clock_s = time.time() - t_start

    result = {
        "month": MONTH,
        "n_bars_5m": n_bars,
        "data_range": {"start": df5.index.min().isoformat(), "end": df5.index.max().isoformat()},
        "engines": list(_ENGINE_FACTORIES),
        "per_engine": per_engine,
        "first_event_confirmed_at": first_ts.isoformat() if first_ts else None,
        "last_event_confirmed_at": last_ts.isoformat() if last_ts else None,
        "store_hash": store_hash,
        "store_hash_definition": (
            "sha256 over '<engine_name>:<event_id>' for every event across all 12 "
            "registered engines, in engine-registration order then store insertion "
            "order (deterministic; engine_id is itself a sha256 of event identity, "
            "core/events.py::compute_event_id)."
        ),
        "prefix_invariance": {
            "n_cuts": _PREFIX_INVARIANCE_N_CUTS,
            "engines_checked": list(_PREFIX_INVARIANCE_ENGINES),
            "results": prefix_invariance_results,
        },
        "wall_clock_seconds": round(wall_clock_s, 3),
        "findings": [
            "amd: 0 events this month (v0 ACCUMULATION_ACTIVE threshold never reached on "
            "real NQ 5m data in this sample; see module docstring FINDING; not a code "
            "defect -- engines/amd.py's own synthetic tests confirm the FSM triggers "
            "correctly when the threshold IS met)."
        ],
    }

    out_path = out_path or os.path.join(BOT_REPO, "reports", "ict_v2", "integration_run_summary.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    return result


if __name__ == "__main__":
    res = run_integration()
    print(json.dumps({k: v for k, v in res.items() if k != "per_engine"}, indent=2, default=str))
    for name, info in res["per_engine"].items():
        print(name, info["total_events"], info["by_event_type"])
