"""
SIM-only orchestration tests for bot.py. No broker, no network, no live orders.

Fast synthetic tests drive the bot's fill/risk/restart logic with hand-made bars;
the final (slower) test replays real bars and checks the engine signal list matches
the backtest over a window (a windowed parity check — full 6-month parity is inherited
unchanged because ProfileAEngine/M1.run were not touched in Step 4).

Run:  python test_bot_sim.py
"""
import sys, os, subprocess
from datetime import datetime
from store import Store
import bot as B
from mffu_state import MFFUState, MFFUConfig, EVALUATION
import config

PASS, FAIL = [], []
DB = "/tmp/botsim_test.db"
T = lambda hh, mm: datetime(2025, 1, 2, hh, mm)


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if (detail and not cond) else ""))


def fresh(mffu=None):
    st = Store(DB); st.reset()
    return B.SimBot(st, mffu=mffu)


def sig(ts, side="long", entry=22000.0, stop=21980.0, target=22040.0):
    return dict(ts_signal=str(ts), side=side, entry=entry, stop=stop, target=target, liq="asia_high")


def evset(b):
    return [e["level"] for e in b.st.events(limit=200)]


def assert_no_live():
    print("\n0 — SIM-only guarantees:")
    src = open(os.path.join(os.path.dirname(__file__), "bot.py")).read()
    check("no TradovateClient import", "import TradovateClient" not in src and "TradovateClient(" not in src)
    check("no live REST/WS/auth calls", all(s not in src for s in ("authenticate(", "place_bracket(", "placeOSO", "_post(", "tradovateapi")))
    check("no live argparse option / run_live / LIVE disabled",
          'add_argument("--live"' not in src and "def run_live" not in src and "LIVE_ENABLED = False" in src)


# ---------------- lifecycle ----------------
def life_tp1_tp2():
    print("\n1a — lifecycle: TP1 then TP2 (eval qty 4):")
    b = fresh()
    b._consider(sig(T(10, 0)), T(10, 0), 22000, 22005, 21999, 22002)      # entry fills @22000
    check("entry filled, pos open (qty 4)", b.trade and b.trade["filled"] == 4 and b.mffu.position_open)
    b._sim_fills(T(10, 5), 22025, 22025, 22010, 22020)                    # TP1 @22020 (2 lots)
    check("TP1 filled, stop reduced to 2", b.trade["tp1_done"] == 2 and b.active.working_orders()["STOP"]["qty"] == 2)
    b._sim_fills(T(10, 10), 22030, 22045, 22030, 22042)                   # TP2 @22040 (2 lots)
    check("closed flat after TP2", b.active is None and not b.mffu.position_open)
    check("balance +240 (80+160)", b.mffu.balance == 50_240, f"{b.mffu.balance}")
    evs = evset(b)
    check("events present", all(e in evs for e in ("entry_placed", "entry_filled", "tp1_filled", "stop_reduced", "tp2_filled", "trade_closed")))


def life_tp1_stop():
    print("\n1b — lifecycle: TP1 then STOP:")
    b = fresh()
    b._consider(sig(T(10, 0)), T(10, 0), 22000, 22005, 21999, 22002)
    b._sim_fills(T(10, 5), 22025, 22025, 22010, 22020)                    # TP1
    b._sim_fills(T(10, 10), 21985, 21990, 21979, 21980)                   # stop @21980 on remaining 2
    check("closed flat", b.active is None and not b.mffu.position_open)
    check("balance ~scratch 50,000 (+80 -80)", b.mffu.balance == 50_000, f"{b.mffu.balance}")
    check("stop_filled logged", "stop_filled" in evset(b))


def life_stop_first():
    print("\n1c — lifecycle: STOP before TP1:")
    b = fresh()
    b._consider(sig(T(10, 0)), T(10, 0), 22000, 22005, 21999, 22002)
    b._sim_fills(T(10, 5), 21985, 21990, 21979, 21982)                    # full stop (4 lots)
    check("closed flat", b.active is None)
    check("balance -160", b.mffu.balance == 49_840, f"{b.mffu.balance}")
    check("targets cancelled", "cancelled" in evset(b))


def life_entry_expires():
    print("\n1d — lifecycle: entry expires unfilled:")
    b = fresh()
    s = sig(T(10, 0)); s["entry"] = 21990.0                               # below the bars -> never fills
    b._consider(s, T(10, 0), 22000, 22005, 21999, 22002)
    check("bracket pending (entry not filled)", b.active is not None and b.trade["filled"] == 0)
    for k in range(14):
        if b.active:
            b._sim_fills(T(10, 5 + k), 22000, 22005, 21999, 22002)        # still never reaches 21990
    check("entry cancelled after TTL", b.active is None)
    check("no trade counted (trades_today 0)", b.mffu.trades_today == 0 and len(b.st.trades()) == 0)
    check("cancelled logged", "cancelled" in evset(b))


# ---------------- risk rejection ----------------
def do_trade(b, ts, win=True):
    b._consider(sig(ts), ts, 22000, 22005, 21999, 22002)
    b._sim_fills(ts, 22050, 22050, 22030, 22045) if win else b._sim_fills(ts, 21979, 21985, 21979, 21980)


def risk_max_trades():
    print("\n2a — risk: max 2 trades/day:")
    b = fresh()
    do_trade(b, T(10, 0)); do_trade(b, T(10, 20))
    check("2 trades taken", b.mffu.trades_today == 2 and len(b.st.trades()) == 2)
    b._consider(sig(T(11, 0)), T(11, 0), 22000, 22005, 21999, 22002)
    check("3rd rejected (max_trades)", b.active is None and "risk_rejected" in evset(b))


def risk_open_position():
    print("\n2b — risk: open-position block:")
    b = fresh()
    b._consider(sig(T(10, 0)), T(10, 0), 22000, 22005, 21999, 22002)      # leaves position open
    n_before = len(b.st.trades())
    b._consider(sig(T(10, 5)), T(10, 5), 22000, 22005, 21999, 22002)      # 2nd while open
    check("2nd signal rejected while in position", b.trade["entry"] == 22000 and len(b.st.trades()) == n_before)
    check("position still the first one", b.mffu.position_open)


def risk_daily_halt():
    print("\n2c — risk: $800 daily-loss halt:")
    b = fresh()
    b._consider(sig(T(10, 0), stop=21900.0), T(10, 0), 22000, 22005, 21999, 22002)   # 100pt stop, qty4 -> $800 risk
    b._sim_fills(T(10, 5), 21899, 21905, 21899, 21900)                                # stop -> -$800
    check("day loss = 800, halted", b.mffu.daily_loss_used == 800 and b.mffu.should_halt_today())
    b._consider(sig(T(10, 30)), T(10, 30), 22000, 22005, 21999, 22002)
    check("new trade blocked (daily halt)", b.active is None)
    check("account not failed", b.mffu.phase == EVALUATION and not b.mffu.breached)


def risk_floor_buffer():
    print("\n2d — risk: floor-buffer block (configurable):")
    b = fresh(mffu=MFFUState(MFFUConfig(min_floor_buffer=1500)))          # distance 2000 - risk must stay >=1500
    b._consider(sig(T(10, 0), entry=22000.0, stop=21925.0), T(10, 0), 22000, 22005, 21999, 22002)  # 75pt*8=$600 risk -> 1400<1500
    check("rejected too_close_to_floor", b.active is None and "risk_rejected" in evset(b))


# ---------------- restart recovery ----------------
def restart_recovery():
    print("\n3 — restart recovery from snapshots:")
    # pending bracket
    b = fresh()
    s = sig(T(10, 0)); s["entry"] = 21990.0
    b._consider(s, T(10, 0), 22000, 22005, 21999, 22002)                  # pending (unfilled)
    r = B.SimBot.restore(b.st)
    check("pending bracket restored", r.active is not None and r.trade["filled"] == 0 and r.active.bid == b.active.bid)
    # open position
    b2 = fresh()
    b2._consider(sig(T(10, 0)), T(10, 0), 22000, 22005, 21999, 22002)     # entry fills, open
    snap_mffu = b2.mffu.snapshot()
    r2 = B.SimBot.restore(b2.st)
    check("open position restored", r2.active is not None and r2.trade["filled"] == 4 and r2.mffu.position_open)
    check("MFFUState restored identically", r2.mffu.snapshot() == snap_mffu)
    # reloaded bot can keep trading the same position to completion
    r2._sim_fills(T(10, 10), 22050, 22050, 22030, 22045)
    check("reloaded bot closes the trade", r2.active is None and not r2.mffu.position_open)


# ---------------- windowed signal parity ----------------
def sim_signal_parity():
    print("\n4 — SIM replay signal list == backtest (window, ~6 weeks):")
    START, END = "2025-10-20", "2025-12-01"
    b = B.run_sim(START, END, reset=True, db_path=DB)
    sim_keys = {s["ts_signal"] for s in b.signals}
    # backtest reference for the same window
    sys.path.insert(0, os.path.join(B.FW, "engine")); sys.path.insert(0, os.path.join(B.FW, "models"))
    import htf, model01_sweep_mss_fvg as M1, pandas as pd
    from strategy_engine_profileA import PROFILE_A
    f = htf.build_features("NQ", "5m"); f.index.name = "timestamp"
    tr = M1.run(f, "NQ", PROFILE_A); tr = tr[tr.session == "ny_am"].copy()
    tr["k"] = tr["date"].astype(str) + " " + tr["time"]
    tr["d"] = pd.to_datetime(tr["date"].astype(str))
    ref = tr[(tr.d >= START) & (tr.d < END)]
    ref_keys = set(ref["k"])
    check(f"engine signals == backtest ({len(ref_keys)} trades): missing={len(ref_keys - sim_keys)} extra={len(sim_keys - ref_keys)}",
          sim_keys == ref_keys, f"missing={sorted(ref_keys - sim_keys)[:3]} extra={sorted(sim_keys - ref_keys)[:3]}")
    check("dashboard/store received events", len(b.st.events(limit=5)) > 0 and len(b.st.get_state()) > 0)


# ---------------- regression of sibling suites ----------------
def regression():
    print("\n5 — regression (sibling test suites):")
    here = os.path.dirname(os.path.abspath(__file__))
    for t in ("test_mffu_state.py", "test_two_leg_bracket.py"):
        r = subprocess.run([sys.executable, os.path.join(here, t)], capture_output=True, text=True)
        check(f"{t} still passes", r.returncode == 0, r.stdout.splitlines()[-1] if r.stdout else r.stderr[-200:])


if __name__ == "__main__":
    assert_no_live()
    for fn in (life_tp1_tp2, life_tp1_stop, life_stop_first, life_entry_expires,
               risk_max_trades, risk_open_position, risk_daily_halt, risk_floor_buffer,
               restart_recovery, regression, sim_signal_parity):
        fn()
    print(f"\n================  {len(PASS)} passed, {len(FAIL)} failed  ================")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)
