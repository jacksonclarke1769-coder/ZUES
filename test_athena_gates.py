"""ATHENA III forward-only assertions: backfilled decisions can never trigger or satisfy
a gate; gates fire only at 10/20/30 FORWARD decisions; production-gate-on = instant FAIL."""
import numpy as np
import pandas as pd
from athena_gate_report import evaluate


def mk(n, eligible, keep_frac=0.62, agree=True, fail_open=0, start="2026-06-15 10:00"):
    """Synthesize a decisions frame."""
    ts = pd.date_range(start, periods=n, freq="1D")
    # interleave keeps evenly so synthetic halves are stationary (period-5 pattern)
    keep = (np.arange(n) % 5) < int(round(5 * keep_frac))
    rows = pd.DataFrame(dict(
        signal_time=ts.astype(str), direction=["long"] * n,
        drift=np.where(keep, 50.0, -50.0),
        decision=np.where(keep, "KEEP", "SUSPEND"),
        reference=np.where(keep, "KEEP", "SUSPEND"),
        agree=[agree] * n, fresh=[True] * n,
        fail_open=[False] * n, trial_eligible=[eligible] * n))
    for i in range(fail_open):
        rows.loc[i, "fail_open"] = True
    return rows


BACKFILL = mk(7, eligible=False, start="2025-11-03 10:00")


def test_backfilled_seven_do_not_trigger_gate1():
    rep = evaluate(BACKFILL)
    assert rep["gate"] is None
    assert rep["n_forward"] == 0 and rep["n_backfilled"] == 7
    assert "no gate triggered (0/10" in rep["verdict"]


def test_gate1_fires_only_at_10_forward():
    assert evaluate(mk(9, True))["gate"] is None
    rep = evaluate(mk(10, True))
    assert rep["gate"] == "GATE 1" and rep["verdict"] in ("PASS", "HOLD")


def test_gate2_and_final_thresholds():
    assert evaluate(mk(19, True))["gate"] == "GATE 1"
    assert evaluate(mk(20, True))["gate"] == "GATE 2"
    assert evaluate(mk(29, True))["gate"] == "GATE 2"
    assert evaluate(mk(30, True))["gate"] == "FINAL"


def test_mixed_backfilled_plus_forward_counts_forward_only():
    mixed = pd.concat([BACKFILL, mk(9, True)], ignore_index=True)
    rep = evaluate(mixed)
    assert rep["n_forward"] == 9 and rep["n_backfilled"] == 7
    assert rep["gate"] is None                      # 16 total rows but only 9 forward
    rep2 = evaluate(pd.concat([BACKFILL, mk(10, True)], ignore_index=True))
    assert rep2["gate"] == "GATE 1"


def test_perfect_backfill_cannot_promote():
    """Even 30 perfect backfilled rows must not reach FINAL."""
    rep = evaluate(mk(30, eligible=False, start="2025-10-01 10:00"))
    assert rep["gate"] is None
    assert "PROMOTE" not in rep["verdict"]


def test_final_gate_with_pending_cme_holds_not_promotes():
    rep = evaluate(mk(30, True), cme=None)
    assert rep["gate"] == "FINAL"
    assert rep["verdict"] == "HOLD"                 # CME parity pending blocks promotion


def test_final_gate_promotes_with_full_evidence():
    cme = pd.DataFrame(dict(cfd=[20.0, -30.0, 45.0] * 40, cme=[22.0, -28.0, 44.0] * 40))
    rep = evaluate(mk(30, True), cme=cme)
    assert rep["verdict"] == "PROMOTE to PROFILE A v3 CANDIDATE"


def test_fail_open_forces_fail():
    rep = evaluate(mk(10, True, fail_open=1))
    assert rep["verdict"] == "FAIL"


def test_keep_rate_out_of_band_fails_gate():
    rep = evaluate(mk(10, True, keep_frac=0.95))
    assert rep["verdict"] == "FAIL"


def test_production_gate_enabled_is_immediate_fail():
    rep = evaluate(mk(30, True), production_gate_enabled=True)
    assert rep["verdict"].startswith("FAIL")
    assert "incident" in rep["verdict"]


def test_missing_trial_eligible_column_fails_safe():
    d = mk(30, True).drop(columns=["trial_eligible"])
    rep = evaluate(d)
    assert rep["gate"] is None and rep["n_forward"] == 0


def mk_replay(n, eligible_flag=False, start="2025-01-05 10:00"):
    """Replay rows: source=replay. eligible_flag simulates an accidental override."""
    d = mk(n, eligible=eligible_flag, start=start)
    d["source"] = "replay"
    return d


def test_30_perfect_replay_rows_do_not_trigger_gate1():
    rep = evaluate(mk_replay(30))
    assert rep["gate"] is None and rep["n_forward"] == 0


def test_100_perfect_replay_rows_do_not_trigger_final():
    rep = evaluate(mk_replay(100))
    assert rep["gate"] is None
    assert "PROMOTE" not in rep["verdict"]


def test_replay_eligibility_override_is_neutralized():
    """Even if replay rows somehow carry trial_eligible=True, source=replay wins."""
    rep = evaluate(mk_replay(30, eligible_flag=True))
    assert rep["gate"] is None and rep["n_forward"] == 0


def test_replay_plus_backfill_cannot_promote():
    mixed = pd.concat([BACKFILL, mk_replay(100, eligible_flag=True)], ignore_index=True)
    rep = evaluate(mixed)
    assert rep["gate"] is None and rep["n_forward"] == 0
    assert "PROMOTE" not in rep["verdict"]


def test_only_forward_eligible_rows_count_in_full_mix():
    mixed = pd.concat([BACKFILL, mk_replay(50, eligible_flag=True),
                       mk(10, True)], ignore_index=True)
    mixed.loc[mixed.source.isna(), "source"] = "forward_paper"
    rep = evaluate(mixed)
    assert rep["n_forward"] == 10
    assert rep["gate"] == "GATE 1"


def test_production_gate_on_during_replay_is_incident_fail():
    rep = evaluate(mk_replay(30), production_gate_enabled=True)
    assert rep["verdict"].startswith("FAIL") and "incident" in rep["verdict"]
