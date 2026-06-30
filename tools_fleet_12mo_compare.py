"""12-MONTH FLEET ECONOMICS — live bot (A+B partial) vs single@1R (A+B), real Databento.
Rules: buy 1 eval/week; a passed eval -> funded (A4/B2/mm2 -> A6/B3/mm6 + P3 brake); ramp to 20 funded,
then rebuy only when a funded is BLOWN or RETIRED. A funded account RETIRES after 6 payouts -> start a
new eval. Fees: eval cost + activation, both counted. Reports money made, evals bought/blown, funded
made/blown/retired, payouts, net take-home — for BOTH exit models side by side."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import exit_model_validate as V
import apex_eval_deployed as H
import apex_eval_eod_databento as DB
import strategy_engine_profileA as E
import config
T = pd.Timestamp

SB, TRAIL, LOCK_EOD, FLOOR, EXPIRE, DAILY_STOP = 50_000.0, 2_500.0, 52_600.0, 50_100.0, 30, -550.0
SAFETY, CF, CL, NC, MINP = 52_100.0, 2_000.0, 4_000.0, 5, 500.0
DD_ALLOW, BR_ON, BR_OFF = 2_000.0, 0.40, 0.60
EVAL_COST, ACTIVATION, MAX_ACCTS, PAYOUT_CAP = 45.0, 130.0, 20, 6
EVAL = {"A": 10, "B": 5, "M": 6}; PRE = {"A": 4, "B": 2, "M": 2}; POST = {"A": 6, "B": 3, "M": 6}


def run_eval(ev, start):
    thr = SB - TRAIL; bal = SB; peak = SB; t0 = T(ev[start]["ts"]); cur = None; dreal = 0.0
    for k in range(start, len(ev)):
        e = ev[k]; ts = T(e["ts"]); day = ts.normalize()
        if day != cur:
            if cur is not None and (ts - t0).days > EXPIRE: return "BLOWN", k
            peak = max(peak, bal); thr = max(thr, peak - TRAIL); cur = day; dreal = 0.0
        if dreal <= DAILY_STOP: continue
        s = EVAL[e["src"]]
        if bal + min(0.0, e["mae"]) * s <= thr: return "BLOWN", k
        bal += e["pnl"] * s; dreal += e["pnl"] * s
        if bal >= SB + 3000: return "PASS", k
    return "INCOMPLETE", len(ev) - 1


def run_funded(ev, start):
    """Returns (status, free_idx, payout$, n_payouts, first_pay_idx). status in busted/retired/active."""
    thr = SB - TRAIL; bal = SB; peak = SB; locked = False; braked = False
    payout = 0.0; npay = 0; first_pay = None; cur = None; dreal = 0.0; cmonth = None
    for k in range(start, len(ev)):
        e = ev[k]; ts = T(e["ts"]); day = ts.normalize()
        if day != cur:
            peak = max(peak, bal)
            if not locked:
                thr = max(thr, peak - TRAIL)
                if peak >= LOCK_EOD: thr = FLOOR; locked = True
            cur = day; dreal = 0.0
        m = (ts.year, ts.month)
        if cmonth is None: cmonth = m
        if m != cmonth:
            if locked and bal > SAFETY:
                cap = CF if npay < NC else CL
                w = min(bal - SAFETY, cap)
                if w >= MINP:
                    bal -= w; payout += w; npay += 1
                    if first_pay is None: first_pay = k
                    if npay >= PAYOUT_CAP: return "retired", k, payout, npay, first_pay
            cmonth = m
        cushion = bal - thr
        if cushion < BR_ON * DD_ALLOW: braked = True
        elif cushion >= BR_OFF * DD_ALLOW: braked = False
        if dreal <= DAILY_STOP: continue
        base = POST if locked else PRE
        a, b, mm = base["A"], base["B"], base["M"]
        if braked: a, b, mm = max(a // 2, 1), 0, 0
        s = {"A": a, "B": b, "M": mm}[e["src"]]
        if s == 0: continue
        if bal + min(0.0, e["mae"]) * s <= thr:
            return "busted", k, payout, npay, first_pay
        bal += e["pnl"] * s; dreal += e["pnl"] * s
    return "active", len(ev) - 1, payout, npay, first_pay


def build_ev(variant, feats, fi, Bsim, Mm):
    A = V.a_variant(feats, fi, variant)
    ev = [dict(ts=t["ts"], src="A", pnl=t["R"] * t["risk_usd"], mae=min(0.0, t["mae_r"]) * t["risk_usd"]) for t in A]
    for t in Bsim:
        R = t["R"][variant]; gp = R * (t["risk_usd"] / V.DPP)
        ev.append(dict(ts=t["ts"], src="B", pnl=(gp - V.B_COST) * V.DPP, mae=min(0.0, t["mae_pts"][variant]) * V.DPP))
    for e in Mm:
        ev.append(dict(ts=e["ts"], src="M", pnl=e["pnl"], mae=min(0.0, e["mae"])))
    return sorted(ev, key=lambda x: T(x["ts"]))


def fleet(ev):
    end = T(ev[-1]["ts"]).normalize(); win = end - pd.Timedelta(days=365)
    d = win + pd.Timedelta(days=(7 - win.weekday()) % 7); mondays = []
    while d <= end:
        mondays.append(d); d += pd.Timedelta(days=7)
    t0 = T(mondays[0]); last_idx = len(ev) - 1
    pipeline = []                                # (free_idx, is_funded)
    evals = blown_evals = inprog = made = bust = retired = npayouts = 0
    payout_total = 0.0; first_pay_idx = None; reached20 = None
    for wi, mon in enumerate(mondays):
        bi = next((i for i in range(len(ev)) if T(ev[i]["ts"]).normalize() >= mon), None)
        if bi is None: continue
        pipeline = [(f, fn) for (f, fn) in pipeline if f > bi]      # free slots whose account resolved
        if len(pipeline) < MAX_ACCTS and (T(ev[last_idx]["ts"]) - T(ev[bi]["ts"])).days >= EXPIRE:
            evals += 1
            res, eidx = run_eval(ev, bi)
            if res == "PASS":
                st, fidx, pay, np_, fp = run_funded(ev, eidx)
                made += 1; payout_total += pay; npayouts += np_
                if st == "busted": bust += 1
                elif st == "retired": retired += 1
                pipeline.append((fidx, True))
                if fp is not None and (first_pay_idx is None or fp < first_pay_idx): first_pay_idx = fp
            elif res == "BLOWN":
                blown_evals += 1; pipeline.append((eidx, False))
            else:
                inprog += 1; pipeline.append((last_idx + 1, False))
        si = next((i for i, e in enumerate(ev) if T(e["ts"]).normalize() >= mon), 0)
        if sum(1 for (f, fn) in pipeline if fn and f > si) >= MAX_ACCTS and reached20 is None:
            reached20 = wi
    spend = evals * EVAL_COST + made * ACTIVATION
    d2p = (T(ev[first_pay_idx]["ts"]) - t0).days if first_pay_idx is not None else None
    return dict(evals=evals, blown_evals=blown_evals, inprog=inprog, made=made, bust=bust, retired=retired,
                npayouts=npayouts, payout=payout_total, spend=spend, net=payout_total - spend,
                reached20=reached20, d2p=d2p, weeks=len(mondays))


def main():
    print("loading real Databento (last 12mo window)…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5; feats = eng._features(); fi = feats.index
    Bsim = V.b_sim(df5); Mm = H.m_events(df5)
    rows = {}
    for v, name in [("incumbent", "LIVE BOT (A+B partial)"), ("single1", "single@1R (A+B)")]:
        rows[name] = fleet(build_ev(v, feats, fi, Bsim, Mm))

    print(f"\n================ 12-MONTH FLEET ECONOMICS — Apex 50K · cap 20 · 1 eval/wk · 6-payout retire ================")
    print(f"  fees: eval ${EVAL_COST:.0f} + activation ${ACTIVATION:.0f}/funded · EOD rule · real Databento single path\n")
    h = f"  {'metric':>26} | {'LIVE BOT (partial)':>20} | {'single@1R':>14}"
    print(h); print("  " + "-" * (len(h)))
    L = rows["LIVE BOT (A+B partial)"]; S = rows["single@1R (A+B)"]
    def row(lbl, k, money=False, dollar=False):
        a, b = L[k], S[k]
        f = (lambda x: f"${x:,.0f}") if (money or dollar) else (lambda x: f"{x}")
        print(f"  {lbl:>26} | {f(a):>20} | {f(b):>14}")
    row("weeks simulated", "weeks")
    row("evals bought", "evals")
    row("evals BLOWN", "blown_evals")
    row("funded accounts made", "made")
    row("funded BLOWN", "bust")
    row("funded RETIRED (6 payouts)", "retired")
    row("total payouts (count)", "npayouts")
    row("payout $$", "payout", money=True)
    row("spend (evals+activation)", "spend", money=True)
    row("NET take-home", "net", money=True)
    for name, R in rows.items():
        d2p = f"{R['d2p']}d" if R['d2p'] is not None else "none"
        r20 = f"week {R['reached20']+1}" if R['reached20'] is not None else "not reached in 12mo"
        print(f"\n  {name}: reached 20 funded {r20} · first payout {d2p} · {R['inprog']} evals still running at window end")
    print("\n  [caveat] ONE real-data path on the last 12mo (a favorable window vs the 5y average); momentum+brake")
    print("  funded config is paper-validated not live-proven; NO execution friction/slippage modeled — net is a")
    print("  best-case ceiling. single@1R has NEVER traded live. Fees are the modeled Apex discounted rates.")


if __name__ == "__main__":
    main()
