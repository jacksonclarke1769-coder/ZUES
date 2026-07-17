"""WP-E entry point: builds the roll-adjusted frame, asserts it against the
certified unadjusted WP-D frame, runs the full extraction pipeline
(`extract.run_extraction`), and writes the counts-only report
(`reports/ict_v2/03a_phase3_extraction_counts.md`). Run as a script:

    python3 -m research.ict_v2.phase3.run_wp_e

Prints a compact final summary to stdout. Never reads back the HOLDOUT parquet
files it just wrote (PREREG §6/§8).
"""
from __future__ import annotations

import json
import time

from . import extract as ex
from . import frame as fr
from . import report as rp


def main() -> None:
    t_start = time.time()
    print("verifying roll-adjusted frame against certified unadjusted WP-D frame...", flush=True)
    verify = fr.verify_against_unadjusted()
    print(json.dumps(verify, indent=2), flush=True)
    if not (verify["bar_counts_exactly_equal"] and verify["timestamp_index_identical"]):
        raise AssertionError(f"frame verification FAILED: {verify}")

    print("running extraction pipeline (engines + features + outcomes)...", flush=True)
    result = ex.run_extraction()
    print("timings:", result["timings"], flush=True)
    print("knowability_checks:", result["knowability_checks"], "violations:", result["knowability_violations"], flush=True)

    dfs = result["dfs"]
    dfs_is = {name: df[df["split"] == "IS"].drop(columns=["split"]).reset_index(drop=True) for name, df in dfs.items()}
    dfs_holdout = {name: df[df["split"] == "HOLDOUT"].drop(columns=["split"]).reset_index(drop=True) for name, df in dfs.items()}

    for name in dfs:
        print(f"{name}: total={len(dfs[name]):,} IS={len(dfs_is[name]):,} HOLDOUT={len(dfs_holdout[name]):,}", flush=True)

    print("writing counts report...", flush=True)
    report_path = rp.write_report(
        frame_assertion=verify,
        dfs_is=dfs_is,
        dfs_holdout=dfs_holdout,
        timings=result["timings"],
        knowability_checks=result["knowability_checks"],
        knowability_violations=result["knowability_violations"],
        per_engine_event_counts=result["per_engine_event_counts"],
        unsplit_counts=result["unsplit_counts"],
        conformance=result.get("conformance"),
    )
    print("report written:", report_path, flush=True)
    print("total wall clock:", round(time.time() - t_start, 1), "s", flush=True)


if __name__ == "__main__":
    main()
