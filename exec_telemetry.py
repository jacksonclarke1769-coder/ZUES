"""Execution telemetry — observational only, never raises into the order path.

Collects per-A-signal fill quality metrics and appends one CSV row when the
signal resolves (fill confirmed / MISSED / CANCELLED).

DESIGN CONTRACT:
  * Every public method is wrapped in try/except.  Exceptions print loudly and
    return without raising — the order path MUST NEVER see an exception from here.
  * No module-level I/O.  CSV directory is created lazily on first flush.
  * _pending is keyed by signal_ts (sig["ts_signal"] from auto_live).
  * A crash loses at most ONE pending row — acceptable given the observational role.
  * Slippage sign: positive = filled WORSE than expected (higher for short, lower for long).
"""
from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from typing import Optional

CSV_PATH = "out/exec/exec_telemetry.csv"

COLUMNS = [
    "signal_ts", "strategy", "side",
    "signal_bar_ts", "decision_wall_ts", "bar_to_decision_ms",
    "webhook_send_wall_ts", "webhook_http_status", "decision_to_webhook_ms",
    "expected_entry", "expected_stop", "expected_target", "qty",
    "fill_confirm_wall_ts", "webhook_to_fill_ms", "polls_to_confirm",
    "panel_readable", "actual_fill_px", "slippage_pts", "slippage_R",
    "resolution", "notes",
]


def _ms(a: datetime, b: datetime) -> Optional[float]:
    """Return (b - a) in milliseconds, or None if either timestamp is None."""
    if a is None or b is None:
        return None
    return round((b - a).total_seconds() * 1000, 1)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ExecTelemetry:
    """Collects fill-quality data per A signal and flushes one CSV row on resolution."""

    def __init__(self, csv_path: str = CSV_PATH):
        self._csv_path = csv_path
        self._pending: dict[str, dict] = {}  # signal_ts -> row dict

    # ------------------------------------------------------------------ public API

    def on_decision(
        self,
        signal_ts: str,
        signal_bar_ts,           # bar close timestamp (str or datetime)
        decision_wall_ts: datetime,
        expected_entry: float,
        expected_stop: float,
        expected_target: float,
        qty: int,
        side: str,
        strategy: str = "A",
    ) -> None:
        """Call immediately before sending the webhook (after ZEUS gates passed).

        Opens a pending row.  Overwrites any stale row for the same signal_ts
        (a restart re-arms the same signal slot; only the latest attempt counts).
        """
        try:
            self._pending[str(signal_ts)] = dict(
                signal_ts=str(signal_ts),
                strategy=strategy,
                side=side,
                signal_bar_ts=str(signal_bar_ts),
                decision_wall_ts=decision_wall_ts.isoformat() if decision_wall_ts else None,
                bar_to_decision_ms=None,   # computed once webhook wall_ts known (bar -> decision)
                webhook_send_wall_ts=None,
                webhook_http_status=None,
                decision_to_webhook_ms=None,
                expected_entry=float(expected_entry),
                expected_stop=float(expected_stop),
                expected_target=float(expected_target),
                qty=int(qty),
                fill_confirm_wall_ts=None,
                webhook_to_fill_ms=None,
                polls_to_confirm=0,
                panel_readable=False,
                actual_fill_px=None,
                slippage_pts=None,
                slippage_R=None,
                resolution="PENDING",
                notes="",
                # internal tracking (not written to CSV)
                _decision_wall=decision_wall_ts,
                _signal_bar_ts=signal_bar_ts,
                _webhook_wall=None,
            )
        except Exception as e:  # noqa: BLE001
            print(f"[exec-telem] ⚠ on_decision error (signal_ts={signal_ts}): {e!r} — telemetry skipped",
                  flush=True)

    def on_webhook_result(
        self,
        signal_ts: str,
        http_status: Optional[int],
        wall_ts: datetime,
    ) -> None:
        """Call immediately after send() / send_exit3() returns.

        Records the webhook send wall time and HTTP status.
        """
        try:
            row = self._pending.get(str(signal_ts))
            if row is None:
                return   # no pending row (telemetry not armed for this signal)
            row["webhook_send_wall_ts"] = wall_ts.isoformat()
            row["webhook_http_status"] = http_status
            row["_webhook_wall"] = wall_ts
            # bar_to_decision: use bar ts and decision wall ts
            _bts = row.get("_signal_bar_ts")
            _dw = row.get("_decision_wall")
            if _bts is not None and _dw is not None:
                try:
                    _bts_dt = (
                        _bts if isinstance(_bts, datetime)
                        else datetime.fromisoformat(str(_bts).replace("Z", "+00:00"))
                    )
                    if _bts_dt.tzinfo is None:
                        # naive bar ts from the feed (ET) — we can't reliably subtract from UTC wall time;
                        # leave as None rather than compute a wrong number.
                        row["bar_to_decision_ms"] = None
                    else:
                        row["bar_to_decision_ms"] = _ms(_bts_dt, _dw)
                except Exception:  # noqa: BLE001
                    row["bar_to_decision_ms"] = None
            row["decision_to_webhook_ms"] = _ms(row.get("_decision_wall"), wall_ts)
        except Exception as e:  # noqa: BLE001
            print(f"[exec-telem] ⚠ on_webhook_result error (signal_ts={signal_ts}): {e!r}",
                  flush=True)

    def poll_increment(self, signal_ts: str) -> None:
        """Call once per readback poll AFTER a signal is pending.

        Increments the polls_to_confirm counter so we know how many polls it took
        before fill confirmation (or MISSED was declared).
        """
        try:
            row = self._pending.get(str(signal_ts))
            if row is not None:
                row["polls_to_confirm"] = row.get("polls_to_confirm", 0) + 1
        except Exception as e:  # noqa: BLE001
            print(f"[exec-telem] ⚠ poll_increment error: {e!r}", flush=True)

    def on_fill_confirmed(
        self,
        signal_ts: str,
        actual_fill_px: Optional[float],
        panel_readable: bool,
        wall_ts: datetime,
    ) -> None:
        """Call when the readback sentinel confirms the broker position matches expected.

        actual_fill_px comes from readback_tradingview.avg_price_by_account() (None if
        the panel is not connected / not readable — set panel_readable=False in that case).
        """
        try:
            row = self._pending.get(str(signal_ts))
            if row is None:
                return
            row["fill_confirm_wall_ts"] = wall_ts.isoformat()
            row["panel_readable"] = bool(panel_readable)
            row["actual_fill_px"] = float(actual_fill_px) if actual_fill_px is not None else None
            row["resolution"] = "FILLED"
            row["webhook_to_fill_ms"] = _ms(row.get("_webhook_wall"), wall_ts)
            # slippage: (actual - expected) × direction_sign
            # positive = filled worse than expected
            if actual_fill_px is not None:
                _dir = 1 if str(row.get("side", "long")).lower() == "long" else -1
                _slip_pts = round((float(actual_fill_px) - float(row["expected_entry"])) * _dir, 2)
                _stop_dist = abs(float(row["expected_entry"]) - float(row["expected_stop"]))
                row["slippage_pts"] = _slip_pts
                row["slippage_R"] = (
                    round(_slip_pts / _stop_dist, 4) if _stop_dist > 0 else None
                )
            self._flush(str(signal_ts))
        except Exception as e:  # noqa: BLE001
            print(f"[exec-telem] ⚠ on_fill_confirmed error (signal_ts={signal_ts}): {e!r}",
                  flush=True)

    def on_missed(self, signal_ts: str, notes: str = "") -> None:
        """Call when on_missing fires (TTL expired, position never filled).

        Flushes the row with resolution=MISSED.
        """
        try:
            row = self._pending.get(str(signal_ts))
            if row is None:
                # on_missing may fire for signals that weren't in telemetry (e.g. old session)
                return
            row["resolution"] = "MISSED"
            row["notes"] = notes or "on_missing fired (unfilled limit)"
            self._flush(str(signal_ts))
        except Exception as e:  # noqa: BLE001
            print(f"[exec-telem] ⚠ on_missed error (signal_ts={signal_ts}): {e!r}", flush=True)

    def on_cancelled(self, signal_ts: str, notes: str = "") -> None:
        """Call when an armed entry order is explicitly cancelled before fill.

        Flushes the row with resolution=CANCELLED.
        """
        try:
            row = self._pending.get(str(signal_ts))
            if row is None:
                return
            row["resolution"] = "CANCELLED"
            row["notes"] = notes or "cancelled before fill"
            self._flush(str(signal_ts))
        except Exception as e:  # noqa: BLE001
            print(f"[exec-telem] ⚠ on_cancelled error (signal_ts={signal_ts}): {e!r}", flush=True)

    def pending_signal_ts(self) -> Optional[str]:
        """Return the most recently armed pending signal_ts (or None).

        Used by auto_live wiring to route readback poll events to the right row.
        When multiple signals are pending (unusual), returns the most recently armed one.
        """
        try:
            if not self._pending:
                return None
            # _pending is insertion-ordered (Python 3.7+); last inserted = most recent
            return next(reversed(self._pending))
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------ internal

    def _flush(self, signal_ts: str) -> None:
        """Write the resolved row to CSV and remove it from _pending.

        Creates the directory and writes the header if the file is new.
        All I/O errors are caught and printed loudly; the row is dropped on
        persistent failure (observational data only, never retry into the order path).
        """
        try:
            row = self._pending.pop(signal_ts, None)
            if row is None:
                return
            # strip internal tracking fields
            out = {k: row.get(k, "") for k in COLUMNS}
            os.makedirs(os.path.dirname(self._csv_path), exist_ok=True)
            is_new = not os.path.exists(self._csv_path)
            with open(self._csv_path, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=COLUMNS)
                if is_new:
                    w.writeheader()
                w.writerow(out)
        except Exception as e:  # noqa: BLE001
            print(f"[exec-telem] ⚠ CSV flush FAILED (signal_ts={signal_ts}): {e!r} — row dropped",
                  flush=True)
