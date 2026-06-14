"""D1c morning-drift context gate for Profile A — CERBERUS-validated, DEFAULT OFF.

Frozen rule (zero parameters, PROMETHEUS wave-2b / CERBERUS 2026-06-12):
a Profile A entry may only be working/filled while
    sign(last_completed_1m_close - rth_0930_open) == trade direction.

Deployment semantics (matches the validated backtest):
- evaluate on every completed 1m bar; suspend the pending OTE limit while disagreeing,
  re-arm when agreeing again.
- FAIL-CLOSED: if the gate is enabled and the 1m feed is stale (> stale_after_s) or the
  09:30 open is missing, allows() returns False (suspend). A gate failure can only cost
  income, never add risk.
- drift == 0 counts as disagreement (np.sign(0) != ±1 in the validated backtest).
- Scope: Profile A ONLY. Never apply to Profile B (untested).

HEIMDALL integration: keep_rate(n=90) should live in 45–80%; outside that band raise
YELLOW (environment shift or feed bug). Validated era keep-rate: 62%.
"""
from collections import deque

LONG, SHORT = 1, -1
_DIR = {"long": LONG, "short": SHORT, LONG: LONG, SHORT: SHORT}


class DriftGate:
    def __init__(self, enabled=False, stale_after_s=120, keep_window=90):
        self.enabled = enabled
        self.stale_after_s = stale_after_s
        self.session_open = None        # 09:30 RTH open price
        self.session_date = None
        self.last_close = None
        self.last_close_ts = None
        self._decisions = deque(maxlen=keep_window)

    # ---- feed hooks -------------------------------------------------------
    def on_session_open(self, ts, open_price):
        """Call at 09:30 ET with the RTH 1m open."""
        self.session_open = float(open_price)
        self.session_date = ts.date()
        self.last_close = None
        self.last_close_ts = None

    def on_bar_close(self, ts, close):
        """Call on every COMPLETED 1m bar (RTH)."""
        if self.session_date is not None and ts.date() == self.session_date:
            self.last_close = float(close)
            self.last_close_ts = ts

    # ---- decision ---------------------------------------------------------
    def drift(self):
        if self.session_open is None or self.last_close is None:
            return None
        return self.last_close - self.session_open

    def allows(self, direction, now):
        """True = order may work. Disabled gate always allows (status-quo ZEUS)."""
        if not self.enabled:
            return True
        d = _DIR.get(direction)
        if d is None:
            raise ValueError(f"bad direction {direction!r}")
        # fail-closed conditions
        if self.session_open is None or self.last_close_ts is None:
            self._decisions.append(0)
            return False
        if (now - self.last_close_ts).total_seconds() > self.stale_after_s + 60:
            self._decisions.append(0)
            return False
        dr = self.drift()
        ok = (dr > 0 and d == LONG) or (dr < 0 and d == SHORT)   # drift==0 -> False
        self._decisions.append(1 if ok else 0)
        return ok

    # ---- monitoring -------------------------------------------------------
    def keep_rate(self):
        """Rolling keep-rate over the decision window (None until >=30 decisions)."""
        if len(self._decisions) < 30:
            return None
        return sum(self._decisions) / len(self._decisions)

    def heimdall_status(self):
        kr = self.keep_rate()
        if not self.enabled:
            return "OFF"
        if kr is None:
            return "WARMUP"
        return "OK" if 0.45 <= kr <= 0.80 else "YELLOW"
