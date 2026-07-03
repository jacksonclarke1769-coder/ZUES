"""Execution slippage tripwire — SLIP-class halt.  Spec: docs/specs/slippage_tripwire_spec.md

Watches real fill quality (from exec_telemetry) and reacts when live entries fill systematically
WORSE than the backtest-modeled level, or aren't filling at all.  The certified 58.2% eval pass rate
assumes ~0 entry slippage; this is the part that checks that assumption against reality and, in halt
mode, freezes new entries before an unmodeled cost silently drains the ~$1,905 eval cushion.

DESIGN CONTRACT (mirrors exec_telemetry.py):
  * OBSERVATIONAL-FIRST, HALT-ONLY.  It NEVER flattens.  A breach means the ENTRY assumption is
    leaking, not that the open position is wrong — existing brackets stay on the book.
  * NEVER raises into the order path.  Every public method is try/except-wrapped, prints loudly,
    returns.  A tripwire bug must never block or crash a trade.
  * Pure decision core: evaluate() has no I/O and no state — fully unit-testable.
  * Default OFF.  mode "off" is a hard no-op; "alert" computes + notifies but never halts; "halt"
    also invokes on_halt (wired to ReadbackSentinel.slip_halt in production).

Sign convention (inherited from exec_telemetry): slippage_R positive == filled WORSE than expected.
Better-than-modeled fills (negative R) never trip anything.
"""
from __future__ import annotations

import csv
import os
from collections import deque
from datetime import datetime, timezone
from typing import Callable, Optional

EVENT_CSV = "out/exec/slip_halt_events.csv"
_EVENT_COLS = ["wall_ts", "action", "mode", "reason", "n_resolved", "n_fills", "last_slip_R"]


def evaluate(slips: list, resolutions: list, cfg: dict) -> tuple:
    """Pure decision core.  No I/O, no state.

    slips        : slippage_R for FILLED entries, oldest→newest (floats; + == worse).
    resolutions  : "FILLED"/"MISSED" per resolved A signal, oldest→newest.
    cfg          : thresholds (see config_defaults.slip_tripwire_cfg()).

    Returns (action, reason) where action is one of None / "ALERT" / "HALT".
    HALT dominates ALERT.  No action of any kind before cfg['warmup_min'] resolved signals.
    """
    n_resolved = len(resolutions)
    if n_resolved < cfg["warmup_min"]:
        return (None, "")

    halt_reasons: list = []
    alert_reasons: list = []

    # --- single-fill outlier (most recent fill) ---
    if slips:
        last = slips[-1]
        if last > cfg["single_r_halt"]:
            halt_reasons.append(
                f"single fill {last:+.2f}R worse (cap {cfg['single_r_halt']:.2f}R)")
        elif last > cfg["single_r_alert"]:
            alert_reasons.append(
                f"single fill {last:+.2f}R worse (alert {cfg['single_r_alert']:.2f}R)")

    # --- rolling mean entry slippage ---
    win = slips[-cfg["window_n"]:]
    if len(win) >= cfg["warmup_min"]:
        mean_r = sum(win) / len(win)
        if mean_r > cfg["mean_r_halt"]:
            halt_reasons.append(
                f"mean entry slippage {mean_r:.3f}R over last {len(win)} fills "
                f"(cap {cfg['mean_r_halt']:.2f}R)")

    # --- rolling miss rate (a limit you can't fill is a phantom edge) ---
    rwin = resolutions[-cfg["miss_window_n"]:]
    n_fill = rwin.count("FILLED")
    n_miss = rwin.count("MISSED")
    denom = n_fill + n_miss
    if denom >= cfg["warmup_min"]:
        miss_rate = n_miss / denom
        if miss_rate > cfg["miss_rate_halt"]:
            halt_reasons.append(
                f"miss rate {miss_rate:.0%} over last {denom} signals "
                f"(cap {cfg['miss_rate_halt']:.0%})")

    if halt_reasons:
        return ("HALT", "; ".join(halt_reasons))
    if alert_reasons:
        return ("ALERT", "; ".join(alert_reasons))
    return (None, "")


class SlipTripwire:
    """Stateful observational monitor.  Feed it resolved A signals; it decides ALERT / HALT.

    mode:
      "off"   — hard no-op (observe() returns immediately).
      "alert" — compute breaches, call on_alert + log the event; NEVER calls on_halt.
      "halt"  — same as alert, and for HALT verdicts also calls on_halt(reason) exactly once
                (wire on_halt to ReadbackSentinel.slip_halt — latches entries, no flatten).
    """

    def __init__(
        self,
        cfg: dict,
        mode: str = "alert",
        on_alert: Optional[Callable[[str], None]] = None,
        on_halt: Optional[Callable[[str], None]] = None,
        event_csv: str = EVENT_CSV,
    ):
        self.cfg = dict(cfg)
        self.mode = mode if mode in ("off", "alert", "halt") else "alert"
        self.on_alert = on_alert
        self.on_halt = on_halt
        self._event_csv = event_csv
        self._slips: deque = deque(maxlen=max(self.cfg["window_n"], self.cfg["miss_window_n"], 64))
        self._res: deque = deque(maxlen=max(self.cfg["window_n"], self.cfg["miss_window_n"], 64))
        self._halted = False          # latched once a HALT verdict has fired (idempotent)
        self._alerted_reasons: set = set()  # de-dupe repeated identical ALERTs

    # ------------------------------------------------------------------ public API
    def observe_fill(self, slippage_R: Optional[float]) -> tuple:
        """Record a FILLED entry (slippage_R may be None if the panel couldn't price the fill)."""
        return self._observe("FILLED", slippage_R)

    def observe_miss(self) -> tuple:
        """Record a MISSED entry (limit never filled)."""
        return self._observe("MISSED", None)

    def _observe(self, resolution: str, slippage_R: Optional[float]) -> tuple:
        """Ingest one resolved signal, evaluate, and fire side-effects per mode.
        Returns (action, reason) for the caller/tests.  Never raises."""
        try:
            if self.mode == "off":
                return (None, "")
            self._res.append(resolution)
            if resolution == "FILLED" and slippage_R is not None:
                self._slips.append(float(slippage_R))

            action, reason = evaluate(list(self._slips), list(self._res), self.cfg)
            if action is None:
                return (None, "")

            if action == "HALT":
                if self._halted:
                    return (action, reason)     # already latched — don't spam
                self._halted = True
                self._notify(f"⚠ SLIP-TRIPWIRE HALT — {reason}")
                self._log_event("HALT", reason)
                if self.mode == "halt" and self.on_halt is not None:
                    try:
                        self.on_halt(reason)
                    except Exception as e:  # noqa: BLE001
                        print(f"[slip-tripwire] ⚠ on_halt error: {e!r}", flush=True)
                else:
                    # alert mode: report what it WOULD have done, so we learn without acting.
                    self._notify("   (alert-only mode: entries NOT halted — would freeze in halt mode)")
                return (action, reason)

            if action == "ALERT":
                if reason not in self._alerted_reasons:
                    self._alerted_reasons.add(reason)
                    self._notify(f"⚠ SLIP-TRIPWIRE watch — {reason}")
                    self._log_event("ALERT", reason)
                return (action, reason)

            return (None, "")
        except Exception as e:  # noqa: BLE001 — observational: never break the order path
            print(f"[slip-tripwire] ⚠ observe error ({resolution}): {e!r} — skipped", flush=True)
            return (None, "")

    def status(self) -> dict:
        """Small snapshot for the dashboard / exec report."""
        try:
            slips = list(self._slips)
            mean_r = round(sum(slips) / len(slips), 4) if slips else None
            res = list(self._res)
            denom = res.count("FILLED") + res.count("MISSED")
            miss_rate = round(res.count("MISSED") / denom, 4) if denom else None
            return dict(mode=self.mode, halted=self._halted, n_resolved=len(res),
                        n_fills=len(slips), mean_slip_R=mean_r, miss_rate=miss_rate)
        except Exception:  # noqa: BLE001
            return dict(mode=self.mode, halted=self._halted, error=True)

    # ------------------------------------------------------------------ internal
    def _notify(self, msg: str) -> None:
        print(f"[slip-tripwire] {msg}", flush=True)
        if self.on_alert is not None:
            try:
                self.on_alert(msg)
            except Exception:  # noqa: BLE001 — alerting never breaks safety
                pass

    def _log_event(self, action: str, reason: str) -> None:
        try:
            slips = list(self._slips)
            row = dict(
                wall_ts=datetime.now(timezone.utc).isoformat(),
                action=action, mode=self.mode, reason=reason,
                n_resolved=len(self._res), n_fills=len(slips),
                last_slip_R=(slips[-1] if slips else ""),
            )
            os.makedirs(os.path.dirname(self._event_csv), exist_ok=True)
            is_new = not os.path.exists(self._event_csv)
            with open(self._event_csv, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=_EVENT_COLS)
                if is_new:
                    w.writeheader()
                w.writerow(row)
        except Exception as e:  # noqa: BLE001
            print(f"[slip-tripwire] ⚠ event-log write failed: {e!r} — dropped", flush=True)
