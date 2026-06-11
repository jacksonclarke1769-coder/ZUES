"""
MFFUState — MyFundedFutures Core 50K account / risk state engine.

Broker-independent. No Tradovate calls, no orders, no strategy/engine imports. All P&L
is passed IN as dollars by the caller (the future bot.py); this module only tracks state
and answers risk-gate questions. It replaces the old Apex-style EvalState.

MFFU Core 50K model (all thresholds configurable via MFFUConfig):
  • start $50,000 · evaluation target +$3,000 · END-OF-DAY trailing drawdown $2,000
  • the drawdown floor trails the highest END-OF-DAY balance and LOCKS at the start
    balance once it would exceed it:  floor = min(eod_high_water - 2,000, lock_at)
  • $800 internal daily-loss kill-switch (NOT an MFFU rule — our safety) · max 2 trades/day
  • one position at a time · news-blackout & session gating · flatten before hard close
  • funded payout: >=5 winning days, >=$2,100 profit buffer, $5,000 cap, $250 min withdraw

Phases: EVALUATION → FUNDED → PAYOUT_ELIGIBLE (→ FUNDED after a payout) · FAILED on breach.
Intraday breach convention (matches the validated funded backtest): the floor is fixed for
the day off the prior end-of-day high-water mark; equity (= balance + unrealized) touching
the floor at any point fails the account. The floor only trails at end_of_day_update().
"""
from dataclasses import dataclass, asdict, field

EVALUATION = "EVALUATION"
FUNDED = "FUNDED"
PAYOUT_ELIGIBLE = "PAYOUT_ELIGIBLE"
FAILED = "FAILED"


def _mins(ts):
    """Minute-of-day from a datetime-like (ET-localized) or an int. None -> None."""
    if ts is None:
        return None
    if isinstance(ts, int):
        return ts
    return ts.hour * 60 + ts.minute


@dataclass
class MFFUConfig:
    # account / drawdown
    start_balance: float = 50_000.0
    eval_target: float = 3_000.0          # +$3,000 to pass
    trail_dd: float = 2_000.0             # end-of-day trailing drawdown
    lock_at: float = 50_000.0             # floor locks here (== start for Core)
    # evaluation
    min_trading_days: int = 2
    eval_consistency: float = 0.50        # eval only: no single day > 50% of total profit; None=off
    # funded payout
    win_day_min: float = 50.0             # a day counts as "winning" at >= this profit
    min_winning_days: int = 5
    payout_buffer: float = 2_100.0        # profit buffer required before withdrawing
    payout_cap: float = 5_000.0           # max single withdrawal
    min_withdraw: float = 250.0
    funded_consistency: float = None      # Core: none at funded stage
    # internal safety / ops (configurable, not MFFU rules)
    daily_loss_limit: float = 800.0       # halt new trades for the day at this realized+open loss
    max_trades_per_day: int = 2
    min_floor_buffer: float = 0.0         # block a new trade if distance-to-floor < this ($)
    # session / time gating (minutes ET)
    session_start_min: int = 9 * 60 + 30
    session_end_min: int = 11 * 60 + 30
    hard_close_min: int = 14 * 60 + 30

    @classmethod
    def from_config_modules(cls, EVAL, PAYOUT, SAFETY, STRAT=None):
        """Build from config.py dicts (keeps a single source of truth)."""
        c = cls(
            start_balance=EVAL.get("start_balance", 50_000.0),
            eval_target=EVAL.get("pass_target", 53_000.0) - EVAL.get("start_balance", 50_000.0),
            trail_dd=EVAL.get("trail_dd", 2_000.0),
            lock_at=EVAL.get("lock_at", 50_000.0),
            min_trading_days=EVAL.get("min_days", 2),
            eval_consistency=EVAL.get("eval_consistency", 0.50),
            win_day_min=PAYOUT.get("win_day_min", 50.0),
            min_winning_days=PAYOUT.get("min_win_days", 5),
            payout_buffer=PAYOUT.get("buffer", 2_100.0),
            payout_cap=PAYOUT.get("cap", 5_000.0),
            min_withdraw=PAYOUT.get("min_withdraw", 250.0),
            funded_consistency=PAYOUT.get("consistency", None),
            daily_loss_limit=SAFETY.get("max_daily_loss", 800.0),
            max_trades_per_day=SAFETY.get("max_trades_per_day", 2),
        )
        if STRAT:
            c.session_start_min = STRAT.get("nyam_start_min", c.session_start_min)
            c.session_end_min = STRAT.get("nyam_end_min", c.session_end_min)
            c.hard_close_min = STRAT.get("flat_min", c.hard_close_min)
        return c


class MFFUState:
    def __init__(self, cfg=None):
        self.cfg = cfg or MFFUConfig()
        c = self.cfg
        self.phase = EVALUATION
        self.balance = c.start_balance            # realized
        self.unrealized = 0.0
        self.eod_hwm = c.start_balance            # highest END-OF-DAY balance (drives the floor)
        self.eod_balance = c.start_balance        # last finalized EOD balance
        # day counters
        self.day_pnl = 0.0
        self.trades_today = 0
        self._halted = False
        # lifetime counters
        self.trading_days = 0
        self.winning_days = 0
        self.max_day_profit = 0.0                 # for eval consistency
        self.total_payouts = 0
        self.total_paid = 0.0
        # position
        self.position = None                      # dict(qty, entry, stop, filled) or None
        # status
        self.breached = False

    # ---------------- derived ----------------
    @property
    def equity(self):
        return self.balance + self.unrealized

    @property
    def realized_pnl(self):
        return self.balance - self.cfg.start_balance

    @property
    def floor(self):
        return min(self.eod_hwm - self.cfg.trail_dd, self.cfg.lock_at)

    @property
    def distance_to_floor(self):
        return self.equity - self.floor

    @property
    def daily_loss_used(self):
        # realized loss today + any open drawdown (only the loss side counts)
        return max(0.0, -(self.day_pnl + self.unrealized))

    @property
    def position_open(self):
        return self.position is not None

    # ---------------- risk gate ----------------
    def can_open_trade(self, ts=None, in_news_blackout=False, in_session=None, trade_risk=0.0):
        """Return (ok: bool, reason: str). All blocks are configurable thresholds."""
        c = self.cfg
        if self.phase == FAILED or self.breached:
            return False, "account_failed"
        if self.position_open:
            return False, "position_open"
        if self.should_halt_today():
            return False, "daily_halt"
        if self.daily_loss_used >= c.daily_loss_limit:
            return False, "daily_loss_limit"
        if self.trades_today >= c.max_trades_per_day:
            return False, "max_trades_per_day"
        if in_news_blackout:
            return False, "news_blackout"
        if in_session is None and ts is not None:
            m = _mins(ts)
            in_session = (m is not None and c.session_start_min <= m < c.session_end_min)
        if in_session is False:
            return False, "outside_session"
        if (self.distance_to_floor - max(0.0, trade_risk)) < c.min_floor_buffer:
            return False, "too_close_to_floor"
        return True, "ok"

    # ---------------- trade lifecycle ----------------
    def record_trade_open(self, qty, entry_px, stop_px, ts=None):
        """Mark a position opened (counts toward trades/day). Idempotent-safe."""
        if self.position_open:
            raise RuntimeError("already in a position")
        self.position = dict(qty=qty, entry=entry_px, stop=stop_px, filled=0)
        self.trades_today += 1
        return self.position

    def record_fill(self, qty, price=None):
        """Record a (partial) fill of the open position's working quantity."""
        if not self.position_open:
            return
        self.position["filled"] = min(self.position["qty"], self.position["filled"] + qty)

    def update_unrealized(self, unrealized_usd):
        """Mark-to-market the open position in $; checks intraday breach + daily-loss."""
        self.unrealized = float(unrealized_usd)
        self._check_breach()
        return dict(equity=self.equity, distance_to_floor=self.distance_to_floor,
                    daily_loss_used=self.daily_loss_used, breached=self.breached)

    def record_trade_close(self, pnl_usd, ts=None):
        """Realize a trade's P&L ($), flatten the position, check breach."""
        self.balance += pnl_usd
        self.day_pnl += pnl_usd
        self.unrealized = 0.0
        self.position = None
        self._check_breach()
        return dict(balance=self.balance, day_pnl=self.day_pnl, phase=self.phase)

    def _check_breach(self):
        if self.phase == FAILED:
            return
        if self.equity <= self.floor:
            self.phase = FAILED
            self.breached = True

    # ---------------- time / flatten / halt ----------------
    def should_flatten_now(self, ts=None):
        """Flatten if past hard-close, or on breach/halt while holding."""
        if not self.position_open:
            return False
        if self.breached or self.phase == FAILED or self.should_halt_today():
            return True
        m = _mins(ts)
        return m is not None and m >= self.cfg.hard_close_min

    def should_halt_today(self):
        return self._halted or self.phase == FAILED or self.daily_loss_used >= self.cfg.daily_loss_limit

    def halt_today(self):
        self._halted = True

    # ---------------- end of day ----------------
    def end_of_day_update(self, ts=None):
        """Finalize the day: trailing DD, winning-day & phase transitions, reset counters."""
        events = []
        if self.phase == FAILED:
            return events
        traded = self.trades_today > 0
        if traded:
            self.trading_days += 1
        if self.day_pnl >= self.cfg.win_day_min:
            self.winning_days += 1
            events.append("WINNING_DAY")
        self.max_day_profit = max(self.max_day_profit, self.day_pnl)
        # EOD balance + trailing high-water mark (the floor only moves here)
        self.eod_balance = self.balance
        self.eod_hwm = max(self.eod_hwm, self.balance)
        # phase transitions
        if self.phase == EVALUATION and self._eval_passed():
            self._promote_to_funded(); events.append("PASSED_EVAL")
        elif self.phase in (FUNDED, PAYOUT_ELIGIBLE) and self._payout_eligible():
            if self.phase != PAYOUT_ELIGIBLE:
                events.append("PAYOUT_ELIGIBLE")
            self.phase = PAYOUT_ELIGIBLE
        # reset day
        self.day_pnl = 0.0
        self.trades_today = 0
        self.unrealized = 0.0
        self._halted = False
        return events

    def _eval_passed(self):
        c = self.cfg
        if self.balance < c.start_balance + c.eval_target:
            return False
        if self.trading_days < c.min_trading_days:
            return False
        if c.eval_consistency is not None:
            profit = self.balance - c.start_balance
            if profit > 0 and self.max_day_profit > c.eval_consistency * profit:
                return False
        return True

    def _promote_to_funded(self):
        """Eval pass -> a FRESH funded account (own $50k & $2k trailing DD)."""
        c = self.cfg
        self.phase = FUNDED
        self.balance = c.start_balance
        self.unrealized = 0.0
        self.eod_hwm = c.start_balance
        self.eod_balance = c.start_balance
        self.winning_days = 0
        self.max_day_profit = 0.0

    def _payout_eligible(self):
        c = self.cfg
        profit = self.balance - c.start_balance
        if self.winning_days < c.min_winning_days or profit < c.payout_buffer:
            return False
        if c.funded_consistency is not None and profit > 0 and self.max_day_profit > c.funded_consistency * profit:
            return False
        return True

    def request_payout(self):
        """Withdraw if eligible. Returns the paid amount ($) or 0.0."""
        if self.phase != PAYOUT_ELIGIBLE:
            return 0.0
        c = self.cfg
        profit = self.balance - c.start_balance
        amt = min(profit, c.payout_cap)
        if amt < c.min_withdraw:
            return 0.0
        self.balance -= amt
        self.eod_hwm = max(c.start_balance, self.balance)
        self.eod_balance = self.balance
        self.winning_days = 0
        self.total_payouts += 1
        self.total_paid += amt
        self.phase = FUNDED
        return amt

    # ---------------- snapshot ----------------
    def snapshot(self):
        return dict(
            cfg=asdict(self.cfg),
            phase=self.phase, balance=self.balance, unrealized=self.unrealized,
            eod_hwm=self.eod_hwm, eod_balance=self.eod_balance,
            day_pnl=self.day_pnl, trades_today=self.trades_today, halted=self._halted,
            trading_days=self.trading_days, winning_days=self.winning_days,
            max_day_profit=self.max_day_profit, total_payouts=self.total_payouts,
            total_paid=self.total_paid, position=self.position, breached=self.breached)

    @classmethod
    def from_snapshot(cls, s):
        st = cls(MFFUConfig(**s["cfg"]))
        st.phase = s["phase"]; st.balance = s["balance"]; st.unrealized = s["unrealized"]
        st.eod_hwm = s["eod_hwm"]; st.eod_balance = s["eod_balance"]
        st.day_pnl = s["day_pnl"]; st.trades_today = s["trades_today"]; st._halted = s["halted"]
        st.trading_days = s["trading_days"]; st.winning_days = s["winning_days"]
        st.max_day_profit = s["max_day_profit"]; st.total_payouts = s["total_payouts"]
        st.total_paid = s["total_paid"]; st.position = s["position"]; st.breached = s["breached"]
        return st

    def status(self):
        return dict(phase=self.phase, balance=round(self.balance, 2), equity=round(self.equity, 2),
                    realized_pnl=round(self.realized_pnl, 2), unrealized=round(self.unrealized, 2),
                    day_pnl=round(self.day_pnl, 2), eod_balance=round(self.eod_balance, 2),
                    high_water_mark=round(self.eod_hwm, 2), drawdown_floor=round(self.floor, 2),
                    distance_to_floor=round(self.distance_to_floor, 2),
                    daily_loss_used=round(self.daily_loss_used, 2), trades_today=self.trades_today,
                    position_open=self.position_open, winning_days=self.winning_days,
                    trading_days=self.trading_days)
