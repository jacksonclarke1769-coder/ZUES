"""Cell enumeration + shared context builder for the 36-cell survey."""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import LONG, SHORT, load_1m
from survey_engine import build_tf_context, df1m_to_arrays, run_cell, cell_stats

CONCEPT_NAMES = ["FVG", "IFVG", "OB", "Breaker", "Sweep", "MSS"]
TFS = [1, 5, 15]
DIRECTIONS = [(LONG, "long"), (SHORT, "short")]


def cell_key(concept, tf, dir_name):
    return f"{concept}_{tf}m_{dir_name}"


def all_cells():
    for concept in CONCEPT_NAMES:
        for tf in TFS:
            for d, dname in DIRECTIONS:
                yield concept, tf, d, dname


def build_all_contexts(df1m: pd.DataFrame) -> dict:
    return {tf: build_tf_context(df1m, tf) for tf in TFS}


def run_all_cells(df1m: pd.DataFrame, contexts: dict, window_start, window_end) -> dict:
    arrs = df1m_to_arrays(df1m)
    out = {}
    for concept, tf, d, dname in all_cells():
        ctx = contexts[tf]
        tr = run_cell(arrs, ctx, concept, d, window_start, window_end)
        out[cell_key(concept, tf, dname)] = tr
    return out


def stats_table(trades_by_cell: dict) -> dict:
    return {k: cell_stats(v) for k, v in trades_by_cell.items()}
