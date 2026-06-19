"""Multi-firm funded-account rule profiles + risk models — SIM / RESEARCH ONLY.

Nothing here places, sizes, or gates a LIVE order. It is the home for firm rule sets used by
sims and the dashboard cushion display. Live risk gates stay in auto_safety.py.

APEX TRADER FUNDING — structurally different from MFFU/Topstep:
  * The trailing threshold trails the INTRA-TRADE *unrealized* peak (open-position highs ratchet
    it up tick-by-tick), NOT just the end-of-day balance.
  * It LOCKS once the account is up `trailing + $100`: the threshold freezes at start + $100 and
    never trails again.
  * No daily loss limit (our ARES -$700 stop is OUR control, not Apex's).
  * 30% consistency rule for payouts (no single day >= 30% of total profit).

⚠️ THE NUMBERS BELOW ARE FROM PUBLIC DOCS AND MUST BE VERIFIED against your live Apex contract
before ANY live use. They change. This module is sim-only by design.
"""

APEX_LOCK_ABOVE_START = 100.0      # threshold locks at start + $100 once cleared
APEX_CONSISTENCY = 0.30            # no single day >= 30% of total profit (payout rule)

# size -> start balance, trailing drawdown, eval profit target, max contracts (VERIFY)
APEX_ACCOUNTS = {
    "50K":  dict(start=50_000,  trailing=2_500, target=3_000, max_contracts=10),
    "100K": dict(start=100_000, trailing=3_000, target=6_000, max_contracts=14),
    "150K": dict(start=150_000, trailing=5_000, target=9_000, max_contracts=17),
}


class ApexAcct:
    """Apex trailing-threshold account (sim).

    threshold(t) = min(peak_equity(t) - trailing, start + $100)
      * peak_equity trails the UNREALIZED high (open-position favourable excursion ratchets it),
      * once peak_equity - trailing >= start + $100 the threshold locks at start + $100 forever.
    Breach if equity ever touches/falls to the threshold.
    """

    def __init__(self, spec, lock_above=APEX_LOCK_ABOVE_START):
        self.start = float(spec["start"])
        self.trail = float(spec["trailing"])
        self.target = float(spec.get("target", 0.0))
        self.lock_at = self.start + lock_above
        self.bal = self.start
        self.peak = self.start
        self.threshold = self.start - self.trail
        self.breached = False
        self.passed = False
        self.locked = False

    def _retrail(self):
        self.threshold = min(self.peak - self.trail, self.lock_at)
        if self.peak - self.trail >= self.lock_at:
            self.locked = True

    def mark(self, equity):
        """Mark the account to an equity value (realized + any open unrealized). Ratchets the
        trailing threshold on new highs and flags a breach if equity hits the threshold."""
        if equity > self.peak:
            self.peak = equity
            self._retrail()
        if equity <= self.threshold + 1e-9:
            self.breached = True
        return self.breached

    def apply_trade(self, pnl, mfe=0.0, mae=0.0):
        """Coarse single-trade approximation in $ (the SIM uses bar-by-bar mark() for true path):
        adverse excursion first (typically near entry, checked vs the pre-run floor), then the
        favourable run ratchets the trail, then realized pnl settles — so giving back open profit
        breaches at settle against the ratcheted floor. mfe>=0, mae<=0."""
        self.mark(self.bal + min(0.0, mae))      # adverse first (near entry)
        self.mark(self.bal + max(0.0, mfe))      # favourable run ratchets the trail
        self.bal += pnl
        self.mark(self.bal)                      # settle — give-back breaches here vs ratcheted floor
        if self.target > 0 and self.bal >= self.start + self.target:
            self.passed = True
        return self.breached

    @property
    def cushion(self):
        return self.bal - self.threshold


def consistency_ok(daily_pnls, threshold=APEX_CONSISTENCY):
    """30% rule: the best single day must be <= threshold of total (positive) profit."""
    total = sum(p for p in daily_pnls if p > 0)
    if total <= 0:
        return None
    return (max(daily_pnls) / total) <= threshold
