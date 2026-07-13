"""WP-D `parity/model01_canary.py`: the 581/581 dual-implementation gate.

Two tests:
  * `test_parity_fast_subset` -- CI-time (~6s), a ~7-month real-data slice (first
    40,000 certified 5m bars). The oracle is regenerated FRESH on the SAME slice (not
    the static 581-row reference CSV, which was built over the full 5.5yr dataset and
    isn't comparable to a truncated V2 run bar-for-bar) -- a genuine, self-contained
    dual-implementation check, just over less data. Runs on every plain
    `pytest research/ict_v2/tests -q`.
  * `test_parity_full_581_certified_signals` -- the complete real dataset (5.5yr,
    353,952 5m bars), reproducing the certified 581-signal set exactly. Slow (~1min);
    SKIPPED unless `--full` is passed (see `tests/conftest.py`) so it doesn't blow the
    repo's plain-`pytest -q` time budget. Run once, result recorded in
    `reports/ict_v2/parity_canary_summary.json` and the Phase-2 report.
"""
from __future__ import annotations

import pytest

from research.ict_v2.parity import model01_canary as C


def test_parity_fast_subset():
    df5 = C.load_certified_5m()
    df5_sub = df5.iloc[:40_000]  # ~7 months, ample warmup for every V2/oracle roller

    oracle_raw = C.regenerate_oracle_candidates(df5_sub)
    v2_raw, _store = C.run_v2_walk(df5_sub)
    oracle_pop = C.apply_certified_selection(oracle_raw, df5_sub)
    v2_pop = C.apply_certified_selection(v2_raw, df5_sub)

    result = C.compare_signal_sets(oracle_pop, v2_pop, df5_sub)
    assert result["mismatched"] == [], result["mismatched"]
    assert result["oracle_count"] == result["v2_count"] == result["matched"]
    assert result["oracle_count"] > 0, "fast subset produced zero signals -- widen the slice"


@pytest.mark.slow
def test_parity_full_581_certified_signals(request):
    if not request.config.getoption("--full"):
        pytest.skip("full-dataset (5.5yr) parity run only executes with --full; see conftest.py")

    result = C.run_full_parity()

    assert result["mismatched"] == [], result["mismatched"]
    assert result["oracle_count"] == 581
    assert result["v2_count"] == 581
    assert result["matched"] == 581
    assert all(v == 0 for v in result["building_block_selfcheck_mismatches"].values()), result[
        "building_block_selfcheck_mismatches"
    ]
