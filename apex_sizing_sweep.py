"""APEX sizing sweep — find the spray-EV-optimal A/B/mm sizing for the 50K eval.

Uses the validated apex_eval_deployed harness (engine reproduces apex_sim exactly). Generates the
A/B/mm trade streams ONCE at size=1, then rescales linearly per config (pnl/mfe/mae ∝ contracts;
the $550 daily stop is a FIXED $ and does NOT scale) and re-runs the Apex trailing eval (+30-day clock).

Spray EV is NOT just PASS% — a fast bust resets cheaply, so the decision metrics are:
  * funded/slot/90d  = PASS% × (90 / median cycle-days)   [throughput: funded accounts per eval-slot per quarter]
  * $/funded         = (1/PASS%) × eval_cost              [expected eval spend to produce one funded account]
Ranked by throughput. eval_cost is parameterised (Apex 50K reset ≈ $35 on sale).
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import apex_eval_deployed as H
import funded_rules as FR

EVAL_COST = 35.0          # Apex 50K eval/reset on sale (parameterise to taste)
SPEC = FR.APEX_ACCOUNTS["50K"]

# A:B:mm grid — proportional scale-downs of the deployed 10/5/6, plus momentum-off variants
CONFIGS = [
    (14, 7, 8), (12, 6, 7),
    (10, 5, 6),                         # DEPLOYED
    (8, 4, 5), (6, 3, 4), (6, 3, 0),
    (5, 3, 3), (4, 2, 2), (4, 2, 0),
    (3, 2, 2), (3, 2, 0), (2, 1, 0),
]


def base_streams():
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1          # generate at unit size -> exact linear rescale
    df5 = H.load_bars()
    print(f"  bars {df5.index.min().date()} -> {df5.index.max().date()} ({len(df5):,})", flush=True)
    A, B, M = H.a_events(df5), H.b_events(df5), H.m_events(df5)
    print(f"  unit streams: A={len(A)} B={len(B)} mm-days={len(M)}", flush=True)
    return A + B + M


def evaluate(base, a, b, m):
    sc = {"A": a, "B": b, "M": m}
    ev = [dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*sc[e["src"]],
               mfe=e["mfe"]*sc[e["src"]], mae=e["mae"]*sc[e["src"]]) for e in base if sc[e["src"]] > 0]
    ev = H.apply_daily_stop(ev)                  # fixed $550 stop
    # rolling start: first event of each trading day, leaving 30d room to resolve
    seen, starts = set(), []
    for i, e in enumerate(ev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d not in seen:
            seen.add(d); starts.append(i)
    last = pd.Timestamp(ev[-1]["ts"])
    starts = [i for i in starts if (last - pd.Timestamp(ev[i]["ts"])).days > H.EXPIRE_DAYS]
    out = [H.eval_from(ev, s, SPEC) for s in starts]      # (result, days, ntr)
    n = len(out)
    npass = sum(1 for o in out if o[0] == "PASS")
    nbust = sum(1 for o in out if o[0] == "BUST")
    nexp = sum(1 for o in out if o[0] == "EXPIRE")
    pass_days = [o[1] for o in out if o[0] == "PASS"]
    cyc_days = [o[1] for o in out if o[0] in ("PASS", "BUST", "EXPIRE") and o[1] is not None]
    p = npass / n
    med_pass = float(np.median(pass_days)) if pass_days else float("nan")
    med_cyc = float(np.median(cyc_days)) if cyc_days else float("nan")
    throughput = p * (90.0 / med_cyc) if med_cyc and med_cyc == med_cyc and med_cyc > 0 else 0.0
    cost_per_funded = (EVAL_COST / p) if p > 0 else float("inf")
    return dict(a=a, b=b, m=m, mnq=a+b+m, n=n,
                pass_pct=100*p, bust_pct=100*nbust/n, exp_pct=100*nexp/n,
                med_pass=med_pass, med_cyc=med_cyc,
                throughput=throughput, cost_per_funded=cost_per_funded)


def main():
    print("generating unit streams (one-time)…", flush=True)
    base = base_streams()
    rows = [evaluate(base, a, b, m) for (a, b, m) in CONFIGS]
    rows.sort(key=lambda r: r["throughput"], reverse=True)

    print(f"\n  eval_cost=${EVAL_COST:.0f}  ·  Apex 50K $2.5k-trail/$3k-target  ·  $550 daily stop  ·  30-day clock")
    print(f"  {'A/B/mm':>10}{'MNQ':>5}{'PASS%':>7}{'BUST%':>7}{'EXP%':>6}{'medPass':>8}{'medCyc':>8}"
          f"{'funded/slot/90d':>16}{'$/funded':>10}")
    print("  " + "-" * 84)
    for r in rows:
        tag = f"{r['a']}/{r['b']}/{r['m']}"
        star = "  <- DEPLOYED" if (r['a'], r['b'], r['m']) == (10, 5, 6) else ""
        print(f"  {tag:>10}{r['mnq']:>5}{r['pass_pct']:>7.1f}{r['bust_pct']:>7.1f}{r['exp_pct']:>6.1f}"
              f"{r['med_pass']:>8.0f}{r['med_cyc']:>8.0f}{r['throughput']:>16.2f}{r['cost_per_funded']:>10.0f}{star}")
    best = rows[0]
    print(f"\n  best throughput: A{best['a']}/B{best['b']}/mm{best['m']} "
          f"({best['mnq']} MNQ) — {best['pass_pct']:.0f}% pass, {best['throughput']:.2f} funded/slot/90d, "
          f"${best['cost_per_funded']:.0f}/funded")
    print("  [note] per-trade give-back (slightly optimistic on leg-overlap); Dukascopy proxy; "
          "throughput assumes instant reset after bust.")


if __name__ == "__main__":
    main()
