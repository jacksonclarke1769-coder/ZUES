"""P3 — cushion brake (Project Titan, promoted to production). State-dependent sizing:
when the funded cushion (equity - trailing floor) falls below 40% of the trailing-DD
allowance, cut to max(A//2,1) and B=0; resume the frozen allocation at 60%. Hysteresis
latch (no flip-flop in the [40%,60%) band). Survival 89.6 -> 97.9% with ~flat income.

Pure + restart-safe (snapshot/restore). NEVER increases size; only protects near the floor.
"""


class P3Brake:
    def __init__(self, on_frac=0.40, off_frac=0.60, braked=False):
        assert 0 < on_frac < off_frac <= 1, "need 0 < on < off <= 1"
        self.on_frac = on_frac
        self.off_frac = off_frac
        self.braked = bool(braked)

    def update(self, cushion, dd_allowance):
        """Update the latch from the current cushion. Returns braked (bool).
        Brake ON below on_frac*dd; OFF at/above off_frac*dd; HOLD in between (hysteresis).
        Fail-safe: a non-positive/None dd_allowance or cushion -> brake ON (closest to floor)."""
        try:
            on = self.on_frac * dd_allowance
            off = self.off_frac * dd_allowance
        except Exception:                                # noqa: BLE001
            self.braked = True
            return True
        if cushion is None or dd_allowance is None or dd_allowance <= 0:
            self.braked = True
        elif cushion < on:
            self.braked = True
        elif cushion >= off:
            self.braked = False
        # else: hold the current latch (hysteresis band)
        return self.braked

    def size(self, a_base, b_base):
        """(a_size, b_size) for the current latch. Braked -> half A (>=1), no B."""
        a_base = int(a_base); b_base = int(b_base)
        if self.braked:
            return max(a_base // 2, 1), 0
        return a_base, b_base

    def thresholds(self, dd_allowance):
        return dict(on=self.on_frac * dd_allowance, off=self.off_frac * dd_allowance)

    # ---- restart-safe ----
    def snapshot(self):
        return dict(on_frac=self.on_frac, off_frac=self.off_frac, braked=self.braked)

    @classmethod
    def from_snapshot(cls, s):
        s = s or {}
        return cls(on_frac=s.get("on_frac", 0.40), off_frac=s.get("off_frac", 0.60),
                   braked=s.get("braked", False))
