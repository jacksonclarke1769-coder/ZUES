"""MONDAY AUDIT — one command to audit a paper session end to end:
  * ARGUS session verdict (engine ran / no setup / blocked / inconclusive)
  * A vs B decision counts from the decision log
  * A vs B P&L from the calendar ledger (realised vs hypothetical)
  * writes reports/monday-session-<date>.md
Run after the paper session:  python3 tools/monday_audit.py --date today [--parity]
"""
import argparse
import csv
import json
import os
import subprocess
import sys

_TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_TOOLS))             # bot dir (decision_log, trade_results)
sys.path.insert(0, _TOOLS)                              # tools dir (the auditor)
import decision_log as DL
import trade_results as TR
import audit_live_engine_session as AUD
audit, write_report, _date = AUD.audit, AUD.write_report, AUD._date


def _decision_split(date, log_dir=DL.LOG_DIR):
    path = os.path.join(log_dir, f"{date}.jsonl")
    counts = {"A": {}, "B": {}}
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            prof = "B" if (r.get("profile") == "B") else "A"
            fa = r.get("final_action", "?")
            counts[prof][fa] = counts[prof].get(fa, 0) + 1
    return counts


def _pnl_split(date, path=TR.PATH):
    out = {"A": {"realised": 0.0, "hypothetical": 0.0, "n": 0},
           "B": {"realised": 0.0, "hypothetical": 0.0, "n": 0}}
    if os.path.exists(path):
        for r in csv.DictReader(open(path)):
            if (r.get("date") or "").strip() != date:
                continue
            strat = "B" if (r.get("strategy") or "").strip().upper() == "B" else "A"
            try:
                pnl = float(r.get("pnl") or 0)
            except ValueError:
                continue
            bucket = "realised" if TR.is_realised(r.get("note")) else "hypothetical"
            out[strat][bucket] += pnl
            out[strat]["n"] += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="today")
    ap.add_argument("--session", default="ny-am")
    ap.add_argument("--parity", action="store_true", help="also re-run exit3 + B parity (slow)")
    a = ap.parse_args()
    date = _date(a.date)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    arg = audit(date, a.session)
    dec = _decision_split(date)
    pnl = _pnl_split(date)
    write_report(arg)                                   # ARGUS detail report

    parity = {}
    if a.parity:
        for name, tool in [("exit3", "tools/check_exit3_parity.py"),
                           ("profile_b", "tools/check_profile_b_parity.py")]:
            r = subprocess.run([sys.executable, tool], capture_output=True, text=True,
                               cwd=here, timeout=300)
            parity[name] = "PASS" if r.returncode == 0 else "FAIL"

    # ---- console ----
    print(f"\n================ MONDAY SESSION AUDIT — {date} ({a.session}) ================")
    print(f"ARGUS VERDICT: {arg['verdict']}")
    print(f"  decision rows: {arg['rows']}  ·  no_signal: {arg['counts']['no_signal']}  ·  "
          f"data RED/YELLOW: {arg['feed']['red']}/{arg['feed']['yellow']}")
    for prof in ("A", "B"):
        d = dec[prof]; p = pnl[prof]
        sig = d.get("paper_signal", 0) + d.get("live_send", 0)
        blk = sum(d.get(k, 0) for k in ("d1c_blocked", "ares_blocked", "data_blocked", "exitlock_blocked"))
        print(f"  Profile {prof}: signals {sig} · blocked {blk} · trades {p['n']} · "
              f"realised ${p['realised']:+,.0f} · hypothetical ${p['hypothetical']:+,.0f}")
    if parity:
        print("  parity: " + " · ".join(f"{k}={v}" for k, v in parity.items()))
    for s in arg["suspicions"]:
        print(f"  ! {s}")

    # ---- session report ----
    rep = os.path.join(here, "reports", f"monday-session-{date}.md")
    with open(rep, "w") as fh:
        fh.write(f"# Monday Paper Session — {date} ({a.session})\n\n")
        fh.write(f"**ARGUS verdict: {arg['verdict']}**\n\n")
        fh.write(f"- decision rows: {arg['rows']} · no_signal: {arg['counts']['no_signal']} · "
                 f"feed RED/YELLOW: {arg['feed']['red']}/{arg['feed']['yellow']}\n")
        fh.write("\n| Profile | Signals | Blocked | Trades | Realised $ | Hypothetical $ |\n")
        fh.write("|---|--:|--:|--:|--:|--:|\n")
        for prof in ("A", "B"):
            d = dec[prof]; p = pnl[prof]
            sig = d.get("paper_signal", 0) + d.get("live_send", 0)
            blk = sum(d.get(k, 0) for k in ("d1c_blocked", "ares_blocked", "data_blocked", "exitlock_blocked"))
            fh.write(f"| {prof} | {sig} | {blk} | {p['n']} | {p['realised']:+,.0f} | {p['hypothetical']:+,.0f} |\n")
        if parity:
            fh.write("\nparity: " + ", ".join(f"{k}={v}" for k, v in parity.items()) + "\n")
        if arg["suspicions"]:
            fh.write("\n## Integrity notes\n" + "\n".join(f"- {s}" for s in arg["suspicions"]) + "\n")
        fh.write("\n_All paper P&L is HYPOTHETICAL (modeled fills, not broker-confirmed). "
                 "Live remains blocked; exit-model-approved.flag not created._\n")
    print(f"\nreport: {rep}")
    bad = any(k in arg["verdict"] for k in ("INCONCLUSIVE", "FAIL"))
    print("\n" + ("MONDAY AUDIT: review needed — " + arg["verdict"] if bad
                  else "MONDAY AUDIT: clean — " + arg["verdict"]))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
