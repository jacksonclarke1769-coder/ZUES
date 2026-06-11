"""
Tests for paper-LIVE validation mode. Data-only; no broker, no orders, no credentials.

Run:  python test_paper_live.py
"""
import sys, os, subprocess
from datetime import datetime
from store import Store
import paper_live as PL
from paper_live import PaperTracker, PaperLiveRunner, ReplayFeed, FakeFeed
import config

PASS, FAIL = [], []
CSV = "/tmp/paper_test.csv"
T = lambda hh, mm: datetime(2025, 11, 3, hh, mm)   # EST weekday


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if (detail and not cond) else ""))


def sig(side="long", entry=22000.0, stop=21980.0, target=22040.0):
    return dict(side=side, entry=entry, stop=stop, target=target, liq="asia_high")


def fresh_tracker():
    if os.path.exists(CSV):
        os.remove(CSV)
    return PaperTracker(cfg=config, csv_path=CSV)


# ---------------- 2. no live broker calls ----------------
def t_no_live():
    print("\n2 — no live broker calls / data-only:")
    src = open(os.path.join(os.path.dirname(__file__), "paper_live.py")).read()
    # Option A: a market-data client is allowed (auth/contract/get_bars), but NO order method may appear.
    check("no order placement anywhere (data-only)", all(s not in src for s in
          ("place_bracket", "placeOSO", "place_market", "place_order", "liquidatePosition", "/order/", ".flatten(")))
    check("market data is read-only (auth + contract + get_bars only)",
          "get_bars" in src and "resolve_front_month" in src and "authenticate" in src)
    check("feeds present (Replay / Fake / Live)",
          all(x in src for x in ("class ReplayFeed", "class FakeFeed", "class LiveBarFeed")))


# ---------------- 5. fake feed -> each lifecycle outcome ----------------
def t_lifecycle_outcomes():
    print("\n5 — fake bars produce each fill outcome (tracker ledger):")
    # entry fill -> TP1 -> TP2
    t = fresh_tracker()
    t.add_watch(sig(), 0, T(10, 0), 22001, 22005, 21999, 22002)        # entry fills clean
    t.on_bar(1, T(10, 5), 22015, 22025, 22010, 22020)                  # TP1 @22020
    t.on_bar(2, T(10, 10), 22030, 22045, 22030, 22042)                 # TP2 @22040
    r = t.rows[-1]
    check("entry fill + TP1 + TP2 -> +1.5R", r["result_R"] == 1.5 and r["tp1_time"] and r["tp2_time"] and r["fill_quality"] == "clean")

    # entry fill -> stop (before TP1)
    t = fresh_tracker()
    t.add_watch(sig(), 0, T(10, 0), 22001, 22005, 21999, 22002)
    t.on_bar(1, T(10, 5), 21985, 21990, 21979, 21982)                  # stop @21980
    r = t.rows[-1]
    check("entry fill + stop -> ~-1R", r["result_R"] < -0.99 and r["stop_time"] and not r["tp1_time"])

    # entry fill -> TP1 -> stop
    t = fresh_tracker()
    t.add_watch(sig(), 0, T(10, 0), 22001, 22005, 21999, 22002)
    t.on_bar(1, T(10, 5), 22015, 22025, 22010, 22020)                  # TP1
    t.on_bar(2, T(10, 10), 21985, 21990, 21979, 21981)                 # stop on remainder
    r = t.rows[-1]
    check("TP1 then stop -> ~0R (scratch)", -0.1 < r["result_R"] <= 0 and r["tp1_time"] and r["stop_time"])

    # entry expiry (never touched)
    t = fresh_tracker()
    t.add_watch(sig(entry=21990.0), 0, T(10, 0), 22001, 22005, 21999, 22002)   # entry below bars
    t.on_bar(1, T(11, 35), 22001, 22005, 21999, 22002)                # 11:35 ET > entry window -> expire
    r = t.rows[-1]
    check("entry expiry -> missed, result None", r["fill_quality"] == "missed" and r["result_R"] is None and "entry_expired_unfilled" in r["notes"])

    # touch-only fill (miss-risk flag) + gap classification
    t = fresh_tracker()
    t.add_watch(sig(), 0, T(10, 0), 22001, 22005, 22000, 22002)        # low == entry exactly -> touch
    r_open = t.open[0]
    check("exact-touch entry flagged miss-risk", r_open["fill_quality"] == "touch" and "touch_only_fill_miss_risk" in r_open["notes"])


# ---------------- CSV + metrics shape ----------------
def t_csv_and_metrics():
    print("\n5b — CSV ledger + metrics panel:")
    t = fresh_tracker()
    t.add_watch(sig(), 0, T(10, 0), 22001, 22005, 21999, 22002); t.on_bar(1, T(10, 5), 22015, 22025, 22010, 22020); t.on_bar(2, T(10, 10), 22030, 22045, 22030, 22042)  # win
    t.add_watch(sig(), 0, T(10, 20), 22001, 22005, 21999, 22002); t.on_bar(1, T(10, 25), 21985, 21990, 21979, 21982)  # loss
    check("CSV written with exact columns", open(CSV).readline().strip() == ",".join(PL.CSV_COLS))
    m = t.metrics()
    check("metrics panel has all required keys", all(k in m for k in
          ("total_paper_signals", "filled_paper_trades", "missed_paper_trades", "tp1_hit_pct", "tp2_hit_pct",
           "stop_hit_pct", "est_PF", "est_expectancy_R", "avg_stop_size_pts", "avg_slippage_est_pts")))
    check("counts sane (2 signals, 2 filled)", m["total_paper_signals"] == 2 and m["filled_paper_trades"] == 2)
    check("avg stop size = 20pt", m["avg_stop_size_pts"] == 20.0)


# ---------------- 4. persist / resume after restart ----------------
def t_restart():
    print("\n4 — state persists and resumes after restart:")
    st = Store("/tmp/paper_restart.db"); st.reset()
    t = fresh_tracker()
    t.add_watch(sig(), 0, T(10, 0), 22001, 22005, 21999, 22002); t.on_bar(1, T(10, 5), 22015, 22025, 22010, 22020); t.on_bar(2, T(10, 10), 22030, 22045, 22030, 22042)  # resolved win
    t.add_watch(sig(), 3, T(10, 20), 22001, 22005, 21999, 22002)      # left OPEN (filled, no exit yet)
    st.set_state(paper_tracker_snapshot=t.snapshot())
    rows_before, open_before = list(t.rows), len(t.open)
    # restore via the runner
    r = PaperLiveRunner.restore(st, "2025-11-01", "2025-12-01")
    check("rows preserved on restore", r.tracker.rows == rows_before)
    check("open watch preserved on restore", len(r.tracker.open) == open_before == 1)
    # the resumed tracker can finish the open trade
    r.tracker.on_bar(4, T(10, 30), 22030, 22045, 22030, 22042)        # TP2
    check("resumed tracker closes the open trade (+1.5R)", r.tracker.rows[-1]["result_R"] == 1.5 and len(r.tracker.open) == 0)


# ---------------- 3. runs without credentials (ReplayFeed) ----------------
def t_credfree_run():
    print("\n3 — paper-live runs WITHOUT credentials (ReplayFeed, short window):")
    st = Store("/tmp/paper_credfree.db"); st.reset()
    csv = "/tmp/paper_credfree.csv"
    runner = PaperLiveRunner(st, "2025-11-24", "2025-12-01", csv_path=csv)
    runner.run(ReplayFeed("2025-11-24", "2025-12-01", warmup_days=30))
    m = st.get_state("paper")
    check("completed and persisted metrics", m is not None and "total_paper_signals" in m)
    check("produced >=1 paper signal", m and m["total_paper_signals"] >= 1, f"{m}")
    check("CSV ledger exists with header", os.path.exists(csv) and open(csv).readline().startswith("date,direction"))
    check("dashboard store has paper panel + events", len(st.events(limit=5)) > 0 and st.get_state("paper") is not None)
    print(f"    panel: {m}")


# ---------------- 1. regression ----------------
def t_regression():
    print("\n1 — regression (existing suites green):")
    here = os.path.dirname(os.path.abspath(__file__))
    for t in ("test_mffu_state.py", "test_two_leg_bracket.py"):
        r = subprocess.run([sys.executable, os.path.join(here, t)], capture_output=True, text=True)
        check(f"{t} still passes", r.returncode == 0, (r.stdout.splitlines() or [r.stderr[-160:]])[-1])


if __name__ == "__main__":
    for fn in (t_no_live, t_lifecycle_outcomes, t_csv_and_metrics, t_restart, t_regression, t_credfree_run):
        fn()
    print(f"\n================  {len(PASS)} passed, {len(FAIL)} failed  ================")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)
