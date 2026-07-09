"""
Generic bar-walk exit resolver for the SMC3 exit-model audit (STEP 3).

One function replays ANY of the ~30 exit models battery over a frozen entry
(entry price/stop/risk are FROZEN from the SMC3 baseline; only the exit
logic varies).  Costs mirror smc3_engine.py's convention exactly:
  * $2.50/side commission, 1 tick (0.25pt) adverse slippage, PER FILL.
  * A single-exit (100% qty) trade pays 2 sides (entry+exit) = $5, matching
    the frozen baseline exactly.
  * A partial-exit trade pays 1 (entry) + n_legs_filled (each its own exit
    fill) sides -- i.e. EACH tranche bears its own $2.50 + 1 tick, per the
    audit spec ("per tranche for partials").
  * Stop-first-within-a-bar convention (mirrors smc3_engine / sweep_engine).

Research-only.
"""
from __future__ import annotations
import numpy as np

POINT_VALUE = 20.0
TICK = 0.25
COMMISSION_PER_SIDE = 2.50
SLIPPAGE_TICKS = 1.0
LONG, SHORT = 1, -1


def simulate(h: np.ndarray, l: np.ndarray, c: np.ndarray, t_open_ns: np.ndarray,
            entry_idx: int, dir_: int, entry: float, stop: float, risk_pts: float,
            legs: list, horizon_idx: int, time_cutoff_idx: int | None = None,
            effective_stop_initial: float | None = None,
            cost_mult: float = 1.0, extra_slip_pts: float = 0.0):
    """
    legs: list of dicts, SORTED nearest-to-entry first (favorable direction):
          {"qty": float (0,1], "price": float, "tag": str,
           "move_stop_to": float|None}
    Returns a dict: R, net_dollars, exit_reason (tag of the LAST fill),
          exit_time_ns, hold_min, n_legs_filled, legs_hit (list of tags),
          horizon_timeout (bool), stopped_before_any_leg (bool).
    cost_mult / extra_slip_pts: stress-test knobs (2x costs, +slip).
    """
    minute_ns = 60_000_000_000
    slip = (SLIPPAGE_TICKS * TICK + extra_slip_pts) * 1.0
    comm = COMMISSION_PER_SIDE * cost_mult
    risk_dollars = risk_pts * POINT_VALUE

    entry_fill = entry + slip if dir_ == LONG else entry - slip

    current_stop = effective_stop_initial if effective_stop_initial is not None else stop
    remaining = 1.0
    leg_idx = 0
    n = len(legs)
    gross_dollars = 0.0
    legs_hit = []
    n_fills = 0   # exit fills (each pays its own commission)
    exit_ns = None
    horizon_timeout = False
    stopped_before_any_leg = False

    end = min(horizon_idx, len(h) - 1)
    j = entry_idx + 1
    while j <= end:
        hi = h[j]; lo = l[j]
        stop_hit = (lo <= current_stop) if dir_ == LONG else (hi >= current_stop)
        time_hit = (time_cutoff_idx is not None) and (j >= time_cutoff_idx)

        if stop_hit:
            exit_fill = current_stop - slip if dir_ == LONG else current_stop + slip
            pts = (exit_fill - entry_fill) if dir_ == LONG else (entry_fill - exit_fill)
            gross_dollars += remaining * pts * POINT_VALUE
            n_fills += 1
            legs_hit.append("stop")
            if leg_idx == 0:
                stopped_before_any_leg = True
            remaining = 0.0
            exit_ns = int(t_open_ns[j] + minute_ns)
            break

        if time_hit:
            mtm = c[j]
            exit_fill = mtm - slip if dir_ == LONG else mtm + slip
            pts = (exit_fill - entry_fill) if dir_ == LONG else (entry_fill - exit_fill)
            gross_dollars += remaining * pts * POINT_VALUE
            n_fills += 1
            legs_hit.append("time_cutoff")
            remaining = 0.0
            exit_ns = int(t_open_ns[j] + minute_ns)
            break

        while leg_idx < n:
            leg = legs[leg_idx]
            tgt = leg["price"]
            hit = (hi >= tgt) if dir_ == LONG else (lo <= tgt)
            if not hit:
                break
            exit_fill = tgt - slip if dir_ == LONG else tgt + slip
            pts = (exit_fill - entry_fill) if dir_ == LONG else (entry_fill - exit_fill)
            q = leg["qty"]
            gross_dollars += q * pts * POINT_VALUE
            n_fills += 1
            legs_hit.append(leg["tag"])
            remaining -= q
            if leg.get("move_stop_to") is not None:
                current_stop = leg["move_stop_to"]
            leg_idx += 1
            if remaining <= 1e-9:
                break

        if remaining <= 1e-9:
            exit_ns = int(t_open_ns[j] + minute_ns)
            break
        j += 1

    if remaining > 1e-9:
        # horizon exhausted without stop/time-cutoff/targets fully filling
        jf = end
        mtm = c[jf]
        exit_fill = mtm - slip if dir_ == LONG else mtm + slip
        pts = (exit_fill - entry_fill) if dir_ == LONG else (entry_fill - exit_fill)
        gross_dollars += remaining * pts * POINT_VALUE
        n_fills += 1
        legs_hit.append("horizon_timeout")
        exit_ns = int(t_open_ns[jf] + minute_ns)
        horizon_timeout = True

    total_commission = comm * (1 + n_fills)   # 1 entry fill + n exit fills
    net_dollars = gross_dollars - total_commission
    R = net_dollars / risk_dollars if risk_dollars > 0 else np.nan
    hold_min = (exit_ns - int(t_open_ns[entry_idx] + minute_ns)) / 1e9 / 60.0 if exit_ns else np.nan

    return dict(R=R, net_dollars=net_dollars, exit_reason=legs_hit[-1] if legs_hit else "none",
               legs_hit=legs_hit, n_fills=n_fills, exit_time_ns=exit_ns, hold_min=hold_min,
               horizon_timeout=horizon_timeout, stopped_before_any_leg=stopped_before_any_leg)
