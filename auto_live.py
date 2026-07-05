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

import env_loader  # noqa: F401 — loads .env into os.environ (TRADERSPOST_LIVE_URL etc.) before any env reads
import config
from store import Store
from journal import Journal
from instance_lock import InstanceLock, LockHeld
from auto_safety import (EVAL_TIERS, FUNDED_TIERS, APPROVAL_DIR, DailyGuard,
                         resolve_d1c_for_feed, full_auto_preflight, feed_timeframe,
                         webhook_route_collisions)


def _tier_spec(tier):
    """Resolve a --tier name to its sizing spec — eval OR funded (Apex-50K / Apex-50K-scaled etc.)."""
    s = EVAL_TIERS.get(tier) or FUNDED_TIERS.get(tier)
    if s is None:
        raise ValueError(f"unknown tier {tier!r}; options: {list(EVAL_TIERS) + list(FUNDED_TIERS)}")
    return s
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


def _on_missing_cancel_is_safe(auto_inst):
    """Cancel-all-working-MNQ is SAFE only when A is the sole open lane (single-lane A-only machine).
    Returns (safe:bool, reason:str). Called by the on_missing handler before sending cancel.
    Exported at module level so test_fill_confirm_ttl can import it directly."""
    b_open = bool(getattr(auto_inst, "b_tracker", None) and auto_inst.b_tracker.open)
    b_risk = bool(getattr(auto_inst, "open_risk", {}).get("B"))
    if b_open or b_risk:
        return False, f"B lane open (b_tracker={b_open}, open_risk_B={b_risk})"
    return True, "single-lane A-only (selected machine)"


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

    # Apex-legal read-back: the :9222 TradingView account-manager panel (NO API key — Tradovate API is
    # banned on Apex eval/funded and the TradersPost API is waitlisted). Reads positions/fills off the
    # SAME CDP channel the feed uses. Opt-in via READBACK_SOURCE=tradingview; fail-closed until
    # readback_tradingview._PANEL_JS is pointed at the connected broker (then build+verify per RUNBOOK).
    import os as _os
    if _os.environ.get("READBACK_SOURCE", "").lower() in ("tradingview", "tv"):
        try:
            from readback_tradingview import TradingViewBrokerView
            broker = TradingViewBrokerView(account_label=acct_id)
            broker.net_by_account()                 # probe: raises TradingViewReadbackUnconfigured until _PANEL_JS reads the panel
            _pa = broker.primary_account()          # key the sentinel on the REAL Tradovate account id
            if _pa:
                acct_id = _pa
        except Exception as e:                      # noqa: BLE001 — degrade, never crash the launcher
            print(f"  read-back: TradingView panel not ready ({type(e).__name__}: {e})", flush=True)
            broker = None
        sentinel = ReadbackSentinel(acct_id, floor=floor, journal=journal)
        return sentinel, broker

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
                 profile_b=True, readback=None, notify=None, tjournal=None, exit_override=None,
                 buf_fn=None):
        self.exit_override = exit_override   # explicit --exit-model launch override (still gated by resolve_exit_model)
        self.buf_fn = buf_fn        # () -> current 5m bar DataFrame (for HTF alignment); None = no compute
        self.logger = logger           # ARGUS decision logger (auditability; fail-safe, optional)
        self.entry_gate = entry_gate   # infrastructure readiness gate (data GREEN + dead-man alive)
        self.readback = readback       # Stage B: live broker read-back sentinel (closes-the-loop). Optional.
        self.notify = notify           # Telegram notifier (signals + modeled outcomes). Optional, fail-safe.
        self.tjournal = tjournal       # learning journal (why won/lost). Optional, fail-safe.
        self.telemetry = None          # ExecTelemetry instance (wired by main()); observational only.
        self.slip = None               # SlipTripwire instance (wired by main() if --slip-tripwire); observational.
        self.fill_telem = None         # FillTelemetry instance (wired by main(), default ON); observation-only, fail-open.
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
        # PROSPECTIVE risk gate state (audit R1): lane -> open bracket risk $ (cleared per ET day / on resolve)
        self.open_risk = {}
        self._risk_day = None

    def _risk_gate(self, strategy, entry, stop, qty):
        """Audit R1: act BEFORE the order. (1) A stop-cap ≤80pt (shadow overlay promoted to enforced);
        (2) open + new bracket risk must fit inside the live cushion — the retrospective $550 stop
        cannot stop concurrent A+B brackets from stacking past the trailing floor. NOTE: deliberately
        NOT bound to the $550 headroom — a single certified A trade risks >$550 by design (the sims
        let the tripping trade's full loss land); the binding, bust-terminal constraint is the cushion.
        Only ever blocks (fail-closed on error). Returns (ok, why).

        TODO(recert): TEMPORARY EVAL-SURVIVAL GATE, not a certified daily-stop gate (operator-confirmed
        2026-07-02). Once Phase 2/3 re-certifies sizing under corrected 1m-truth fills, decide whether
        the daily stop becomes prospective, dynamic, or stays retrospective — then re-derive this gate
        from the re-certified stream instead of the cushion heuristic."""
        try:
            import config_defaults as CD
            _ed = et_date()
            if self._risk_day != _ed:                          # new ET day -> fresh book
                self._risk_day = _ed
                self.open_risk.clear()
            stop_pts = abs(float(entry) - float(stop))
            if stop_pts <= 0:
                return False, "invalid stop distance", 0
            cap = getattr(CD, "A_STOP_CAP_PTS", 0) or 0
            if strategy == "A" and cap and stop_pts > cap:
                return False, f"A stop {stop_pts:.0f}pt > cap {cap:.0f}pt", 0
            risk1 = stop_pts * CD.POINT_VALUE_MNQ              # $ risk per contract
            open_risk = sum(self.open_risk.values())
            cushion = None
            if self.cushion_fn is not None:
                try:
                    cushion, _dd = self.cushion_fn()
                except Exception:                              # noqa: BLE001
                    cushion = None
            # dollar budget for THIS trade = min(certified size-to-risk budget [A only],
            # cushion headroom net of already-open bracket risk). SIZE DOWN, don't reject —
            # Phase-3 recert: keeping every trade at reduced qty beats capping (57.7% vs 45.2%).
            budget = float("inf")
            if strategy == "A" and getattr(CD, "A_RISK_BUDGET_USD", 0):
                budget = float(CD.A_RISK_BUDGET_USD)
            if cushion is not None:
                frac = float(getattr(CD, "OPEN_RISK_CUSHION_FRAC", 0.9))
                budget = min(budget, max(0.0, float(cushion)) * frac - open_risk)
            q = int(qty) if budget == float("inf") else min(int(qty), int(budget // risk1))
            if q < 1:
                return False, (f"no size fits: risk ${risk1:,.0f}/ct vs budget ${max(0.0, budget):,.0f} "
                               f"(open ${open_risk:,.0f}"
                               + (f", cushion ${cushion:,.0f}" if cushion is not None else "") + ")"), 0
            return True, (f"sized {qty}->{q} (risk ${risk1:,.0f}/ct, budget ${budget:,.0f})"
                          if q < int(qty) else ""), q
        except Exception as e:                                 # noqa: BLE001 — a broken gate must not trade
            return False, f"risk gate error: {e!r}", 0

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
        # WATCHDOG ENTRY GATE — fail-closed BY DESIGN when enforcement is armed: a dead watchdog blocks
        # new entries, never positions/exits. Requires a fresh watchdog heartbeat (<90s) AND no HALT.flag.
        # Skipped entirely when WATCHDOG_ENFORCE is unset/0 (Monday-safe — no dependency until armed).
        if os.environ.get("WATCHDOG_ENFORCE") == "1":
            try:
                import watchdog_belief
                _wb = watchdog_belief.watchdog_entry_block()
                if _wb:
                    return "watchdog gate: " + _wb
            except Exception as _we:  # noqa: BLE001 — a gate ERROR must fail CLOSED (block), never permit
                print(f"[auto-live] ⚠ watchdog gate error — blocking (fail-closed): {_we!r}", flush=True)
                return "watchdog gate error (fail-closed)"
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
        # --- HTF alignment filter (shadow-logged; live gate via HTF_SKIP_ENABLED in config_defaults) ---
        import config_defaults as _CD_htf
        _htf_align = None
        if self.buf_fn is not None:
            try:
                from htf_alignment import compute_htf_alignment
                _, _, _, _htf_align = compute_htf_alignment(
                    self.buf_fn(), ts, sig.get("side", "long"))
            except Exception as _htf_e:  # noqa: BLE001 — shadow metric; a gate error never adds risk
                print(f"[auto-live] ⚠ HTF align error: {_htf_e!r} — allowed (shadow gate)", flush=True)
                _htf_align = None
        if getattr(_CD_htf, "HTF_SKIP_ENABLED", False) and _htf_align is not None and _htf_align <= -2:
            self.blocked += 1
            print(f"[auto-live] HTF SKIP (align={_htf_align:.0f} <= -2) — no webhook", flush=True)
            self._dlog("blocked", "d1c", bar_ts=ts, side=sig.get("side"),
                       reason=f"htf_alignment {_htf_align:.0f} <= -2", htf_align=_htf_align)
            return
        spec = _tier_spec(self.tier)
        # P3 cushion brake: near the floor, cut A to max(am//2,1) (and B to 0, handled in on_b_signal)
        braked = self._apply_p3()
        a_size, _ = self.p3.size(spec["am"], spec.get("bm", 0))
        # PROSPECTIVE risk gate (audit R1 + Phase-3 size-to-risk): sizes DOWN to the $ budget, blocks at 0
        _rok, _rwhy, _rq = self._risk_gate("A", sig["entry"], sig["stop"], a_size)
        if not _rok:
            self.blocked += 1
            print(f"[auto-live] RISK GATE BLOCK (A): {_rwhy} — no webhook", flush=True)
            self._dlog("blocked", "risk", bar_ts=ts, side=sig.get("side"), reason=_rwhy,
                       htf_align=_htf_align)
            return
        if _rq < a_size:
            print(f"[auto-live] RISK GATE SIZE (A): {_rwhy}", flush=True)
            a_size = _rq
        d1c_status = (self.gate.heimdall_status() if self.d1c_mode != "OFF" else "OFF")
        # CONFIGLOCK: resolve the official exit model fail-closed (never silently SINGLE_TARGET).
        from runtime_config import resolve_exit_model, ConfigLockError
        try:
            _exit_model = resolve_exit_model(self.mode if self.mode in ("live", "paper") else "live",
                                             requested=self.exit_override)
        except ConfigLockError as e:
            print(f"[auto-live] CONFIGLOCK: unsafe exit model blocked — {e}", flush=True)
            self._dlog("blocked", "exitlock", bar_ts=ts, side=sig.get("side"), reason=str(e),
                       htf_align=_htf_align)
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
        # TELEMETRY: record decision wall time before any send (observational; fail-safe)
        _telem_decision_wall = datetime.now(timezone.utc)
        try:
            if self.telemetry is not None:
                self.telemetry.on_decision(
                    str(sig["ts_signal"]), ts, _telem_decision_wall,
                    common["entry"], common["stop"], common["target"], a_size, sig["side"], "A")
        except Exception as _te:  # noqa: BLE001
            print(f"[exec-telem] ⚠ on_decision hook error: {_te!r}", flush=True)
        # FILL TELEMETRY: record the committed decision (observation-only; fail-open, never blocks send)
        try:
            if self.fill_telem is not None:
                # sizing forensics (observational only): qty_formula = uncapped size-to-risk ask;
                # qty_cap = tier/P3-braked cap re-read from state (pure, no mutation, no gate re-entry).
                import config_defaults as _CD_szf
                _stop_pts_f = abs(float(sig["entry"]) - float(sig["stop"]))
                _budget_f = float(getattr(_CD_szf, "A_RISK_BUDGET_USD", 0) or 0)
                _risk1_f = _stop_pts_f * _CD_szf.POINT_VALUE_MNQ
                _qty_formula = int(_budget_f // _risk1_f) if (_budget_f and _risk1_f > 0) else None
                _qty_cap = self.p3.size(spec["am"], spec.get("bm", 0))[0]
                self.fill_telem.on_decision(
                    strategy="A", side=sig["side"], signal_ts=sig["ts_signal"], account=self.account,
                    intended_price=float(sig["entry"]), submitted_price=BP.round_tick(common["entry"], "MNQ"),
                    stop=BP.round_tick(common["stop"], "MNQ"), target=BP.round_tick(common["target"], "MNQ"),
                    qty=a_size, qty_formula=_qty_formula, qty_cap=_qty_cap, qty_submitted=a_size,
                    d1c=dict(mode=self.d1c_mode, status=d1c_status, allowed=True, drift=self.gate.drift()),
                    decision_wall_ts=_telem_decision_wall.isoformat(), bar_ts=str(ts))
        except Exception as _fe:  # noqa: BLE001
            print(f"[fill-telem] ⚠ on_decision hook error: {_fe!r}", flush=True)
        # EXITFORGE: official model is EXIT3_FIXED_PARTIAL -> two split bracket legs, fail-closed
        if _exit_model == "EXIT3_FIXED_PARTIAL":
            legs, err = BP.build_entry_exit3(**common)
            if err:
                print(f"[auto-live] FAIL CLOSED — exit3 legs not built: {err}", flush=True)
                return
            res = self.sender.send_exit3(legs, self.account, root="MNQ")
            ok = res.get("ok")
            # FILL TELEMETRY: one ORDER_SENT per leg + register resting limits (observation-only; fail-open)
            try:
                if self.fill_telem is not None:
                    self.fill_telem.on_order_sent(strategy="A", side=sig["side"], signal_ts=sig["ts_signal"],
                                                  account=self.account, legs=legs, result=res, bar_ts=ts)
            except Exception as _fe:  # noqa: BLE001
                print(f"[fill-telem] ⚠ on_order_sent hook error: {_fe!r}", flush=True)
        elif _exit_model == "SINGLE_1R":
            # full-qty single +1R target (gated paper-test candidate). resolve_exit_model already
            # fail-safed to EXIT3 if SINGLE_1R wasn't approved for this live mode, so reaching here is intentional.
            from config_defaults import single1r_target
            _t1r = single1r_target(common["entry"], common["stop"], sig["side"])
            payload, err = BP.build_entry(**dict(common, target=_t1r, r_target=1.0))
            if err:
                print(f"[auto-live] FAIL CLOSED — single@1R payload not built: {err}", flush=True)
                return
            res = self.sender.send(payload)
            ok = res.get("sent")
        else:
            # FAIL CLOSED: never silently route an unknown exit (kills the old SINGLE_TARGET@2R misfire).
            print(f"[auto-live] FAIL CLOSED — unknown/unsafe exit model '{_exit_model}' — no order sent",
                  flush=True)
            self._dlog("blocked", "exitlock", bar_ts=ts, side=sig.get("side"),
                       reason=f"unknown exit model {_exit_model}", htf_align=_htf_align)
            return
        # TELEMETRY: capture webhook send result (observational; fail-safe)
        try:
            if self.telemetry is not None:
                _telem_http = None
                if _exit_model == "EXIT3_FIXED_PARTIAL":
                    # use the HTTP status of the first sent leg (entry-establishing)
                    for _tl in res.get("legs", []):
                        if _tl.get("status"):
                            _telem_http = _tl["status"]; break
                else:
                    _telem_http = res.get("status")
                self.telemetry.on_webhook_result(
                    str(sig["ts_signal"]), _telem_http, datetime.now(timezone.utc))
        except Exception as _te:  # noqa: BLE001
            print(f"[exec-telem] ⚠ on_webhook_result hook error: {_te!r}", flush=True)
        if ok or self.mode != "live":
            self.sent += 1
            self.open_risk["A"] = abs(float(sig["entry"]) - float(sig["stop"])) * a_size * 2.0   # audit R1
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
            self._dlog("blocked", "exitlock", bar_ts=ts, side=sig["side"], reason=_reason,
                       htf_align=_htf_align)
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
                       traderspost_status=_reason, live=(self.mode == "live"),
                       htf_align=_htf_align)

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
        spec = _tier_spec(self.tier)
        self._apply_p3()
        _, b_size = self.p3.size(spec["am"], spec.get("bm", 0))
        if b_size <= 0:                                  # P3 brake (or tier has no B) -> no B trade
            self.b_blocked += 1
            self._dlog("blocked", "ares", bar_ts=ts, side=sig.get("side"),
                       reason="P3 brake (B=0)" if self.p3.braked else "no B size in tier", profile="B")
            return
        # PROSPECTIVE risk gate (audit R1): cushion-fit BEFORE any payload is built. B keeps its tier
        # qty when it fits (no A-style $ budget); sized down only by cushion headroom.
        _rok, _rwhy, _rq = self._risk_gate("B", sig["entry"], sig["stop"], b_size)
        if _rok and _rq < b_size:
            print(f"[auto-live] RISK GATE SIZE (B): {_rwhy}", flush=True)
            b_size = _rq
        if not _rok:
            self.b_blocked += 1
            print(f"[auto-live] RISK GATE BLOCK (B): {_rwhy} — no webhook", flush=True)
            self._dlog("blocked", "risk", bar_ts=ts, side=sig.get("side"), reason=_rwhy, profile="B")
            return
        # B exit: PARTIAL_1R (50% @ +1R, 50% @ frozen 1.5R target, shared stop) when approved & qty>=2;
        # else the prior SINGLE bracket. Frozen B signal/stop/1.5R-target are UNCHANGED — exit split only.
        from config_defaults import resolve_b_exit
        b_exit = resolve_b_exit(self.mode)
        # If this session runs the SINGLE_1R candidate (A-side, flag-gated), B routes full-qty @ +1R too
        # (paper-test parity). resolve_exit_model applies the same live approval gate, so a non-approved
        # live session resolves to EXIT3 here -> _single1r False -> B keeps its normal partial/single.
        from runtime_config import resolve_exit_model as _rxm
        _single1r = (_rxm(self.mode if self.mode in ("live", "paper") else "live",
                          requested=self.exit_override) == "SINGLE_1R")
        b_common = dict(
            account=self.account, strategy="B", setup=sig.get("liq", "orb"),
            signal_ts=sig["ts_signal"], side=sig["side"], qty=b_size,
            entry=float(sig["entry"]) + self.basis_offset,
            stop=float(sig["stop"]) + self.basis_offset,
            target=float(sig["target"]) + self.basis_offset,
            root="MNQ", order_type="limit", mode_meta=dict(mode="ARES", tier=self.tier, profile="B"))
        b_legs = None
        if _single1r:                                        # SINGLE_1R candidate: full-qty B @ +1R, shared stop
            from config_defaults import single1r_target
            _t1r = single1r_target(b_common["entry"], b_common["stop"], sig["side"])
            payload, err = BP.build_entry(**dict(b_common, target=_t1r, r_target=1.0))
            if err:
                print(f"[auto-live] B FAIL CLOSED — single@1R payload not built: {err}", flush=True)
                return
            res = self.sender.send(payload)
            ok = res.get("sent")
        elif b_exit == "PARTIAL_1R" and b_size >= 2:
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
            self.open_risk["B"] = abs(float(sig["entry"]) - float(sig["stop"])) * b_size * 2.0   # audit R1
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
        _xlabel = "single@1R" if _single1r else ("PARTIAL(50%@1R/50%@1.5R)" if b_legs is not None else "single")
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
                route = sig
                if self.p3.braked and sig.get("action") in ("enter", "flip"):
                    # P3 cushion brake: near the floor, add NO new momentum exposure (flatten if holding, else skip)
                    route = ({**sig, "action": "flatten", "position": 0, "side": "flat"}
                             if getattr(self.m_executor, "position", 0) else None)
                    print(f"[momentum] P3-braked → no new exposure ({sig.get('action')} blocked)", flush=True)
                if route is not None:
                    self.m_executor.on_signal(route, ts)
                    for bk in self.books:                    # FAN-OUT: same Momentum signal -> each book (its mm)
                        bk.route_m(route, ts)
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
    p.add_argument("--tier", required=True, choices=list(EVAL_TIERS) + list(FUNDED_TIERS))
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
    p.add_argument("--exit-model", dest="exit_model", default=None,
                   help="override the exit model for this launch (e.g. SINGLE_1R). Still gated: "
                        "live SINGLE_1R needs single-1r-approved.flag, else fail-safe to EXIT3.")
    p.add_argument("--confirm", action="store_true",
                   help="required (with --live) to arm SUPERVISED LIVE AUTO; extra human gate")
    p.add_argument("--eyes-confirmed-blind", dest="eyes_confirmed_blind", action="store_true",
                   help="OPERATOR OVERRIDE (with --live --confirm): run supervised eye-confirmed live with NO "
                        "automated read-back. You accept trading blind (modeled P&L/daily-stop may diverge) and "
                        "will confirm fills by eye on the platform. Use only when read-back is unavailable and "
                        "you are watching. Bracket stops still protect filled orders.")
    p.add_argument("--readback", action="store_true",
                   help="Stage B: enable the Tradovate read-back sentinel (closes the fills-by-eye loop). "
                        "Reconciles broker position/balance vs the bot's belief every poll; HALTS entries + "
                        "flattens fail-closed on a confirmed mismatch. Needs read-only Tradovate API creds.")
    p.add_argument("--readback-poll", type=int, default=20,
                   help="seconds between read-back polls (default 20)")
    p.add_argument("--slip-tripwire", action="store_true",
                   help="arm the execution slippage tripwire (observational; spec "
                        "docs/specs/slippage_tripwire_spec.md). Watches real fill quality off exec_telemetry "
                        "and, per --slip-mode, alerts / latches a SLIP-class read-back halt on breach. Default OFF.")
    p.add_argument("--slip-mode", choices=["alert", "halt"], default="alert",
                   help="slip-tripwire behaviour when armed: 'alert' computes + Telegrams breaches but NEVER "
                        "halts (Monday rollout default); 'halt' also freezes entries via the read-back sentinel "
                        "(no flatten). Ignored unless --slip-tripwire.")
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
    spec = _tier_spec(a.tier)
    # ARES sizing into the engine's eval qty (Profile A only live)
    config.SIZING = dict(getattr(config, "SIZING", {}), eval_qty=spec["am"], fund_qty=2)

    sender = BridgeSender(store=Store(), journal=j, mode=("live" if mode == "live" else "dry-run"),
                          live_url=os.environ.get("TRADERSPOST_LIVE_URL"))
    # ARGUS decision logger — proves the engine ran (no-signal/candidate/block/send rows). Fail-safe.
    from decision_log import DecisionLogger
    import decision_log as _DL
    try:                                   # audit A10/J: the log must state the RESOLVED exit model,
        from runtime_config import resolve_exit_model as _rx   # not a hardcoded constant
        _DL.EXIT_MODEL = _rx(mode if mode in ("live", "paper") else "live",
                             requested=getattr(a, "exit_model", None))
    except Exception:                      # noqa: BLE001 — logging metadata must never block launch
        pass
    _session_id = f"{a.account}-{a.tier}-{mode}-{et_date()}"
    _dlogger = DecisionLogger(a.account, mode, _session_id, profile="A", feed_source=a.feed,
                              engine_timeframe="5m")
    # --- Stage B: live read-back sentinel (closes the fills-by-eye loop) ---
    # LIVE REQUIRES read-back. Without a Tradovate read connection the bot cannot see its own fills/
    # positions and trades BLIND — phantom fills + unmanaged orphan positions (the 2026-06-30 finding:
    # an unfilled retest-limit was booked as a real trade because the bot never reads the broker).
    # Build read-back for ANY real-order (live) run, not only when --readback was passed; paper is exempt.
    _need_readback = (mode == "live")
    readback, _rb_broker = (build_readback(a, mode, j)
                            if (getattr(a, "readback", False) or _need_readback) else (None, None))
    if _need_readback and _rb_broker is None:
        if getattr(a, "eyes_confirmed_blind", False):
            # OPERATOR OVERRIDE (explicit, per-launch): supervised eye-confirmed live with NO automated
            # read-back. The operator accepts trading BLIND — modeled P&L & the daily stop run on ASSUMED
            # fills and may DIVERGE from reality (the 2026-06-30 phantom mode) — and will confirm every
            # fill by eye on the broker platform. All other rails remain: broker-side bracket stops on
            # each filled order, the $550 daily stop (on modeled P&L), EOD flatten, and the kill-switch.
            readback = None
            print("⚠️  SUPERVISED-LIVE-BLIND (--eyes-confirmed-blind): NO automated read-back. The bot CANNOT "
                  "see its own fills — modeled P&L & the daily stop MAY DIVERGE from reality. YOU must watch "
                  "the broker platform and eye-confirm every fill; bracket stops protect filled orders. "
                  "Proceeding at the operator's explicit instruction.", flush=True)
        else:
            print("REFUSED LIVE — NO READ-BACK: the bot cannot see its fills/positions, so it would trade BLIND "
                  "(phantom fills, unmanaged orphans — the 2026-06-30 finding). Wire read-back (TradingView panel "
                  "via READBACK_SOURCE=tradingview, or the TradersPost API) and relaunch — OR pass "
                  "--eyes-confirmed-blind to run supervised eye-confirmed live. Standing down.", flush=True)
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
                    p3_enabled=not getattr(a, "no_p3", False), readback=readback, notify=tg, tjournal=journal,
                    exit_override=getattr(a, "exit_model", None))

    # --- Execution telemetry (observational, fail-safe; never touches the order path) ---
    try:
        from exec_telemetry import ExecTelemetry
        auto.telemetry = ExecTelemetry()
        print("  exec telemetry ON -> out/exec/exec_telemetry.csv", flush=True)
    except Exception as _et_e:  # noqa: BLE001
        print(f"  ⚠ exec telemetry DISABLED ({_et_e!r})", flush=True)
        auto.telemetry = None

    # --- Fill telemetry (observation-only, DEFAULT ON; async, fail-open — never blocks/delays order flow) ---
    try:
        from fill_telemetry import FillTelemetry
        auto.fill_telem = FillTelemetry(telegram=(tg if getattr(tg, "enabled", False) else None))
        if readback is not None:
            readback.fill_telem = auto.fill_telem      # FILL_CONFIRMED mirror (guarded, fail-open in live_readback)
        print("  fill telemetry ON -> out/fill_telemetry/<ET-date>.jsonl", flush=True)
    except Exception as _ft_e:  # noqa: BLE001
        print(f"  ⚠ fill telemetry DISABLED ({_ft_e!r})", flush=True)
        auto.fill_telem = None

    # --- Slippage tripwire (observational; default OFF; fail-safe, never touches the order path) ---
    auto.slip = None
    if getattr(a, "slip_tripwire", False):
        try:
            from slip_tripwire import SlipTripwire
            from config_defaults import slip_tripwire_cfg
            _slip_alert = (lambda m: tg.send(m)) if getattr(tg, "enabled", False) else None
            _slip_halt = (lambda why: auto.readback.slip_halt(why)) if readback is not None else None
            auto.slip = SlipTripwire(slip_tripwire_cfg(), mode=a.slip_mode,
                                     on_alert=_slip_alert, on_halt=_slip_halt)
            _mode_note = ("HALT-capable (freezes entries via read-back sentinel on breach)"
                          if a.slip_mode == "halt" else "ALERT-only (never halts — watches + Telegrams)")
            print(f"  slip tripwire ON [{a.slip_mode}] -> {_mode_note}; events out/exec/slip_halt_events.csv",
                  flush=True)
        except Exception as _st_e:  # noqa: BLE001
            print(f"  ⚠ slip tripwire DISABLED ({_st_e!r})", flush=True)
            auto.slip = None

    # --- Profile MOMENTUM lane (default OFF; --profile-momentum routes it via the same bridge) ---
    # PHASE/FIRM gate: momentum trades variance for income, so it auto-enables ONLY where the ruleset rewards
    # that (Apex eval / MFFU funded) and stays off where variance is punished (MFFU eval trailing-DD, Apex
    # funded $1k daily-kill). The --profile-momentum flag REQUESTS the lane; the tier decides if it arms.
    from auto_safety import momentum_active_for_tier
    _m_phase_ok, _m_phase_why = momentum_active_for_tier(a.tier)
    _momentum_armed = getattr(a, "profile_momentum", False) and _m_phase_ok
    if getattr(a, "profile_momentum", False) and not _m_phase_ok:
        print(f"  Profile MOMENTUM requested but GATED OFF for tier '{a.tier}': {_m_phase_why}. "
              "Lane not armed (funded-only / phase rule).", flush=True)
    if _momentum_armed:
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
        print(f"  Profile MOMENTUM lane ON ({_m_phase_why}) — {a.momentum_qty} MNQ, {a.momentum_stop:.0f}pt "
              "cat-stop, half-overlap gate (A/B/M), EOD ~15:30 (deferred guardian).", flush=True)

    # --- FAN-OUT secondary books (e.g. Apex): same engine signals -> another account/size/rules/webhook ---
    for _spec in getattr(a, "apex_book", []):
        try:
            from fanout_book import SecondaryBook
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

    # --- ROUTING-INTEGRITY GUARD: refuse to launch if two accounts resolve to the SAME webhook URL ---
    # A shared URL (copy-paste slip, or two books both falling back to TRADERSPOST_APEX_URL) would fire
    # one account's orders into another's broker. Catch it BEFORE the loop — never at order time.
    _routes = [(a.account, sender.live_url)] + [(b.account, b.sender.live_url) for b in auto.books]
    _collisions = webhook_route_collisions(_routes)
    if _collisions:
        print("REFUSED: routing-integrity guard — these accounts share ONE webhook URL (orders would CROSS):",
              flush=True)
        for _u, _accts in _collisions.items():
            print(f"   {' + '.join(_accts)}  ->  webhook …{_u[-12:]}", flush=True)
        print("   Fix: give EACH account its own TRADERSPOST_<ACCOUNT>_URL. A shared TRADERSPOST_APEX_URL "
              "fallback routes multiple books to the SAME broker account.", flush=True)
        return 2

    if readback is not None:
        # critical mismatch -> flatten via the SAME bridge route as the guardian, then stay halted.
        def _rb_flatten(reason):
            print(f"[auto-live] ☠ READ-BACK CRITICAL: {reason} — FLATTEN + HALT", flush=True)
            try:
                # fresh reason per firing: the flatten signalId derives from it — the static default
                # ("emergency") was BURNED by the 2026-07-01 firing and dedup-blocks every retry (audit T0-2)
                import time as _tt
                if hasattr(sender, "flatten"):
                    sender.flatten(a.account, reason=f"readback_{int(_tt.time())}")
            except Exception as e:                                # noqa: BLE001 — halt stands regardless
                print(f"[auto-live] read-back flatten error: {e!r} (entries already halted)", flush=True)
            # FILL TELEMETRY: resting entries resolved by the critical flatten (observation-only; fail-open)
            try:
                if auto.fill_telem is not None:
                    auto.fill_telem.on_order_resolved(account=a.account, reason="readback_critical_flatten")
            except Exception as _fe:                              # noqa: BLE001
                print(f"[fill-telem] ⚠ on_order_resolved hook error: {_fe!r}", flush=True)
        readback.on_critical = _rb_flatten

        # Order TTL: the A entry-limit fill window is owned by the model; the cancel fired here
        # IS the live order TTL (~2 min after the model gives up expecting the filled position).
        def _rb_on_missing(expected_qty):
            """MISSING_POSITION persisted for missing_confirm polls — likely an unfilled limit.
            Cancel all working MNQ orders and reset the sentinel to flat. SAFE only because the
            selected machine is single-lane A-only; guard skips cancel if another lane is open."""
            import time as _ttt
            safe, why = _on_missing_cancel_is_safe(auto)
            if not safe:
                print(f"[auto-live] on_missing: guard — {why}; cancel NOT sent. Manual review needed.",
                      flush=True)
                if tg.enabled:
                    tg.send(f"⚠ entry unfilled (expected {expected_qty} MNQ) — cancel SKIPPED "
                            f"({why}). Manual review needed.")
                return
            try:
                cancel_p, _ = BP.build_cancel(account=a.account, strategy="A",
                                              signal_ts=int(_ttt.time()), root="MNQ")
                sender.send(cancel_p)
                print(f"[auto-live] on_missing: expected={expected_qty} unfilled — "
                      f"working orders CANCELLED", flush=True)
            except Exception as _e:                               # noqa: BLE001 — on_flat still runs
                print(f"[auto-live] on_missing: cancel send failed: {_e!r}", flush=True)
            readback.on_flat()
            # TELEMETRY: mark the pending A signal as MISSED (observational; fail-safe)
            try:
                if auto.telemetry is not None:
                    _pts = auto.telemetry.pending_signal_ts()
                    if _pts is not None:
                        auto.telemetry.on_missed(_pts)
                        # SLIP TRIPWIRE: an unfilled limit is a MISSED signal (observational; fail-safe).
                        if auto.slip is not None:
                            auto.slip.observe_miss()
            except Exception as _te:  # noqa: BLE001
                print(f"[exec-telem] ⚠ on_missed hook error: {_te!r}", flush=True)
            # FILL TELEMETRY: terminal state for the resting entry (TTL/cancel) (observation-only; fail-open)
            try:
                if auto.fill_telem is not None:
                    auto.fill_telem.on_order_resolved(account=a.account, reason="on_missing_ttl_cancel")
            except Exception as _fe:  # noqa: BLE001
                print(f"[fill-telem] ⚠ on_order_resolved hook error: {_fe!r}", flush=True)
            if tg.enabled:
                tg.send(f"⚠ entry unfilled at broker → working orders cancelled; "
                        f"modeled tracker may diverge (phantom-trade guard). "
                        f"Expected {expected_qty} MNQ.")
        readback.on_missing = _rb_on_missing

        if tg.enabled:
            readback.on_alert = tg.send                           # operator hears every BLACK/read-fail (audit A1)
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
    _mo = {"d": None}                      # market-open ping tracker (one 09:30 ET Telegram ping per trading day)
    from preopen_guard import PreopenGuard
    _preopen = PreopenGuard()              # pre-open feed-readiness alerts (ORB + Momentum need a clean open)
    runner = PaperLiveRunner(store, "live", "live")
    runner.bot.on_decision = lambda sig, placed, reason, ts: (
        runner._orig(sig, placed, reason, ts), auto.on_decision(sig, placed, reason, ts))
    runner._orig = runner._on_decision
    # P3 reads the live cushion from the account state machine (distance to the trailing floor)
    auto.cushion_fn = lambda: (runner.bot.mffu.distance_to_floor, runner.bot.mffu.cfg.trail_dd)
    # HTF alignment: live 5m bar buffer (ProfileAEngine) at signal time
    auto.buf_fn = lambda: runner.bot.engine.buf
    # SEED modeled equity from broker reality (audit R2/N): a fresh state machine starts at $50k with a
    # full $2k cushion — the real account may already be down. Gates (P3, too_close_to_floor, risk gate)
    # must see the REAL cushion, else they permit trades the floor can't absorb. Read-only; best-effort.
    if _rb_broker is not None:
        try:
            _real_eq = _rb_broker.balance(readback.account)
            if _real_eq is not None and 0 < float(_real_eq) < runner.bot.mffu.cfg.start_balance * 2:
                runner.bot.mffu.balance = float(_real_eq)
                runner.bot.mffu.eod_hwm = max(runner.bot.mffu.eod_hwm, float(_real_eq))
                print(f"  modeled equity SEEDED from broker: ${float(_real_eq):,.2f} "
                      f"(cushion ${runner.bot.mffu.distance_to_floor:,.0f})", flush=True)
            else:
                print(f"  ⚠ equity seed skipped (broker balance unreadable) — modeled state starts at "
                      f"${runner.bot.mffu.balance:,.0f}; gates run on MODELED cushion", flush=True)
        except Exception as _se:                                # noqa: BLE001 — seeding must not block launch
            print(f"  ⚠ equity seed failed ({_se!r}) — gates run on MODELED cushion", flush=True)
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
        _mom_on = _momentum_armed                                          # only defer if momentum actually armed
        _g_sched = _Sched(flatten_at=_dtime(15, 30)) if _mom_on else None   # half-day flat (12:45) unchanged
        def _on_flatten_ok():                                  # preserves readback.on_flat; ADDS fill-telem resolution
            if readback is not None:
                readback.on_flat()
            try:                                              # FILL TELEMETRY: EOD/kill flatten resolves resting entries
                if auto.fill_telem is not None:
                    auto.fill_telem.on_order_resolved(account=a.account, reason="guardian_eod_or_kill_flatten")
            except Exception as _fe:                          # noqa: BLE001 — observation-only, never breaks the guardian
                print(f"[fill-telem] ⚠ on_order_resolved hook error: {_fe!r}", flush=True)
        guardian = FlattenGuardian(
            a.account, root="MNQ", scheduler=_g_sched,
            hb_meta=dict(mode=mode, account=a.account, tier=a.tier, d1c_mode=d1c_mode,
                         execution=a.execution, ares_tier=a.tier),
            build=lambda: (BridgeSender(store=Store(), journal=Journal(), mode=_gmode, live_url=_gurl),
                           Store(), Journal()),
            on_flatten_ok=_on_flatten_ok)
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
        _brec = {"n": 0, "open_snap": []} # B closed-count + pre-on_bar open snapshot (sentinel exit accounting)

        def _record_resolved():
            """Append any newly-RESOLVED trades to the dashboard P&L calendar ledger.
            Uses the proven PaperTracker outcome (stop/TP1/TP2/EOD -> result_R); display-only."""
            import trade_results
            old = _rec["n"]
            _rec["n"] = trade_results.record_resolved(
                runner.tracker.rows, old, mode, a.account, _qty)
            if _rec["n"] > old:                                # A resolved -> release its open-risk slot (R1)
                auto.open_risk.pop("A", None)
            if not auto.b_tracker.open:                        # B flat -> release B's slot (R1)
                auto.open_risk.pop("B", None)
            for r in runner.tracker.rows[old:_rec["n"]]:   # Telegram outcome + learning journal (modeled)
                # sentinel: decrement expected as each A position resolves (audit R4/A5).
                # Rejected/blocked rows never called on_entry (gate stopped the send) -> skip,
                # or a healthy broker position would be phantom-decremented (false ORPHAN BLACK).
                # Tracker rows carry a `notes` LIST (paper_live) -> join like record_resolved does.
                _rn = r.get("notes")
                _rn = ",".join(_rn) if isinstance(_rn, (list, tuple)) else (_rn or "")
                if readback is not None and not trade_results.is_rejected(_rn):
                    _rdir = r.get("direction")
                    if _rdir in ("long", "short"):
                        _rdelta = -_qty if _rdir == "long" else _qty
                        if abs(readback.expected) >= _qty:
                            readback.on_partial_or_exit(_rdelta)
                        else:
                            readback.on_flat()   # clamp: never leave phantom opposite sign
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
            # sentinel: B exit accounting (paper-tracker closed count drives expected decrement).
            # No rejected-guard needed: b_tracker.on_signal and readback.on_entry sit in the SAME
            # post-send block in on_b_signal (blocked B signals return before either fires).
            if readback is not None:
                _b_old = _brec["n"]
                _b_new = auto.b_tracker.closed
                if _b_new > _b_old:
                    _cur_keys = {auto.b_tracker._key(w) for w in auto.b_tracker.open}
                    for _bw in _brec["open_snap"]:
                        if auto.b_tracker._key(_bw) not in _cur_keys:
                            _bqty = int(_bw["qty"])
                            _bdelta = -_bqty if _bw["side"] == "long" else _bqty
                            if abs(readback.expected) >= _bqty:
                                readback.on_partial_or_exit(_bdelta)
                            else:
                                readback.on_flat()   # clamp: never leave phantom opposite sign
                _brec["n"] = _b_new

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
                _brec["open_snap"] = list(auto.b_tracker.open)   # snapshot before exits resolve
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
            # WATCHDOG BELIEF (observation-only; fail-open like the telemetry hooks — a broken publish
            # never blocks the engine). Snapshots what the engine now believes (expected net, resting
            # sids, day P&L) to out/watchdog/belief.json for the INDEPENDENT watchdog to reconcile.
            try:
                import watchdog_belief
                watchdog_belief.publish_belief(auto)
            except Exception as _wbe:  # noqa: BLE001 — belief publishing must NEVER raise into the order path
                print(f"[watchdog-belief] ⚠ publish hook error: {_wbe!r}", flush=True)
            _bar["i"] += 1

        def _process(ts, o, h, l, c):
            if auto.killed():
                print(f"[auto-live] KILL: {auto.killed()} — halting new entries", flush=True)
            # FILL TELEMETRY: scan resting entry limits for touches on this bar (observation-only; fail-open)
            try:
                if auto.fill_telem is not None:
                    auto.fill_telem.on_bar(ts, o, h, l, c)
            except Exception as _fe:                           # noqa: BLE001
                print(f"[fill-telem] ⚠ on_bar hook error: {_fe!r}", flush=True)
            auto.feed_gate(ts, o, c)                           # D1c on every bar (+09:30 open)
            if dual_1m:
                done = _agg.add(ts, o, h, l, c)                # native 1m -> D1c; aggregated 5m -> engine
                if done:
                    d_ts, do, dh, dl, dc, _ = done
                    _engine_bar(d_ts, do, dh, dl, dc)
            else:
                _engine_bar(ts, o, h, l, c)
            _persist_data_status(store)
            # --- DAILY STOP enforcement on MODELED P&L (no broker read-back). Derived from the ledger
            #     every bar (idempotent — a restart re-reads the same total, never double-counts),
            #     EXCLUDING rejected/blocked rows (trades never entered). Trips the persistent DailyGuard
            #     -> killed()='daily loss stop hit' blocks new entries + the flatten guardian flattens. ---
            try:
                import trade_results as _tr
                _ed = et_date()
                _dp = _tr.day_entered_pnl(auto.account, _ed)
                if _dp <= -abs(auto.daily_stop) and not auto.guard.is_stopped(auto.account, _ed):
                    auto.guard.stop_now(auto.account, _ed,
                                        reason=f"daily loss ${_dp:.0f} <= -${auto.daily_stop} (modeled)")
                    print(f"[auto-live] 🛑 DAILY STOP HIT — modeled day P&L ${_dp:.0f} <= "
                          f"-${auto.daily_stop}; new entries blocked, guardian will flatten", flush=True)
                    if tg.enabled:
                        tg.send(f"🛑 DAILY STOP — {auto.account}\nModeled day P&L ${_dp:.0f} hit "
                                f"-${auto.daily_stop}. New entries blocked for the day.")
            except Exception:                                  # noqa: BLE001 — never break the loop
                pass
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
                    # TELEMETRY: track fill confirmation state before poll (observational; fail-safe)
                    _telem_was_fc = getattr(readback, "_fill_confirmed", False)
                    _telem_pts = auto.telemetry.pending_signal_ts() if auto.telemetry is not None else None
                    if _telem_pts is not None and auto.telemetry is not None:
                        try:
                            auto.telemetry.poll_increment(_telem_pts)
                        except Exception as _te:  # noqa: BLE001
                            print(f"[exec-telem] ⚠ poll_increment error: {_te!r}", flush=True)
                    conf = readback.poll(_rb_broker)
                    if conf:
                        print(f"[auto-live] read-back: {[(c,d) for c,_,d in conf]}", flush=True)
                    # TELEMETRY: if fill just confirmed, record actual fill price (observational; fail-safe)
                    if (_telem_pts is not None and auto.telemetry is not None
                            and not _telem_was_fc and getattr(readback, "_fill_confirmed", False)):
                        try:
                            _fp, _pr = None, False
                            if hasattr(_rb_broker, "avg_price_by_account"):
                                _fp = _rb_broker.avg_price_by_account(readback.account)
                                _pr = _fp is not None
                            _slip_r = auto.telemetry.on_fill_confirmed(
                                _telem_pts, _fp, _pr, datetime.now(timezone.utc))
                            # SLIP TRIPWIRE: feed the just-computed entry slippage (observational; fail-safe).
                            if auto.slip is not None:
                                auto.slip.observe_fill(_slip_r)
                        except Exception as _te:  # noqa: BLE001
                            print(f"[exec-telem] ⚠ on_fill_confirmed error: {_te!r}", flush=True)
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
            # --- Market-open ping: ONE Telegram message per ET trading day at the 09:30 cash open ---
            #     Fires off the bar clock (so it tracks real market time), once per ET date, only when
            #     armed live and it's a trading day. The per-day latch + 09:30-window means a mid-morning
            #     restart won't re-fire, and it never fires on weekends/holidays. Advisory only.
            if tg.enabled and armed["v"]:
                try:
                    _mpt = pd.Timestamp(ts); _met = (_mpt.tz_convert(NY) if _mpt.tzinfo else _mpt)
                    _mday = _met.date()
                    if (_mo["d"] != _mday and _met.hour == 9 and _met.minute >= 30
                            and _Sched().is_trading_day(_mday)):
                        _mo["d"] = _mday
                        tg.send("🔔 Market is OPEN — ZEUS is watching. Time to trade.\n"
                                f"{a.account} · {a.tier} · NY-AM window live (A{spec['am']}/B{spec['bm']}).")
                except Exception:                              # noqa: BLE001 — never break the loop
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
            # WATCHDOG ARM-TIME CHECK (additive, guarded). Fail-closed ONLY when enforcement is armed
            # (WATCHDOG_ENFORCE=1): a config-hash drift vs evidence/eval_config.sha256, or an absent/stale
            # watchdog, REFUSES to arm — so the enforcing watchdog must be up first. When enforcement is
            # unset it is print-warn only (observing). A check error never permits when enforcing.
            try:
                import watchdog_belief as _wbchk
                _wd_enf = os.environ.get("WATCHDOG_ENFORCE") == "1"
                _cfg_ok, _cfg_miss = _wbchk.verify_eval_config_hashes()
                _wd_gate = _wbchk.watchdog_entry_block()
                if _wd_enf and (not _cfg_ok or _wd_gate):
                    print(f"REFUSED {modlabel} — watchdog enforcement armed but "
                          + (f"config drift {_cfg_miss}" if not _cfg_ok else "")
                          + ("; " if (not _cfg_ok and _wd_gate) else "")
                          + (_wd_gate or ""), flush=True)
                    return 2
                if not _cfg_ok or _wd_gate:
                    print(f"  ⚠ watchdog preflight (observing): config_ok={_cfg_ok} gate={_wd_gate}", flush=True)
            except Exception as _wce:  # noqa: BLE001
                if os.environ.get("WATCHDOG_ENFORCE") == "1":
                    print(f"REFUSED {modlabel} — watchdog arm-time check error (fail-closed): {_wce!r}", flush=True)
                    return 2
                print(f"  ⚠ watchdog arm-time check error (observing): {_wce!r}", flush=True)
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
                try:                                                 # FILL TELEMETRY: manual flatten resolves resting entries
                    if auto.fill_telem is not None:
                        auto.fill_telem.on_order_resolved(account=a.account, reason="manual_flatten")
                except Exception as _fe:                             # noqa: BLE001
                    print(f"[fill-telem] ⚠ on_order_resolved hook error: {_fe!r}", flush=True)
                return "🚨 FLATTEN sent + HALTED. Confirm flat in Tradovate. /resume to re-arm."

            def _h_resume(_a):
                store.set_state(auto_live_halt="", auto_live_kill="")
                if readback is not None and readback.halted:      # sentinel halt was sticky for life (audit A1)
                    readback.reset()
                    return "🟢 RESUMED — halt + read-back sentinel cleared, watching for entries again."
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
        try:                                                  # FILL TELEMETRY: drain the writer queue on clean exit
            if getattr(auto, "fill_telem", None) is not None:
                auto.fill_telem.close()
        except Exception as _fe:                              # noqa: BLE001 — shutdown flush never blocks exit
            print(f"[fill-telem] ⚠ shutdown flush skipped: {_fe!r}", flush=True)
        lock.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
