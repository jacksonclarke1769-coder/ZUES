"""ARES AUTO LIVE — automated Profile A trading via the TradersPost bridge.

ZEUS decides → BRIDGE transmits → TradersPost executes. The SimBot is the BRAIN's
position model (sim-only, never places orders itself); the bridge is the ARM.

Live data: credential-free Dukascopy NQ feed (CFD proxy, ~1min delayed; SMALL BASIS vs
Tradovate — calibrate in Stage 2). Profile A (D1c-filtered) + Profile B (ORB) both run in the
live loop; B is gated by --no-profile-b and the P3 brake (zeros B near the floor).

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
from p3_brake import P3Brake
from strategy_engine_profileB import ProfileBEngine


def et_date():
    from zoneinfo import ZoneInfo
    return datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).date().isoformat()


def build_readback(a, mode, journal):
    """Build the Stage B read-back sentinel + a READ-ONLY Tradovate broker view.

    floor = MFFU trailing line (start - trail_dd) from config.EVAL. Returns (sentinel, broker);
    broker is None if no read-only Tradovate connection can be made (caller refuses live if so).
    Fail-closed: a sentinel that cannot read the broker halts entries via BROKER_READ_FAIL.
    """
    from live_readback import ReadbackSentinel, TradovateBrokerView
    ev = getattr(config, "EVAL", {})
    floor = float(ev.get("start_balance", 50_000.0)) - float(ev.get("trail_dd", 2_000.0))
    broker = None
    acct_id = a.account
    try:
        from tradovate_client import TradovateClient
        # READ-ONLY: pass NO safety -> live_orders_ok=False -> this client can NEVER place an order
        # (every real-order method calls _guard_live() which raises). Same config.TRADOVATE/config.HOSTS
        # the bot's data path uses (the env + explicit account_spec live INSIDE config.TRADOVATE).
        client = TradovateClient(config.TRADOVATE, config.HOSTS)
        client.authenticate()                       # auth + resolve the EXPLICIT account (account_spec)
        if getattr(client, "account_id", None):
            acct_id = str(client.account_id)         # numeric Tradovate id == positions()[].accountId
        broker = TradovateBrokerView(client)
        broker.net_by_account()                     # probe the connection (raises if unauthenticated)
    except Exception as e:                          # noqa: BLE001 — degrade, never crash the launcher
        print(f"  read-back: no Tradovate read connection ({type(e).__name__}: {e})", flush=True)
        broker = None
    sentinel = ReadbackSentinel(acct_id, floor=floor, journal=journal)
    return sentinel, broker


class LiveAuto:
    def __init__(self, account, tier, mode, store, journal, sender, daily_stop,
                 d1c_mode="ACTIVE_EVAL_FILTER", basis_offset=0.0, d1c_stale_after_s=360,
                 entry_gate=None, logger=None, cushion_fn=None, p3_enabled=True,
                 profile_b=True, readback=None, notify=None, tjournal=None):
        self.logger = logger           # ARGUS decision logger (auditability; fail-safe, optional)
        self.entry_gate = entry_gate   # infrastructure readiness gate (data GREEN + dead-man alive)
        self.readback = readback       # Stage B: live broker read-back sentinel (closes-the-loop). Optional.
        self.notify = notify           # Telegram notifier (signals + modeled outcomes). Optional, fail-safe.
        self.tjournal = tjournal       # learning journal (why won/lost). Optional, fail-safe.
        # P3 cushion brake + Profile B (research-validated; gated like everything else, paper-first)
        self.p3 = P3Brake()
        self.p3_enabled = p3_enabled
        self.cushion_fn = cushion_fn   # () -> (cushion$, dd_allowance$) or None
        self.profile_b = profile_b
        self.b_engine = ProfileBEngine()
        from profile_b_tracker import ProfileBPaperTracker
        self.b_tracker = ProfileBPaperTracker(store, account, mode, notify=notify, journal=tjournal)   # B P&L + TG + journal
        self.b_sent = self.b_blocked = 0
        # Profile MOMENTUM lane (OFF unless main() wires it behind --profile-momentum) + shared overlap gate
        self.m_engine = None; self.m_executor = None; self.overlap = None
        self.books = []                # fan-out: secondary account books (e.g. Apex) fed the SAME signals
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
        if self.store.get_state("auto_live_halt"):       # soft halt (Telegram /stop): no new entries,
            return "halted (no new entries)"             # but guardian ignores it so the open trade runs
        if hasattr(self.sender, "incident_blocked") and self.sender.incident_blocked():
            return "exit3 incident — manual reset required"
        if self.guard.is_stopped(self.account, et_date()):
            return "daily loss stop hit"
        return None

    def _dlog(self, fn, *a, **k):
        """ARGUS fail-safe: a logging error never raises into the engine, never blocks a send.
        But it must be LOUD — a silently-swallowed log error is exactly how a real B trade
        (2026-06-22 ORB, -$230) went unrecorded and the session auditor reported it CLEAN."""
        try:
            if self.logger is not None:
                getattr(self.logger, fn)(*a, **k)
        except Exception as e:                           # noqa: BLE001
            print(f"[auto-live] ⚠ ARGUS LOG FAILED ({fn}): {e!r} — DECISION NOT RECORDED", flush=True)

    def _apply_p3(self):
        """Update the P3 brake from the live cushion. Returns braked (bool). Inert (no brake)
        if disabled or the cushion is unavailable — P3 only ever REDUCES size near the floor."""
        if not self.p3_enabled or self.cushion_fn is None:
            return False
        try:
            cushion, dd = self.cushion_fn()
            return self.p3.update(cushion, dd)
        except Exception:                                # noqa: BLE001
            return False

    def on_decision(self, sig, placed, reason, ts):
        """SimBot fires this. placed=True means it passed the SimBot risk gate
        (window/one-position/2-per-day/news). We add ZEUS gates + send via bridge."""
        if not placed:
            self.j.append("STATE_ASSERT", self.account, payload=dict(
                action="auto_live_skip", reason=reason, side=sig.get("side")))
            self._dlog("candidate_rejected", bar_ts=ts, side=sig.get("side"),
                       reason=reason or "simbot_risk_gate", entry=sig.get("entry"),
                       stop=sig.get("stop"), target=sig.get("target"))
            return
        kill = self.killed()
        if kill:
            self.blocked += 1
            self.j.append("STATE_ASSERT", self.account, payload=dict(
                action="auto_live_blocked", reason=kill, side=sig.get("side")))
            print(f"[auto-live] BLOCKED ({kill}) — no webhook", flush=True)
            self._dlog("blocked", "ares", bar_ts=ts, side=sig.get("side"), reason=kill)
            return
        # infrastructure readiness gate: block entries on YELLOW/RED data or a dead nervous system
        if self.entry_gate is not None:
            ready, why = self.entry_gate()
            if not ready:
                self.blocked += 1
                self.j.append("STATE_ASSERT", self.account, payload=dict(
                    action="auto_live_blocked", reason="entry gate: " + why, side=sig.get("side")))
                print(f"[auto-live] BLOCKED (entry gate: {why}) — no webhook", flush=True)
                self._dlog("blocked", "data", bar_ts=ts, side=sig.get("side"), reason=why)
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
                self._dlog("blocked", "d1c", bar_ts=ts, side=sig.get("side"),
                           reason=f"drift disagrees (drift={drift})", d1c_mode=self.d1c_mode,
                           d1c_checked=True, d1c_allowed=False)
                return
        spec = EVAL_TIERS[self.tier]
        # P3 cushion brake: near the floor, cut A to max(am//2,1) (and B to 0, handled in on_b_signal)
        braked = self._apply_p3()
        a_size, _ = self.p3.size(spec["am"], spec.get("bm", 0))
        d1c_status = (self.gate.heimdall_status() if self.d1c_mode != "OFF" else "OFF")
        # CONFIGLOCK: resolve the official exit model fail-closed (never silently SINGLE_TARGET).
        from runtime_config import resolve_exit_model, ConfigLockError
        try:
            _exit_model = resolve_exit_model(self.mode if self.mode in ("live", "paper") else "live")
        except ConfigLockError as e:
            print(f"[auto-live] CONFIGLOCK: unsafe exit model blocked — {e}", flush=True)
            self._dlog("blocked", "exitlock", bar_ts=ts, side=sig.get("side"), reason=str(e))
            return
        common = dict(
            account=self.account, strategy="A", setup=sig.get("liq", "sweep-OTE"),
            signal_ts=sig["ts_signal"], side=sig["side"], qty=a_size,
            entry=float(sig["entry"]) + self.basis_offset,
            stop=float(sig["stop"]) + self.basis_offset,
            target=float(sig["target"]) + self.basis_offset,
            root="MNQ", order_type="limit",
            mode_meta=dict(mode="ARES", tier=self.tier),
            d1c_meta=dict(mode=self.d1c_mode, status=d1c_status))
        # EXITFORGE: official model is EXIT3_FIXED_PARTIAL -> two split bracket legs, fail-closed
        if _exit_model == "EXIT3_FIXED_PARTIAL":
            legs, err = BP.build_entry_exit3(**common)
            if err:
                print(f"[auto-live] FAIL CLOSED — exit3 legs not built: {err}", flush=True)
                return
            res = self.sender.send_exit3(legs, self.account, root="MNQ")
            ok = res.get("ok")
        else:
            payload, err = BP.build_entry(**common)
            if err:
                print(f"[auto-live] FAIL CLOSED — payload not built: {err}", flush=True)
                return
            res = self.sender.send(payload)
            ok = res.get("sent")
        if ok or self.mode != "live":
            self.sent += 1
            if self.overlap is not None:                   # feed the cross-strategy overlap gate (A open)
                self.overlap.on_open("A", sig["side"])
            if self.readback is not None:                  # Stage B: tell the sentinel what we now expect to hold
                self.readback.on_entry(sig["side"], a_size)
            if self.notify is not None:                    # Telegram: signal alert on send
                self.notify.signal("A", sig["side"], a_size, float(sig["entry"]),
                                   float(sig["stop"]), float(sig.get("target") or 0), self.mode)
            for bk in self.books:                          # FAN-OUT: same A signal -> each secondary book
                bk.route_a(sig, ts)
        print(f"[auto-live] A {sig['side']} {a_size}MNQ{' (P3-braked)' if braked else ''} "
              f"{_exit_model} @ {sig['entry']:.2f} stop {sig['stop']:.2f} tgt {sig['target']:.2f} "
              f"-> {res.get('reason', 'sent')}",
              flush=True)
        # ARGUS: record the resolved decision (exitlock-block vs paper/live signal) with Exit #3 fields
        _reason = res.get("reason", "")
        if not ok and "exit model" in _reason.lower():
            self._dlog("blocked", "exitlock", bar_ts=ts, side=sig["side"], reason=_reason)
        else:
            _lf = {}
            if _exit_model == "EXIT3_FIXED_PARTIAL":
                for L in legs:
                    if L["role"] == "entry_tp1":
                        _lf.update(tp1_qty=L["qty"], tp1_target=L["target"])
                    elif L["role"] == "entry_tp2":
                        _lf.update(tp2_qty=L["qty"], tp2_target=L["target"])
            self._dlog("signal", bar_ts=ts, side=sig["side"], entry=common["entry"],
                       stop=common["stop"], qty_total=spec["am"],
                       tp1_qty=_lf.get("tp1_qty"), tp1_target=_lf.get("tp1_target"),
                       tp2_qty=_lf.get("tp2_qty"), tp2_target=_lf.get("tp2_target"),
                       signal_id_base=sig["ts_signal"], webhook_sent=bool(ok),
                       traderspost_status=_reason, live=(self.mode == "live"))

    def on_b_signal(self, sig, ts, bar_i=None):
        """Profile B (ORB) entry. NEVER consults D1c. Single bracket (its own ATR stop/target,
        NOT Exit #3). Gated by kill-switch / entry-gate / daily-stop / P3 brake (B=0 near floor).
        Still blocked live by the EXITLOCK flag (it's a buy/sell entry)."""
        if not self.profile_b:
            return
        kill = self.killed()
        if kill:
            self.b_blocked += 1
            self._dlog("blocked", "ares", bar_ts=ts, side=sig.get("side"), reason=kill, profile="B")
            return
        if self.entry_gate is not None:
            ready, why = self.entry_gate()
            if not ready:
                self.b_blocked += 1
                self._dlog("blocked", "data", bar_ts=ts, side=sig.get("side"), reason=why, profile="B")
                return
        spec = EVAL_TIERS[self.tier]
        self._apply_p3()
        _, b_size = self.p3.size(spec["am"], spec.get("bm", 0))
        if b_size <= 0:                                  # P3 brake (or tier has no B) -> no B trade
            self.b_blocked += 1
            self._dlog("blocked", "ares", bar_ts=ts, side=sig.get("side"),
                       reason="P3 brake (B=0)" if self.p3.braked else "no B size in tier", profile="B")
            return
        # B exit: PARTIAL_1R (50% @ +1R, 50% @ frozen 1.5R target, shared stop) when approved & qty>=2;
        # else the prior SINGLE bracket. Frozen B signal/stop/1.5R-target are UNCHANGED — exit split only.
        from config_defaults import resolve_b_exit
        b_exit = resolve_b_exit(self.mode)
        b_common = dict(
            account=self.account, strategy="B", setup=sig.get("liq", "orb"),
            signal_ts=sig["ts_signal"], side=sig["side"], qty=b_size,
            entry=float(sig["entry"]) + self.basis_offset,
            stop=float(sig["stop"]) + self.basis_offset,
            target=float(sig["target"]) + self.basis_offset,
            root="MNQ", order_type="limit", mode_meta=dict(mode="ARES", tier=self.tier, profile="B"))
        b_legs = None
        if b_exit == "PARTIAL_1R" and b_size >= 2:
            b_legs, err = BP.build_entry_exit3(**b_common)   # TP1 @ +1R, TP2 @ B's 1.5R target, shared stop
            if err:
                print(f"[auto-live] B FAIL CLOSED — partial legs not built: {err}", flush=True)
                return
            res = self.sender.send_exit3(b_legs, self.account, root="MNQ")
            ok = res.get("ok")
        else:                                                # qty=1 or SINGLE -> prior single OCO bracket
            payload, err = BP.build_entry(**b_common)
            if err:
                print(f"[auto-live] B FAIL CLOSED — payload not built: {err}", flush=True)
                return
            res = self.sender.send(payload)
            ok = res.get("sent")
        if ok or self.mode != "live":
            self.b_sent += 1
            if self.overlap is not None:                 # feed the cross-strategy overlap gate (B open)
                self.overlap.on_open("B", sig["side"])
            if self.readback is not None:                # Stage B: B adds to expected broker position too
                self.readback.on_entry(sig["side"], b_size)
            if self.notify is not None:                  # Telegram: signal alert on send
                self.notify.signal("B", sig["side"], b_size, float(sig["entry"]),
                                   float(sig["stop"]), float(sig.get("target") or 0), self.mode)
            if bar_i is not None:                        # track B paper-P&L -> dashboard calendar
                self.b_tracker.on_signal(sig, b_size, bar_i, ts, partial=(b_legs is not None))
            for bk in self.books:                        # FAN-OUT: same B signal -> each secondary book
                bk.route_b(sig, ts)
        _xlabel = "PARTIAL(50%@1R/50%@1.5R)" if b_legs is not None else "single"
        print(f"[auto-live] B {sig['side']} {b_size}MNQ ORB {_xlabel} @ {sig['entry']:.2f} "
              f"stop {sig['stop']:.2f} tgt {sig['target']:.2f} -> {res.get('reason', 'sent')}",
              flush=True)
        _reason = res.get("reason", "")
        if not ok and "exit model" in _reason.lower():
            self._dlog("blocked", "exitlock", bar_ts=ts, side=sig["side"], reason=_reason, profile="B")
        else:
            # PARTIAL_1R -> two legs (TP1 @ +1R, TP2 @ 1.5R); single -> all to tp2 slot, tp1 empty.
            _bl = {}
            if b_legs is not None:
                for Lg in b_legs:
                    if Lg["role"] == "entry_tp1":
                        _bl.update(tp1_qty=Lg["qty"], tp1_target=Lg["target"])
                    elif Lg["role"] == "entry_tp2":
                        _bl.update(tp2_qty=Lg["qty"], tp2_target=Lg["target"])
            self._dlog("signal", bar_ts=ts, side=sig["side"], entry=float(sig["entry"]),
                       stop=float(sig["stop"]), qty_total=b_size,
                       tp1_qty=_bl.get("tp1_qty"), tp1_target=_bl.get("tp1_target"),
                       tp2_qty=_bl.get("tp2_qty", b_size), tp2_target=_bl.get("tp2_target", float(sig["target"])),
                       signal_id_base=sig["ts_signal"], webhook_sent=bool(ok),
                       traderspost_status=_reason, live=(self.mode == "live"), profile="B")

    def on_m_bar(self, ts, o, h, l, c):
        """Profile MOMENTUM: feed the engine a completed 5m bar, route any position change. OFF unless wired.
        Returns the engine's latest_signal() dict (or None if not wired / still warming up) so the caller
        can log the evaluation (ARGUS-M) — a zero-trade momentum session must be provable, like A."""
        if self.m_engine is None or self.m_executor is None:
            return None
        try:
            self.m_engine.add_bar(ts, o, h, l, c)
            sig = self.m_engine.latest_signal()
            if sig is not None:
                self.m_executor.on_signal(sig, ts)
                for bk in self.books:                        # FAN-OUT: same Momentum signal -> each book (its mm)
                    bk.route_m(sig, ts)
            return sig
        except Exception as e:                               # noqa: BLE001 — momentum must never break the loop
            print(f"[momentum] on_m_bar error (skipped): {type(e).__name__}: {e}", flush=True)
            return None

    def _log_m_decision(self, ts, sig, data_state="GREEN", engine_bar=None):
        """ARGUS-M: one JSONL row per momentum 5m RTH evaluation so a zero-trade (shadow) momentum session
        is provable — mirrors Profile A's _dlogger. Fail-safe: NEVER raises into the loop, NEVER places/affects
        a send. `ts` is naive ET (same convention as the A/B loggers)."""
        dl = getattr(self, "m_dlogger", None)
        if dl is None:
            return
        try:
            ds = dict(data_state=data_state, data_ready=(data_state == "GREEN"),
                      engine_bar=engine_bar, exit_model="MOMENTUM_POSITION")
            if data_state != "GREEN":                         # feed not ready -> the engine couldn't decide
                dl.log("skipped", bar_ts=str(ts), candidate_detected=False,
                       rejection_reason="feed_not_green", **ds); return
            if sig is None:                                   # ready feed, engine still warming up
                dl.log("skipped", bar_ts=str(ts), candidate_detected=False,
                       rejection_reason="momentum_warmup", **ds); return
            live = (self.mode == "live") and not getattr(self.m_executor, "shadow", True)
            if sig.get("changed"):                            # enter / flip / flatten -> a real momentum signal
                dl.log("live_send" if live else "paper_signal",
                       bar_ts=str(ts), candidate_detected=True, side=sig.get("side"),
                       m_action=sig.get("action"), position=sig.get("position"), prev=sig.get("prev"),
                       slot=sig.get("slot"), close_price=sig.get("close"), shadow=(not live), **ds)
            else:                                             # ready, no position change (flat or holding)
                dl.log("no_signal", bar_ts=str(ts), candidate_detected=False,
                       position=sig.get("position"), slot=sig.get("slot"), close_price=sig.get("close"),
                       note=("holding" if sig.get("position") else "flat"), **ds)
        except Exception:                                     # noqa: BLE001 — logging never breaks momentum
            return

    def overlap_new_day(self):
        """Clear A/B from the overlap gate at a new ET day (intraday positions; conservative)."""
        if self.overlap is not None:
            self.overlap.on_close("A"); self.overlap.on_close("B")


def main(argv=None):
    p = argparse.ArgumentParser(description="ARES AUTO LIVE (Profile A, fail-closed)")
    p.add_argument("--account", required=True)
    p.add_argument("--tier", required=True, choices=list(EVAL_TIERS))
    p.add_argument("--live", action="store_true", help="fire REAL webhooks (gated)")
    p.add_argument("--poll", type=int, default=60)
    p.add_argument("--d1c-mode", default="active-eval-filter",
                   choices=["off", "shadow", "active-eval-filter"])
    p.add_argument("--require-d1c-active", action="store_true",
                   help="ABORT the live launch unless D1c resolves to ACTIVE_EVAL_FILTER (real-time 1m feed "
                        "confirmed). Guards against silently trading the UN-filtered model on a stale feed.")
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
    p.add_argument("--no-profile-b", action="store_true", help="disable Profile B (A-only fallback)")
    p.add_argument("--profile-momentum", action="store_true",
                   help="enable the Profile MOMENTUM lane (Zarattini; default OFF) — routes via the same bridge")
    p.add_argument("--momentum-qty", type=int, default=2, help="Momentum base size in MNQ (default 2)")
    p.add_argument("--momentum-stop", type=float, default=120.0, help="Momentum catastrophic stop (pts, default 120)")
    p.add_argument("--apex-book", action="append", default=[], metavar="ACCOUNT:TIER",
                   help="fan-out a secondary book (e.g. APEX-50K-1:Apex-50K-eval); webhook from "
                        "TRADERSPOST_<ACCOUNT>_URL or TRADERSPOST_APEX_URL. Repeatable. MFFU/primary unaffected.")
    p.add_argument("--no-p3", action="store_true", help="disable the P3 cushion brake")
    p.add_argument("--confirm", action="store_true",
                   help="required (with --live) to arm SUPERVISED LIVE AUTO; extra human gate")
    p.add_argument("--readback", action="store_true",
                   help="Stage B: enable the Tradovate read-back sentinel (closes the fills-by-eye loop). "
                        "Reconciles broker position/balance vs the bot's belief every poll; HALTS entries + "
                        "flattens fail-closed on a confirmed mismatch. Needs read-only Tradovate API creds.")
    p.add_argument("--readback-poll", type=int, default=20,
                   help="seconds between read-back polls (default 20)")
    p.add_argument("--heartbeat-min", type=int, default=60,
                   help="minutes between Telegram heartbeat health pings while live (0 = off, default 60)")
    p.add_argument("--controlled-tv-full-live-test", "--controlled-tv-live-test",
                   dest="controlled_tv_live_test", action="store_true",
                   help="SUPERVISED single-session live test on the TradingView browser feed "
                        "(needs controlled-tv-full-live-test-approved.flag; production browser-feed block stays)")
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
    # --- supervised live auto requires the explicit human --confirm gate (data/exec proof checked post-warmup) ---
    if mode == "live" and not a.confirm:
        print("REFUSED LIVE: --live requires --confirm (supervised-live-auto human gate). Running live without "
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
    # ARGUS decision logger — proves the engine ran (no-signal/candidate/block/send rows). Fail-safe.
    from decision_log import DecisionLogger
    _session_id = f"{a.account}-{a.tier}-{mode}-{et_date()}"
    _dlogger = DecisionLogger(a.account, mode, _session_id, profile="A", feed_source=a.feed,
                              engine_timeframe="5m")
    # --- Stage B: live read-back sentinel (closes the fills-by-eye loop) ---
    readback, _rb_broker = build_readback(a, mode, j) if getattr(a, "readback", False) else (None, None)
    if getattr(a, "readback", False) and mode == "live" and _rb_broker is None:
        print("REFUSED LIVE: --readback requested but no Tradovate read-back connection could be built "
              "(missing/invalid API creds). Read-back is fail-closed — refusing to run live blind.", flush=True)
        return 2

    # --- Telegram notifier (signals + modeled outcomes) — no-op unless TELEGRAM_BOT_TOKEN/CHAT_ID set ---
    from telegram_notify import Telegram
    tg = Telegram(label=f"{a.account} · {a.tier}")
    if tg.enabled:
        print(f"  telegram notifications ON ({a.account})", flush=True)
        tg.info(f"🚀 <b>ARES starting up</b> · {a.account} · {a.tier} · {('LIVE' if mode=='live' else 'PAPER')} · warming feed…")

    # --- learning journal: records every resolved trade + WHY it won/lost (+ post-exit 'stopped early') ---
    from trade_journal import TradeJournal
    from shadow_overlay import ShadowOverlay
    # observe-only forward test of the research's Profile A <=80pt stop-cap (never touches execution)
    shadow = ShadowOverlay(cap_pts=80.0, path=f"logs/shadow/{a.account}_stop_cap.jsonl")
    journal = TradeJournal(a.account, mode, notify=tg, shadow=shadow)
    print("  trade journal ON -> logs/journal/<date>.jsonl (why won/lost + post-exit review)", flush=True)

    auto = LiveAuto(a.account, a.tier, mode, Store(), j, sender, spec["daily_stop"],
                    d1c_mode=d1c_mode, basis_offset=a.basis_offset,
                    d1c_stale_after_s=(120 if dual_1m else 360), logger=_dlogger,
                    profile_b=not getattr(a, "no_profile_b", False),
                    p3_enabled=not getattr(a, "no_p3", False), readback=readback, notify=tg, tjournal=journal)

    # --- Profile MOMENTUM lane (default OFF; --profile-momentum routes it via the same bridge) ---
    if getattr(a, "profile_momentum", False):
        from profile_momentum_engine import ProfileMomentumEngine
        from profile_momentum_live import MomentumExecutor, MomentumPaperTracker
        from overlap_gate import OverlapGate
        auto.overlap = OverlapGate(factor=0.5, participants={"A", "B", "M"})   # half-size 2nd same-dir concurrent
        auto.m_engine = ProfileMomentumEngine()
        auto.m_dlogger = DecisionLogger(a.account, mode, _session_id, profile="M",   # ARGUS-M: provable
                                        feed_source=a.feed, engine_timeframe="5m")    # zero-trade momentum log
        m_tracker = MomentumPaperTracker(a.account, mode, dpp=2.0, stop_pts=a.momentum_stop,
                                         notify=tg, journal=journal)
        auto.m_executor = MomentumExecutor(a.account, sender, root="MNQ", base_qty=a.momentum_qty,
                                           stop_pts=a.momentum_stop, mode=mode, overlap_gate=auto.overlap,
                                           notify=tg, tracker=m_tracker, basis_offset=a.basis_offset,
                                           entry_gate=auto.entry_gate, killed=auto.killed)
        print(f"  Profile MOMENTUM lane ON — {a.momentum_qty} MNQ, {a.momentum_stop:.0f}pt cat-stop, "
              "half-overlap gate (A/B/M). NOTE: own EOD ~15:00; recommend its OWN account vs the 14:30 A-guardian.",
              flush=True)

    # --- FAN-OUT secondary books (e.g. Apex): same engine signals -> another account/size/rules/webhook ---
    for _spec in getattr(a, "apex_book", []):
        try:
            from fanout_book import SecondaryBook
            from auto_safety import FUNDED_TIERS
            _acct, _tname = _spec.split(":", 1)
            _tspec = EVAL_TIERS.get(_tname) or FUNDED_TIERS.get(_tname)
            if not _tspec:
                print(f"  [fan-out] unknown tier '{_tname}' — book {_acct} SKIPPED", flush=True); continue
            from config_defaults import resolve_apex_live
            _bk_url = os.environ.get(f"TRADERSPOST_{_acct.replace('-', '_').upper()}_URL") or os.environ.get("TRADERSPOST_APEX_URL")
            _bk_live = (mode == "live") and resolve_apex_live("live")    # live routing only if apex-approved.flag
            _bk_sender = BridgeSender(store=Store(), journal=j, mode=("live" if _bk_live else "dry-run"), live_url=_bk_url)
            _book = SecondaryBook(_acct, _tspec, _bk_sender, ("live" if _bk_live else "paper"),
                                  notify=tg, basis_offset=a.basis_offset, label=_acct)
            auto.books.append(_book)
            _gate = "LIVE-ROUTING" if _bk_live else ("SHADOW (no apex-approved.flag)" if mode == "live" else "paper")
            print(f"  FAN-OUT book: {_acct} @ {_tname}  A{_tspec.get('am',0)}/B{_tspec.get('bm',0)}/M{_tspec.get('mm',0)} "
                  f"· {'kill-guard ON' if _book.kill else 'no kill-guard'} · {_gate} · "
                  f"{'webhook set' if _bk_url else '⚠ NO webhook (set TRADERSPOST_'+_acct.replace('-','_').upper()+'_URL)'}",
                  flush=True)
        except Exception as _fe:                              # noqa: BLE001 — a book never breaks the primary
            print(f"  [fan-out] book '{_spec}' FAILED to build (skipped): {_fe!r}", flush=True)
    journal.books = auto.books                                # feed each book the primary's scaled resolved P&L

    if readback is not None:
        # critical mismatch -> flatten via the SAME bridge route as the guardian, then stay halted.
        def _rb_flatten(reason):
            print(f"[auto-live] ☠ READ-BACK CRITICAL: {reason} — FLATTEN + HALT", flush=True)
            try:
                sender.flatten(a.account) if hasattr(sender, "flatten") else None
            except Exception as e:                                # noqa: BLE001 — halt stands regardless
                print(f"[auto-live] read-back flatten error: {e!r} (entries already halted)", flush=True)
        readback.on_critical = _rb_flatten
        print(f"  read-back sentinel armed (Tradovate position+balance every {a.readback_poll}s, "
              f"floor=${readback.floor:,.0f}) — fail-closed", flush=True)

    # build the live loop (Dukascopy credential-free feed + SimBot wired to the bridge)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from paper_live import DukascopyLiveFeed, PaperLiveRunner
    import pandas as pd
    import time as _t_mod
    NY = "America/New_York"
    _rb = {"day": None, "t": 0.0}          # Stage B read-back poll tracker (last reset-day, last poll ts)
    _hb = {"t": _t_mod.time()}             # Telegram heartbeat tracker (last ping ts)
    _ctl = {"c": None, "t": 0.0}           # Telegram remote-control poller (set once live) + last-poll ts
    _md = {"d": None}                      # overlap-gate day tracker (clear A/B each new ET day)
    from preopen_guard import PreopenGuard
    _preopen = PreopenGuard()              # pre-open feed-readiness alerts (ORB + Momentum need a clean open)
    runner = PaperLiveRunner(store, "live", "live")
    runner.bot.on_decision = lambda sig, placed, reason, ts: (
        runner._orig(sig, placed, reason, ts), auto.on_decision(sig, placed, reason, ts))
    runner._orig = runner._on_decision
    # P3 reads the live cushion from the account state machine (distance to the trailing floor)
    auto.cushion_fn = lambda: (runner.bot.mffu.distance_to_floor, runner.bot.mffu.cfg.trail_dd)
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
    posture = "SUPERVISED LIVE AUTO" if mode == "live" else "PAPER (dry-run)"
    print(f"=== ARES {posture} · {mode.upper()} · {a.account} · tier {a.tier} "
          f"(A={spec['am']} MNQ) ===")
    _prof_label = "Profile A only" if getattr(a, "no_profile_b", False) else "Profile A + B (ORB)"
    print(f"  data: {data_line} · {_prof_label} · "
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
                         auto_exec_mode=mode, auto_daily_stop=str(spec["daily_stop"]),
                         auto_exec_posture=posture)   # human-facing execution-posture label
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
        # --- guardian (EOD/kill flatten) + entry gate, armed BEFORE the live feed runs ---
        from flatten_guardian import FlattenGuardian
        from heimdall_monitor import deadman_status, entry_ready
        from tv_feed import Bar5Aggregator
        _gmode = "live" if mode == "live" else "dry-run"
        _gurl = os.environ.get("TRADERSPOST_LIVE_URL")
        # Momentum holds to ~15:30 ET; the validated edge (PF 1.83) needs it past the 14:30 A-flat. When the
        # momentum lane is on, defer the EOD BACKSTOP to 15:30 so it doesn't cut momentum. SAFE: A is flat by
        # 14:30 via its own model logic and B closes via its own bracket/max-hold(2h)/RTH-end — a 15:30 backstop
        # is actually MORE faithful to B's backtest, not less. KILL flattens still fire instantly (unaffected).
        from scheduler import Scheduler as _Sched
        from datetime import time as _dtime
        _mom_on = getattr(a, "profile_momentum", False)
        _g_sched = _Sched(flatten_at=_dtime(15, 30)) if _mom_on else None   # half-day flat (12:45) unchanged
        guardian = FlattenGuardian(
            a.account, root="MNQ", scheduler=_g_sched,
            hb_meta=dict(mode=mode, account=a.account, tier=a.tier, d1c_mode=d1c_mode,
                         execution=a.execution, ares_tier=a.tier),
            build=lambda: (BridgeSender(store=Store(), journal=Journal(), mode=_gmode, live_url=_gurl),
                           Store(), Journal()))
        guardian.start()
        print(f"  flatten guardian armed (wall-clock EOD {'15:30 (momentum lane)' if _mom_on else '14:30'} "
              f"+ kill, feed-independent, {_gmode})", flush=True)
        # entries are blocked until ARMED (live arms only after the preflight passes); paper trades now.
        armed = {"v": (mode != "live")}

        from scheduler import Scheduler as _Sched
        from zoneinfo import ZoneInfo as _ZI

        def _entry_ready():
            if auto.readback is not None and auto.readback.halted:    # Stage B: broker read-back disagreement -> fail closed
                return False, "readback HALT: " + (auto.readback.reason or "broker mismatch")
            if not armed["v"]:
                return False, "arming — preflight not passed"
            # holiday gate (defense in depth): never trade a weekend / US market holiday
            _today = datetime.now(timezone.utc).astimezone(_ZI("America/New_York")).date()
            if not _Sched().is_trading_day(_today):
                return False, "market holiday / non-trading day (%s)" % _today
            dstate = feed.data_state() if hasattr(feed, "data_state") else ("GREEN", "")
            return entry_ready(dstate, deadman_status())
        auto.entry_gate = _entry_ready
        print("  entry gate armed (block entries unless armed + data GREEN + dead-man alive + trading day)",
              flush=True)

        # one shared live generator + one per-bar processor (warm-to-GREEN and the main loop both use it)
        _agg = Bar5Aggregator() if dual_1m else None
        live_gen = feed.live()
        _qty = spec["am"]                  # ARES A-tier size (e.g. 3 MNQ for A3)
        _bar = {"i": 0}                    # monotonic engine-bar index for the fill tracker
        _rec = {"n": 0}                    # tracker.rows already appended to the calendar ledger

        def _record_resolved():
            """Append any newly-RESOLVED trades to the dashboard P&L calendar ledger.
            Uses the proven PaperTracker outcome (stop/TP1/TP2/EOD -> result_R); display-only."""
            import trade_results
            old = _rec["n"]
            _rec["n"] = trade_results.record_resolved(
                runner.tracker.rows, old, mode, a.account, _qty)
            for r in runner.tracker.rows[old:_rec["n"]]:   # Telegram outcome + learning journal (modeled)
                rr = r.get("result_R")
                if rr is None:
                    continue
                pnl = trade_results.pnl_from_r(rr, r["entry"], r["stop"], _qty)
                r1, r2 = bool(r.get("tp1_time")), bool(r.get("tp2_time"))
                reason = "target" if r2 else ("stop" if r.get("stop_time") else "eod")
                direc = r.get("direction", "?")
                if tg.enabled:
                    tg.outcome("A", direc, rr, pnl, reason, mode)
                if journal is not None:
                    journal.on_resolved("A", direc, _qty, r["entry"], r["stop"], r.get("tp2"),
                                        None, reason, rr, pnl, r.get("fill_time") or r.get("date"),
                                        reached_1r=r1, reached_2r=r2, hold_bars=None)

        def _engine_bar(bts, bo, bh, bl, bc):
            runner.tracker.on_bar(_bar["i"], bts, bo, bh, bl, bc)   # advance open watches -> resolve exits
            if journal is not None:                                # journal post-exit watch (stopped-early detection)
                journal.on_bar(bh, bl)
            runner._cur = (_bar["i"], bo, bh, bl, bc)
            _nsig = len(runner.bot.signals)
            runner.bot.process_bar(bts, bo, bh, bl, bc)            # may open a watch via _on_decision
            # Profile B (ORB) runs on the same 5m bars, independent of Profile A
            try:
                auto.b_engine.add_bar(bts, bo, bh, bl, bc)
                _bsig = auto.b_engine.latest_signal()
                if _bsig is not None:
                    auto.on_b_signal(_bsig, bts, _bar["i"])
                auto.b_tracker.on_bar(_bar["i"], bts, bo, bh, bl, bc)   # fills/exits -> calendar
            except Exception as _be:                               # noqa: BLE001 — B never breaks A
                print(f"[auto-live] B engine error (ignored): {_be!r}", flush=True)
            _msig = auto.on_m_bar(bts, bo, bh, bl, bc)             # Profile MOMENTUM lane (no-op unless wired)
            # ARGUS: an in-window decision bar with NO signal must still be logged (zero-trade proof)
            try:
                _mins = bts.hour * 60 + bts.minute
                if len(runner.bot.signals) == _nsig and (9 * 60 + 30) <= _mins <= (13 * 60 + 35):
                    _ds = feed.data_state()[0] if hasattr(feed, "data_state") else "GREEN"
                    _dlogger.no_signal(bts, data_state=_ds, data_ready=(_ds == "GREEN"),
                                       engine_bar=_bar["i"])
            except Exception:                                      # noqa: BLE001 — never break the loop
                pass
            # ARGUS-M: log every momentum 5m RTH evaluation (warmup/flat/holding/signal) — zero-trade proof
            try:
                if getattr(auto, "m_dlogger", None) is not None:
                    _mmin = bts.hour * 60 + bts.minute
                    if (9 * 60 + 30) <= _mmin < (16 * 60):         # momentum RTH window (engine ignores non-RTH)
                        _mds = feed.data_state()[0] if hasattr(feed, "data_state") else "GREEN"
                        auto._log_m_decision(bts, _msig, data_state=_mds, engine_bar=_bar["i"])
            except Exception:                                      # noqa: BLE001 — never break the loop
                pass
            runner.bot._persist()
            runner.tracker.persist(store)
            _record_resolved()
            _bar["i"] += 1

        def _process(ts, o, h, l, c):
            if auto.killed():
                print(f"[auto-live] KILL: {auto.killed()} — halting new entries", flush=True)
            auto.feed_gate(ts, o, c)                           # D1c on every bar (+09:30 open)
            if dual_1m:
                done = _agg.add(ts, o, h, l, c)                # native 1m -> D1c; aggregated 5m -> engine
                if done:
                    d_ts, do, dh, dl, dc, _ = done
                    _engine_bar(d_ts, do, dh, dl, dc)
            else:
                _engine_bar(ts, o, h, l, c)
            _persist_data_status(store)
            if auto.overlap is not None:                  # overlap gate: clear A/B at each new ET day
                _d2 = pd.Timestamp(ts).tz_convert(NY).date() if pd.Timestamp(ts).tzinfo else pd.Timestamp(ts).date()
                if _md["d"] != _d2:
                    _md["d"] = _d2; auto.overlap_new_day()
            # --- Stage B: read-back reconcile (rate-limited; bot starts each ET day flat) ---
            if readback is not None and _rb_broker is not None:
                _d = pd.Timestamp(ts).tz_convert(NY).date() if pd.Timestamp(ts).tzinfo else pd.Timestamp(ts).date()
                if _rb["day"] != _d:                          # new trading day -> bot is flat at the open
                    _rb["day"] = _d; readback.on_flat()
                _now = _t_mod.time()
                if _now - _rb["t"] >= a.readback_poll:
                    _rb["t"] = _now
                    conf = readback.poll(_rb_broker)
                    if conf:
                        print(f"[auto-live] read-back: {[(c,d) for c,_,d in conf]}", flush=True)
            # --- Pre-open feed-readiness guard: if the feed isn't GREEN before the 09:30 ET open, alert the
            #     operator EARLY to fix Chrome — a late feed silently kills the ORB + Momentum opening range.
            #     Advisory only: never changes sizing/entries (the fail-closed data gate already blocks trades). ---
            try:
                _pt = pd.Timestamp(ts); _net = (_pt.tz_convert(NY) if _pt.tzinfo else _pt)
                _pds = feed.data_state()[0] if hasattr(feed, "data_state") else "GREEN"
                _pa = _preopen.evaluate(_net, _pds)
                if _pa is not None:
                    print(f"[preopen] {_pa['kind'].upper()} {_pa['et']} — {_pa['msg']}", flush=True)
                    if tg.enabled:
                        tg.send(f"⏰ Pre-open · {a.account}\n{_pa['msg']}")
            except Exception:                                  # noqa: BLE001 — guard never breaks the loop
                pass
            # --- Telegram heartbeat: periodic 'still alive + healthy' ping while live ---
            if tg.enabled and a.heartbeat_min > 0 and armed["v"]:
                _now = _t_mod.time()
                if _now - _hb["t"] >= a.heartbeat_min * 60:
                    _hb["t"] = _now
                    _ds = feed.data_state()[0] if hasattr(feed, "data_state") else "GREEN"
                    _pt = pd.Timestamp(ts); _et = (_pt.tz_convert(NY) if _pt.tzinfo else _pt).strftime("%H:%M ET")
                    tg.heartbeat(_et, _ds, auto.sent, auto.b_sent, auto.blocked, auto.gate.heimdall_status())
            # --- Telegram remote control: poll owner commands, dispatch, reply (rate-limited) ---
            if _ctl["c"] is not None:
                _now = _t_mod.time()
                if _now - _ctl["t"] >= 8:                  # poll getUpdates at most every ~8s
                    _ctl["t"] = _now
                    for _cmd, _reply in _ctl["c"].poll():
                        print(f"[tg-control] /{_cmd} -> {_reply[:80]}", flush=True)
                        tg.send(_reply)

        # --- LIVE: warm the live feed to GREEN, THEN run the preflight (the Dukascopy warmup tail is
        #     stale by design; the live TV feed is current, so wait for it to catch up before arming) ---
        if mode == "live":
            import time as _t
            print("  waiting for live feed to reach GREEN before arming…", flush=True)
            t_end = _t.time() + 300
            for ts, o, h, l, c in live_gen:
                _process(ts, o, h, l, c)
                st, _why = (feed.data_state() if hasattr(feed, "data_state") else ("GREEN", ""))
                if st == "GREEN" or _t.time() > t_end:
                    break
            dgreen = False
            try:
                import zeus_server
                dgreen = bool(zeus_server.assemble_state()["deployment"].get("green"))
            except Exception:
                dgreen = False
            ds_gate = dict(_persist_data_status(store) or {}, daily_stop=spec["daily_stop"])
            ok, fails, eff_d1c, summ = full_auto_preflight(
                a.account, a.feed, requested_d1c, ds_gate, store=dash_store, dashboard_green=dgreen,
                controlled_test=a.controlled_tv_live_test)
            modlabel = "CONTROLLED TV LIVE TEST" if a.controlled_tv_live_test else "SUPERVISED LIVE AUTO"
            if not ok:
                print(f"REFUSED {modlabel} — fail closed:")
                for f in fails:
                    print(f"  ✗ {f}")
                return 2
            if getattr(a, "require_d1c_active", False) and eff_d1c != "ACTIVE_EVAL_FILTER":
                print(f"REFUSED {modlabel}: --require-d1c-active set but D1c resolved to {eff_d1c} "
                      f"(feed not confirmed real-time 1m). D1c is part of the validated model — refusing to "
                      f"trade the UN-filtered version. Fix the feed (logged-in Chrome :9222, NQ 1m, real-time) "
                      f"and relaunch.", flush=True)
                return 2
            armed["v"] = True
            print(f"  {modlabel} preflight PASSED (D1c={eff_d1c}) — ARMED, live webhooks active.", flush=True)
            if a.controlled_tv_live_test:
                print("  ⚠ SUPERVISED TEST on browser feed — operator MUST watch.", flush=True)

        print("  going live · watching the NY-AM window…", flush=True)

        def _health_fields():                            # shared by the go-live card AND /health command
            _ds = (feed.data_state()[0] if hasattr(feed, "data_state") else "GREEN")
            return {
                "Sizing": f"A {spec['am']} MNQ + B {spec['bm']} MNQ",
                "D1c": d1c_mode + (" ✅" if d1c_mode == "ACTIVE_EVAL_FILTER" else " ⚠️ SHADOW"),
                "Data": f"{'✅' if _ds == 'GREEN' else '🔴'} {_ds} · {a.feed}",
                "Daily stop": f"-${spec['daily_stop']:,}",
                "Profiles": "A + B (ORB)" if not getattr(a, "no_profile_b", False) else "A only",
                "Read-back": ("on" if readback is not None else "off") + " · Journal: on · Guardian+gate: armed",
            }

        if tg.enabled:                                   # Telegram: LIVE + health confirmation
            tg.health(mode, a.account, a.tier, _health_fields())
            # --- inbound remote control: owner can text /health /status /stop /flatten /resume ---
            from telegram_control import TelegramControl, HELP
            ctl = TelegramControl()                      # same token/chat_id from env as the notifier

            def _h_health(_a):
                tg.health(mode, a.account, a.tier, _health_fields()); return "✅ sent health card"

            def _h_status(_a):
                _ds = (feed.data_state()[0] if hasattr(feed, "data_state") else "GREEN")
                halt = "🛑 HALTED" if auto.killed() else "🟢 active"
                return (f"{halt} · {a.account}\n"
                        f"• Data: {'✅' if _ds == 'GREEN' else '🔴'} {_ds} · D1c {auto.gate.heimdall_status()}\n"
                        f"• Trades: {auto.sent + auto.b_sent} (A:{auto.sent} B:{auto.b_sent}) · blocked {auto.blocked}")

            def _h_journal(_a):
                es = getattr(journal, "entries", []) if journal is not None else []
                if not es:
                    return "no trades journaled yet today"
                e = es[-1]
                return f"📓 last: P{e['profile']} {e['side']} {e['R']:+.2f}R\n{e['why']}"

            def _h_stop(_a):
                store.set_state(auto_live_halt="telegram /stop")
                return "🛑 HALTED — no new entries. Any open trade runs to its bracket. /resume to re-arm."

            def _h_flatten(_a):
                store.set_state(auto_live_kill="telegram /flatten")   # guardian flattens on next tick + halts
                if guardian is not None:
                    try:
                        guardian._flatten("TELEGRAM")                # immediate, same bridge route as EOD/kill
                    except Exception as e:                           # noqa: BLE001
                        return f"⚠ flatten signal sent (kill flag set); immediate call failed: {e}"
                return "🚨 FLATTEN sent + HALTED. Confirm flat in Tradovate. /resume to re-arm."

            def _h_resume(_a):
                store.set_state(auto_live_halt="", auto_live_kill="")
                return "🟢 RESUMED — halt cleared, watching for entries again."

            def _h_shadow(_a):
                try:
                    from shadow_overlay import ShadowOverlay, load
                    rows = load(shadow.path)                  # full cross-session tally from disk
                    s = ShadowOverlay.summarize(rows, shadow.cap); b, c = s["baseline"], s["capped"]
                    if b["n"] == 0:
                        return f"🧪 Shadow stop-cap ≤{int(shadow.cap)}pt — no Profile A trades observed yet"
                    return (f"🧪 <b>Shadow stop-cap ≤{int(shadow.cap)}pt</b> (observe-only, A)\n"
                            f"• Baseline (all A): {b['n']} tr · {b['totR']:+.1f}R · ${b['totUSD']:+,.0f} · worst-day ${s['worst_day_baseline']:,.0f}\n"
                            f"• Capped book: {c['n']} tr · {c['totR']:+.1f}R · ${c['totUSD']:+,.0f} · worst-day ${s['worst_day_capped']:,.0f}\n"
                            f"• Would-SKIP {s['skipped_n']} (={s['skipped_R']:+.1f}R / ${s['skipped_USD']:+,.0f})")
                except Exception as e:                       # noqa: BLE001
                    return f"⚠ /shadow failed: {e}"

            store.set_state(auto_live_halt="")            # fresh session starts un-halted (kill stays sticky)
            (ctl.on("health", _h_health).on("status", _h_status).on("ping", lambda _a: "🟢 pong — ARES alive")
                .on("journal", _h_journal).on("stop", _h_stop).on("flatten", _h_flatten).on("shadow", _h_shadow)
                .on("resume", _h_resume).on("help", lambda _a: HELP).on("start", lambda _a: HELP))
            _ctl["c"] = ctl if ctl.enabled else None
            if ctl.enabled:
                print("  telegram remote control armed (/help for commands)", flush=True)

        for ts, o, h, l, c in live_gen:
            _process(ts, o, h, l, c)
    except KeyboardInterrupt:
        print(f"\n[auto-live] stopped · {auto.sent} routed · {auto.blocked} gate-blocked · "
              f"{auto.d1c_blocked} D1c-blocked · D1c {auto.gate.heimdall_status()}")
    finally:
        if getattr(auto, "m_executor", None) is not None and auto.m_executor.position != 0:
            try:
                auto.m_executor.eod_flat(pd.Timestamp.utcnow(), ref=None)   # safety: close momentum on shutdown
            except Exception as _me:                          # noqa: BLE001
                print(f"[momentum] shutdown flat skipped: {_me!r}", flush=True)
        if guardian is not None:
            guardian.stop()
        lock.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
