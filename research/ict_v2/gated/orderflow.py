"""Order-flow / depth interface -- STUB (Court docket D1: no live depth/OFI feed
wired up in Phase 2). `engines/displacement.py` (WP-B) will call this once real
data lands; until then every method raises `DataGated` and the corresponding
event attributes stay `None` + `data_gated=True`.
"""
from __future__ import annotations

from typing import Any

from . import DataGated

__all__ = ["DataGated", "OrderFlowInterface"]


class OrderFlowInterface:
    """Placeholder surface for order-flow-imbalance / depth-imbalance / spread.
    No implementation exists in Phase 2 -- every call is gated."""

    def ofi(self, bar: Any) -> float:
        """Order-flow imbalance for `bar`. Gated: no live depth feed."""
        raise DataGated("order-flow imbalance: no live depth feed wired up in Phase 2 (docket D1)")

    def depth_imbalance(self, bar: Any) -> float:
        """Bid/ask depth imbalance for `bar`. Gated: no live depth feed."""
        raise DataGated("depth imbalance: no live depth feed wired up in Phase 2 (docket D1)")

    def spread(self, bar: Any) -> float:
        """Quoted bid/ask spread at `bar`. Gated: no live depth feed."""
        raise DataGated("spread: no live depth feed wired up in Phase 2 (docket D1)")
