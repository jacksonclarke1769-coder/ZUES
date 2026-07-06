"""vpc_trail.py — PHASE-0-SIM-ONLY — canonical VPC trail; not imported by any live path yet; the
future live manager will call THIS, never a second implementation.

Extracted, behavior-preserving, from the exit re-walk loop that previously lived inline in
`tools_vpc_1m_truth.py` (vpc_1m_truth_trades(), roughly lines 222-246). This module makes NO
modeling changes — it is a mechanical extraction of the exact existing semantics into a reusable
unit:
  - `VpcTrail` — a STATEFUL STEPPER: the single per-bar unit that both a historical replay loop
    (walk_1m_trail below) and a future live bar-close feed can call, one bar at a time, so there is
    never a second implementation of the trail logic.
  - `walk_1m_trail` — a pure historical wrapper that reproduces the CURRENT 1m-truth re-walk loop
    exactly, including the 5m-boundary advance (`j5`) and the `atr_now = A[j5-1]` (fallback
    `A[ei-1]`) ATR-selection logic, and the EOD fallback exit (`C1[last]`).

Rules preserved exactly (do NOT "improve" these — this is a behavior-preserving extraction):
  - ADVERSE-FIRST ordering: the stop check on each bar uses the stop level established BEFORE that
    bar's own close is folded into the trail (the trail update happens strictly after the stop
    check, taking effect only from the next bar onward).
  - Peak tracking is on 1-minute CLOSE (not high/low), mirrored for shorts.
  - The trail ratchet is one-directional: `stop = max(stop, candidate)` for longs,
    `min(stop, candidate)` for shorts — structurally incapable of loosening the stop.
  - `d == 1` means long; any other value (the codebase uses `-1`) means short — same convention as
    `nq_vwap_pullback.vpc_signals()` / `tools_vpc_1m_truth.vpc_1m_truth_trades()`.

No live-path file imports this module yet (LIVE HOLD ACTIVE, PHASE-0-SIM-ONLY).
"""
import numpy as np


class VpcTrail:
    """Stateful per-trade trail stepper. Call `step()` once per bar (bar-close semantics — the
    caller decides bar granularity/timing; this class only tracks stop/peak state and applies the
    adverse-first check + one-directional ratchet)."""

    def __init__(self, entry, direction, init_stop_dist, trail_atr):
        self.entry = entry
        self.direction = direction
        self.trail_atr = trail_atr
        long = (direction == 1)
        self.stop = entry - init_stop_dist if long else entry + init_stop_dist
        self.peak = entry
        self.stop_path = []

    def step(self, bar_low, bar_high, bar_close, atr_now):
        """Advance the trail by exactly one bar.

        Returns (exit_flag, stop_level):
          - exit_flag = "stop" if this bar's low/high touched the stop set BEFORE this bar
            (adverse-first) -> stop_level is the exit price (self.stop, unchanged this bar).
          - exit_flag = None otherwise -> stop_level is the (possibly ratcheted) new stop after
            folding this bar's close into the peak.
        """
        long = (self.direction == 1)
        hit = (bar_low <= self.stop) if long else (bar_high >= self.stop)
        if hit:
            return ("stop", self.stop)
        self.peak = max(self.peak, bar_close) if long else min(self.peak, bar_close)
        cand = (self.peak - self.trail_atr * atr_now) if long else (self.peak + self.trail_atr * atr_now)
        new = max(self.stop, cand) if long else min(self.stop, cand)
        assert (new >= self.stop) if long else (new <= self.stop), "trail ratchet moved AGAINST price"
        self.stop_path.append((self.stop, new))
        self.stop = new
        return (None, new)


def walk_1m_trail(idx1_slice, H1, L1, C1, A5, idx5, ei, entry, direction, init_stop_dist, trail_atr):
    """Pure historical wrapper: reproduces the CURRENT 1m-truth exit re-walk loop EXACTLY (see
    module docstring), driving a `VpcTrail` one 1-minute bar at a time.

    Parameters (all arrays/positions as already used by the caller — no re-derivation here):
      idx1_slice, H1, L1, C1 -- the 1-minute timestamp/high/low/close arrays for this trade's day,
                                 already sliced to start at the entry's 1m bar (i.e. what the caller
                                 previously indexed as `idx1[a1:]`, `H1[a1:]`, etc.).
      A5, idx5               -- the day's 5-MINUTE atr/timestamp arrays (full day, unsliced — `ei`
                                 is this trade's entry position within them).
      ei                     -- entry's position (index) within the day's 5-minute bars.
      entry, direction        -- entry price and direction (1=long, else short).
      init_stop_dist          -- the initial stop distance (points) used to seed the trail.
      trail_atr               -- the trail's ATR multiplier.

    Returns (exit_px, exit_reason, stop_path):
      exit_reason is "stop" or "eod". stop_path is the list of (old_stop, new_stop) tuples the
      trail ratcheted through (empty if the trade stopped out on its very first bar).
    """
    n = len(idx5)
    trail = VpcTrail(entry, direction, init_stop_dist, trail_atr)
    j5 = ei
    exit_px = None
    exit_reason = None
    for x in range(len(idx1_slice)):
        while j5 + 1 < n and idx1_slice[x] >= idx5[j5 + 1]:
            j5 += 1
        atr_prev = A5[j5 - 1] if j5 - 1 >= 0 else np.nan
        atr_now = atr_prev if not np.isnan(atr_prev) else A5[ei - 1]
        flag, level = trail.step(L1[x], H1[x], C1[x], atr_now)
        if flag == "stop":
            exit_px = level
            exit_reason = "stop"
            break
    if exit_px is None:
        exit_px = C1[len(idx1_slice) - 1]
        exit_reason = "eod"
    return exit_px, exit_reason, trail.stop_path
