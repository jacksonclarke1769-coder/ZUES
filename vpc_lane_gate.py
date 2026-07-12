"""
Two-lane (Profile A + VPC) risk accounting — ADDITIVE, DISARMED-by-default.

The design spec requires a single authoritative, lane-agnostic daily-risk ledger with pre-trade
admission control: a lane may open only if `combined_open_risk + new_risk <= remaining_daily_budget`.
This is the module where two-lane discipline lives (the C1 target config: A $900/cap-6 + VPC
$600/cap-3). It is the VPC lane's OWN gate — it does NOT modify `LiveAuto._risk_gate` or any locked
config; at Phase-4 arming the live wiring calls THIS book additively (like Profile B threads
`_risk_gate("B", ...)`), and the per-lane sizing numbers below are seeded from the go-live-recert-
gated locked config, never hard-coded into a shipped decision.

CONFLICT RULE (documented, per doc-2's "Conflict rules with A" BLOCKS-ARMING item):
  A and VPC are decorrelated by design (union corr ~+0.16, mostly non-overlapping days) and BOTH
  LANES MAY HOLD SIMULTANEOUSLY. This gate therefore imposes NO direction-conflict block — the only
  two-lane constraint enforced here is the shared combined-open-risk ceiling. Whether an
  opposite-direction A+VPC stack on the same instrument should additionally be blocked/flagged is an
  EXPLICIT RISK/BUSINESS DECISION reserved to an operator DEC (it is NOT improvised here); until such
  a DEC exists this gate deliberately does not encode one. `flag_opposite_direction()` is provided as
  an OBSERVATIONAL helper (never blocks) so the paper shadow can measure the frequency the DEC needs.

FAIL-CLOSED: any error, or a trade that cannot fit even one contract, returns (False, 0, why). Sizes
DOWN rather than rejecting where a smaller qty fits (matching `_risk_gate`'s certified philosophy).
"""

# C1 target defaults (design DEC-20260712 §3). Passed in explicitly at construction so the arm-time
# locked config is the authority — these named constants are documentation of the target, not a
# second source of truth the live path reads.
C1_LANE_CAPS = {"A": 6, "V": 3}
C1_LANE_BUDGET_USD = {"A": 900.0, "V": 600.0}


class VpcLaneRiskBook:
    """Lane-agnostic daily open-risk ledger with per-lane cap + per-lane size-to-risk budget +
    a shared combined-open-risk ceiling. One instance per account per ET day (call `new_day()` on
    the roll). Risk is booked in $ (stop_pts * point_value * qty)."""

    def __init__(self, *, lane_caps=None, lane_budget_usd=None, daily_budget_usd,
                 point_value, cushion_frac=1.0):
        if daily_budget_usd is None or float(daily_budget_usd) <= 0:
            raise ValueError("daily_budget_usd must be > 0")
        if point_value is None or float(point_value) <= 0:
            raise ValueError("point_value must be > 0")
        self.lane_caps = dict(lane_caps or C1_LANE_CAPS)
        self.lane_budget_usd = dict(lane_budget_usd or C1_LANE_BUDGET_USD)
        self.daily_budget_usd = float(daily_budget_usd)
        self.point_value = float(point_value)
        self.cushion_frac = float(cushion_frac)
        self.open_risk = {}                  # lane -> open bracket risk $ (one entry per lane held)
        self.open_side = {}                  # lane -> "long"/"short" (observational, for conflict flag)
        self.reserved = {}                   # lane -> RESERVED risk $ (admitted, not yet opened) — F3

    def new_day(self):
        self.open_risk.clear()
        self.open_side.clear()
        self.reserved.clear()

    def combined_open_risk(self):
        """Open PLUS reserved risk (F3): the combined-ceiling must count risk that a same-bar admit
        has already committed to, even before on_open lands — otherwise two same-bar admissions both
        pass against the same headroom and silently overbook the ceiling."""
        return sum(self.open_risk.values()) + sum(self.reserved.values())

    def remaining_daily_budget(self):
        return max(0.0, self.daily_budget_usd * self.cushion_frac - self.combined_open_risk())

    def flag_opposite_direction(self, lane, side):
        """OBSERVATIONAL ONLY — never blocks. Returns the set of other lanes currently holding the
        OPPOSITE direction, so the paper shadow can measure opposite-direction A+VPC stacking for
        the pending conflict-policy DEC. A non-empty return is a FLAG, not a veto."""
        return {ln: s for ln, s in self.open_side.items()
                if ln != lane and s is not None and s != side}

    def admit(self, lane, *, stop_pts, requested_qty, side=None, reserve=True):
        """ATOMIC CHECK-AND-RESERVE pre-trade admission (F3). Returns (ok, sized_qty, why).
        Sizes DOWN to fit (never up). Order of constraints:
          1. per-lane contract cap
          2. per-lane size-to-risk $ budget (qty <= budget / risk_per_contract)
          3. shared combined-open-risk ceiling (qty s.t. combined(open+reserved) + new <= daily budget)
        On success it RESERVES the sized risk immediately (unless reserve=False), so a second same-bar
        admit sees the reduced headroom and the combined ceiling holds even before on_open lands. The
        caller MUST either on_open (converts the reservation to open risk) or release(lane) (frees it,
        e.g. if the payload/send fails after admit). Fail-closed on any error or zero-fit."""
        try:
            sp = abs(float(stop_pts))
            if sp <= 0:
                return False, 0, "invalid stop distance"
            req = int(requested_qty)
            if req <= 0:
                return False, 0, "requested_qty <= 0"
            if lane in self.open_risk or lane in self.reserved:
                return False, 0, f"lane {lane} already holds/reserved a position"
            risk1 = sp * self.point_value               # $ risk per contract
            q = req
            cap = self.lane_caps.get(lane)
            if cap is not None:
                q = min(q, int(cap))
            lbud = self.lane_budget_usd.get(lane)
            if lbud is not None:
                q = min(q, int(lbud // risk1))
            rem = self.remaining_daily_budget()
            q = min(q, int(rem // risk1))
            if q < 1:
                return (False, 0,
                        f"no size fits: risk ${risk1:,.0f}/ct vs lane_budget "
                        f"${(lbud or 0):,.0f}, remaining_daily ${rem:,.0f}, cap {cap}")
            if reserve:
                self.reserved[lane] = risk1 * q         # ATOMIC: commit the headroom now
                self.open_side.setdefault(lane, side)   # observational (for the conflict flag)
            why = "" if q == req else (
                f"sized {req}->{q} (risk ${risk1:,.0f}/ct, lane_budget ${(lbud or 0):,.0f}, "
                f"remaining_daily ${rem:,.0f}, cap {cap})")
            return True, q, why
        except Exception as e:                          # noqa: BLE001 — a broken gate must not trade
            return False, 0, f"lane risk book error: {e!r}"

    def release(self, lane):
        """Free a reservation without opening (e.g. the payload/send failed after admit)."""
        self.reserved.pop(lane, None)
        if lane not in self.open_risk:
            self.open_side.pop(lane, None)

    def on_open(self, lane, *, stop_pts, qty, side=None):
        """Book an opened position's open risk (call AFTER a successful admit + send). Converts any
        reservation for the lane into realized open risk (idempotent w.r.t. the reservation)."""
        self.reserved.pop(lane, None)
        self.open_risk[lane] = abs(float(stop_pts)) * self.point_value * int(qty)
        self.open_side[lane] = side

    def on_close(self, lane):
        """Release a lane's open risk (and any stray reservation) when its position resolves."""
        self.open_risk.pop(lane, None)
        self.reserved.pop(lane, None)
        self.open_side.pop(lane, None)
