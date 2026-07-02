"""ACCOUNT-SIZE RESEARCH (2026-07-02) — locked ZEUS machine across Apex 50K/100K/150K EOD evals.

RESEARCH ONLY. Locked machine unchanged: A-only Exit#3 + D1c, 1m-truth fills, size-to-risk.
Rules modeled (2026 4.0 EOD, help-center-derived — VERIFY vs live contract):
  50K : target $3k  trail $2.5k  DLL $1.0k  lock start+$100  ladder ~ $13.0k lifetime (known)
  100K: target $6k  trail $3.0k  DLL $1.5k  lock start+$100  ladder ~ $17.0k lifetime (ESTIMATE)
  150K: target $9k  trail $4.0k  DLL $2.0k  lock start+$100  ladder ~ $21.5k lifetime (endpoints
        $2.5k->$5k documented; intermediate steps estimated monotone)
ARES self-imposed daily stop scales with the DLL at the 50K ratio (0.55x): 550 / 825 / 1100.
Risk budgets per operator grid; funded E[paid] approximated as pass% x ladder-capped funded sim at
40% of the eval budget (the certified 50K funded fraction A4/A10).
"""
import os, sys, warnings, json; warnings.filterwarnings("ignore")
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

NY = "America/New_York"
EXPIRE_DAYS = 30
SPECS = {
    "50K":  dict(start=50_000.0,  trail=2_500.0, target=3_000.0, dll=1_000.0, stop=550.0,
                 ladder=[1_500, 1_500, 2_000, 2_500, 2_500, 3_000], fee_mo=45.0,
                 budgets=[800, 950, 1_200, 1_600, 2_000], max_qty=60),
    "100K": dict(start=100_000.0, trail=3_000.0, target=6_000.0, dll=1_500.0, stop=825.0,
                 ladder=[2_000, 2_000, 2_500, 3_000, 3_500, 4_000], fee_mo=90.0,
                 budgets=[1_200, 1_450, 1_600, 2_400, 3_200], max_qty=80),
    "150K": dict(start=150_000.0, trail=4_000.0, target=9_000.0, dll=2_000.0, stop=1_100.0,
                 ladder=[2_500, 3_000, 3_500, 4_000, 4_500, 5_000], fee_mo=130.0,
                 budgets=[1_600, 1_900, 2_000, 3_200, 4_800], max_qty=120),
}
MAX_A_QTY = 40          # research ceiling on A size regardless of budget (fill-quality realism)


def build_events(rows, budget, max_qty):
    ev = []
    for t in rows:
        risk1 = t["risk_usd"]
        q = min(max_qty, MAX_A_QTY, int(budget // risk1))
        if q < 1:
            continue
        ev.append(dict(ts=pd.Timestamp(t["ts"]), pnl=t["R"] * risk1 * q,
                       mae=min(0.0, t["mae_r"]) * risk1 * q))
    ev.sort(key=lambda e: e["ts"])
    return ev


def day_rows(ev, stop, dll):
    """Collapse to (day, realized, marked-trough) with the ARES stop + Apex DLL applied."""
    days = {}
    for e in ev:
        d = e["ts"].normalize()
        r = days.setdefault(d, dict(real=0.0, trough=0.0, stopped=False))
        if r["stopped"]:
            continue
        r["trough"] = min(r["trough"], r["real"] + e["mae"])
        r["real"] += e["pnl"]
        if r["real"] <= -stop:
            r["stopped"] = True
    out = []
    for d in sorted(days):
        r = days[d]
        # HONEST DLL semantics: the day is FLATTENED the moment the marked open loss touches -DLL —
        # including trades that would have recovered. (A clamp on realized-only is optimistic.)
        if r["trough"] <= -dll:
            real, trough = -dll, -dll
        else:
            real, trough = r["real"], r["trough"]
        out.append((d, real, trough))
    return out


def eval_run(days, s0, spec):
    sb, tr, tg = spec["start"], spec["trail"], spec["target"]
    thr, bal, peak, locked = sb - tr, sb, sb, False
    t0 = days[s0][0]
    for i in range(s0, len(days)):
        d, real, trough = days[i]
        if (d - t0).days > EXPIRE_DAYS:
            return "EXPIRE", EXPIRE_DAYS
        if bal + min(0.0, trough) <= thr:
            return "BUST", (d - t0).days
        bal += real
        peak = max(peak, bal)                # EOD ratchet (close-set)
        if not locked:
            thr = max(thr, peak - tr)
            if peak - tr >= sb + 100.0:
                thr = sb + 100.0; locked = True
        if bal <= thr:
            return "BUST", (d - t0).days
        if bal >= sb + tg:
            return "PASS", (d - t0).days
    return "INCOMPLETE", None


def funded_paid(days, spec):
    """Ladder-capped funded life from every ~quarterly start; mean lifetime paid."""
    sb, tr = spec["start"], spec["trail"]
    ladder = spec["ladder"]
    min_req, floor = sb + tr + 100.0, sb + tr - 400.0
    paids = []
    starts = [i for i, (d, _, _) in enumerate(days) if (days[-1][0] - d).days >= 365][::63]
    for s0 in starts:
        thr, bal, peak, locked = sb - tr, sb, sb, False
        li, paid = 0, 0.0
        since = dict(profit=0.0, maxd=0.0, qual=0)
        last = days[s0][0]
        for i in range(s0, len(days)):
            d, real, trough = days[i]
            if bal + min(0.0, trough) <= thr:
                break
            bal += real
            since["profit"] += real; since["maxd"] = max(since["maxd"], real)
            if real >= 250.0:
                since["qual"] += 1
            peak = max(peak, bal)
            if not locked:
                thr = max(thr, peak - tr)
                if peak - tr >= sb + 100.0:
                    thr = sb + 100.0; locked = True
            if bal <= thr:
                break
            if (d - last).days >= 30:
                last = d
                if (bal >= min_req and since["qual"] >= 5 and since["profit"] > 0
                        and since["maxd"] < 0.5 * since["profit"]):
                    amt = min(ladder[li], bal - floor)
                    if amt > 0:
                        bal -= amt; paid += amt; li += 1
                        since = dict(profit=0.0, maxd=0.0, qual=0)
                        if li >= len(ladder):
                            break
        paids.append(paid)
    return float(np.mean(paids)) if paids else 0.0


def main():
    print("loading frames + locked A stream (exit3 + D1c, 1m truth)…", flush=True)
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    rows = a_streams_d1c(eng._features(), mp, d1_tz)["exit3"][0]

    out = {}
    hdr = (f"{'acct':>5}{'budget':>8}{'pass':>7}{'bust':>7}{'exp':>6}{'med':>5}{'p<24':>7}{'p>=24':>7}"
           f"{'worst-day':>10}{'E[fund$]':>9}{'E[$/attempt]':>13}")
    print("\n" + hdr); print("-" * len(hdr))
    for name, spec in SPECS.items():
        for budget in spec["budgets"]:
            ev = build_events(rows, budget, spec["max_qty"])
            days = day_rows(ev, spec["stop"], spec["dll"])
            starts, seen = [], set()
            for i, (d, _, _) in enumerate(days):
                if d not in seen and (days[-1][0] - d).days > EXPIRE_DAYS:
                    seen.add(d); starts.append(i)
            res = [eval_run(days, s, spec) for s in starts]
            n = len(res)
            p = 100 * sum(1 for r in res if r[0] == "PASS") / n
            b = 100 * sum(1 for r in res if r[0] == "BUST") / n
            x = 100 * sum(1 for r in res if r[0] == "EXPIRE") / n
            md = int(np.median([r[1] for r in res if r[0] == "PASS"]) or 0) if p else 0
            cut = pd.Timestamp("2024-01-01", tz=NY)
            pe = [r for r, s in zip(res, starts) if days[s][0] < cut]
            pl = [r for r, s in zip(res, starts) if days[s][0] >= cut]
            pe_p = 100 * sum(1 for r in pe if r[0] == "PASS") / max(1, len(pe))
            pl_p = 100 * sum(1 for r in pl if r[0] == "PASS") / max(1, len(pl))
            worst = min(r for _, r, _ in days)
            # funded at 40% of eval budget (certified 50K fraction)
            fdays = day_rows(build_events(rows, 0.4 * budget, spec["max_qty"]),
                             spec["stop"], spec["dll"])
            fp = funded_paid(fdays, spec)
            e_attempt = (p / 100) * fp - spec["fee_mo"] * 1.5      # ~1.5 mo of eval fees/attempt
            out[f"{name}@{budget}"] = dict(pass_pct=round(p, 1), bust_pct=round(b, 1),
                                           exp_pct=round(x, 1), med_days=md,
                                           pass_early=round(pe_p, 1), pass_late=round(pl_p, 1),
                                           worst_day=round(worst), e_funded=round(fp),
                                           e_per_attempt=round(e_attempt))
            print(f"{name:>5}{budget:>8,}{p:>6.1f}%{b:>6.1f}%{x:>5.1f}%{md:>5}{pe_p:>6.1f}%"
                  f"{pl_p:>6.1f}%{worst:>10,.0f}{fp:>9,.0f}{e_attempt:>13,.0f}", flush=True)
        print("-" * len(hdr))

    with open("reports/account_size_research_2026-07-02.json", "w") as f:
        json.dump(dict(rules="Apex 4.0 EOD (help-center-derived; 100K/150K ladders ESTIMATED) — "
                             "VERIFY vs contract", machine="locked v2026.07.02 A-only stream",
                       results=out), f, indent=1)
    print("[saved] reports/account_size_research_2026-07-02.json", flush=True)


if __name__ == "__main__":
    main()
