"""ARES AUTO LIVE — automated Profile A trading via the TradersPost bridge.

ZEUS decides → BRIDGE transmits → TradersPost executes. The SimBot is the BRAIN's
position model (sim-only, never places orders itself); the bridge is the ARM.

Live data: credential-free Dukascopy NQ feed (CFD proxy, ~1min delayed; SMALL BASIS vs
Tradovate — calibrate in Stage 2). Profile A only today (B not in the live engine yet).

SAFETY (fail closed):
  * PAPER by default — live data, real signals, dry-run webhooks LOGGED, no orders.
  * LIVE webhook firing requires BOTH evidence/approvals/traderspost-approved.flag AND
    evidence/approvals/bracket-verified.flag (Stage 2 proved brackets attach at Tradovate).
  * Single-instance lock. Per-bar kill-switch + lockout check. Daily-loss guard.
  * SimBot already enforces NY-AM window, one-position-at-a-time, 2 trades/day, flat-by-14:30.
  * MFFU is SEMI-AUTO ONLY — you must SUPERVISE the session. This is not set-and-forget.

Run (paper, safe):
  python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative
Run (live — only after Stage 2 + both flags):
  TRADERSPOST_LIVE_URL=... python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative --live
"""
import argparse
import os
import sys
from datetime import datetime, timezone

import config
from store import Store
from journal import Journal
from instance_lock import InstanceLock, LockHeld
from auto_safety import EVAL_TIERS, APPROVAL_DIR, DailyGuard
import bridge_traderspost as BP
from bridge_sender import BridgeSender
from flatten import LOCK_KEY


def et_date():
    from zoneinfo import ZoneInfo
    return datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).date().isoformat()


class LiveAuto:
    def __init__(self, account, tier, mode, store, journal, sender, daily_stop):
        self.account, self.tier, self.mode = account, tier, mode
        self.store, self.j, self.sender = store, journal, sender
        self.daily_stop = daily_stop
        self.guard = DailyGuard(store)
        self.sent = 0
        self.blocked = 0

    def killed(self):
        if self.store.get_state(LOCK_KEY):
            return "emergency lockout active"
        if self.store.get_state("auto_live_kill"):
            return "operator kill switch"
        if self.guard.is_stopped(self.account, et_date()):
            return "daily loss stop hit"
        return None

    def on_decision(self, sig, placed, reason, ts):
        """SimBot fires this. placed=True means it passed the SimBot risk gate
        (window/one-position/2-per-day/news). We add ZEUS gates + send via bridge."""
        if not placed:
            self.j.append("STATE_ASSERT", self.account, payload=dict(
                action="auto_live_skip", reason=reason, side=sig.get("side")))
            return
        kill = self.killed()
        if kill:
            self.blocked += 1
            self.j.append("STATE_ASSERT", self.account, payload=dict(
                action="auto_live_blocked", reason=kill, side=sig.get("side")))
            print(f"[auto-live] BLOCKED ({kill}) — no webhook", flush=True)
            return
        spec = EVAL_TIERS[self.tier]
        payload, err = BP.build_entry(
            account=self.account, strategy="A", setup=sig.get("liq", "sweep-OTE"),
            signal_ts=sig["ts_signal"], side=sig["side"], qty=spec["am"],
            entry=float(sig["entry"]), stop=float(sig["stop"]),
            target=float(sig["target"]), root="MNQ", order_type="limit",
            mode_meta=dict(mode="ARES", tier=self.tier),
            d1c_meta=dict(mode="OFF", note="live drift not wired — raw validated A"))
        if err:
            print(f"[auto-live] FAIL CLOSED — payload not built: {err}", flush=True)
            return
        res = self.sender.send(payload)
        if res.get("sent") or self.mode != "live":
            self.sent += 1
        print(f"[auto-live] {sig['side']} {spec['am']}MNQ @ {sig['entry']:.2f} "
              f"stop {sig['stop']:.2f} tgt {sig['target']:.2f} -> {res.get('reason', 'sent')}",
              flush=True)


def main(argv=None):
    p = argparse.ArgumentParser(description="ARES AUTO LIVE (Profile A, fail-closed)")
    p.add_argument("--account", required=True)
    p.add_argument("--tier", required=True, choices=list(EVAL_TIERS))
    p.add_argument("--live", action="store_true", help="fire REAL webhooks (gated)")
    p.add_argument("--poll", type=int, default=60)
    a = p.parse_args(argv)

    mode = "live" if a.live else "paper"
    # --- live gating: both flags required, else refuse live and fall to paper ---
    if mode == "live":
        need = ["traderspost-approved.flag", "bracket-verified.flag"]
        missing = [f for f in need if not os.path.exists(os.path.join(APPROVAL_DIR, f))]
        url = os.environ.get("TRADERSPOST_LIVE_URL")
        if missing or not url:
            print("REFUSED LIVE — fail closed:")
            for f in missing:
                print(f"  ✗ missing {APPROVAL_DIR}/{f}")
            if not url:
                print("  ✗ TRADERSPOST_LIVE_URL not set")
            print("  (bracket-verified.flag is set ONLY after Stage 2 proves the stop+target "
                  "attach at Tradovate. Do not skip it — a naked auto-entry blows the eval.)")
            return 2

    try:
        lock = InstanceLock().acquire()
    except LockHeld as e:
        print(f"REFUSED — {e}")
        return 2

    store = Store(getattr(config, "PAPER_DB_PATH", "data/paper.db"))
    j = Journal()
    spec = EVAL_TIERS[a.tier]
    # ARES sizing into the engine's eval qty (Profile A only live)
    config.SIZING = dict(getattr(config, "SIZING", {}), eval_qty=spec["am"], fund_qty=2)

    sender = BridgeSender(store=Store(), journal=j, mode=("live" if mode == "live" else "dry-run"),
                          live_url=os.environ.get("TRADERSPOST_LIVE_URL"))
    auto = LiveAuto(a.account, a.tier, mode, Store(), j, sender, spec["daily_stop"])

    # build the live loop (Dukascopy credential-free feed + SimBot wired to the bridge)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from paper_live import DukascopyLiveFeed, PaperLiveRunner
    import pandas as pd
    NY = "America/New_York"
    runner = PaperLiveRunner(store, "live", "live")
    runner.bot.on_decision = lambda sig, placed, reason, ts: (
        runner._orig(sig, placed, reason, ts), auto.on_decision(sig, placed, reason, ts))
    runner._orig = runner._on_decision
    runner.bot.trade_from = pd.Timestamp.now("UTC").tz_convert(NY)

    feed = DukascopyLiveFeed(poll_sec=a.poll, warmup_days=40)
    feed.connect()
    print(f"=== ARES AUTO LIVE · {mode.upper()} · {a.account} · tier {a.tier} "
          f"(A={spec['am']} MNQ) ===")
    print("  data: Dukascopy NQ (CFD proxy, ~1min delayed) · Profile A only · "
          "D1c OFF (drift not wired live)")
    print("  SAFETY: paper unless --live + both flags · SUPERVISE (MFFU semi-auto) · "
          "Ctrl+C to stop")
    if mode == "paper":
        print("  PAPER — webhooks are dry-run LOGGED, NO orders placed.")
    try:
        for ts, o, h, l, c in feed.history():
            runner.bot.process_bar(ts, o, h, l, c)         # warmup
        print("  warmed up · going live · watching the NY-AM window…", flush=True)
        for ts, o, h, l, c in feed.live():
            if auto.killed():
                print(f"[auto-live] KILL: {auto.killed()} — halting new entries", flush=True)
            runner._cur = (0, o, h, l, c)
            runner.bot.process_bar(ts, o, h, l, c)
            runner.bot._persist()
    except KeyboardInterrupt:
        print(f"\n[auto-live] stopped · {auto.sent} signals routed · {auto.blocked} blocked")
    finally:
        lock.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
