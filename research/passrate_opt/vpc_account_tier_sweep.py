"""ZEUS passrate_opt — VPC eval PASS-RATE across ACCOUNT-SIZE TIERS x FIRM x SIZING (honest sim).

Extends 01_vpc_firm_sizing to the ACCOUNT TIER dimension (25K/50K/100K/150K).

READ-ONLY on bot strategy code. REUSES THE EXACT 50K HARNESS BY IMPORT:
  * research/passrate_opt/vpc_firm_sizing.py  -> run_cell / eval_one / per_year_passes /
    bounded_starts / all_starts  (the certified per-firm eval rule + rolling-start machinery)
  * that module in turn imports the certified VPC events (fork_b) + day-collapse
    (tools_account_size_research.day_rows).
The ONLY thing this file adds is TIER PARAMETRIZATION: it sets the module globals START & TARGET
per tier and passes tier-scaled dd/dll in the firm dict. NOTHING in the eval logic is re-implemented
— eval_one/run_cell are called verbatim from vpc_firm_sizing so the 50K canary reproduces exactly.

The Apex '$100 lock buffer' (peak-dd >= START+100 => threshold locks at START+100) is account-size
independent in the real Apex rule and in the reused eval_one — it scales correctly across tiers.

ARES self-imposed daily realized stop = $550, held IDENTICAL across firms AND tiers (certified
machinery). NOTE: a fixed $550 daily stop is proportionally HARSHER on a 25K (vs its ~$1,500 trail)
than on a 150K — flagged in the report, not silently rescaled.

FIRM $ VERIFICATION (see reports/cross_firm/00_firm_rules_2026.md, trading-team root):
  * Apex tiers (25K 1500/1500 · 50K 3000/2500 · 100K 6000/3000 · 150K 9000/5000) = Apex's
    PUBLISHED per-tier target/trail. Best-verified set here (still re-confirm before commitment).
  * 50K row for EVERY firm is held IDENTICAL to the certified 01 sweep (canary anchor).
  * ALL non-Apex, non-50K cells use STANDARD SCALING (target=6% of size; trail scaled) and are
    UNVERIFIED — flagged per firm. ETF_Static $ are the least trustworthy (static archetype).
  * Topstep has NO 25K tier in reality — its 25K row is an EXTRAPOLATION, double-flagged.
"""
import os, sys, json, hashlib, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import vpc_firm_sizing as M          # THE 50K harness — reused verbatim (run_cell/eval_one/etc.)
F = M.F                              # certified VPC builders + Databento loader
NO_DLL = M.NO_DLL

# ---- TIER BASE (account size + profit target) ---------------------------------------------------
# target = standard 6%-of-size prop target (25K 1500 / 50K 3000 / 100K 6000 / 150K 9000).
TIERS = {
    "25K":  dict(start=25_000.0,  target=1_500.0),
    "50K":  dict(start=50_000.0,  target=3_000.0),
    "100K": dict(start=100_000.0, target=6_000.0),
    "150K": dict(start=150_000.0, target=9_000.0),
}

# ---- FIRM CONSTANTS (tier-invariant: archetype, consistency %, min-days, time limit) -------------
FIRM_CONST = {
    "Apex50K":      dict(dd_type="trail",  expire_days=30,   consistency=None, min_days=1),
    "Topstep50K":   dict(dd_type="trail",  expire_days=None, consistency=0.50, min_days=5),
    "MFFU_Builder": dict(dd_type="trail",  expire_days=None, consistency=None, min_days=2),
    "Bulenox_EOD":  dict(dd_type="trail",  expire_days=None, consistency=None, min_days=1),
    "ETF_Static":   dict(dd_type="static", expire_days=None, consistency=None, min_days=5),
}

# ---- PER-(firm,tier) DRAWDOWN $ -----------------------------------------------------------------
# 50K column == certified 01 sweep EXACTLY (canary anchor). Apex column = Apex PUBLISHED tiers.
# All other non-50K cells = STANDARD SCALING, UNVERIFIED.
DD = {
    "Apex50K":      {"25K": 1500.0, "50K": 2500.0, "100K": 3000.0, "150K": 5000.0},  # Apex published
    "Topstep50K":   {"25K": 1500.0, "50K": 2000.0, "100K": 3000.0, "150K": 4500.0},  # 25K = EXTRAPOLATED (no real tier)
    "MFFU_Builder": {"25K": 1500.0, "50K": 2000.0, "100K": 3000.0, "150K": 4500.0},  # scaled UNVERIFIED
    "Bulenox_EOD":  {"25K": 1500.0, "50K": 2500.0, "100K": 3000.0, "150K": 4500.0},  # scaled UNVERIFIED
    "ETF_Static":   {"25K": 1500.0, "50K": 2000.0, "100K": 3000.0, "150K": 4500.0},  # scaled, MOST UNVERIFIED
}
# ---- PER-(firm,tier) DAILY-LOSS-LIMIT $ (soft flatten) ------------------------------------------
DLL = {
    "Apex50K":      {"25K": 500.0,  "50K": 1000.0, "100K": 2000.0, "150K": 3000.0},  # scaled from 50K=1000
    "Bulenox_EOD":  {"25K": 550.0,  "50K": 1100.0, "100K": 2200.0, "150K": 3300.0},  # scaled from 50K=1100
    "Topstep50K":   {t: NO_DLL for t in TIERS},
    "MFFU_Builder": {t: NO_DLL for t in TIERS},
    "ETF_Static":   {t: NO_DLL for t in TIERS},
}

# firms whose non-50K / all rows are unverified-by-scaling (for report flagging)
VERIFIED_APEX = {"Apex50K"}   # Apex $ published; still re-confirm

BUDGETS = M.BUDGETS           # [600, 900, 1200, 1500, 2000]
CAPS = M.CAPS                 # [3, 4, 6, 8, 10]


def firm_dict(fname, tier):
    d = dict(FIRM_CONST[fname])
    d["dd"] = DD[fname][tier]
    d["dll"] = DLL[fname][tier]
    d["_name"] = fname
    return d


def set_tier(tier):
    """Parametrize the reused module's globals for this tier. eval_one reads M.START / M.TARGET."""
    M.START = TIERS[tier]["start"]
    M.TARGET = TIERS[tier]["target"]


def md5_of(obj):
    return hashlib.md5(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def main():
    print("loading Databento 5m + VPC trades (reused fork_b machinery, tier-invariant events)…", flush=True)
    df5 = F.databento_5m_rth()
    feats = F.v.features(df5); feats = feats[feats.date >= F.START_DATE]
    vpc = F.vpc_trades_rich(feats)
    M.DATA_END = df5.index.max()
    print(f"  VPC trades={len(vpc)} net={vpc.pnl_pts.sum():.0f}pt  data_end={M.DATA_END.date()}", flush=True)

    # ---- CANARY: 50K Apex $600/cap3 must reproduce 12.6/3.6/83.8/19d ----
    set_tier("50K")
    can = M.run_cell(vpc, firm_dict("Apex50K", "50K"), 600, 3)
    ok = (can["pass_pct"], can["bust_pct"], can["exp_pct"], can["med_days"]) == (12.6, 3.6, 83.8, 19)
    print(f"[CANARY] 50K Apex $600/cap3 -> {can['pass_pct']}/{can['bust_pct']}/{can['exp_pct']} "
          f"med {can['med_days']}d  (target 12.6/3.6/83.8/19)  {'PASS' if ok else 'FAIL'}", flush=True)

    firms = list(FIRM_CONST.keys())
    tiers = list(TIERS.keys())

    grid = {}   # grid[tier][firm] = [cells]
    print("\n=== FULL TIER x FIRM x SIZING SWEEP ===", flush=True)
    for tier in tiers:
        set_tier(tier)
        grid[tier] = {}
        for fname in firms:
            fd = firm_dict(fname, tier)
            cells = []
            for b in BUDGETS:
                for c in CAPS:
                    r = M.run_cell(vpc, fd, b, c)
                    if r:
                        r["tier"] = tier
                        cells.append(r)
            grid[tier][fname] = cells
            # native metric: raw pass% for time-limited (Apex), resolved% for unlimited
            timed = FIRM_CONST[fname]["expire_days"] is not None
            key = (lambda r: r["pass_pct"]) if timed else (lambda r: (r["pass_resolved_pct"] or 0))
            best = max(cells, key=key)
            bv = best["pass_pct"] if timed else best["pass_resolved_pct"]
            print(f"  [{tier:4s}] {fname:13s} best {'pass' if timed else 'passRes'}={bv}%  "
                  f"@ ${best['budget']}/cap{best['cap']}  bust {best['bust_pct']}%  "
                  f"med {best['med_days']}d  cen {best['censored_pct']}%", flush=True)

    # ---- RANKINGS across all (tier,firm,sizing) cells ----
    flat = []
    for tier in tiers:
        for fname in firms:
            for r in grid[tier][fname]:
                timed = FIRM_CONST[fname]["expire_days"] is not None
                native_pass = r["pass_pct"] if timed else (r["pass_resolved_pct"] or 0)
                flat.append(dict(tier=tier, firm=fname, budget=r["budget"], cap=r["cap"],
                                 pass_pct=r["pass_pct"], native_pass=native_pass,
                                 bust_pct=r["bust_pct"], cen=r["censored_pct"],
                                 med=r["med_days"], p25=r["p25_days"], p75=r["p75_days"],
                                 pass_res=r["pass_resolved_pct"], timed=timed))
    # rank A: max pass% (native)
    rankA = sorted(flat, key=lambda r: -r["native_pass"])[:15]
    # rank B: pass-per-unit-time = pass≥bust AND fastest median (safety: require pass>=bust, med<30)
    quick = [r for r in flat if r["pass_pct"] >= r["bust_pct"] and r["med"] is not None and r["med"] < 30]
    rankB = sorted(quick, key=lambda r: (r["med"], -r["native_pass"]))[:15]
    # rank C: pure speed-normalized pass rate (native_pass / median days) among pass>=bust
    ppd = [dict(r, ppd=round(r["native_pass"] / r["med"], 3))
           for r in flat if r["pass_pct"] >= r["bust_pct"] and r["med"]]
    rankC = sorted(ppd, key=lambda r: -r["ppd"])[:15]

    print("\n=== RANK A: MAX pass% (native) ===", flush=True)
    for r in rankA[:8]:
        print(f"  {r['tier']:4s} {r['firm']:13s} ${r['budget']}/cap{r['cap']}  "
              f"pass {r['native_pass']}% bust {r['bust_pct']}% med {r['med']}d", flush=True)
    print("=== RANK B: pass>=bust AND median<30d (fast+safe) ===", flush=True)
    for r in rankB[:8]:
        print(f"  {r['tier']:4s} {r['firm']:13s} ${r['budget']}/cap{r['cap']}  "
              f"pass {r['native_pass']}% bust {r['bust_pct']}% med {r['med']}d", flush=True)

    # ---- PER-YEAR concentration on top cells (rank A top-3 + rank B top-2) ----
    print("\n=== PER-YEAR concentration (top cells) ===", flush=True)
    peryear = {}
    top_for_year = []
    seen = set()
    for r in (rankA[:3] + rankB[:2]):
        k = (r["tier"], r["firm"], r["budget"], r["cap"])
        if k not in seen:
            seen.add(k); top_for_year.append(r)
    for r in top_for_year:
        set_tier(r["tier"])
        py = M.per_year_passes(vpc, firm_dict(r["firm"], r["tier"]), r["budget"], r["cap"])
        tot = sum(v["passes"] for v in py.values())
        share = {y: (round(100 * v["passes"] / tot, 1) if tot else 0) for y, v in py.items()}
        flag = any(s > 50 for s in share.values())
        key = f"{r['tier']}|{r['firm']}|${r['budget']}/cap{r['cap']}"
        peryear[key] = dict(by_year={int(y): v for y, v in py.items()}, share=share, concentrated=flag)
        print(f"  {key:34s} passes={ {y: v['passes'] for y,v in py.items()} } "
              f"share%={share} {'<<CONCENTRATION>>' if flag else ''}", flush=True)

    out = dict(
        meta=dict(
            vendor="Databento NQ 1m->5m RTH",
            window=f"{F.START_DATE.date()}->{M.DATA_END.date()}",
            engine="REUSED vpc_firm_sizing.run_cell/eval_one/per_year_passes (import) — tier only "
                   "parametrizes START/TARGET globals + scaled dd/dll; NO eval logic re-implemented",
            ares_daily_stop=M.ARES_STOP,
            tiers={t: dict(v) for t, v in TIERS.items()},
            firm_const=FIRM_CONST, DD=DD,
            DLL={f: {t: ("NO_DLL" if x >= 1e11 else x) for t, x in d.items()} for f, d in DLL.items()},
            verification="Apex $ = Apex published per-tier (best-verified, re-confirm). 50K row of "
                         "every firm = certified 01 anchor. ALL other non-Apex cells = standard "
                         "scaling, UNVERIFIED; ETF_Static $ least trustworthy; Topstep 25K is an "
                         "EXTRAPOLATION (no real 25K tier). ARES $550 stop fixed across tiers "
                         "(proportionally harsher on 25K).",
        ),
        canary=dict(cell="50K Apex $600/cap3", got=[can["pass_pct"], can["bust_pct"], can["exp_pct"], can["med_days"]],
                    target=[12.6, 3.6, 83.8, 19], reproduced=ok),
        grid=grid, rankA=rankA, rankB=rankB, rankC=rankC, per_year_top=peryear,
    )
    out["md5"] = md5_of({k: v for k, v in out.items() if k != "meta"})
    with open(os.path.join(REPO, "reports", "passrate_opt", "03_vpc_account_tier_sweep.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n[md5] {out['md5']}")
    print("[saved] reports/passrate_opt/03_vpc_account_tier_sweep.json")
    return out


if __name__ == "__main__":
    main()
