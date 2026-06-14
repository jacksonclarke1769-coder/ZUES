"""ATHENA II/III automated gate evaluator — FORWARD-ONLY trial clock.

Gates trigger on FORWARD paper decisions only (trial_eligible == True, i.e. signal_time >=
trial_start in out/d1c_shadow/trial_state.json). Backfilled decisions (the 7 November-2025
pipeline-proof rows) appear in diagnostics and can NEVER trigger or satisfy a gate.
Frozen criteria — no tunable thresholds beyond the mandate's.

Usage: python3 athena_gate_report.py   (run any time; evaluates the highest triggered gate)
"""
import json, os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SHADOW = os.path.join(HERE, "out", "d1c_shadow")
DEC = os.path.join(SHADOW, "decisions.csv")
CME = os.path.join(SHADOW, "cme_parity.csv")      # optional rolling file (athena_p4 format)
TRIAL_STATE = os.path.join(SHADOW, "trial_state.json")
GATES = [("GATE 1", 10), ("GATE 2", 20), ("FINAL", 30)]


def _check(name, ok, detail, pending=False):
    return {"name": name, "status": "PEND" if pending else ("PASS" if ok else "FAIL"),
            "detail": detail}


def evaluate(dec, cme=None, production_gate_enabled=False):
    """Pure gate logic. `dec` must carry trial_eligible; only eligible rows count.
    Returns report dict: {gate, n_forward, n_backfilled, verdict, checks, diagnostics}."""
    if "trial_eligible" not in dec.columns:
        dec = dec.assign(trial_eligible=False)     # fail-safe: nothing counts forward
    if "source" in dec.columns:
        # HERMES hard rule: replay rows can NEVER be eligible, even if a merged log
        # carries trial_eligible=True on them (accidental-override protection).
        dec = dec.copy()
        dec.loc[dec.source == "replay", "trial_eligible"] = False
    fwd = dec[dec.trial_eligible == True]          # noqa: E712
    back = dec[dec.trial_eligible != True]         # noqa: E712
    n = len(fwd)
    gate = None
    for g, thr in GATES:
        if n >= thr:
            gate = g
    rep = dict(n_forward=n, n_backfilled=len(back), gate=gate,
               diagnostics=dict(backfilled_agreement=(round(float(back.agree.mean()), 4)
                                                      if len(back) else None),
                                backfilled_fail_open=int(back.fail_open.sum()) if len(back) else 0))
    if production_gate_enabled:
        rep["verdict"] = "FAIL (production gate enabled during paper trial — incident)"
        rep["checks"] = [_check("production gate OFF throughout trial", False, "ENABLED")]
        return rep
    if gate is None:
        nxt = next((f"{g} at {t}" for g, t in GATES if n < t), "—")
        rep["verdict"] = f"no gate triggered ({n}/10 forward; next: {nxt})"
        rep["checks"] = []
        return rep

    checks = [_check("production gate OFF throughout trial", True, "OFF")]
    fr = fwd[fwd.fresh == True]                    # noqa: E712
    agr = fr.agree.mean() if len(fr) else 1.0
    checks.append(_check("decision agreement >=99% (forward, fresh-feed)", agr >= 0.99,
                         f"{agr*100:.2f}% on {len(fr)} decisions"))
    kr = (fwd.decision == "KEEP").mean()
    checks.append(_check("keep-rate 45-80% (forward)", 0.45 <= kr <= 0.80, f"{kr*100:.1f}%"))
    fo = int(fwd.fail_open.sum())
    checks.append(_check("zero fail-open events (forward)", fo == 0, f"{fo} events"))
    st = pd.to_datetime(fwd.signal_time.astype(str).str.replace(r"[+-]\d\d:\d\d$", "", regex=True))
    dups = int(st.duplicated().sum())
    checks.append(_check("journal chain intact", dups == 0, f"{dups} duplicate signal rows"))
    if cme is not None and len(cme):
        big = cme[cme.cme.abs() >= 5]              # outside the +/-5pt chatter zone
        sa = ((big.cfd > 0) == (big.cme > 0)).mean() if len(big) else 1.0
        checks.append(_check("CME drift-sign agreement >=99% (outside chatter zone)",
                             sa >= 0.99, f"{sa*100:.2f}% ({len(big)} stamps)"))
    else:
        checks.append(_check("CME drift-sign agreement >=99%", False,
                             "rolling cme_parity.csv absent", pending=True))
    if gate in ("GATE 2", "FINAL"):
        h1, h2 = fwd.iloc[: n // 2], fwd.iloc[n // 2:]
        k1, k2 = (h1.decision == "KEEP").mean(), (h2.decision == "KEEP").mean()
        checks.append(_check("no monitoring/drift degradation", abs(k1 - k2) <= 0.20,
                             f"forward keep-rate halves {k1*100:.0f}% vs {k2*100:.0f}%"))
        nul = int(fwd.decision.isna().sum())
        checks.append(_check("no silent failures", nul == 0, f"{nul} null decisions"))
    if gate == "FINAL":
        h1, h2 = fwd.iloc[: n // 2], fwd.iloc[n // 2:]
        med1, med2 = h1.drift.abs().median(), h2.drift.abs().median()
        checks.append(_check("drift consistency (no structural degradation)",
                             pd.notna(med1) and pd.notna(med2) and med2 > 0.25 * med1,
                             f"median |drift| halves {med1:.0f} -> {med2:.0f}pt"))
    statuses = [c["status"] for c in checks]
    rep["checks"] = checks
    rep["verdict"] = ("FAIL" if "FAIL" in statuses else
                      ("HOLD" if "PEND" in statuses else
                       ("PROMOTE to PROFILE A v3 CANDIDATE" if gate == "FINAL" else "PASS")))
    return rep


def main():
    if not os.path.exists(DEC):
        print("no shadow decisions yet — forward clock 0/30"); return
    dec = pd.read_csv(DEC)
    cme = pd.read_csv(CME) if os.path.exists(CME) else None
    try:
        with open(TRIAL_STATE) as f:
            stt = json.load(f)
    except (OSError, ValueError):
        stt = {}
    rep = evaluate(dec, cme, bool(stt.get("production_gate_enabled", False)))
    print(f"forward decisions: {rep['n_forward']}/30 · backfilled (diagnostics only): "
          f"{rep['n_backfilled']}")
    if rep["gate"]:
        print(f"\n================ ATHENA {rep['gate']} REPORT (forward-only) ================")
        for c in rep["checks"]:
            print(f"  [{c['status']}] {c['name']}: {c['detail']}")
        out = os.path.join(SHADOW, f"{rep['gate'].replace(' ', '_')}_REPORT.json")
        with open(out, "w") as f:
            json.dump({**rep, "asof": str(pd.Timestamp.now())}, f, indent=2)
        print(f"saved {out}")
    print(f"\nVERDICT: {rep['verdict']}")


if __name__ == "__main__":
    main()
