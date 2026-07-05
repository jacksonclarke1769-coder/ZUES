"""FILL TELEMETRY — observation-only fill-quality recorder. NEVER blocks or delays order flow.

Records the resting-entry lifecycle so touch-fill SIMULATIONS can be checked against LIVE reality:
  DECISION -> ORDER_SENT (per leg) -> TOUCH* (price traded at/through the resting limit) ->
  FILL_CONFIRMED (read-back) | ORDER_RESOLVED (cancel/TTL/flatten).

The crown jewels are TOUCH records: a bar that trades at-or-through a resting entry limit WITHOUT a
subsequent FILL_CONFIRMED is exactly what separates an optimistic touch-fill backtest from the truth.

DESIGN CONTRACT (fail OPEN — a broken logger must never reach the order path):
  * Every public method is wrapped in try/except; an exception prints ONE warning line and returns.
  * Producers NEVER block: writes go through a bounded queue.Queue via put_nowait; on queue.Full (or any
    enqueue error) a `dropped` counter is incremented and a DROPS event is emitted when pressure clears.
  * A single daemon writer thread drains the queue to append-only JSONL; writer errors never kill it.
  * The engine's own fail-CLOSED behaviour is untouched — this module only observes.

STORAGE: append-only JSONL, one record per line, daily files out/fill_telemetry/<ET-date>.jsonl.
  Survives restart trivially (append). The in-memory resting-order REGISTRY is not persisted — registry
  loss on restart is acceptable v1 (records already written survive); only touches on still-registered
  orders are missed after a mid-episode restart.

Records NEVER contain the raw account id or webhook URLs. Accounts appear only as
account_tag = sha1(account)[:8]. A defensive _scrub runs on every write (belt and braces).

Book depth unavailable from the TV feed — entry-bar penetration depth (TOUCH records) is the
accepted proxy (vault: Fill Model Audit — 2026-07-05).

SCHEMA v2 (2026-07-05) adds sizing forensics: DECISION carries qty_formula (uncapped size-to-risk
ask), qty_cap (tier/P3 cap before the risk gate), qty_submitted (final sent qty); ORDER_SENT carries
per-leg qty_submitted + qty_submitted_total; FILL_CONFIRMED carries qty_filled, partial_fill, and
time_to_fill_s (± poll_s granularity, noted via time_to_fill_s_caveat).
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 2
BASE_DIR = "out/fill_telemetry"
NY = ZoneInfo("America/New_York")
POLL_S = 20                     # read-back cadence (fill-confirm latency caveat carried in the record)
QUEUE_MAX = 2048
_SENTINEL = object()            # writer-thread stop marker

_SECRET_HINTS = ("url", "token", "apikey", "api_key", "key", "secret", "webhook", "password", "auth")


def account_tag(account) -> str:
    """Stable non-reversible tag for an account. NEVER the raw id (Apex/broker account leakage guard)."""
    return hashlib.sha1(str(account).encode()).hexdigest()[:8]


def _scrub(d: dict) -> dict:
    """Defense in depth: drop secret-ish keys, redact any URL-looking value. We never put secrets in,
    but a record built from a payload could carry one, so scrub before it ever hits disk."""
    out = {}
    for k, v in d.items():
        if any(h in str(k).lower() for h in _SECRET_HINTS):
            continue
        if isinstance(v, str) and ("http://" in v or "https://" in v):
            v = "[redacted]"
        out[k] = v
    return out


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


class FillTelemetry:
    """Async, non-blocking fill-quality recorder + resting-order registry. Observation only."""

    def __init__(self, base_dir: str = BASE_DIR, poll_s: int = POLL_S,
                 telegram=None, maxsize: int = QUEUE_MAX):
        self.base_dir = base_dir
        self.poll_s = poll_s
        self.telegram = telegram              # optional Telegram notifier (fail-safe) for the drops alert
        self._q: queue.Queue = queue.Queue(maxsize=maxsize)
        self._registry: dict[str, dict] = {}  # sid -> resting-order state (own state, NOT the engine's)
        self._reg_lock = threading.Lock()     # EOD flatten resolves from the guardian THREAD; guard the registry
        self.dropped = 0                       # exposed counter (records shed under back-pressure / broken queue)
        self._dropped_logged = 0               # count already surfaced via a DROPS event
        self._drops_alerted = False            # one Telegram drops alert per session (max)
        self._thread = threading.Thread(target=self._writer, name="fill-telem-writer", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------ enqueue (never blocks)

    def _put(self, rec: dict) -> bool:
        try:
            self._q.put_nowait(rec)
            return True
        except queue.Full:
            self.dropped += 1
            return False
        except Exception as e:                                     # noqa: BLE001 — broken queue must fail OPEN
            self.dropped += 1
            print(f"[fill-telem] ⚠ enqueue failed: {e!r} — record dropped", flush=True)
            return False

    def _emit(self, rec: dict) -> None:
        ok = self._put(rec)
        if ok and self.dropped > self._dropped_logged:
            self._flush_drops()

    def _flush_drops(self) -> None:
        n = self.dropped - self._dropped_logged
        drops = self._common("DROPS", None, None, None, None)
        drops.update(dropped=n, dropped_total=self.dropped)
        if not self._put(drops):
            return                                                 # still under pressure — retry next emit
        self._dropped_logged = self.dropped
        if self.telegram is not None and not self._drops_alerted:
            self._drops_alerted = True
            try:
                self.telegram.send(f"⚠ fill-telemetry shed {self.dropped} record(s) under load "
                                   "(observation-only — order flow UNAFFECTED).")
            except Exception:                                      # noqa: BLE001 — alert failure is swallowed
                pass

    # ------------------------------------------------------------------ record helper

    def _common(self, event, strategy, side, signal_ts, acct_tag, sid=None, signal_id_base=None) -> dict:
        utc = datetime.now(timezone.utc)
        row = dict(schema=SCHEMA_VERSION, event=event, ts_utc=utc.isoformat(),
                   et_date=utc.astimezone(NY).date().isoformat(),
                   strategy=strategy, side=side,
                   signal_ts=(None if signal_ts is None else str(signal_ts)),
                   account_tag=acct_tag)
        if sid is not None:
            row["sid"] = sid
        if signal_id_base is not None:
            row["signal_id_base"] = str(signal_id_base)
        return row

    # ------------------------------------------------------------------ public API (all fail-open)

    def on_decision(self, *, strategy, side, signal_ts, account, intended_price, submitted_price,
                    stop, target, qty, d1c=None, decision_wall_ts=None, bar_ts=None,
                    signal_id_base=None, targets=None, qty_formula=None, qty_cap=None,
                    qty_submitted=None) -> None:
        """One record when ZEUS commits to a signal (post-gates, pre-send). Observational.

        Sizing-forensics (schema v2, all optional so old callers keep working):
          qty_formula  — contracts the size-to-risk formula wants UNCAPPED (before any tier/P3 cap).
          qty_cap      — the tier/P3-braked cap on qty BEFORE the prospective risk gate.
          qty_submitted — the final qty actually sent (post risk-gate sizing)."""
        try:
            rec = self._common("DECISION", strategy, side, signal_ts, account_tag(account),
                               signal_id_base=(signal_id_base if signal_id_base is not None else signal_ts))
            rec.update(intended_price=_f(intended_price), submitted_price=_f(submitted_price),
                       stop=_f(stop), target=_f(target), targets=targets, qty=int(qty) if qty is not None else None,
                       qty_formula=(int(qty_formula) if qty_formula is not None else None),
                       qty_cap=(int(qty_cap) if qty_cap is not None else None),
                       qty_submitted=(int(qty_submitted) if qty_submitted is not None
                                      else (int(qty) if qty is not None else None)),
                       d1c=(d1c or {}), decision_wall_ts=str(decision_wall_ts) if decision_wall_ts else None,
                       bar_ts=str(bar_ts) if bar_ts is not None else None)
            self._emit(rec)
        except Exception as e:                                     # noqa: BLE001 — NEVER raise into the order path
            print(f"[fill-telem] ⚠ on_decision error: {e!r}", flush=True)

    def on_order_sent(self, *, strategy, side, signal_ts, account, legs, result=None, bar_ts=None) -> None:
        """One record per Exit#3 leg + register each as a RESTING entry order (registry keyed by sid).
        `legs` = build_entry_exit3 output [{role, qty, target, payload}, ...]; `result` = send_exit3 dict."""
        try:
            tag = account_tag(account)
            res_by_role = {r.get("role"): r for r in (result or {}).get("legs", [])} if result else {}
            legs = legs or []
            qty_submitted_total = 0                                 # sum across legs (sizing forensics)
            for leg in legs:
                p = leg.get("payload", {}) or {}
                lq = p.get("quantity", leg.get("qty"))
                try:
                    if lq is not None:
                        qty_submitted_total += int(lq)
                except (TypeError, ValueError):                    # noqa: BLE001 — malformed qty just skipped
                    pass
            for leg in legs:
                p = leg.get("payload", {}) or {}
                sid = (p.get("extras", {}) or {}).get("signalId") or p.get("signalId")
                level = _f(p.get("limitPrice"))
                lstop = _f((p.get("stopLoss", {}) or {}).get("stopPrice"))
                ltgt = _f((p.get("takeProfit", {}) or {}).get("limitPrice"))
                lqty = p.get("quantity", leg.get("qty"))
                lqty_i = int(lqty) if lqty is not None else None
                rres = res_by_role.get(leg.get("role"), {})
                send_ok = bool(rres.get("sent"))
                rec = self._common("ORDER_SENT", strategy, side, signal_ts, tag, sid=sid)
                rec.update(role=leg.get("role"), limit=level, stop=lstop, target=ltgt,
                           qty=lqty_i, qty_submitted=lqty_i, qty_submitted_total=qty_submitted_total,
                           send_ok=send_ok, bar_ts=str(bar_ts) if bar_ts is not None else None)
                self._emit(rec)
                if sid is not None and level is not None and side in ("long", "short"):
                    with self._reg_lock:                           # register the resting limit for TOUCH scanning
                        self._registry[sid] = dict(sid=sid, role=leg.get("role"), side=side,
                                                   strategy=strategy, signal_ts=str(signal_ts),
                                                   account_tag=tag, level=level, stop=lstop,
                                                   target=ltgt, qty=lqty_i,
                                                   touch_seq=0, sent_wall_ts=time.time())
        except Exception as e:                                     # noqa: BLE001
            print(f"[fill-telem] ⚠ on_order_sent error: {e!r}", flush=True)

    def on_bar(self, ts, o, h, l, c) -> None:
        """Per completed 1m bar: emit a TOUCH for each resting order the bar traded at/through.
        long: bar_low <= level; short: bar_high >= level. filled_yet is always False at record time —
        the fill (if any) is confirmed later by read-back; a TOUCH with no matching FILL_CONFIRMED is
        the signal that a touch-fill sim over-counts."""
        try:
            lo, hi = _f(l), _f(h)
            if lo is None or hi is None:
                return
            with self._reg_lock:
                items = list(self._registry.items())
            for sid, r in items:
                lvl = r["level"]
                touched = (lo <= lvl) if r["side"] == "long" else (hi >= lvl)
                if not touched:
                    continue
                r["touch_seq"] += 1
                rec = self._common("TOUCH", r["strategy"], r["side"], r["signal_ts"],
                                   r["account_tag"], sid=sid)
                rec.update(role=r.get("role"), bar_ts=str(ts), open=_f(o), high=hi, low=lo,
                           close=_f(c), level=lvl, touch_seq=r["touch_seq"], filled_yet=False)
                self._emit(rec)
        except Exception as e:                                     # noqa: BLE001
            print(f"[fill-telem] ⚠ on_bar error: {e!r}", flush=True)

    def on_fill_confirmed(self, *, account, expected=None, broker=None, poll_s=None) -> None:
        """Mirror what read-back learns: broker position now matches expected. Deregisters the episode's
        resting orders and carries the prior TOUCH count so fill-time-vs-touch-time stays derivable.

        Sizing-forensics (schema v2): qty_filled (broker net, explicit alias of `broker`), partial_fill
        (|broker| < |expected|), and time_to_fill_s (confirm wall-ts minus the earliest ORDER_SENT
        wall-ts among the deregistered resting orders) — granularity is the read-back poll cadence,
        carried in time_to_fill_s_caveat so it's never read as an exact fill timestamp."""
        try:
            tag = account_tag(account)
            now_wall = time.time()
            with self._reg_lock:
                matched = [(sid, r) for sid, r in self._registry.items() if r["account_tag"] == tag]
                for sid, _ in matched:
                    self._registry.pop(sid, None)
            touch_total = sum(r["touch_seq"] for _, r in matched)
            head = matched[0][1] if matched else {}
            _sent_list = [r.get("sent_wall_ts") for _, r in matched if r.get("sent_wall_ts") is not None]
            time_to_fill_s = (now_wall - min(_sent_list)) if _sent_list else None
            _poll_s = poll_s if poll_s is not None else self.poll_s
            partial_fill = None
            if broker is not None and expected is not None:
                partial_fill = abs(int(broker)) < abs(int(expected))
            rec = self._common("FILL_CONFIRMED", head.get("strategy"), head.get("side"),
                               head.get("signal_ts"), tag)
            rec.update(expected=(int(expected) if expected is not None else None),
                       broker=(int(broker) if broker is not None else None),
                       qty_filled=(int(broker) if broker is not None else None),
                       partial_fill=partial_fill,
                       time_to_fill_s=(round(time_to_fill_s, 3) if time_to_fill_s is not None else None),
                       time_to_fill_s_caveat=f"±{_poll_s}s poll granularity (not an exact fill timestamp)",
                       prior_touch_count=touch_total, n_resting=len(matched),
                       poll_s=_poll_s)
            self._emit(rec)
        except Exception as e:                                     # noqa: BLE001
            print(f"[fill-telem] ⚠ on_fill_confirmed error: {e!r}", flush=True)

    def on_order_resolved(self, *, account, reason, signal_ts=None) -> None:
        """Terminal state for the resting-order registry: cancel / TTL / on_missing / EOD-or-manual flatten.
        Deregisters the episode's resting orders and emits one ORDER_RESOLVED per (or a bare one if none)."""
        try:
            tag = account_tag(account)
            with self._reg_lock:
                matched = [(sid, r) for sid, r in self._registry.items() if r["account_tag"] == tag]
                for sid, _ in matched:
                    self._registry.pop(sid, None)
            if not matched:
                rec = self._common("ORDER_RESOLVED", None, None, signal_ts, tag)
                rec.update(reason=str(reason), n_resting=0)
                self._emit(rec)
                return
            for sid, r in matched:
                rec = self._common("ORDER_RESOLVED", r.get("strategy"), r.get("side"),
                                   r.get("signal_ts"), tag, sid=sid)
                rec.update(role=r.get("role"), reason=str(reason), touch_seq=r.get("touch_seq"), n_resting=len(matched))
                self._emit(rec)
        except Exception as e:                                     # noqa: BLE001
            print(f"[fill-telem] ⚠ on_order_resolved error: {e!r}", flush=True)

    # ------------------------------------------------------------------ writer thread + lifecycle

    def _write(self, rec: dict) -> None:
        et_date = rec.get("et_date") or datetime.now(timezone.utc).astimezone(NY).date().isoformat()
        os.makedirs(self.base_dir, exist_ok=True)
        path = os.path.join(self.base_dir, f"{et_date}.jsonl")
        with open(path, "a") as f:
            f.write(json.dumps(_scrub(rec), default=str) + "\n")

    def _writer(self) -> None:
        while True:
            try:
                rec = self._q.get()
            except Exception:                                      # noqa: BLE001 — a broken get must not kill the thread
                time.sleep(0.05)
                continue
            try:
                if rec is _SENTINEL:
                    return
                self._write(rec)
            except Exception as e:                                 # noqa: BLE001 — writer errors NEVER kill the process
                print(f"[fill-telem] ⚠ writer error: {e!r} — record dropped", flush=True)
            finally:
                try:
                    self._q.task_done()
                except Exception:                                  # noqa: BLE001
                    pass

    def flush(self, timeout: float = 5.0) -> None:
        """Best-effort, time-bounded drain (tests + clean shutdown). Never blocks unbounded."""
        try:
            end = time.time() + timeout
            while getattr(self._q, "unfinished_tasks", 0) > 0 and time.time() < end:
                time.sleep(0.005)
        except Exception:                                          # noqa: BLE001
            pass

    def close(self, timeout: float = 5.0) -> None:
        self.flush(timeout)
        try:
            self._q.put_nowait(_SENTINEL)
        except Exception:                                          # noqa: BLE001
            pass
        try:
            self._thread.join(timeout)
        except Exception:                                          # noqa: BLE001
            pass
