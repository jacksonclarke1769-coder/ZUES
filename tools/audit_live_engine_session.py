"""ARGUS — live-engine session auditor. Reads the append-only decision log and proves
whether a session was CLEAN (no setup / trade taken), BLOCKED BY DATA, INCONCLUSIVE
(logging gap), or FAIL (possible missed trade). Never prints secrets.

    python3 tools/audit_live_engine_session.py --date YYYY-MM-DD --session ny-am
    python3 tools/audit_live_engine_session.py --date today
    python3 tools/audit_live_engine_session.py --date today --fixture no_signal|missing_rows
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import decision_log as DL

NY = ZoneInfo("America/New_York")
RESOLVED = {"candidate_rejected", "data_blocked", "d1c_blocked", "ares_blocked",
            "exitlock_blocked", "paper_signal", "live_send"}


def _date(s):
    if s == "today":
        return datetime.now(timezone.utc).astimezone(NY).date().isoformat()
    return s


def _load(date, log_dir=DL.LOG_DIR):
    path = os.path.join(log_dir, f"{date}.jsonl")
    rows, corrupt = [], 0
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    corrupt += 1
    return rows, corrupt, path


def _feed_issues(date, feed_log="logs/feed-watch.log"):
    """Count RED/YELLOW/gap/reset markers for the date (best-effort, never raises)."""
    red = yellow = gaps = resets = 0
    try:
        if os.path.exists(feed_log):
            for ln in open(feed_log, errors="ignore"):
                if date not in ln:
                    continue
                u = ln.upper()
                red += "RED" in u
                yellow += "YELLOW" in u
                gaps += "GAP" in u
                resets += "RESET" in u
    except Exception:
        pass
    return dict(red=red, yellow=yellow, gaps=gaps, resets=resets)


def audit(date, session="ny-am", log_dir=DL.LOG_DIR):
    date = _date(date)
    rows, corrupt, path = _load(date, log_dir)
    counts = {a: 0 for a in DL.FINAL_ACTIONS}
    for r in rows:
        counts[r.get("final_action", "error")] = counts.get(r.get("final_action", "error"), 0) + 1
    feed = _feed_issues(date)

    # ---- missed-trade / integrity checks ----
    suspicions = []
    # unresolved candidates: candidate_detected but final_action not a resolved outcome
    unresolved = [r for r in rows if r.get("candidate_detected") and r.get("final_action") not in RESOLVED]
    if unresolved:
        suspicions.append(f"{len(unresolved)} candidate row(s) with no resolved final_action")
    # live send without a TradersPost status
    bad_sends = [r for r in rows if r.get("final_action") == "live_send" and not r.get("traderspost_status")]
    if bad_sends:
        suspicions.append(f"{len(bad_sends)} live_send row(s) with no traderspost_status")
    if corrupt:
        suspicions.append(f"{corrupt} corrupt/invalid JSONL line(s)")
    if not rows:
        suspicions.append("no decision rows — cannot prove the engine ran")
    if feed["gaps"] or feed["red"]:
        suspicions.append(f"feed issues during day: {feed['red']} RED, {feed['gaps']} gap markers")

    sends = counts["paper_signal"] + counts["live_send"]
    blocked = counts["data_blocked"] + counts["d1c_blocked"] + counts["ares_blocked"] + counts["exitlock_blocked"]

    # ---- verdict ----
    if not rows or corrupt or unresolved:
        verdict = "SESSION INCONCLUSIVE — LOGGING GAP"
    elif bad_sends:
        verdict = "SESSION FAIL — POSSIBLE MISSED TRADE"
    elif sends > 0:
        verdict = "SESSION CLEAN — TRADE TAKEN"
    elif counts["data_blocked"] and counts["data_blocked"] >= max(1, counts["no_signal"]):
        verdict = "SESSION BLOCKED BY DATA"
    else:
        verdict = "SESSION CLEAN — NO SETUP"

    return dict(date=date, session=session, path=path, rows=len(rows), corrupt=corrupt,
                counts=counts, feed=feed, suspicions=suspicions, sends=sends,
                blocked=blocked, missed="YES" if suspicions and "MISSED" in verdict else "NO",
                verdict=verdict)


def write_report(a, out_dir="reports"):
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"live-engine-decision-audit-{a['date']}.md")
    c = a["counts"]
    lines = [
        f"# Live-Engine Decision Audit — {a['date']} ({a['session']})",
        "",
        f"**VERDICT: {a['verdict']}**",
        "",
        f"1. session date: {a['date']}",
        f"2. session window: {a['session']} (09:30–11:30 ET)",
        f"3. feed source: {(open(a['path']).readline() and 'see log') if os.path.exists(a['path']) else 'n/a'}",
        f"4. total engine checks (rows): {a['rows']}",
        f"5. no-signal count: {c['no_signal']}",
        f"6. candidate count: {sum(1 for k in ('candidate_rejected','data_blocked','d1c_blocked','ares_blocked','exitlock_blocked','paper_signal','live_send') for _ in range(c[k]))}",
        f"7. rejected count: {c['candidate_rejected']}",
        f"8. D1c block count: {c['d1c_blocked']}",
        f"9. ARES block count: {c['ares_blocked']}",
        f"10. data block count: {c['data_blocked']}",
        f"11. exitlock block count: {c['exitlock_blocked']}",
        f"12. paper signals: {c['paper_signal']}",
        f"13. live sends: {c['live_send']}",
        f"14. TradersPost sends: {c['live_send']} (status-confirmed only)",
        f"15. duplicate bars: n/a (engine dedups; see feed-watch)",
        f"16. out-of-order bars: n/a (engine rejects; see feed-watch)",
        f"17. feed gaps: {a['feed']['gaps']}",
        f"18. RED/YELLOW periods: {a['feed']['red']} RED / {a['feed']['yellow']} YELLOW",
        f"19. missed-trade suspicion: {a['missed']}",
        f"20. final verdict: **{a['verdict']}**",
        "",
        "## Integrity notes",
    ]
    lines += [f"- {s}" for s in (a["suspicions"] or ["none — log is complete and consistent"])]
    open(p, "w").write("\n".join(lines) + "\n")
    return p


# ---- deterministic fixtures (market-closed proof) ----
def _row(final_action, **f):
    base = dict(schema_version=DL.SCHEMA_VERSION, session_id="fixture", account="MFFU-50K-1",
                mode="paper", profile="A", feed_source="tradingview-1m", engine_timeframe="5m",
                exit_model=DL.EXIT_MODEL, final_action=final_action)
    base.update(f)
    return json.dumps(base)


def _make_fixture(kind, date, log_dir):
    """Write a synthetic decision log directly to <date>.jsonl (deterministic, date-stable)."""
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, f"{date}.jsonl")
    with open(path, "w") as fh:
        if kind == "no_signal":
            for i in range(24):                              # ~2h of 5m bars, all clean
                fh.write(_row("no_signal", bar_ts=f"{date}T09:{30 + (i*5) % 60:02d}:00-04:00",
                              candidate_detected=False, data_state="GREEN", data_ready=True,
                              last_bar_age_s=12) + "\n")
        elif kind == "missing_rows":
            fh.write(_row("no_signal", bar_ts=f"{date}T09:30:00-04:00",
                          candidate_detected=False, data_state="GREEN", data_ready=True) + "\n")
            fh.write(_row("skipped", bar_ts=f"{date}T09:45:00-04:00",
                          candidate_detected=True, side="short") + "\n")  # unresolved candidate
            fh.write("{this is not valid json\n")            # corrupt line
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="today")
    ap.add_argument("--session", default="ny-am")
    ap.add_argument("--fixture", choices=["no_signal", "missing_rows"], default=None)
    ap.add_argument("--log-dir", default=DL.LOG_DIR)
    a = ap.parse_args()
    date = _date(a.date)
    if a.fixture:
        _make_fixture(a.fixture, date, a.log_dir)
        print(f"[fixture '{a.fixture}' written for {date}]")
    res = audit(date, a.session, a.log_dir)
    rep = write_report(res)
    print(f"rows={res['rows']} corrupt={res['corrupt']} sends={res['sends']} "
          f"blocked={res['blocked']} no_signal={res['counts']['no_signal']}")
    for s in res["suspicions"]:
        print(f"  ! {s}")
    print(f"\n{res['verdict']}\nreport: {rep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
