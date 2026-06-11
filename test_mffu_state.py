"""
Simulation tests for MFFUState (MyFundedFutures Core 50K). BROKER-INDEPENDENT.
No Tradovate, no orders, no bot.py. All P&L injected as dollars.

Run:   python test_mffu_state.py     (exit 0 = all pass)
"""
import sys
from datetime import datetime
from mffu_state import MFFUState, MFFUConfig, EVALUATION, FUNDED, PAYOUT_ELIGIBLE, FAILED

PASS, FAIL = [], []
T = lambda hh, mm: datetime(2025, 1, 2, hh, mm)   # an ET-localized-ish time (uses hour/minute only)


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if (detail and not cond) else ""))


def trade(st, pnl, ts=None):
    """open -> close a single trade for $pnl (in session by default)."""
    st.record_trade_open(qty=2, entry_px=22000, stop_px=21980, ts=ts or T(10, 0))
    st.record_trade_close(pnl, ts or T(10, 30))


# ----------------------------------------------------------------- 1
def s1_winning_day():
    print("\n1 — normal winning day:")
    st = MFFUState()
    ok, _ = st.can_open_trade(ts=T(10, 0))
    check("can open at start (in session)", ok)
    trade(st, +500)
    ev = st.end_of_day_update(T(16, 0))
    check("balance +500 = 50,500", st.balance == 50_500)
    check("winning day recorded", "WINNING_DAY" in ev and st.winning_days == 1)
    check("EOD high-water moved to 50,500", st.eod_hwm == 50_500)
    check("floor trailed to 48,500", st.floor == 48_500)
    check("still EVALUATION", st.phase == EVALUATION)


# ----------------------------------------------------------------- 2
def s2_losing_day():
    print("\n2 — normal losing day:")
    st = MFFUState()
    trade(st, -200)
    ev = st.end_of_day_update(T(16, 0))
    check("balance -200 = 49,800", st.balance == 49_800)
    check("no winning day", "WINNING_DAY" not in ev and st.winning_days == 0)
    check("not breached (49,800 > floor 48,000)", st.phase == EVALUATION and not st.breached)
    check("floor unchanged at 48,000 (EOD hwm stays 50,000)", st.floor == 48_000)


# ----------------------------------------------------------------- 3
def s3_daily_loss_halt():
    print("\n3 — daily-loss kill-switch ($800):")
    st = MFFUState()
    trade(st, -800)
    check("daily_loss_used == 800", st.daily_loss_used == 800)
    check("should_halt_today True", st.should_halt_today())
    ok, reason = st.can_open_trade(ts=T(10, 0))
    check("new trade blocked (daily_loss)", (not ok) and reason in ("daily_halt", "daily_loss_limit"))
    check("account NOT failed (just halted)", st.phase == EVALUATION and not st.breached)


# ----------------------------------------------------------------- 4
def s4_eod_drawdown_update_and_lock():
    print("\n4 — EOD drawdown trails then locks at start:")
    st = MFFUState()
    for p in (700, 700, 700):                 # 50,700 / 51,400 / 52,100
        trade(st, p); st.end_of_day_update(T(16, 0))
    check("eod hwm 52,100", st.eod_hwm == 52_100)
    check("floor LOCKED at 50,000 (not 50,100)", st.floor == 50_000)
    # a further down day reduces balance but floor never drops below the lock from hwm
    trade(st, -300); st.end_of_day_update(T(16, 0))
    check("floor still locked 50,000 after a down day", st.floor == 50_000)


# ----------------------------------------------------------------- 5
def s5_drawdown_breach():
    print("\n5 — drawdown breach -> FAILED:")
    st = MFFUState()                          # floor 48,000
    st.record_trade_open(2, 22000, 21980, T(10, 0))
    r = st.update_unrealized(-2000)           # equity 48,000 <= floor
    check("breach flagged on unrealized touch of floor", r["breached"] and st.phase == FAILED)
    check("should_flatten_now True after breach", st.should_flatten_now(T(10, 5)))
    ok, reason = st.can_open_trade(ts=T(10, 0))
    check("no new trades after failure", (not ok) and reason == "account_failed")


# ----------------------------------------------------------------- 6
def s6_max_trades_per_day():
    print("\n6 — max trades/day = 2:")
    st = MFFUState()
    trade(st, +100); trade(st, +100)
    ok, reason = st.can_open_trade(ts=T(10, 0))
    check("3rd trade blocked", (not ok) and reason == "max_trades_per_day")
    st.end_of_day_update(T(16, 0))
    ok2, _ = st.can_open_trade(ts=T(10, 0))
    check("resets next day", ok2 and st.trades_today == 0)


# ----------------------------------------------------------------- 7
def s7_open_position_block():
    print("\n7 — one position at a time:")
    st = MFFUState()
    st.record_trade_open(2, 22000, 21980, T(10, 0))
    ok, reason = st.can_open_trade(ts=T(10, 5))
    check("blocked while position open", (not ok) and reason == "position_open")
    try:
        st.record_trade_open(2, 22010, 21990, T(10, 5)); raised = False
    except RuntimeError:
        raised = True
    check("double-open raises", raised)


# ----------------------------------------------------------------- 8
def s8_eval_to_funded():
    print("\n8 — evaluation -> funded:")
    st = MFFUState()
    evs = []
    for _ in range(3):                        # +1000 x3 over 3 days = +3,000, max-day 1000 <= 50% of 3000
        trade(st, +1000); evs += st.end_of_day_update(T(16, 0))
    check("PASSED_EVAL emitted", "PASSED_EVAL" in evs)
    check("phase == FUNDED", st.phase == FUNDED)
    check("funded account reset to fresh 50,000", st.balance == 50_000 and st.eod_hwm == 50_000)
    check("winning-day counter reset for funded", st.winning_days == 0)


def s8b_eval_consistency_block():
    print("\n8b — eval consistency blocks an over-concentrated pass:")
    st = MFFUState()
    trade(st, +2600); st.end_of_day_update(T(16, 0))   # one huge day
    trade(st, +400); st.end_of_day_update(T(16, 0))    # total 3000 but max-day 2600 > 50%
    check("balance hit target 53,000", st.balance == 53_000)
    check("NOT promoted (consistency fail)", st.phase == EVALUATION)


# ----------------------------------------------------------------- 9
def s9_payout_eligibility():
    print("\n9 — funded payout eligibility + withdrawal:")
    st = MFFUState(); st.phase = FUNDED        # start funded for this test
    evs = []
    for _ in range(5):                         # 5 winning days @ +500 => profit 2,500 >= 2,100 buffer
        trade(st, +500); evs += st.end_of_day_update(T(16, 0))
    check("PAYOUT_ELIGIBLE reached", st.phase == PAYOUT_ELIGIBLE and "PAYOUT_ELIGIBLE" in evs)
    check("5 winning days tracked", st.winning_days == 5)
    paid = st.request_payout()
    check("payout = min(profit 2,500, cap 5,000) = 2,500", paid == 2_500)
    check("balance back to 50,000 after payout", st.balance == 50_000)
    check("winning days reset, back to FUNDED", st.winning_days == 0 and st.phase == FUNDED)


# ----------------------------------------------------------------- 10
def s10_snapshot_reload():
    print("\n10 — snapshot save/reload:")
    st = MFFUState(); st.phase = FUNDED
    trade(st, +400); st.end_of_day_update(T(16, 0))
    st.record_trade_open(3, 22000, 21975, T(10, 0)); st.update_unrealized(+120)
    snap = st.snapshot()
    st2 = MFFUState.from_snapshot(snap)
    same = (st2.status() == st.status() and st2.snapshot() == snap and st2.cfg == st.cfg)
    check("reloaded state identical", same)
    # continue on the reloaded copy
    st2.record_trade_close(+250, T(10, 30))
    check("reloaded copy keeps trading correctly", st2.balance == st.balance + 250 and not st2.position_open)


# ----------------------------------------------------------------- extra safety gates
def s11_safety_gates():
    print("\n11 — news / session / floor-buffer / flatten gates:")
    st = MFFUState()
    ok, r = st.can_open_trade(ts=T(10, 0), in_news_blackout=True)
    check("news blackout blocks", (not ok) and r == "news_blackout")
    ok, r = st.can_open_trade(ts=T(13, 0))
    check("outside session blocks (13:00)", (not ok) and r == "outside_session")
    # min floor buffer configurable
    st2 = MFFUState(MFFUConfig(min_floor_buffer=1500))   # distance 2000 - risk 600 = 1400 < 1500
    ok, r = st2.can_open_trade(ts=T(10, 0), trade_risk=600)
    check("too-close-to-floor blocks (configurable buffer)", (not ok) and r == "too_close_to_floor")
    ok2, _ = st2.can_open_trade(ts=T(10, 0), trade_risk=100)  # 2000-100=1900 >= 1500
    check("allows when buffer satisfied", ok2)
    # flatten before hard close
    st3 = MFFUState(); st3.record_trade_open(2, 22000, 21980, T(10, 0))
    check("no flatten mid-session", not st3.should_flatten_now(T(11, 0)))
    check("flatten at/after hard close 14:30", st3.should_flatten_now(T(14, 30)))


if __name__ == "__main__":
    for fn in (s1_winning_day, s2_losing_day, s3_daily_loss_halt, s4_eod_drawdown_update_and_lock,
               s5_drawdown_breach, s6_max_trades_per_day, s7_open_position_block, s8_eval_to_funded,
               s8b_eval_consistency_block, s9_payout_eligibility, s10_snapshot_reload, s11_safety_gates):
        fn()
    print(f"\n================  {len(PASS)} passed, {len(FAIL)} failed  ================")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)
