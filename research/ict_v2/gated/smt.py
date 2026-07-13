"""Formal SMT (Smart Money Technique / inter-market divergence) interface -- STUB.

A real causal V2 SMT detector needs its own swing/sweep engine run on a
synchronized second instrument (ES), which is out of scope for WP-A/B/C. Note:
the frozen framework's `smt_bull`/`smt_bear` feature columns (used by model01's
Model 8 variant) are a pre-computed convenience flag from that OTHER, non-causal
pipeline -- they are NOT a substitute for this interface and must not be wired
into V2 engines as if they were a certified V2 detector.
"""
from __future__ import annotations

from typing import Any

from . import DataGated

__all__ = ["DataGated", "SMTInterface"]


class SMTInterface:
    """Placeholder surface for formal (causal, V2-native) SMT divergence between
    the primary instrument and a synchronized second instrument. Gated: no
    second-instrument engine is built in Phase 2."""

    def divergence(self, primary_bar: Any, secondary_bar: Any) -> bool:
        raise DataGated(
            "formal SMT: ES-synchronized second-instrument V2 engine not built in Phase 2 (docket D1)"
        )
