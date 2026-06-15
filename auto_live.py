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
import json
import os
import sys
from datetime import datetime, timezone

import config
from store import Store
from journal import Journal
from instance_lock import InstanceLock, LockHeld
from auto_safety import (EVAL_TIERS, APPROVAL_DIR, DailyGuard,
                         resolve_d1c_for_feed, full_auto_preflight, feed_timeframe)
import bridge_traderspost as BP
from bridge_sender import BridgeSender
from flatten import LOCK_KEY
from drift_gate import DriftGate
import d1c_filter
from datetime import time as _dtime


def et_date():
    from zoneinfo import ZoneInfo
    return datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).date().isoformat()


class LiveAuto:
    def __init__(self, account, tier, mode, store, journal, sender, daily_stop,
                 d1c_mode="ACTIVE_EVAL_FILTER", basis_offset=0.0, d1c_stale_after_s=360,
                 entry_gate=None):
        self.entry_gate = entry_gate   # infrastructure readiness gate (data GREEN + dead-man alive)
        self.account, self.tier, self.mode = account, tier, mode
        self.store, self.j, self.sender = store, journal, sender
        self.daily_stop = daily_stop
        self.guard = DailyGuard(store)
        self.d1c_mode = d1c_mode
        self.basis_offset = basis_offset   # points added to feed prices to match Tradovate
        # real CERBERUS-validated D1c. 1m feed -> 120s (validated); 5m feed -> 360s tolerance.
        self.gate = DriftGate(enabled=(d1c_mode in ("ACTIVE_EVAL_FILTER", "SHADOW")),
                              stale_after_s=d1c_stale_after_s)
        self.sent = self.blocked = self.d1c_blocked = 0

    def feed_gate(self, ts, o, c):
        """Call every completed bar (ET) so D1c has the 09:30 open + last close."""
        if ts.time() == _dtime(9, 30):
            self.gate.on_session_open(ts, o)
        self.gate.on_bar_close(ts, c)

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
        # infrastructure readiness gate: block entries on YELLOW/RED data or a dead nervous system
        if self.entry_gate is not None:
            ready, why = self.entry_gate()
            if not ready:
                self.blocked += 1
                self.j.append("STATE_ASSERT", self.account, payload=dict(
                    action="auto_live_blocked", reason="entry gate: " + why, side=sig.get("side")))
                print(f"[auto-live] BLOCKED (entry gate: {why}) — no webhook", flush=True)
                return
        # --- D1c defensive filter (Profile A only) ---
        if self.d1c_mode in ("ACTIVE_EVAL_FILTER", "SHADOW"):
            keep = self.gate.allows(sig["side"], ts)
            drift = self.gate.drift()
            decision = "KEEP" if keep else "SUSPEND/BLOCK"
            permit = keep or self.d1c_mode == "SHADOW"
            d1c_filter.log_decision(
                self.account, self.d1c_mode, sig.get("liq", "sweep-OTE"), sig["side"],
                drift, (1 if (drift or 0) > 0 else -1 if (drift or 0) < 0 else 0),
                decision, f"keep_rate={self.gate.keep_rate()}", permit, source="ares_eval")
            if self.d1c_mode == "ACTIVE_EVAL_FILTER" and not keep:
                self.d1c_blocked += 1
                print(f"[auto-live] D1c BLOCK ({sig['side']}, drift={drift}) — no webhook",
                      flush=True)
                return
        spec = EVAL_TIERS[self.tier]
        d1c_status = (self.gate.heimdall_status() if self.d1c_mode != "OFF" else "OFF")
        payload, err = BP.build_entry(
            account=self.account, strategy="A", setup=sig.get("liq", "sweep-OTE"),
            signal_ts=sig["ts_signal"], side=sig["side"], qty=spec["am"],
            entry=float(sig["entry"]) + self.basis_offset,
            stop=float(sig["stop"]) + self.basis_offset,
            target=float(sig["target"]) + self.basis_offset,
            root="MNQ", order_type="limit",
            mode_meta=dict(mode="ARES", tier=self.tier),
            d1c_meta=dict(mode=self.d1c_mode, status=d1c_status))
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
    p.add_argument("--d1c-mode", default="active-eval-filter",
                   choices=["off", "shadow", "active-eval-filter"])
    p.add_argument("--basis-offset", type=float, default=0.0,
                   help="points added to feed prices to match Tradovate (measure via Stage 2)")
    p.add_argument("--feed", default="dukascopy",
                   choices=["dukascopy", "tradovate", "tradingview", "tradingview-5m", "tradingview-1m"],
                   help="dukascopy=credential-free CFD proxy (basis); tradovate=zero-basis API md (needs access); "
                        "tradingview/-5m=REAL CME 5m via Chrome CDP; tradingview-1m=1m (engine path NOT built — refused)")
    p.add_argument("--mode", default="eval", choices=["eval", "funded"],
                   help="ARES eval mode (default) or ZEUS funded mode")
    p.add_argument("--execution", default="traderspost", choices=["traderspost"],
                   help="execution route (TradersPost bridge only today)")
    p.add_argument("--confirm", action="store_true",
                   help="required (with --live) to arm FULL AUTO; extra human gate")
    p.add_argument("--warmup-source", default="dukascopy", choices=["dukascopy", "tradingview"],
                   dest="warmup_source",
                   help="(tradingview feed) deep warmup source: dukascopy=40d current bars basis-aligned to CME "
                        "(default, guarantees prev-week/day levels); tradingview=chart cache only (shallow)")
    p.add_argument("--warmup-days", type=int, default=45, dest="warmup_days",
                   help="(tradingview feed) calendar days of warmup history to pull (default 45)")
    a = p.parse_args(argv)
    requested_d1c = a.d1c_mode.upper().replace("-", "_")

    # tradingview-1m: read native 1m (D1c) and AGGREGATE 1m->5m for the engine (Profile A stays 5m).
    # Aggregation is verified to match TradingView's native 5m bar-for-bar, so Profile A is unchanged.
    dual_1m = (feed_timeframe(a.feed) == 1)

    # --- Task 4: D1c may be ACTIVE_EVAL_FILTER only on a real-time 1m feed; else forced SHADOW ---
    realtime_confirmed = os.environ.get("TV_REALTIME_CONFIRMED") == "1"
    d1c_mode, d1c_downgrade = resolve_d1c_for_feed(requested_d1c, a.feed, realtime_confirmed)
    if d1c_downgrade:
        print(f"  D1c: requested {requested_d1c} -> {d1c_mode} ({d1c_downgrade})")

    mode = "live" if a.live else "paper"
    # --- full-auto requires the explicit human --confirm gate (data/exec proof checked post-warmup) ---
    if mode == "live" and not a.confirm:
        print("REFUSED LIVE: --live requires --confirm (full-auto human gate). Running live without "
              "confirmation is forbidden.")
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
    auto = LiveAuto(a.account, a.tier, mode, Store(), j, sender, spec["daily_stop"],
                    d1c_mode=d1c_mode, basis_offset=a.basis_offset,
                    d1c_stale_after_s=(120 if dual_1m else 360))

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

    if a.feed == "tradovate":
        from paper_live import LiveBarFeed
        feed = LiveBarFeed(config, poll_sec=a.poll)      # zero-basis CME md (needs API access)
        contract = feed.connect()
        data_line = f"Tradovate API market data (zero basis) · {contract.get('name')}"
    elif a.feed in ("tradingview", "tradingview-5m"):
        from tv_feed import TradingViewFeed
        feed = TradingViewFeed(poll_sec=a.poll, warmup=5000,           # REAL CME 5m live tail via Chrome CDP
                               warmup_source=a.warmup_source, warmup_days=a.warmup_days)
        contract = feed.connect()
        data_line = (f"TradingView CDP · REAL CME · {contract.get('name')} @ {contract.get('resolution')}m "
                     f"· warmup={a.warmup_source} {a.warmup_days}d")
    elif a.feed == "tradingview-1m":
        from tv_feed import TradingViewFeed
        feed = TradingViewFeed(poll_sec=a.poll, warmup=5000, expect_res="1",   # native 1m -> D1c; agg 5m -> engine
                               warmup_source=a.warmup_source, warmup_days=a.warmup_days)
        contract = feed.connect()
        data_line = (f"TradingView CDP · REAL CME · {contract.get('name')} @ 1m->5m DUAL "
                     f"(engine 5m + D1c 1m) · warmup={a.warmup_source} {a.warmup_days}d")
    else:
        feed = DukascopyLiveFeed(poll_sec=a.poll, warmup_days=40)
        feed.connect()
        data_line = "Dukascopy NQ (CFD proxy 5m, has basis)"
    print(f"=== ARES AUTO LIVE · {mode.upper()} · {a.account} · tier {a.tier} "
          f"(A={spec['am']} MNQ) ===")
    print(f"  data: {data_line} · Profile A only · "
          f"D1c {d1c_mode} (real DriftGate, validated 1m — running on 5m feed)")
    print("  SAFETY: paper unless --live + both flags · SUPERVISE (MFFU semi-auto) · "
          "Ctrl+C to stop")
    if a.basis_offset:
        print(f"  basis offset: {a.basis_offset:+.2f} pts added to all prices")
    elif mode == "live" and a.feed == "dukascopy":
        print("  WARNING: basis_offset=0 — calibrate it from Stage 2 before live (Dukascopy is a proxy)")
    if mode == "paper":
        print("  PAPER — webhooks are dry-run LOGGED, NO orders placed.")
    dash_store = Store()       # default DB (data/bot.db) — the one zeus_server dashboard reads
    # keep the dashboard truthful about the actual execution posture
    dash_store.set_state(execution_route=a.execution,
                         webhook_mode=("live" if mode == "live" else "dry-run"),
                         auto_exec_mode=mode, auto_daily_stop=str(spec["daily_stop"]))
    def _persist_data_status(_=None):
        """Mirror feed.data_status() into the DASHBOARD store so it never shows false-green."""
        if hasattr(feed, "data_status"):
            ds = feed.data_status()
            dash_store.set_state(data_status=json.dumps(ds))
            return ds
        return None

    guardian = None
    try:
        n_warm = 0
        for ts, o, h, l, c in feed.history():
            auto.feed_gate(ts, o, c)
            runner.bot.process_bar(ts, o, h, l, c)         # warmup
            n_warm += 1
        ds = _persist_data_status(store)
        if ds is not None:
            print(f"  warmup: {n_warm} bars · span {ds['span_days']}d · warmup_ok={ds['warmup_ok']} "
                  f"· basis {ds['basis']:+.2f} · DATA_READY={ds['DATA_READY']}", flush=True)
            if not ds["DATA_READY"]:
                print("  DATA NOT READY: " + "; ".join(ds["reasons"]), flush=True)
        # --- APOLLO: FULL AUTO master gate (only when --live). Fail-closed. ---
        if mode == "live":
            dgreen = False
            try:
                import zeus_server
                dgreen = bool(zeus_server.assemble_state()["deployment"].get("green"))
            except Exception:
                dgreen = False
            ds_gate = dict(ds or {}, daily_stop=spec["daily_stop"])
            ok, fails, eff_d1c, summ = full_auto_preflight(
                a.account, a.feed, requested_d1c, ds_gate, store=dash_store, dashboard_green=dgreen)
            if not ok:
                print("REFUSED FULL AUTO — fail closed:")
                for f in fails:
                    print(f"  ✗ {f}")
                lock.release()
                return 2
            print(f"  FULL AUTO preflight PASSED (D1c={eff_d1c}) — arming live webhooks.", flush=True)
        # --- wall-clock EOD + kill auto-flatten (feed-independent; closes a live position even
        #     if the bar feed dies before 14:30). Builds its own DB objects inside its thread. ---
        from flatten_guardian import FlattenGuardian
        from heimdall_monitor import deadman_status, entry_ready
        _gmode = "live" if mode == "live" else "dry-run"
        _gurl = os.environ.get("TRADERSPOST_LIVE_URL")
        guardian = FlattenGuardian(
            a.account, root="MNQ",
            hb_meta=dict(mode=mode, account=a.account, tier=a.tier, d1c_mode=d1c_mode,
                         execution=a.execution, ares_tier=a.tier),
            build=lambda: (BridgeSender(store=Store(), journal=Journal(), mode=_gmode, live_url=_gurl),
                           Store(), Journal()))
        guardian.start()
        print(f"  flatten guardian armed (wall-clock EOD 14:30 + kill, feed-independent, {_gmode})",
              flush=True)
        # entry readiness gate: only route entries when data is GREEN and the dead-man is alive
        def _entry_ready():
            dstate = feed.data_state() if hasattr(feed, "data_state") else ("GREEN", "")
            return entry_ready(dstate, deadman_status())
        auto.entry_gate = _entry_ready
        print("  entry gate armed (block entries unless data GREEN + dead-man alive)", flush=True)
        print("  warmed up · going live · watching the NY-AM window…", flush=True)
        if dual_1m:
            # native 1m -> D1c (validated fidelity); aggregated 5m -> Profile A engine
            from tv_feed import Bar5Aggregator
            agg = Bar5Aggregator()
            for ts, o, h, l, c in feed.live():                # native 1m bars
                if auto.killed():
                    print(f"[auto-live] KILL: {auto.killed()} — halting new entries", flush=True)
                auto.feed_gate(ts, o, c)                       # D1c on every 1m close (+09:30 open)
                done = agg.add(ts, o, h, l, c)
                if done:
                    d_ts, do, dh, dl, dc, _ = done
                    runner._cur = (0, do, dh, dl, dc)
                    runner.bot.process_bar(d_ts, do, dh, dl, dc)   # engine on completed 5m
                    runner.bot._persist()
                _persist_data_status(store)
        else:
            for ts, o, h, l, c in feed.live():
                if auto.killed():
                    print(f"[auto-live] KILL: {auto.killed()} — halting new entries", flush=True)
                auto.feed_gate(ts, o, c)
                runner._cur = (0, o, h, l, c)
                runner.bot.process_bar(ts, o, h, l, c)
                runner.bot._persist()
                _persist_data_status(store)
    except KeyboardInterrupt:
        print(f"\n[auto-live] stopped · {auto.sent} routed · {auto.blocked} gate-blocked · "
              f"{auto.d1c_blocked} D1c-blocked · D1c {auto.gate.heimdall_status()}")
    finally:
        if guardian is not None:
            guardian.stop()
        lock.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
