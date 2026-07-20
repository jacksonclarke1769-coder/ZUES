"""
Lookahead self-test (shift-invariance) for the HTF confluence chain's detectors —
self_test.py pattern (backtests/zeus-ict-2026-07/concept_survey/self_test.py), adapted.
Truncating the future must not change past signals: build the full candidate pipeline on
the buffered window and on a truncated copy (last N 1m bars dropped); every candidate
confirmed more than a safety margin before the truncation point must be byte-identical
(direction, mode, entry_price, stop_price, invalidate_price, conf_ts) between the two runs.
Also checks the 1H bias series itself. Abort (non-zero exit) if any detector fails.
"""
import sys

import numpy as np
import pandas as pd

from chain import (BUFFER_START, WINDOW_END, load_1m, build_all)

TRUNCATE_1M_BARS = 8000       # ~5.5 days dropped from the end
MARGIN = pd.Timedelta(days=3)  # >> max forward dependency (8*15m=2h arm window + fractal 3/3)


def _cand_key_set(cand: pd.DataFrame, cutoff_ts):
    if cand is None or not len(cand):
        return set()
    sub = cand[cand["conf_ts"] < cutoff_ts]
    keys = set()
    for r in sub.itertuples(index=False):
        keys.add((int(r.direction), r.mode, round(float(r.entry_price), 4),
                   round(float(r.stop_price), 4), round(float(r.invalidate_price), 4),
                   r.conf_ts))
    return keys


def _bias_key_set(bias_ctx: dict, cutoff_ts):
    conf_ts = bias_ctx["conf_ts"]
    bias = bias_ctx["bias"]
    mask = conf_ts < cutoff_ts
    return set(zip(conf_ts[mask].astype(str), bias[mask].round(4)))


def run():
    df1m_full = load_1m()
    df1m_full = df1m_full.loc[BUFFER_START:WINDOW_END]
    df1m_trunc = df1m_full.iloc[:-TRUNCATE_1M_BARS]

    ctx_full = build_all(df1m_full)
    ctx_trunc = build_all(df1m_trunc)

    trunc_end_ts = df1m_trunc.index[-1]
    cutoff = trunc_end_ts - MARGIN

    all_ok = True

    kf_bias = _bias_key_set(ctx_full["bias_ctx"], cutoff)
    kt_bias = _bias_key_set(ctx_trunc["bias_ctx"], cutoff)
    ok = kf_bias == kt_bias
    print(f"[{'OK' if ok else 'FAIL'}] detector=1H_bias full={len(kf_bias)} trunc={len(kt_bias)}")
    if not ok:
        all_ok = False
        print("   missing_in_trunc:", list(kf_bias - kt_bias)[:5])
        print("   extra_in_trunc:  ", list(kt_bias - kf_bias)[:5])

    kf_cand = _cand_key_set(ctx_full["candidates"], cutoff)
    kt_cand = _cand_key_set(ctx_trunc["candidates"], cutoff)
    ok = kf_cand == kt_cand
    print(f"[{'OK' if ok else 'FAIL'}] detector=chain_candidates(sweep+FVG+disp) "
          f"full={len(kf_cand)} trunc={len(kt_cand)}")
    if not ok:
        all_ok = False
        print("   missing_in_trunc:", list(kf_cand - kt_cand)[:5])
        print("   extra_in_trunc:  ", list(kt_cand - kf_cand)[:5])

    # sweeps too (Condition 2 alone)
    def sweep_key_set(sw, cutoff_ts):
        if not len(sw):
            return set()
        sub = sw[sw["conf_ts"] < cutoff_ts]
        return set(zip(sub["idx"].astype(int), sub["direction"].astype(int),
                        sub["extreme"].round(4), sub["conf_ts"].astype(str)))

    kf_sw = sweep_key_set(ctx_full["sweeps"], cutoff)
    kt_sw = sweep_key_set(ctx_trunc["sweeps"], cutoff)
    ok = kf_sw == kt_sw
    print(f"[{'OK' if ok else 'FAIL'}] detector=15m_sweep full={len(kf_sw)} trunc={len(kt_sw)}")
    if not ok:
        all_ok = False
        print("   missing_in_trunc:", list(kf_sw - kt_sw)[:5])
        print("   extra_in_trunc:  ", list(kt_sw - kf_sw)[:5])

    if not all_ok:
        print("LOOKAHEAD SELF-TEST FAILED — ABORT")
        sys.exit(1)
    print("LOOKAHEAD SELF-TEST: ALL HTF-CHAIN DETECTORS PASS (shift-invariant)")


if __name__ == "__main__":
    run()
