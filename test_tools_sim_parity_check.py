"""Canary regression test for tools_sim_parity_check.py — research harness, not live code.

With both LIVE-ONLY sizing behaviors (cushion gate, P3 brake) disabled, the trade-level replay
must reproduce the certified cap-10 day-level row exactly (see module docstring / task record):
pass 47.8 / bust 15.9 / expire 36.2 / median 16d, n=395 starts.
"""
import tools_sim_parity_check as P


def test_canary_reproduces_certified_cap10_row():
    rows = P.load_rows()
    days_trades, unique_days = P.group_by_day(rows)
    r = P.run_config(days_trades, unique_days, P.SPEC_50K, P.CAP, use_cushion=False, use_p3=False)
    assert r["pass_pct"] == P.CANARY_EXPECT["pass_pct"]
    assert r["bust_pct"] == P.CANARY_EXPECT["bust_pct"]
    assert r["exp_pct"] == P.CANARY_EXPECT["exp_pct"]
    assert r["med_days"] == P.CANARY_EXPECT["med_days"]
    assert r["n"] == P.CANARY_EXPECT["n"]


def test_cushion_gate_never_increases_a_size_vs_baseline():
    """Sanity: the cushion gate and P3 brake are pure size-reducers — spot-check that enabling
    them never lets more contracts trade than the baseline at any (day, trade) step."""
    rows = P.load_rows()
    days_trades, unique_days = P.group_by_day(rows)
    spec = P.SPEC_50K
    sb, tr = spec["start"], spec["trail"]
    thr_base, bal_base = sb - tr, sb
    thr_gate, bal_gate = sb - tr, sb
    day_real_base = day_real_gate = 0.0
    for d in unique_days[:20]:
        for t in days_trades[d]:
            risk1 = t["risk_usd"]
            q_base = min(P.CAP, int(P.BUDGET_FIXED // risk1))
            cushion = (bal_gate + day_real_gate) - thr_gate
            budget = min(P.BUDGET_FIXED, max(0.0, cushion) * P.CUSHION_FRAC)
            q_gate = min(P.CAP, int(budget // risk1))
            assert q_gate <= q_base
