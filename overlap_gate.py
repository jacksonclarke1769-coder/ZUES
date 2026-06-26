"""
OVERLAP SIZING GATE — cross-strategy concurrency sizing for the live stack (A / B / Momentum).

WHY (validated in research/momentum_overlap_eval.py): the strategies NEVER trade opposite concurrently,
but they DO stack same-direction ~12% of the time, and naive full-size stacking is the correlated tail
that hurts the prop EVAL (pass 83%->79%) and DOUBLES funded busts (4->8). HALF-sizing the 2nd
same-direction concurrent trade keeps ~74% of the added income, restores eval pass to ~82%, and makes
the worst day SMALLER than A+B alone. This gate implements that half-overlap policy.

POLICY: when a NEW signal fires, if ANY OTHER participating strategy already holds an open position in
the SAME direction, the new order is sized down by `factor` (default 0.5, floored at `min_qty`). Opposite
direction or no concurrent position -> full size. A strategy never gates itself.

USAGE (the bot owns ONE shared gate across strategies):
    gate.on_open("A", +1)                              # when a strategy's entry is actually placed
    qty, halved = gate.size("MOM", +1, base_qty=2)     # when a new signal fires -> the qty to send
    gate.on_close("A")                                 # when its position resolves / is flattened

FAIL-SAFE: never raises; on any error `size()` returns the base qty (never a surprise downsize, never 0).
RESTART-SAFE: snapshot()/restore() persist the open-position map.
RESEARCH-BACKED, NOT YET WIRED LIVE — Momentum needs an execution path first; A/B can opt in via participants.
"""
from __future__ import annotations

import math

LONG, SHORT = 1, -1
_DIR = {"long": LONG, "short": SHORT, "buy": LONG, "sell": SHORT, LONG: LONG, SHORT: SHORT}


def _norm(direction):
    d = _DIR.get(direction if not isinstance(direction, str) else direction.lower())
    if d is None:
        raise ValueError(f"bad direction {direction!r}")
    return d


class OverlapGate:
    def __init__(self, factor=0.5, min_qty=1, enabled=True, participants=None):
        self.factor = float(factor)
        self.min_qty = int(min_qty)
        self.enabled = bool(enabled)
        # None = every strategy participates; else only these names are gated / counted
        self.participants = set(participants) if participants is not None else None
        self.open = {}            # strategy -> direction (+1/-1) of its currently-open position
        self.halved = 0           # count of orders downsized this run (telemetry)

    def _in(self, strategy):
        return self.participants is None or strategy in self.participants

    # ---- position lifecycle (call from the bot when entries place / positions resolve) ----
    def on_open(self, strategy, direction):
        try:
            self.open[strategy] = _norm(direction)
        except Exception as e:                              # noqa: BLE001 — never break trading
            print(f"[overlap] on_open ignored ({e})", flush=True)

    def on_close(self, strategy):
        self.open.pop(strategy, None)

    # ---- query ----
    def concurrent_same_dir(self, strategy, direction):
        """True if another PARTICIPATING strategy holds an open position in the same direction."""
        try:
            d = _norm(direction)
        except Exception:
            return False
        if not self._in(strategy):
            return False
        return any(s != strategy and od == d and self._in(s) for s, od in self.open.items())

    # ---- the sizing decision ----
    def size(self, strategy, direction, base_qty):
        """Return (qty_to_send, halved?). Halved when a same-dir concurrent position exists. Fail-safe."""
        try:
            base = int(base_qty)
            if not self.enabled or base <= 0 or not self._in(strategy):
                return base, False
            if not self.concurrent_same_dir(strategy, direction):
                return base, False
            q = max(self.min_qty, int(math.floor(base * self.factor)))
            q = min(q, base)                                # never size UP
            self.halved += int(q < base)
            return q, q < base
        except Exception as e:                              # noqa: BLE001 — sizing must never break trading
            print(f"[overlap] size fail-safe to base ({e})", flush=True)
            try:
                return int(base_qty), False
            except Exception:
                return base_qty, False

    # ---- restart safety ----
    def snapshot(self):
        return dict(open=dict(self.open), halved=self.halved)

    def restore(self, state):
        if not state:
            return
        try:
            self.open = {k: int(v) for k, v in (state.get("open") or {}).items()}
            self.halved = int(state.get("halved", 0))
        except Exception as e:                              # noqa: BLE001
            print(f"[overlap] restore ignored ({e})", flush=True)
