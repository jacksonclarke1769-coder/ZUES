"""WATCHDOG — independent reconciliation sentinel for the live ZEUS bot.

A STANDALONE process (own lock, own loop, own CDP websocket) that reconciles the bot's
PUBLISHED beliefs (out/watchdog/belief.json) against BROKER-side truth read through its OWN
TradingView account-manager scrape. It has ASYMMETRIC authority: it may FLATTEN, CANCEL,
HALT-NEW-ENTRIES, or ALERT — it may NEVER enter, resize, or modify an order.

────────────────────────────────────────────────────────────────────────────────────────────
FAIL-CLOSED POLARITY — THE DEFINING CONTRAST WITH fill_telemetry.py.
  fill_telemetry is FAIL-OPEN: a broken telemetry recorder must never touch order flow, so it
  swallows every error and keeps the engine trading.
  This watchdog is the OPPOSITE — FAIL-CLOSED. Its ABSENCE must eventually BLOCK new entries.
  It does that via a flag-armed engine gate: when WATCHDOG_ENFORCE=1 the engine's killed()
  refuses new entries unless this watchdog's heartbeat is fresh and no HALT.flag is set. So a
  dead/silent watchdog costs income (no new entries) but never adds risk (it never opens,
  resizes, or removes protection from an OPEN position). Every failure branch below restates
  this: on doubt we HALT/ALERT and, only for a CONFIRMED unprotected/parity break, FLATTEN —
  never the reverse.
────────────────────────────────────────────────────────────────────────────────────────────

AUTHORITY BOUNDARY BY CONSTRUCTION: this module imports ONLY flatten/cancel builders — it must
never import build_entry, build_entry_exit3, send_exit3, or any opening path. A later test
asserts this via AST. Keep it structurally obvious.

MODES (env WATCHDOG_MODE, default observe):
  observe  — every action is logged as `would_have` + a Telegram alert; NOTHING is sent, no
             HALT.flag is written.
  enforce  — actions execute (flatten/cancel via the bridge, HALT.flag written).

Prior art reused (patterns, not reinvented): readback_tradingview.TradingViewBrokerView (panel
scrape, fail-closed TradingViewReadbackUnconfigured), tv_feed._CDP / _read_bars_js (own CDP +
last-bar read), bridge_sender.BridgeSender.flatten (cancel-then-exit) + bridge_traderspost.
build_cancel (cancel-only leg), deadman_watch (InstanceLock, market_likely_open, Telegram),
scheduler.HALF_DAYS_2026 (half-day flat time), decay_monitor (transition-only alerting),
fill_telemetry.account_tag (never raw account ids).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import env_loader  # noqa: F401 — loads .env (TRADERSPOST_LIVE_URL, TELEGRAM_*)

from fill_telemetry import account_tag
from instance_lock import InstanceLock, LockHeld
from feed_watch import market_likely_open
from heimdall_monitor import deadman_status
from telegram_notify import Telegram
from watchdog_belief import (BELIEF_PATH, HALT_FLAG_PATH, HEARTBEAT_PATH, WATCHDOG_DIR,
                             verify_eval_config_hashes)

ET = ZoneInfo("America/New_York")

# ══════════════════════════════════════════════════════════════════════════════════════════
# OPERATIONAL CONSTANTS — not research parameters. These govern the watchdog's own timing and
# tolerances; none of them changes any traded quantity, size, price, or strategy. They are
# operational (how fast we poll, how long we tolerate an in-flight fill) — changing them cannot
# alter what the bot trades, only how quickly this independent monitor reacts.
# ══════════════════════════════════════════════════════════════════════════════════════════
LOOP_OPEN_S = 10             # poll cadence while market_likely_open()
LOOP_CLOSED_S = 60           # poll cadence while the market is closed
INFLIGHT_GRACE_S = 90        # skip PARITY/ORPHAN while belief order-state changed <90s ago (in-flight fills)
FEED_STALE_S = 180           # watchdog's OWN second-clock: last 1m bar older than this during open = stale
CONFIG_CHECK_S = 300         # CONFIG INTEGRITY recompute interval (~5 min); also runs at startup
DAILY_LOSS_TOL_USD = 10      # DAILY-LOSS TRUTH tolerance. NOT one tick ($0.50): panel equity rounds to
                             # cents AND folds in fees/commissions, so ≈4 MNQ ticks of rounding headroom
                             # is the honest floor below which a divergence is real, not display noise.
BROKER_READ_STRIKES = 3      # consecutive panel-read failures before a HALT (mirrors live_readback 3-strike)
ACTION_REFIRE_S = 300        # send-dedup backstop: a flatten/cancel fires ONCE per incident (on the
                             # ok→violation transition), then re-fires at most once per this interval —
                             # and ONLY while the unsafe condition is still observable broker-side. A
                             # flatten that worked leaves the broker FLAT, so a parity break driven by a
                             # stale belief (broker already flat) never re-fires; a cancel that worked
                             # leaves no working orders, so it never re-fires either. Guards the wedged
                             # case (broker keeps re-showing a position) without spamming fresh-sid webhooks.
FLAT_TIME_ET = (14, 31)      # SECOND-SIGNATURE EOD flat (1 min after the engine's 14:30 guardian)
HALF_DAY_FLAT_TIME_ET = (12, 46)   # 1 min after the half-day 12:45 guardian flatten
POINT_VALUE_MNQ = 2.0        # $/pt/MNQ — reference only; the watchdog never sizes anything

ROOT = "MNQ"


# ══════════════════════════════════════════════════════════════════════════════════════════
# Verdict / action model
# ══════════════════════════════════════════════════════════════════════════════════════════
@dataclass
class Verdict:
    """Result of ONE invariant check. `action` is the INTENDED effect if enforced."""
    invariant: str
    ok: bool
    action: str = "none"          # none | flatten | cancel | halt
    write_halt: bool = False
    broker_observed: str = ""
    belief_observed: str = ""
    note: str = ""


# ══════════════════════════════════════════════════════════════════════════════════════════
# PURE INVARIANT CHECKS (no I/O — unit-testable). Each returns a Verdict (or a list for ORPHAN).
# ══════════════════════════════════════════════════════════════════════════════════════════
def check_position_parity(broker_net, belief_expected, grace_active):
    """A. POSITION PARITY: panel net vs belief.expected_net. Skipped under the in-flight grace."""
    bo = f"net={broker_net}"
    be = f"expected={belief_expected}"
    if grace_active:
        return Verdict("POSITION_PARITY", True, "none", False, bo, be, "grace: belief changed <90s ago")
    if int(broker_net) == int(belief_expected):
        return Verdict("POSITION_PARITY", True, "none", False, bo, be, "match")
    # Mismatch beyond grace: flatten + HALT. fail-closed — a divergent broker position is
    # unaccounted risk; we reduce it and stop new entries rather than trust the engine's belief.
    return Verdict("POSITION_PARITY", False, "flatten", True, bo, be,
                   "broker net disagrees with engine belief beyond in-flight grace")


def check_orphan_orders(broker_working_ids, broker_working_count, belief_expected,
                        belief_entry_sids, belief_bracket_sids, grace_active):
    """B. ORPHAN ORDERS / UNPROTECTED POSITION. Returns a list of Verdicts (may be empty→ok)."""
    bo = f"working={broker_working_count} ids={sorted(broker_working_ids)}"
    known = set(belief_entry_sids) | set(belief_bracket_sids)
    be = f"expected={belief_expected} sids={sorted(known)}"
    if grace_active:
        return [Verdict("ORPHAN_ORDERS", True, "none", False, bo, be, "grace: belief changed <90s ago")]
    out = []
    # (i) ORPHAN: a broker working order that is not one of ours. Only actionable when we can be
    # sure it is not our own protection — i.e. we believe FLAT, or belief carries known sids to
    # match against. (Post-fill the registry clears; with an OPEN position and NO known sids we
    # deliberately do NOT cancel — canceling our own bracket would create the very exposure we
    # guard. That case is covered by UNPROTECTED / PARITY instead.) fail-closed: cancel is a
    # risk-REDUCING action, safe to send when flat.
    if int(belief_expected) == 0 and broker_working_count > 0:
        out.append(Verdict("ORPHAN_ORDERS", False, "cancel", False, bo, be,
                           "broker has working orders while engine believes FLAT — orphan(s), cancel"))
    elif known and int(belief_expected) != 0:
        unknown = [i for i in broker_working_ids if i not in known]
        if unknown:
            out.append(Verdict("ORPHAN_ORDERS", False, "cancel", False, bo, be,
                               f"working ids not in belief while position open: {unknown}"))
    # (ii) UNPROTECTED: position open but its bracket is absent broker-side (the silent-reject
    # case) → flatten + HALT. Robust to empty belief sids: an OPEN position with ZERO working
    # orders is unprotected regardless of sid fidelity.
    if int(belief_expected) != 0:
        if belief_bracket_sids:
            missing = [s for s in belief_bracket_sids if s not in broker_working_ids]
            if missing:
                out.append(Verdict("UNPROTECTED_POSITION", False, "flatten", True, bo, be,
                                   f"claimed bracket sid(s) absent broker-side: {missing} — position UNPROTECTED"))
        elif broker_working_count == 0:
            out.append(Verdict("UNPROTECTED_POSITION", False, "flatten", True, bo, be,
                               "position open but NO working orders broker-side — position UNPROTECTED"))
    if not out:
        return [Verdict("ORPHAN_ORDERS", True, "none", False, bo, be, "no orphans, protection present")]
    return out


def check_flat_time(now_et, is_half_day, broker_nonflat, broker_net):
    """C. FLAT-TIME SECOND SIGNATURE. Watchdog's OWN wall clock — never consults engine EOD state."""
    hh, mm = HALF_DAY_FLAT_TIME_ET if is_half_day else FLAT_TIME_ET
    past_flat = (now_et.hour, now_et.minute) >= (hh, mm)
    bo = f"net={broker_net} nonflat={broker_nonflat}"
    be = f"flat_after={hh:02d}:{mm:02d}ET half_day={is_half_day}"
    if past_flat and broker_nonflat:
        return Verdict("FLAT_TIME", False, "flatten", False, bo, be,
                       "position still open past the second-signature flat time")
    return Verdict("FLAT_TIME", True, "none", False, bo, be, "flat or before flat time")


def check_feed_liveness(feed_age_s, market_open, engine_alive, position_open, brackets_confirmed):
    """D. FEED LIVENESS, SECOND CLOCK. Only meaningful while the market is open and the ENGINE is
    alive (a dead engine is the deadman's job, not ours)."""
    bo = f"feed_age={None if feed_age_s is None else round(feed_age_s)}s"
    be = f"open={position_open} brackets_confirmed={brackets_confirmed}"
    if not (market_open and engine_alive):
        return Verdict("FEED_LIVENESS", True, "none", False, bo, be, "market closed or engine not alive — inert")
    if feed_age_s is None or feed_age_s <= FEED_STALE_S:
        return Verdict("FEED_LIVENESS", True, "none", False, bo, be, "feed fresh (or unknown, inert)")
    # Feed stale to the watchdog's own clock. Decision tree:
    #   * flat            → HALT new entries (fail-closed; nothing to protect).
    #   * open + brackets confirmed working in the panel → LEAVE the position, HALT new entries
    #     (the brackets protect it; flattening a protected position over a feed blip is the wrong
    #     reflex — T0-3 lesson).
    #   * open + protection UNCONFIRMABLE → FLATTEN (we cannot verify it is protected).
    if not position_open:
        return Verdict("FEED_LIVENESS", False, "halt", True, bo, be,
                       "own-clock feed stale, flat — HALT new entries")
    if brackets_confirmed:
        return Verdict("FEED_LIVENESS", False, "halt", True, bo, be,
                       "own-clock feed stale, position open but brackets confirmed working — leave + HALT")
    return Verdict("FEED_LIVENESS", False, "flatten", True, bo, be,
                   "own-clock feed stale, position open, protection UNCONFIRMABLE — flatten")


def check_config_integrity(config_ok, mismatches):
    """E. CONFIG INTEGRITY. Drift → HALT (never flatten for config drift)."""
    if config_ok:
        return Verdict("CONFIG_INTEGRITY", True, "none", False, "hashes match", "", "ok")
    return Verdict("CONFIG_INTEGRITY", False, "halt", True, str(mismatches), "",
                   "live config drifted from evidence/eval_config.sha256 — HALT (never flatten)")


def check_daily_loss(broker_flat, equity, day_seed_equity, belief_day_pnl):
    """F. DAILY-LOSS TRUTH. Only evaluated when broker-flat (positions settled)."""
    if not (broker_flat and equity is not None and day_seed_equity is not None
            and belief_day_pnl is not None):
        return Verdict("DAILY_LOSS", True, "none", False,
                       f"equity={equity}", f"belief_pnl={belief_day_pnl}",
                       "not broker-flat or inputs missing — inert")
    broker_delta = float(equity) - float(day_seed_equity)
    diff = abs(broker_delta - float(belief_day_pnl))
    bo = f"equity_delta={broker_delta:.2f}"
    be = f"belief_pnl={belief_day_pnl:.2f}"
    if diff > DAILY_LOSS_TOL_USD:
        return Verdict("DAILY_LOSS", False, "halt", True, bo, be,
                       f"broker vs belief day P&L diverge by ${diff:.2f} > ${DAILY_LOSS_TOL_USD} — HALT")
    return Verdict("DAILY_LOSS", True, "none", False, bo, be, f"within ${DAILY_LOSS_TOL_USD}")


# ══════════════════════════════════════════════════════════════════════════════════════════
# TRUTH READER — the broker-side view via the watchdog's OWN CDP. Constructor-injectable.
# ══════════════════════════════════════════════════════════════════════════════════════════
class PanelTruth:
    """Reads the connected TradingView account-manager panel through its own CDP websocket.

    Inherits readback_tradingview's fail-closed contract: if the panel is not configured/readable
    the underlying scrape raises TradingViewReadbackUnconfigured, which we let propagate so the
    watchdog's BROKER_READ strike counter fails closed (HALT), never guesses positions."""

    def __init__(self, broker=None, cdp=None, bars_reader=None, expect_root="NQ"):
        if cdp is None:
            from tv_feed import _CDP
            cdp = _CDP()                     # the watchdog's OWN websocket — never auto_live's
        self._cdp = cdp
        if broker is None:
            from readback_tradingview import TradingViewBrokerView
            broker = TradingViewBrokerView(cdp=cdp)
        self.broker = broker
        self._bars_reader = bars_reader      # injectable for tests
        self.expect_root = expect_root

    def snapshot(self):
        """One panel read → {account, net, working_ids, working_count, equity, nonflat}.
        Raises TradingViewReadbackUnconfigured / RuntimeError on a panel that cannot be read."""
        panel = self.broker._panel()         # raw contract; raises until _PANEL_JS is configured
        balances = panel.get("balances") or []
        account = str(balances[0]["account"]) if balances and balances[0].get("account") else None
        net = 0
        for p in panel.get("positions", []):
            if account is None or str(p.get("account")) == account:
                q = int(p.get("qty", 0) or 0)
                sgn = -1 if str(p.get("side", "long")).lower() == "short" else 1
                net += sgn * q
        working_ids, working_count = [], 0
        for o in panel.get("orders", []):
            if account is not None and str(o.get("account")) != account:
                continue
            if str(o.get("status", "")).lower() == "working":
                working_count += 1
                if o.get("signal") is not None:
                    working_ids.append(str(o["signal"]))
        equity = None
        for b in balances:
            if account is None or str(b.get("account")) == account:
                equity = None if b.get("equity") is None else float(b["equity"])
                break
        return dict(account=account, net=net, working_ids=working_ids,
                    working_count=working_count, equity=equity, nonflat=(net != 0))

    def last_bar_age_s(self, now_utc):
        """Seconds since the last 1m bar on the watchdog's OWN CDP read. None if unreadable."""
        try:
            if self._bars_reader is not None:
                last_ts = self._bars_reader()
            else:
                from tv_feed import _read_bars_js, _to_et
                raw = self._cdp.eval(_read_bars_js(2))
                if not raw:
                    return None
                last_ts = _to_et(raw[-1][0]).tz_convert("UTC")
            if last_ts is None:
                return None
            if getattr(last_ts, "tzinfo", None) is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            return (now_utc - last_ts.to_pydatetime()).total_seconds() \
                if hasattr(last_ts, "to_pydatetime") else (now_utc - last_ts).total_seconds()
        except Exception as e:   # noqa: BLE001 — an own-clock read error is "unknown", handled inert by check_feed
            print(f"[watchdog] feed read error (inert this cycle): {e!r}", flush=True)
            return None


# ══════════════════════════════════════════════════════════════════════════════════════════
# WATCHDOG
# ══════════════════════════════════════════════════════════════════════════════════════════
@dataclass
class ActionRecord:
    invariant: str
    intended: str
    executed: bool
    write_halt: bool
    mode: str
    note: str


class Watchdog:
    """The reconciliation process. Truth-reader and sender are constructor-injectable so the full
    9-test suite (from another agent) can drive fakes; nothing here needs a live CDP to be tested."""

    def __init__(self, *, mode="observe", account="APEX-50K-EVAL-1", truth=None, sender=None,
                 belief_reader=None, telegram=None, config_verifier=None,
                 state_path=None, audit_dir=None):
        assert mode in ("observe", "enforce"), mode
        self.mode = mode
        self.account = account
        self.account_tag = account_tag(account)
        self.truth = truth
        self.sender = sender
        self.belief_reader = belief_reader or (lambda: _read_json(BELIEF_PATH))
        self.tg = telegram if telegram is not None else Telegram(label="[watchdog]")
        self.config_verifier = config_verifier or verify_eval_config_hashes
        self.state_path = state_path or os.path.join(WATCHDOG_DIR, "state.json")
        self.audit_dir = audit_dir or WATCHDOG_DIR
        # runtime state
        self._prev_order_state = None      # (expected_net, tuple(sids)) — grace change detection
        self._order_change_wall = None     # wall time of the last observed belief order-state change
        self._read_strikes = 0
        self._last_action_wall = {}        # invariant -> wall time of its last FIRED send (dedup backstop)
        self._last_config_check = 0.0
        self._config_ok = True
        self._config_mismatches = []
        self._state = {}                   # persisted: day, day_seed_equity, alerted{}, clean_shutdown
        self._prev_verdict = {}            # invariant -> ok(bool) for transition detection

    # ---- persistence ----------------------------------------------------------------------
    def load_state(self):
        self._state = _read_json(self.state_path) or {}
        return self._state

    def save_state(self):
        _atomic_write_json(self.state_path, self._state)

    # ---- audit ----------------------------------------------------------------------------
    def _audit(self, invariant, verdict, action, note, broker_observed="", belief_observed="",
               now_utc=None):
        now_utc = now_utc or datetime.now(timezone.utc)
        row = dict(ts_utc=now_utc.isoformat(), invariant=invariant,
                   broker_observed=broker_observed, belief_observed=belief_observed,
                   verdict=verdict, action=action, mode=self.mode, note=note)
        path = os.path.join(self.audit_dir, f"audit-{now_utc.astimezone(ET).date().isoformat()}.jsonl")
        try:
            os.makedirs(self.audit_dir, exist_ok=True)
            with open(path, "a") as f:
                f.write(json.dumps(row) + "\n")
        except Exception as e:   # noqa: BLE001 — audit failure must never break the safety loop
            print(f"[watchdog] ⚠ audit write failed (swallowed): {e!r}", flush=True)

    # ---- alerting (transition-only, per-invariant per ET day + recovery) -------------------
    def _alert_transition(self, v: Verdict, now_utc):
        alerted = self._state.setdefault("alerted", {})
        was = alerted.get(v.invariant)
        acted = "would_have" if self.mode == "observe" else v.action
        belief_ts = self._state.get("_last_belief_ts", "?")
        if not v.ok and was != "violation":
            alerted[v.invariant] = "violation"
            self._telegram(
                f"⚠ WATCHDOG [{self.mode}] {v.invariant}\n"
                f"broker: {v.broker_observed}  (@{now_utc.isoformat()})\n"
                f"belief: {v.belief_observed}  (@{belief_ts})\n"
                f"action: {acted}\nnote: {v.note}")
        elif v.ok and was == "violation":
            alerted[v.invariant] = "ok"
            self._telegram(f"✅ WATCHDOG [{self.mode}] {v.invariant} RECOVERED\n"
                           f"broker: {v.broker_observed}\nnote: {v.note}")

    def _telegram(self, text):
        try:
            self.tg.send(text)
        except Exception as e:   # noqa: BLE001 — alerting never breaks the safety loop
            print(f"[watchdog] ⚠ telegram failed (swallowed): {e!r}", flush=True)

    # ---- action execution -----------------------------------------------------------------
    def _execute_send(self, v: Verdict, now_utc):
        """Enforce a violation's WEBHOOK action (flatten/cancel). Dedup is decided by the caller
        (_handle/_should_fire); HALT.flag writes are handled separately (idempotent). observe never
        reaches here."""
        ts = int(now_utc.timestamp())
        if v.action == "flatten":
            reason = f"watchdog_{v.invariant.lower()}_{ts}"
            self.sender.flatten(self.account, root=ROOT, reason=reason)
        elif v.action == "cancel":
            self._send_cancel_only(now_utc)

    def _send_cancel_only(self, now_utc):
        """Cancel-only leg (ORPHAN). There is no cancel-only public method on BridgeSender, so we
        build the SAME cancel payload flatten() uses (bridge_traderspost.build_cancel) and send it
        WITHOUT the exit leg — cancel is safe-direction (never opens/closes a position)."""
        try:
            import bridge_traderspost as BP
            cancel_p, _ = BP.build_cancel(account=self.account, strategy="WATCHDOG",
                                          signal_ts=f"watchdog_cancel_{int(now_utc.timestamp())}", root=ROOT)
            self.sender.send(cancel_p)
        except Exception as e:   # noqa: BLE001 — a cancel-build failure must not crash the loop; alerted already
            print(f"[watchdog] ⚠ cancel-only send failed: {e!r}", flush=True)

    def _write_halt(self, v: Verdict, now_utc):
        try:
            os.makedirs(WATCHDOG_DIR, exist_ok=True)
            _atomic_write_json(HALT_FLAG_PATH, dict(ts_utc=now_utc.isoformat(), invariant=v.invariant,
                                                    note=v.note, account_tag=self.account_tag))
        except Exception as e:   # noqa: BLE001
            print(f"[watchdog] ⚠ HALT.flag write failed: {e!r}", flush=True)

    # ---- one verdict → record + side effects ----------------------------------------------
    def _handle(self, v: Verdict, now_utc, records, broker_nonflat=None, broker_working_count=None):
        # transition detection drives audit + alerting (verdicts themselves are too chatty)
        prev = self._prev_verdict.get(v.invariant)
        changed = (prev is None and not v.ok) or (prev is not None and prev != v.ok)
        self._prev_verdict[v.invariant] = v.ok
        if v.ok:
            if changed:                                   # violation → ok recovery: reset the incident so a
                self._last_action_wall.pop(v.invariant, None)  # re-violation later is a fresh transition fire
                self._audit(v.invariant, "ok", "recover", v.note, v.broker_observed,
                            v.belief_observed, now_utc)
                self._alert_transition(v, now_utc)
            return
        # --- violation: dedup ACTIONS (not just alerts). Fire on the ok→violation transition, then at
        # most once per ACTION_REFIRE_S and only while the unsafe condition is still observable. HALT.flag
        # writes are idempotent and are exempt from this dedup (rewriting is harmless).
        fire = self._should_fire(v, now_utc, changed, broker_nonflat, broker_working_count)
        if self.mode == "enforce":
            if v.write_halt:                              # idempotent — keep the flag present every cycle
                self._write_halt(v, now_utc)
            if fire and v.action in ("flatten", "cancel"):
                self._execute_send(v, now_utc)            # observe: NOTHING sent, no HALT flag (by design)
        if fire:
            self._last_action_wall[v.invariant] = now_utc
            acted = "would_have" if self.mode == "observe" else v.action
        else:
            # persistent violation, action already fired: keep the duration row but label it so the log
            # cannot be misread as a repeated send.
            acted = "would_have" if self.mode == "observe" else "suppressed_dedup"
        self._audit(v.invariant, "violation", acted, v.note, v.broker_observed, v.belief_observed, now_utc)
        self._alert_transition(v, now_utc)               # alerting is transition-only internally
        records.append(ActionRecord(v.invariant, v.action,
                                    executed=(fire and self.mode == "enforce"),
                                    write_halt=v.write_halt, mode=self.mode, note=v.note))

    def _should_fire(self, v: Verdict, now_utc, changed, broker_nonflat, broker_working_count):
        """Whether this cycle should EXECUTE the action (vs suppress as an already-fired duplicate)."""
        if v.action == "halt":
            return True                                   # HALT.flag rewrite is idempotent — never spammy
        if v.action not in ("flatten", "cancel"):
            return changed                                # 'none' etc. — only the transition matters
        last = self._last_action_wall.get(v.invariant)
        if last is None or changed:
            return True                                   # first fire of the incident (ok→violation)
        if (now_utc - last).total_seconds() < ACTION_REFIRE_S:
            return False                                  # within the dedup window
        # backstop window elapsed: re-fire ONLY if the unsafe condition is STILL observable broker-side.
        if v.action == "flatten":
            return bool(broker_nonflat)                   # a flatten that worked left the broker flat
        return bool(broker_working_count)                 # a cancel that worked left no working orders

    # ---- grace ----------------------------------------------------------------------------
    def _grace_active(self, belief, now_utc):
        """True while any belief order-state (expected_net or sids) changed <INFLIGHT_GRACE_S ago.
        First-ever observation seeds a startup grace window (conservative: don't act in the first
        90s before we've seen a stable belief)."""
        state = (int(belief.get("expected_net", 0) or 0),
                 tuple(sorted(belief.get("open_entry_sids", []) or [])),
                 tuple(sorted(belief.get("claimed_bracket_sids", []) or [])))
        if state != self._prev_order_state:
            self._prev_order_state = state
            self._order_change_wall = now_utc
        if self._order_change_wall is None:
            return False
        return (now_utc - self._order_change_wall).total_seconds() < INFLIGHT_GRACE_S

    # ---- the cycle ------------------------------------------------------------------------
    def run_cycle(self, now_utc=None, grace_override=None):
        """One reconciliation pass. Returns the list of ActionRecords produced (violations only).
        `grace_override` lets tests pin the in-flight grace deterministically."""
        now_utc = now_utc or datetime.now(timezone.utc)
        now_et = now_utc.astimezone(ET)
        market_open = market_likely_open(now_et)
        records = []

        belief = self.belief_reader() or {}
        self._state["_last_belief_ts"] = belief.get("ts_utc", "?")
        grace = grace_override if grace_override is not None else self._grace_active(belief, now_utc)

        # --- broker truth (fail-closed on unreadable panel) ---
        snap = None
        try:
            snap = self.truth.snapshot()
            self._read_strikes = 0
        except Exception as e:   # noqa: BLE001 — CANNOT SEE broker = fail closed, but NEVER flatten on a read failure
            self._read_strikes += 1
            v = Verdict("BROKER_READ", False, "halt" if self._read_strikes >= BROKER_READ_STRIKES else "none",
                        self._read_strikes >= BROKER_READ_STRIKES, f"read fail x{self._read_strikes} ({type(e).__name__})",
                        "", "panel unreadable — HALT after strikes, NEVER flatten (T0-3 lesson)")
            if not v.ok and v.action == "none":
                # below strike threshold: record/alert transition but take no HALT yet (ORANGE)
                self._handle(Verdict("BROKER_READ", True, "none", False, v.broker_observed, "",
                                     "panel read failing (below strike threshold)"), now_utc, records)
                return records
            self._handle(v, now_utc, records)
            return records

        # --- new-ET-day + day-seed equity bookkeeping (persisted) ---
        today = now_et.date().isoformat()
        if self._state.get("day") != today:
            self._state["day"] = today
            self._state["alerted"] = {}
            self._state.pop("day_seed_equity", None)
        if snap["net"] == 0 and snap["equity"] is not None and self._state.get("day_seed_equity") is None:
            self._state["day_seed_equity"] = snap["equity"]   # first flat read of the ET day

        belief_expected = int(belief.get("expected_net", 0) or 0)
        entry_sids = belief.get("open_entry_sids", []) or []
        bracket_sids = belief.get("claimed_bracket_sids", []) or []
        position_open = snap["nonflat"]

        # --- config integrity on interval ---
        if time.time() - self._last_config_check >= CONFIG_CHECK_S or self._last_config_check == 0.0:
            self._last_config_check = time.time()
            self._config_ok, self._config_mismatches = self.config_verifier()

        # --- feed liveness (own second clock) ---
        feed_age = self.truth.last_bar_age_s(now_utc)
        engine_alive = bool(deadman_status(now=now_utc).get("alive"))
        brackets_confirmed = bool(bracket_sids) and all(s in snap["working_ids"] for s in bracket_sids)

        # --- run the invariants (broker_nonflat / working_count feed the send-dedup backstop) ---
        nf, wc = snap["nonflat"], snap["working_count"]
        self._handle(check_position_parity(snap["net"], belief_expected, grace), now_utc, records, nf, wc)
        for v in check_orphan_orders(snap["working_ids"], snap["working_count"], belief_expected,
                                     entry_sids, bracket_sids, grace):
            self._handle(v, now_utc, records, nf, wc)
        self._handle(check_flat_time(now_et, now_et.date() in _half_days(), position_open, snap["net"]),
                     now_utc, records, nf, wc)
        self._handle(check_feed_liveness(feed_age, market_open, engine_alive, position_open,
                                         brackets_confirmed), now_utc, records, nf, wc)
        self._handle(check_config_integrity(self._config_ok, self._config_mismatches), now_utc, records, nf, wc)
        self._handle(check_daily_loss(snap["net"] == 0, snap["equity"],
                                      self._state.get("day_seed_equity"),
                                      belief.get("day_internal_pnl")), now_utc, records, nf, wc)

        self.save_state()
        return records

    # ---- self-heartbeat -------------------------------------------------------------------
    def write_heartbeat(self, now_utc, last_cycle_ok):
        try:
            _atomic_write_json(HEARTBEAT_PATH, dict(ts=now_utc.isoformat(), pid=os.getpid(),
                                                    mode=self.mode, last_cycle_ok=last_cycle_ok))
        except Exception as e:   # noqa: BLE001
            print(f"[watchdog] ⚠ heartbeat write failed: {e!r}", flush=True)

    # ---- startup / restart audit ----------------------------------------------------------
    def announce_startup(self, now_utc):
        self.load_state()
        unclean = self._state.get("clean_shutdown") is False   # explicit False = crashed last time
        self._state["clean_shutdown"] = False                  # mark running; set True on clean exit
        self._audit("_startup", "info", "startup", f"mode={self.mode}", now_utc=now_utc)
        self._audit("_mode", "info", self.mode, "watchdog mode declared at startup", now_utc=now_utc)
        if unclean:
            self._audit("_restart", "info", "restart", "restarted after non-clean shutdown", now_utc=now_utc)
            self._telegram(f"🔄 WATCHDOG restarted after non-clean shutdown (mode={self.mode}).")
        self.save_state()

    def announce_clean_shutdown(self, now_utc):
        self._state["clean_shutdown"] = True
        self.save_state()
        self._audit("_shutdown", "info", "clean_shutdown", f"mode={self.mode}", now_utc=now_utc)


# ══════════════════════════════════════════════════════════════════════════════════════════
# helpers
# ══════════════════════════════════════════════════════════════════════════════════════════
def _half_days():
    try:
        from scheduler import HALF_DAYS_2026
        return HALF_DAYS_2026
    except Exception:   # noqa: BLE001
        return set()


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:   # noqa: BLE001
        return None


def _atomic_write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


# ══════════════════════════════════════════════════════════════════════════════════════════
# CLI / loop
# ══════════════════════════════════════════════════════════════════════════════════════════
def _build_sender(mode):
    from bridge_sender import BridgeSender
    from store import Store
    from journal import Journal
    live_url = os.environ.get("TRADERSPOST_LIVE_URL") if mode == "enforce" else None
    bmode = "live" if mode == "enforce" else "dry-run"
    return BridgeSender(store=Store(), journal=Journal(), mode=bmode, live_url=live_url)


def run(args):
    mode = os.environ.get("WATCHDOG_MODE", "observe").strip().lower()
    if mode not in ("observe", "enforce"):
        mode = "observe"
    truth = PanelTruth()
    sender = _build_sender(mode)
    wd = Watchdog(mode=mode, account=args.account, truth=truth, sender=sender)
    now = datetime.now(timezone.utc)
    wd.announce_startup(now)
    print(f"[watchdog] started account_tag={wd.account_tag} mode={mode}", flush=True)

    try:
        while True:
            now = datetime.now(timezone.utc)
            ok = True
            try:
                wd.run_cycle(now)
            except Exception as e:   # noqa: BLE001 — a cycle error must not kill the watchdog; log + heartbeat not-ok
                ok = False
                print(f"[watchdog] ⚠ cycle error: {e!r}", flush=True)
            wd.write_heartbeat(now, last_cycle_ok=ok)
            if args.once:
                break
            time.sleep(LOOP_OPEN_S if market_likely_open(now.astimezone(ET)) else LOOP_CLOSED_S)
    finally:
        wd.announce_clean_shutdown(datetime.now(timezone.utc))


def _build_parser():
    p = argparse.ArgumentParser(description="ZEUS independent reconciliation watchdog (fail-closed)")
    p.add_argument("--account", default="APEX-50K-EVAL-1", help="account label (only account_tag is ever emitted)")
    p.add_argument("--once", action="store_true", help="run a single cycle and exit (verification)")
    return p


def main():
    args = _build_parser().parse_args()
    lock = InstanceLock("data/watchdog.lock")
    try:
        lock.acquire()
    except LockHeld as e:
        print(f"[watchdog] ABORT: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        run(args)
    except KeyboardInterrupt:
        print("\n[watchdog] interrupted — exiting cleanly.", flush=True)
    finally:
        lock.release()


if __name__ == "__main__":
    main()
