"""
APEX DAILY-KILL GUARD — the firm-specific safety MFFU doesn't need.

On Apex, a single DAY that loses more than the daily-loss-limit ($1,000 on a 50K, $1,500/$2,000 on
100K/150K) FAILS the whole account — instant, no recovery. This guard watches an account's cumulative
(modeled) day P&L and, BEFORE the day crosses the kill, FLATTENS the account and HALTS it for the rest of
the day — turning a would-be account-kill into just a bad day, salvaging the account (and on an eval, the
remaining 30-day-window attempts). It fires once per day. Fail-safe + restart-safe.

Per-book: each Apex AccountBook owns one of these. MFFU books do NOT use it. The salvage `margin` flattens
early (e.g., at -$850 for a $1k limit) because the modeled P&L lags the real fill and an open trade can run.
"""
from __future__ import annotations


class ApexDailyKill:
    def __init__(self, dll=1000.0, margin=0.85, label="apex"):
        self.dll = abs(float(dll))
        self.margin = float(margin)
        self.kill_at = -self.dll * self.margin     # flatten before the real -$dll kill (e.g., -$850)
        self.label = label
        self.day = None
        self.tripped = False

    def _roll(self, day):
        if day != self.day:
            self.day = day
            self.tripped = False

    def update(self, day, day_pnl):
        """Feed the cumulative MODELED day P&L for the account. Returns True (caller must FLATTEN + halt
        the account for the rest of today) the FIRST time the day crosses the salvage threshold; else False."""
        try:
            self._roll(day)
            if not self.tripped and float(day_pnl) <= self.kill_at:
                self.tripped = True
                print(f"[apex-kill] {self.label}: day P&L ${float(day_pnl):,.0f} <= salvage ${self.kill_at:,.0f} "
                      f"(of -${self.dll:,.0f} kill) -> FLATTEN + halt for the day", flush=True)
                return True
            return False
        except Exception as e:                              # noqa: BLE001 — a guard error must never break trading
            print(f"[apex-kill] update error (ignored): {e!r}", flush=True)
            return False

    def halted(self, day):
        """True if the account is killed-out for `day` (no new entries until tomorrow)."""
        self._roll(day)
        return self.tripped

    # ---- restart safety ----
    def snapshot(self):
        return dict(day=str(self.day) if self.day is not None else None, tripped=self.tripped)

    def restore(self, state):
        if not state:
            return
        try:
            self.day = state.get("day")
            self.tripped = bool(state.get("tripped", False))
        except Exception as e:                              # noqa: BLE001
            print(f"[apex-kill] restore ignored ({e})", flush=True)
