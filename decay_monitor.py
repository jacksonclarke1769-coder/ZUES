"""DECAY MONITOR — observation-only edge-decay watchdog. Reads LIVE trade records; never writes
an order, never gates or delays one, never touches auto_live/zeus_server/bridge/config.

DESIGN CONTRACT (fail OPEN):
  * Pure decision core (`_pf_and_exp`, `_rolling_pf_series`, `_consecutive_streak`, `_window_health`)
    has no I/O and no state — fully unit-testable.
  * `run()` wraps every I/O / parsing step so ONE internal error never raises out of this module:
    on any unexpected exception it logs a single WARNING line and returns a minimal status dict
    (the CLI still exits 0). Per-source read errors are caught individually and recorded in
    status["errors"] rather than aborting the whole run.
  * Never imports/calls anything in auto_live.py, zeus_server.py, bridge_*.py, or config.

SOURCES (precedence, documented per the task spec):
  1. out/ares/trade_results.csv (trade_results.py) — the DailyGuard ledger. AUTHORITATIVE for
     resolved $ P&L. Columns: date,mode,account,strategy,direction,contracts,pnl,note
     (trade_results.py:12). No numeric R column. We read it the same way
     `trade_results.live_trades()` does (trade_results.py:158-186): mode=="live" and not
     `is_rejected(note)` (trade_results.py:32-38) == an ENTERED, resolved live trade. We keep the
     file's own append order (chronological) rather than that helper's newest-first sort, so it
     lines up with the decision log below for the FIFO join.
  2. logs/live_engine_decisions/<date>.jsonl (ARGUS, decision_log.py) — one row per engine
     decision. Rows with final_action=="live_send" (decision_log.py:92-101 / DecisionLogger.signal)
     carry entry_price/stop_price/side/qty_total/bar_ts — the ledger has none of these. We use them
     to (a) derive R = pnl / (|entry-stop| * $2/pt * qty) per trade, and (b) supply the trade's
     entry time (bar_ts) needed for the 10:00-10:29:59 ET window filter (the ledger has no
     entry-time field at all).
  3. out/fill_telemetry/<date>.jsonl (fill_telemetry.py) — forward-looking / optional, being built
     in parallel. Guarded by an existence check; if the directory or module import is missing this
     source is simply skipped (empty list), never an error. DECISION events (fill_telemetry.py:139-
     153) carry side/stop/qty/submitted or intended price and a hashed `account_tag` (accounts are
     never stored in plaintext there — fill_telemetry.account_tag(), fill_telemetry.py:46-48). We
     only use it as a FALLBACK when a ledger trade has no matching decision-log row, matching on
     the same hash so no account id ever needs to be reversed.
  4. If neither (2) nor (3) yields a match for a given ledger row, that trade still counts toward
     PF/$-expectancy (pnl is always known from the ledger) but is EXCLUDED from R-based stats and
     from the window-health monitor (no entry time -> can't classify it into/out of 10:00-10:29:59).

Precedence in one line: ledger pnl is ground truth; decision-log supplies entry meta; fill-telemetry
is a best-effort fallback for entry meta only, never for pnl (it has no resolved-P&L field).

OUTPUT (v1):
  (a) one structured line per monitor appended to logs/decay_monitor.log
  (b) out/decay_monitor/status.json (schema in the module docstring / task spec); last-state
      (previous alarm_pf / previous window flag) is read back from this same file at the start of
      the next run, so transition detection ("off -> on only") and the sustained-20 streak need no
      separate state file.
  (c) on an alarm/flag TRANSITION (off->on only) send ONE Telegram alert via telegram_notify.py;
      alert failure is swallowed (never raises here, mirrors telegram_notify's own contract).

Run mode: `python3 decay_monitor.py` runs once and exits; `--dry-run` prints instead of writing
status.json/log/Telegram.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import trade_results

NY = ZoneInfo("America/New_York")

DEFAULT_LEDGER_PATH = trade_results.PATH                       # out/ares/trade_results.csv
DEFAULT_DECISION_LOG_DIR = "logs/live_engine_decisions"
DEFAULT_FILL_TELEM_DIR = "out/fill_telemetry"
DEFAULT_STATUS_PATH = "out/decay_monitor/status.json"
DEFAULT_LOG_PATH = "logs/decay_monitor.log"

DOLLARS_PER_POINT = trade_results.DOLLARS_PER_POINT            # $2/pt (MNQ), same constant as the ledger

ROLLING_N = 60                 # rolling-edge trailing window (trades)
SUSTAIN_N = 20                 # consecutive trailing-window evaluations for the PF alarm
PF_ALARM_THRESH = 1.0
WINDOW_ROLLING_N = 40          # rolling expectancy inside the 10:00-10:30 engine window
WINDOW_START_SEC = 10 * 3600            # 10:00:00 ET
WINDOW_END_SEC = 10 * 3600 + 30 * 60     # 10:30:00 ET (exclusive -> selects up to 10:29:59)
WEEKS_KEPT = 8


# ---------------------------------------------------------------------------- time helpers

def _parse_dt(raw):
    """Parse an ISO-ish timestamp string to a tz-aware America/New_York datetime. Naive input is
    assumed UTC (safe default) before conversion. Returns None on anything unparsable."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(NY)


def _in_engine_window(dt_et):
    if dt_et is None:
        return False
    secs = dt_et.hour * 3600 + dt_et.minute * 60 + dt_et.second
    return WINDOW_START_SEC <= secs < WINDOW_END_SEC


def _iso_week_label(dt_et):
    y, w, _ = dt_et.isocalendar()
    return f"{y}-W{w:02d}"


def _now_iso(now=None):
    return (now or datetime.now(timezone.utc)).isoformat()


# ---------------------------------------------------------------------------- source readers (I/O, fail-open per source)

def _read_ledger_live_trades(path, errors):
    """Entered, resolved LIVE trades in file (chronological) order. Same filter as
    trade_results.live_trades() (mode=='live', not is_rejected(note)) but without that helper's
    newest-first re-sort, so row order lines up with the decision log for the FIFO join."""
    rows = []
    try:
        if not os.path.exists(path):
            return rows
        with open(path, newline="") as fh:
            for r in csv.DictReader(fh):
                if (r.get("mode") or "").strip().lower() != "live":
                    continue
                if trade_results.is_rejected(r.get("note")):
                    continue
                try:
                    pnl = float(r.get("pnl") or 0)
                except (TypeError, ValueError):
                    continue
                rows.append({
                    "date": (r.get("date") or "").strip(),
                    "account": (r.get("account") or "").strip(),
                    "strategy": (r.get("strategy") or "").strip().upper(),
                    "direction": (r.get("direction") or "").strip().lower(),
                    "contracts": r.get("contracts"),
                    "pnl": pnl,
                    "note": r.get("note") or "",
                })
    except Exception as e:                                      # noqa: BLE001 — one bad source must not sink the run
        errors.append(f"ledger read error ({path}): {e!r}")
    return rows


def _read_decision_log_signals(log_dir, errors):
    """final_action=='live_send' rows from logs/live_engine_decisions/*.jsonl, oldest-first."""
    rows = []
    try:
        if not os.path.isdir(log_dir):
            return rows
        for fp in sorted(glob.glob(os.path.join(log_dir, "*.jsonl"))):
            try:
                with open(fp) as fh:
                    for ln in fh:
                        ln = ln.strip()
                        if not ln:
                            continue
                        try:
                            r = json.loads(ln)
                        except ValueError:
                            continue
                        if (r.get("final_action") or "") != "live_send":
                            continue
                        dt = _parse_dt(r.get("bar_ts"))
                        if dt is None:
                            continue
                        rows.append({
                            "date": dt.date().isoformat(),
                            "dt_et": dt,
                            "account": (r.get("account") or "").strip(),
                            "profile": (r.get("profile") or "A").strip().upper(),
                            "side": (r.get("side") or "").strip().lower(),
                            "entry": r.get("entry_price"),
                            "stop": r.get("stop_price"),
                            "qty": r.get("qty_total"),
                        })
            except Exception as e:                               # noqa: BLE001
                errors.append(f"decision_log read error ({fp}): {e!r}")
    except Exception as e:                                       # noqa: BLE001
        errors.append(f"decision_log glob error: {e!r}")
    rows.sort(key=lambda x: x["dt_et"])
    return rows


def _read_fill_telemetry_decisions(base_dir, errors):
    """Optional fallback source (forward-looking, may not exist yet). DECISION events only —
    fill_telemetry has no resolved-P&L field, so it can never substitute for the ledger, only
    supply entry meta when the decision log has none for a trade."""
    rows = []
    if not os.path.isdir(base_dir):
        return rows
    try:
        for fp in sorted(glob.glob(os.path.join(base_dir, "*.jsonl"))):
            try:
                with open(fp) as fh:
                    for ln in fh:
                        ln = ln.strip()
                        if not ln:
                            continue
                        try:
                            r = json.loads(ln)
                        except ValueError:
                            continue
                        if r.get("event") != "DECISION":
                            continue
                        dt = _parse_dt(r.get("bar_ts") or r.get("signal_ts") or r.get("ts_utc"))
                        if dt is None:
                            continue
                        rows.append({
                            "date": dt.date().isoformat(),
                            "dt_et": dt,
                            "account_tag": r.get("account_tag"),
                            "profile": (r.get("strategy") or "A" or "").strip().upper(),
                            "side": (r.get("side") or "").strip().lower(),
                            "entry": r.get("submitted_price") if r.get("submitted_price") is not None else r.get("intended_price"),
                            "stop": r.get("stop"),
                            "qty": r.get("qty"),
                        })
            except Exception as e:                               # noqa: BLE001
                errors.append(f"fill_telemetry read error ({fp}): {e!r}")
    except Exception as e:                                       # noqa: BLE001
        errors.append(f"fill_telemetry glob error: {e!r}")
    return rows


def _account_tag_fn():
    """fill_telemetry.account_tag, imported defensively -- absence just disables the fallback."""
    try:
        import fill_telemetry
        return fill_telemetry.account_tag
    except Exception:                                            # noqa: BLE001
        return None


# ---------------------------------------------------------------------------- join

def _join_trades(ledger_rows, decision_rows, ft_rows):
    """Best-effort FIFO join: each ledger trade consumes the next unconsumed decision-log
    live_send row keyed on (date, account, profile==strategy, side==direction); if none exists,
    fall back to a fill_telemetry DECISION row matched on (date, account_tag, profile, side).
    Multiple same-key trades on the same day are paired in file order (documented limitation --
    fine at current live volumes; never affects pnl, only the derived R / entry time)."""
    dec_by_key = defaultdict(list)
    for d in decision_rows:
        dec_by_key[(d["date"], d["account"], d["profile"], d["side"])].append(d)

    tag_fn = _account_tag_fn()
    ft_by_key = defaultdict(list)
    for f in ft_rows:
        ft_by_key[(f["date"], f["account_tag"], f["profile"], f["side"])].append(f)

    joined = []
    for t in ledger_rows:
        key = (t["date"], t["account"], t["strategy"], t["direction"])
        meta = None
        bucket = dec_by_key.get(key)
        if bucket:
            meta = bucket.pop(0)
        elif tag_fn is not None:
            try:
                tag = tag_fn(t["account"])
            except Exception:                                    # noqa: BLE001
                tag = None
            if tag is not None:
                fbucket = ft_by_key.get((t["date"], tag, t["strategy"], t["direction"]))
                if fbucket:
                    meta = fbucket.pop(0)

        r = None
        entry_dt_et = None
        if meta is not None:
            entry_dt_et = meta.get("dt_et")
            entry, stop, qty = meta.get("entry"), meta.get("stop"), meta.get("qty")
            if entry is not None and stop is not None and qty:
                try:
                    denom = abs(float(entry) - float(stop)) * DOLLARS_PER_POINT * float(qty)
                    r = (t["pnl"] / denom) if denom else None
                except (TypeError, ValueError, ZeroDivisionError):
                    r = None
        joined.append({**t, "r": r, "entry_dt_et": entry_dt_et})
    return joined


# ---------------------------------------------------------------------------- pure decision core (no I/O)

def _pf_and_exp(trades):
    """PF ($-based), $/trade and R/trade expectancy for a list of joined trades."""
    n = len(trades)
    wins = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    losses = sum(t["pnl"] for t in trades if t["pnl"] < 0)
    if losses < 0:
        pf = wins / abs(losses)
    elif wins > 0:
        pf = None                     # undefined/"infinite" (no losers yet) -- never < threshold
    else:
        pf = 0.0 if n else None
    exp_usd = round(sum(t["pnl"] for t in trades) / n, 2) if n else None
    rs = [t["r"] for t in trades if t.get("r") is not None]
    exp_r = round(sum(rs) / len(rs), 4) if rs else None
    return {"pf": pf, "exp_usd": exp_usd, "exp_r": exp_r, "n": n}


def _rolling_pf_series(trades, window=ROLLING_N):
    """PF of the trailing `window` trades ending at each trade index, oldest evaluation first.
    Empty when there are fewer than `window` trades (no evaluation is possible yet)."""
    return [_pf_and_exp(trades[i - window + 1:i + 1])["pf"] for i in range(window - 1, len(trades))]


def _consecutive_streak_below(series, thresh=PF_ALARM_THRESH):
    """How many of the MOST RECENT evaluations (from the end backwards) have pf < thresh,
    stopping at the first that doesn't (None/undefined PF never counts)."""
    streak = 0
    for pf in reversed(series):
        if pf is not None and pf < thresh:
            streak += 1
        else:
            break
    return streak


def _rolling_edge(trades):
    """Monitor 1: trailing-60 PF/expectancy + sustained-PF<1.0 streak. Pure, no I/O."""
    n = len(trades)
    tail = trades[-ROLLING_N:]
    stats = _pf_and_exp(tail)
    insufficient = n < ROLLING_N
    series = _rolling_pf_series(trades)
    streak = _consecutive_streak_below(series)
    alarm = (not insufficient) and streak >= SUSTAIN_N
    return {**stats, "insufficient": insufficient, "streak": streak, "alarm": alarm}


def _window_health(trades):
    """Monitor 2: trades entered 10:00-10:29:59 ET only. Pure, no I/O."""
    win_trades = [t for t in trades if _in_engine_window(t.get("entry_dt_et"))]
    n = len(win_trades)

    week_counts = defaultdict(int)
    for t in win_trades:
        week_counts[_iso_week_label(t["entry_dt_et"])] += 1
    weeks_sorted = sorted(week_counts.items())[-WEEKS_KEPT:]

    tail = win_trades[-WINDOW_ROLLING_N:]
    rs = [t["r"] for t in tail if t.get("r") is not None]
    rolling40_exp_r = round(sum(rs) / len(rs), 4) if rs else None
    insufficient = len(tail) < WINDOW_ROLLING_N or rolling40_exp_r is None
    flag = (not insufficient) and rolling40_exp_r < 0
    return {
        "n": n,
        "week_counts": dict(weeks_sorted),
        "rolling40_exp_r": rolling40_exp_r,
        "insufficient": insufficient,
        "flag": flag,
    }


# ---------------------------------------------------------------------------- status persistence

def _load_prev_status(status_path):
    try:
        with open(status_path) as fh:
            return json.load(fh)
    except Exception:                                             # noqa: BLE001 — missing/corrupt -> no prior state
        return {}


def _build_status(now, trades, rolling, window, prev, errors):
    prev_alarm_pf = bool((prev.get("alarm_pf")))
    prev_window_flag = bool(((prev.get("window_1000_1030") or {}).get("flag")))
    alarm_pf = bool(rolling["alarm"])
    window_flag = bool(window["flag"])
    status = {
        "ts": _now_iso(now),
        "n_trades_total": len(trades),
        "rolling60": {"pf": rolling["pf"], "exp_usd": rolling["exp_usd"], "exp_r": rolling["exp_r"],
                      "n": rolling["n"], "insufficient": rolling["insufficient"]},
        "alarm_pf": alarm_pf,
        "alarm_streak": rolling["streak"],
        "window_1000_1030": {"week_counts": window["week_counts"], "rolling40_exp_r": window["rolling40_exp_r"],
                              "n": window["n"], "insufficient": window["insufficient"], "flag": window_flag},
        "errors": list(errors),
        "_transitions": {                                         # not part of the v1 contract's required keys,
            "alarm_pf_on": alarm_pf and not prev_alarm_pf,         # but kept alongside for debuggability
            "window_flag_on": window_flag and not prev_window_flag,
        },
    }
    return status


# ---------------------------------------------------------------------------- alerting (fail-open, swallowed)

def _alert(telegram, text, dry_run):
    if dry_run:
        print(f"[decay_monitor] (dry-run) would alert: {text}")
        return
    try:
        tg = telegram
        if tg is None:
            import telegram_notify
            tg = telegram_notify.Telegram()
        tg.info(text)
    except Exception as e:                                        # noqa: BLE001 — alert failure is swallowed
        print(f"[decay_monitor] alert failed (swallowed): {e!r}", flush=True)


def _log_line(log_path, line, dry_run):
    if dry_run:
        print(line)
        return
    try:
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "a") as fh:
            fh.write(line + "\n")
    except Exception as e:                                        # noqa: BLE001 — logging failure must never raise
        print(f"[decay_monitor] log write failed (swallowed): {e!r}", flush=True)


def _write_status(status_path, status, dry_run):
    if dry_run:
        print(json.dumps(status, indent=2))
        return
    try:
        os.makedirs(os.path.dirname(status_path) or ".", exist_ok=True)
        with open(status_path, "w") as fh:
            json.dump(status, fh, indent=2)
    except Exception as e:                                        # noqa: BLE001
        print(f"[decay_monitor] status write failed (swallowed): {e!r}", flush=True)


# ---------------------------------------------------------------------------- orchestration

def run(*, ledger_path=DEFAULT_LEDGER_PATH, decision_log_dir=DEFAULT_DECISION_LOG_DIR,
        fill_telem_dir=DEFAULT_FILL_TELEM_DIR, status_path=DEFAULT_STATUS_PATH,
        log_path=DEFAULT_LOG_PATH, dry_run=False, now=None, telegram=None):
    """One fail-open evaluation pass. NEVER raises -- any unexpected internal error is caught,
    logged as a single WARNING line, and a minimal (all-clear) status is returned/written so a
    cron invocation still exits 0."""
    try:
        errors = []
        prev = _load_prev_status(status_path)

        ledger_rows = _read_ledger_live_trades(ledger_path, errors)
        decision_rows = _read_decision_log_signals(decision_log_dir, errors)
        ft_rows = _read_fill_telemetry_decisions(fill_telem_dir, errors)
        trades = _join_trades(ledger_rows, decision_rows, ft_rows)

        rolling = _rolling_edge(trades)
        window = _window_health(trades)
        status = _build_status(now, trades, rolling, window, prev, errors)

        _log_line(log_path,
                  f"{status['ts']} ROLLING_EDGE n={rolling['n']} pf={rolling['pf']} "
                  f"exp_usd={rolling['exp_usd']} exp_r={rolling['exp_r']} "
                  f"insufficient={rolling['insufficient']} streak={rolling['streak']} "
                  f"alarm={status['alarm_pf']}",
                  dry_run)
        _log_line(log_path,
                  f"{status['ts']} WINDOW_1000_1030 n={window['n']} "
                  f"rolling40_exp_r={window['rolling40_exp_r']} insufficient={window['insufficient']} "
                  f"flag={window['flag']} weeks={window['week_counts']}",
                  dry_run)

        if status["_transitions"]["alarm_pf_on"]:
            _alert(telegram, f"⚠ decay_monitor: rolling-60 PF < {PF_ALARM_THRESH:.2f} sustained "
                             f"{rolling['streak']} consecutive evaluations "
                             f"(pf={rolling['pf']}, exp_usd={rolling['exp_usd']}).", dry_run)
        if status["_transitions"]["window_flag_on"]:
            _alert(telegram, f"⚠ decay_monitor: 10:00-10:30 ET engine-window rolling-40 expectancy "
                             f"turned negative (exp_r={window['rolling40_exp_r']}).", dry_run)

        _write_status(status_path, status, dry_run)
        return status
    except Exception as e:                                        # noqa: BLE001 — fail OPEN, never raise into a caller
        print(f"[decay_monitor] WARNING: internal error, monitoring skipped this run: {e!r}", flush=True)
        return {"ts": _now_iso(now), "n_trades_total": 0,
                "rolling60": {"pf": None, "exp_usd": None, "exp_r": None, "n": 0, "insufficient": True},
                "alarm_pf": False, "alarm_streak": 0,
                "window_1000_1030": {"week_counts": {}, "rolling40_exp_r": None, "n": 0,
                                      "insufficient": True, "flag": False},
                "errors": [f"fatal: {e!r}"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Observation-only decay monitor (never gates orders).")
    ap.add_argument("--dry-run", action="store_true", help="print instead of writing/alerting")
    a = ap.parse_args(argv)
    run(dry_run=a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
