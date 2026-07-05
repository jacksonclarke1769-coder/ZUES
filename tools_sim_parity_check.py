"""SIM-PARITY CHECK (2026-07-05) — fold two LIVE-ONLY sizing behaviors into the eval sim.

RESEARCH ONLY. Does not touch the certified day-level harness (`tools_account_size_research.py`)
or any live code path. This is a NEW, separate trade-level replay that adds intra-run STATE
(balance / trailing-threshold / P3 latch) so a single eval-start's sizing can react to its own
trajectory — something the day-level harness deliberately does not model (every trade there is
sized off a single fixed $1,200 budget, see `tools_account_size_research.build_events` lines 43-53).

Two deployed, LIVE-ONLY behaviors are folded in (deployed machine: cap 10, DEC-20260705-1102):

  1. PROSPECTIVE CUSHION GATE (`auto_live.py` `_risk_gate`, lines 163-211, esp. 195-210):
     per-trade dollar budget = min($1,200, 0.9 * cushion - open_risk), where cushion is the live
     distance-to-floor (`mffu_state.py` `MFFUConfig`/`MFFUState.distance_to_floor`, lines 127-129:
     `equity - floor`, `floor = min(eod_hwm - trail_dd, lock_at)` lines 123-125). One A position at
     a time (auto_live.py docstring line 168, "one A position at a time") => open_risk = 0 at every
     entry, so budget = min(1200, max(0, cushion) * 0.9). q = min(cap, budget // risk1); q < 1 blocks
     the trade outright (auto_live.py lines 204-208, `_rq < a_size` size-down / `q < 1` block).
     In this replay, "cushion" = running INTRADAY balance (prior EOD-settled balance + today's
     already-closed trades' realized P&L, since equity == balance whenever no position is open)
     minus the CURRENT trailing threshold `thr` (the same ratcheting/lock variable computed in
     `tools_account_size_research.eval_run` lines 81-101 — algebraically identical to
     `mffu_state.floor`, ratcheted only at EOD). dd_allowance (denominator for P3, see below) =
     spec["trail"], matching the live `cushion_fn`'s `runner.bot.mffu.cfg.trail_dd` (auto_live.py
     line 985).

  2. P3 CUSHION BRAKE (`p3_brake.py`, whole file — the exact rule replicated):
     - trigger (p3_brake.py lines 17-34, `P3Brake.update`): brake ON when cushion < 0.40 * dd_allowance,
       OFF when cushion >= 0.60 * dd_allowance, HOLD (hysteresis) in between; fail-safe ON if
       cushion/dd_allowance missing or dd_allowance <= 0.
     - size (p3_brake.py lines 36-41, `P3Brake.size`): braked -> (max(a_base // 2, 1), 0); else
       (a_base, b_base). We only use the A side (b_base = 0 throughout; this repo's A-only stream).
     - order of application in `auto_live.py` (lines 317-322): P3 sizes DOWN the tier's base A qty
       first (`spec["am"]`, here `cap`), THEN the cushion gate (_risk_gate) sizes down further from
       that already-P3-reduced qty. This replay applies the two gates in the same order.
     MAPPING NOTE (live-only state with no sim equivalent): the live P3Brake is a long-lived,
     restart-safe object (snapshot/restore, p3_brake.py lines 46-54) that carries its latch across
     the account's entire life. Here every eval START is a hypothetical, independent fresh account
     attempt, so we instantiate a FRESH `P3Brake(braked=False)` per start (matches the class default,
     p3_brake.py line 11) rather than trying to carry a latch across unrelated hypothetical starts.
     This is a deliberate simplification, documented rather than hidden.

CANARY (mandatory, see `main()`): with both behaviors DISABLED (plain `min(cap, 1200 // risk1)`
every trade, no state dependency), the trade-level replay must reproduce the certified cap-10 row
EXACTLY: pass 47.8 / bust 15.9 / expire 36.2 / median 16d (n=395 starts) — the same 50K@$1,200
config as `tools_account_size_research.py` but with `MAX_A_QTY` overridden to 10 (the deployed
cap) instead of the research file's default ceiling of 40.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_profileA as E
import config
import run_d1c_real as RD
import apex_eval_eod_databento as DB
from tools_1m_truth_recert import M1Map
from tools_phase3_config_sweep import a_streams_d1c
from p3_brake import P3Brake

EXPIRE_DAYS = 30
CAP = 10                       # deployed A-tier size ceiling (DEC-20260705-1102)
BUDGET_FIXED = 1_200.0         # config_defaults.A_RISK_BUDGET_USD
CUSHION_FRAC = 0.9             # config_defaults.OPEN_RISK_CUSHION_FRAC

# 50K spec (matches the deployed machine's stop/DLL: stop=550 == ARES 50K daily stop, dll=1000 ==
# Apex 50K DLL) — same numbers as tools_account_size_research.SPECS["50K"].
SPEC_50K = dict(start=50_000.0, trail=2_500.0, target=3_000.0, dll=1_000.0, stop=550.0, max_qty=60)

CANARY_EXPECT = dict(pass_pct=47.8, bust_pct=15.9, exp_pct=36.2, med_days=16, n=395)


def load_rows():
    """Load the certified A stream exactly as tools_account_size_research.main() does."""
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    rows = a_streams_d1c(eng._features(), mp, d1_tz)["exit3"][0]
    rows = sorted(rows, key=lambda t: t["ts"])
    return rows


def group_by_day(rows):
    days_trades = {}
    for t in rows:
        d = pd.Timestamp(t["ts"]).normalize()
        days_trades.setdefault(d, []).append(t)
    unique_days = sorted(days_trades)
    return days_trades, unique_days


def simulate_start(days_trades, unique_days, s0_idx, spec, cap, use_cushion, use_p3):
    """Trade-level replay of one eval start, with intra-run state (balance / trailing threshold /
    P3 latch). Day-level bookkeeping (trough construction, $550 realized daily stop, $1,000 DLL
    clamp, EOD ratchet/lock, bust/pass/expire checks) mirrors
    tools_account_size_research.day_rows/eval_run exactly (lines 56-101)."""
    sb, tr, tg = spec["start"], spec["trail"], spec["target"]
    stop, dll = spec["stop"], spec["dll"]
    thr, bal, peak, locked = sb - tr, sb, sb, False
    t0 = unique_days[s0_idx]
    p3 = P3Brake() if use_p3 else None          # fresh per-start latch (mapping note in module docstring)

    for di in range(s0_idx, len(unique_days)):
        d = unique_days[di]
        if (d - t0).days > EXPIRE_DAYS:
            return "EXPIRE", EXPIRE_DAYS

        day_real, day_trough, day_stopped = 0.0, 0.0, False
        for t in days_trades[d]:
            if day_stopped:
                break
            risk1 = t["risk_usd"]
            intraday_bal = bal + day_real                # EOD-settled bal + today's closed trades
            cushion = intraday_bal - thr                  # == mffu distance_to_floor (equity - floor)

            if use_p3:
                p3.update(cushion, tr)                    # dd_allowance = spec["trail"]
                a_base, _ = p3.size(cap, 0)
            else:
                a_base = cap

            if use_cushion:
                budget = min(BUDGET_FIXED, max(0.0, cushion) * CUSHION_FRAC)
            else:
                budget = BUDGET_FIXED

            q = min(a_base, int(budget // risk1))
            if q < 1:
                continue                                   # blocked at entry: no size fits

            pnl = t["R"] * risk1 * q
            mae = min(0.0, t["mae_r"]) * risk1 * q
            day_trough = min(day_trough, day_real + mae)
            day_real += pnl
            if day_real <= -stop:
                day_stopped = True

        if day_trough <= -dll:
            real, trough = -dll, -dll
        else:
            real, trough = day_real, day_trough

        if bal + min(0.0, trough) <= thr:
            return "BUST", (d - t0).days
        bal += real
        peak = max(peak, bal)
        if not locked:
            thr = max(thr, peak - tr)
            if peak - tr >= sb + 100.0:
                thr = sb + 100.0; locked = True
        if bal <= thr:
            return "BUST", (d - t0).days
        if bal >= sb + tg:
            return "PASS", (d - t0).days
    return "INCOMPLETE", None


def run_config(days_trades, unique_days, spec, cap, use_cushion, use_p3):
    last_day = unique_days[-1]
    starts = [i for i, d in enumerate(unique_days) if (last_day - d).days > EXPIRE_DAYS]
    res = [simulate_start(days_trades, unique_days, s, spec, cap, use_cushion, use_p3) for s in starts]
    n = len(res)
    p = 100 * sum(1 for r in res if r[0] == "PASS") / n
    b = 100 * sum(1 for r in res if r[0] == "BUST") / n
    x = 100 * sum(1 for r in res if r[0] == "EXPIRE") / n
    md = int(np.median([r[1] for r in res if r[0] == "PASS"]) or 0) if p else 0
    # E-ish: a lightweight expectancy proxy (NOT a full funded-phase replay like
    # tools_account_size_research.funded_paid) — first ladder rung * pass-rate, minus ~1.5mo fees.
    e_ish = (p / 100) * 1_500.0 - 45.0 * 1.5
    return dict(pass_pct=round(p, 1), bust_pct=round(b, 1), exp_pct=round(x, 1),
                med_days=md, n=n, e_ish=round(e_ish))


def main():
    print("loading frames + locked A stream (exit3 + D1c, 1m truth)…", flush=True)
    rows = load_rows()
    days_trades, unique_days = group_by_day(rows)

    canary = run_config(days_trades, unique_days, SPEC_50K, CAP, use_cushion=False, use_p3=False)
    print("\nCANARY (both gates disabled, must match certified cap-10 row EXACTLY):")
    print(f"  got:      pass={canary['pass_pct']} bust={canary['bust_pct']} "
          f"exp={canary['exp_pct']} med={canary['med_days']}d n={canary['n']}")
    print(f"  expected: pass={CANARY_EXPECT['pass_pct']} bust={CANARY_EXPECT['bust_pct']} "
          f"exp={CANARY_EXPECT['exp_pct']} med={CANARY_EXPECT['med_days']}d n={CANARY_EXPECT['n']}")
    mismatch = (canary["pass_pct"] != CANARY_EXPECT["pass_pct"] or
                canary["bust_pct"] != CANARY_EXPECT["bust_pct"] or
                canary["exp_pct"] != CANARY_EXPECT["exp_pct"] or
                canary["med_days"] != CANARY_EXPECT["med_days"] or
                canary["n"] != CANARY_EXPECT["n"])
    if mismatch:
        print("\n[CANARY MISMATCH] STOPPING — trade-level replay does not reproduce the certified "
              "day-level row. Do not trust the parity configs below.", flush=True)
        return
    print("[canary OK]\n", flush=True)

    configs = [
        ("baseline (disabled)", False, False),
        ("cushion gate only", True, False),
        ("P3 brake only", False, True),
        ("both", True, True),
    ]
    hdr = f"{'config':>22}{'pass':>7}{'bust':>7}{'exp':>6}{'med':>5}{'n':>6}{'E-ish':>9}"
    print(hdr); print("-" * len(hdr))
    rows_out = {}
    for label, uc, up in configs:
        r = run_config(days_trades, unique_days, SPEC_50K, CAP, use_cushion=uc, use_p3=up)
        rows_out[label] = r
        print(f"{label:>22}{r['pass_pct']:>6.1f}%{r['bust_pct']:>6.1f}%{r['exp_pct']:>5.1f}%"
              f"{r['med_days']:>5}{r['n']:>6}{r['e_ish']:>9,.0f}")
        if label != "baseline (disabled)" and r["pass_pct"] > canary["pass_pct"]:
            print(f"  [WARNING] {label} INCREASED pass rate vs baseline — size reducers should "
                  f"never do this. Treat as a bug, do not trust this row.", flush=True)
    print("-" * len(hdr))
    return rows_out


if __name__ == "__main__":
    main()
