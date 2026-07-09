"""CHECK #4 — FUNDED ROBUSTNESS with MOMENTUM ON (deployed mm: Phase1 mm2 / Phase2 mm6).
Reuses validated engines: V.a_variant (single1 vs incumbent A exit), H.b_events, H.m_events,
and the F.lifecycle structure (== apex_funded_momentum_test.life, supports M src). Adds IS/OOS +
per-start-year + block-bootstrap MC on P(reach-lock) and E[payout/acct]. Then quantifies the
$1k Apex intraday daily-kill interaction."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import exit_model_validate as V
import apex_eval_deployed as H
import apex_funded_eod_databento as F
import strategy_engine_profileA as E
import config

T = pd.Timestamp
NY = "America/New_York"
np.random.seed(11)

# deployed funded sizing
PRE  = {"A": 4, "B": 2, "M": 2}    # phase1 grind
POST = {"A": 6, "B": 3, "M": 6}    # phase2 scaled
PRE_OFF  = {"A": 4, "B": 2, "M": 0}
POST_OFF = {"A": 6, "B": 3, "M": 0}


def lifecycle(ev, start, pre, post, daily_kill=None):
    """== F.lifecycle / MT.life, with M src + optional Apex $1k daily-kill.
    daily_kill=None -> off (matches validated baseline). daily_kill=(salvage,hardkill):
      - realized day P&L <= salvage -> flatten+halt the rest of the day (account survives)
      - realized + open-event intraday trough <= hardkill -> ACCOUNT KILLED (bust)."""
    thr = F.START - F.TRAIL; bal = F.START; peak = F.START; locked = False; d2l = None
    payout = 0.0; npay = 0; t0 = T(ev[start]["ts"]); cur = None; dreal = 0.0; cmonth = None
    last = t0; killed = False; kill_halt = False
    for k in range(start, len(ev)):
        e = ev[k]; ts = T(e["ts"]); day = ts.normalize(); last = ts
        if (ts - t0).days > F.HORIZON_DAYS:
            break
        if cur is None:
            cur = day
        if day != cur:
            peak = max(peak, bal)
            if not locked:
                thr = max(thr, peak - F.TRAIL)
                if peak >= F.LOCK_EOD:
                    thr = F.FLOOR; locked = True; d2l = (ts - t0).days
            cur = day; dreal = 0.0; kill_halt = False
        m = (ts.year, ts.month)
        if cmonth is None:
            cmonth = m
        if m != cmonth:
            if locked and bal > F.SAFETY:
                cap = F.CAP_FIRST if npay < F.N_CAPPED else F.CAP_LATER
                w = min(bal - F.SAFETY, cap)
                if w >= F.MIN_PAYOUT:
                    bal -= w; payout += w; npay += 1
            cmonth = m
        if dreal <= F.DAILY_STOP:          # -$550 self stop: no new entries
            continue
        if kill_halt:                       # apex salvage already flattened today
            continue
        sc = (post if locked else pre).get(e["src"], 0)
        if sc == 0:
            continue
        # trailing-DD intraday liquidation (existing rule)
        if bal + min(0.0, e["mae"]) * sc <= thr:
            return dict(locked=locked, d2l=d2l, payout=payout,
                        bust=("postlock" if locked else "prelock"),
                        months=max(1e-6, (ts - t0).days) / 30.0)
        if daily_kill is not None:
            salv, hardk = daily_kill
            intraday = dreal + min(0.0, e["mae"]) * sc      # worst intraday day P&L incl this event
            if intraday <= hardk:                            # account hard-killed before salvage reacts
                return dict(locked=locked, d2l=d2l, payout=payout,
                            bust=("postlock" if locked else "prelock"),
                            months=max(1e-6, (ts - t0).days) / 30.0, killmode="hardkill")
        bal += e["pnl"] * sc; dreal += e["pnl"] * sc
        if daily_kill is not None and dreal <= daily_kill[0]:
            kill_halt = True                                 # salvage: flatten+halt, survive
    return dict(locked=locked, d2l=d2l, payout=payout, bust=None,
                months=max(1e-6, (last - t0).days) / 30.0)


def funded_starts(ev):
    last = T(ev[-1]["ts"]); seen, st = set(), []
    for i, e in enumerate(ev):
        d = T(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - T(e["ts"])).days >= 270:
            st.append(i)
    return st


def summarize(out):
    n = len(out)
    lk = [o for o in out if o["locked"]]
    d2l = [o["d2l"] for o in lk if o["d2l"] is not None]
    epay = np.mean([o["payout"] for o in out])
    epl = np.mean([o["payout"] for o in lk]) if lk else 0.0
    mol = np.mean([o["months"] for o in lk]) if lk else 0.0
    return dict(n=n, lock=100*len(lk)/n, d2l=int(np.median(d2l)) if d2l else 0,
                mo=epl/mol if mol else 0, epay=epay, epl=epl)


# ---------- block-bootstrap MC (10-day blocks), recompute lock% + E[payout] ----------
def day_blocks(ev):
    by = {}
    for e in ev:
        by.setdefault(T(e["ts"]).normalize(), []).append(e)
    return [by[d] for d in sorted(by)]


def synth_stream(blocks, BLOCK=10):
    n = len(blocks); out_days = []
    while len(out_days) < n:
        s = np.random.randint(0, max(1, n - BLOCK))
        out_days.extend(blocks[s:s + BLOCK])
    out_days = out_days[:n]
    cal = pd.bdate_range("2000-01-03", periods=n)
    ev = []
    for di, day_evs in enumerate(out_days):
        base = T(cal[di])
        for kk, e in enumerate(day_evs):
            ne = dict(e); ne["ts"] = base + pd.Timedelta(minutes=kk); ev.append(ne)
    return ev


def mc(ev, pre, post, n_paths=200, stride=4):
    blocks = day_blocks(ev)
    locks, pays = [], []
    for _ in range(n_paths):
        s = synth_stream(blocks)
        st = funded_starts(s)[::stride]
        out = [lifecycle(s, x, pre, post) for x in st]
        sm = summarize(out)
        locks.append(sm["lock"]); pays.append(sm["epay"])
    locks, pays = np.array(locks), np.array(pays)
    return (np.median(locks), np.percentile(locks, 5), np.percentile(locks, 95),
            np.median(pays), np.percentile(pays, 5), np.percentile(pays, 95))


print("loading real Databento + building streams (A single1 vs incumbent, B, Momentum)…", flush=True)
df5 = F.DB.load_databento_5m()
H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
feats = eng._features(); fi = feats.index
Bf = H.b_events(df5)                 # unit-size B events (pnl/mae $)
Mm = H.m_events(df5)                 # unit-size momentum daily events
Avar = {v: V.a_variant(feats, fi, v) for v in ["incumbent", "single1"]}
print(f"  bars {df5.index.min().date()}..{df5.index.max().date()}  A_inc={len(Avar['incumbent'])} "
      f"A_s1={len(Avar['single1'])}  B={len(Bf)}  mm-days={len(Mm)}", flush=True)


def a_to_ev(variant):
    return [dict(ts=t["ts"], src="A", pnl=t["R"]*t["risk_usd"],
                 mae=min(0.0, t["mae_r"])*t["risk_usd"]) for t in Avar[variant]]


def merged(variant, with_mm):
    base = a_to_ev(variant) + Bf + (Mm if with_mm else [])
    return sorted(base, key=lambda e: T(e["ts"]))


# ===================== HEADLINE: momentum ON, deployed sizing =====================
print("\n================ FUNDED · momentum ON (Phase1 mm2 / Phase2 mm6) · EOD · 18mo ================")
print(f"  {'variant':>22} | {'lock%':>6} {'d2l':>4} {'$/mo':>7} {'E[pay/acct]':>11} {'E[pay|lock]':>11}")
print("  " + "-"*70)
rows = {}
for variant in ["incumbent", "single1"]:
    for tag, wm, pre, post in [("mm OFF", False, PRE_OFF, POST_OFF), ("mm ON", True, PRE, POST)]:
        ev = merged(variant, wm)
        st = funded_starts(ev)
        out = [lifecycle(ev, s, pre, post) for s in st]
        sm = summarize(out)
        rows[(variant, tag)] = (ev, st, sm)
        print(f"  {variant+' '+tag:>22} | {sm['lock']:6.1f} {sm['d2l']:4} ${sm['mo']:6,.0f} "
              f"${sm['epay']:10,.0f} ${sm['epl']:10,.0f}")

# ===================== IS / OOS (by start year) · momentum ON =====================
print("\n================ IS(2021-24) / OOS(2025-26) · momentum ON ================")
print(f"  {'variant':>22} | {'IS lock%':>8} {'IS E[pay]':>9} | {'OOS lock%':>9} {'OOS E[pay]':>10}")
print("  " + "-"*66)
for variant in ["incumbent", "single1"]:
    ev, st, _ = rows[(variant, "mm ON")]
    def sub(lo, hi):
        s2 = [s for s in st if lo <= T(ev[s]["ts"]).year <= hi]
        out = [lifecycle(ev, s, PRE, POST) for s in s2]
        return summarize(out)
    iss = sub(2021, 2024); oos = sub(2025, 2026)
    print(f"  {variant:>22} | {iss['lock']:8.1f} ${iss['epay']:8,.0f} | "
          f"{oos['lock']:9.1f} ${oos['epay']:9,.0f}")

# ===================== PER START-YEAR · momentum ON =====================
print("\n================ PER START-YEAR lock% (E[pay/acct]) · momentum ON ================")
yrs = list(range(2021, 2027))
print(f"  {'variant':>22} | " + " ".join(f"{y:>11}" for y in yrs))
for variant in ["incumbent", "single1"]:
    ev, st, _ = rows[(variant, "mm ON")]
    cells = []
    for y in yrs:
        s2 = [s for s in st if T(ev[s]["ts"]).year == y]
        if not s2:
            cells.append(f"{'--':>11}"); continue
        sm = summarize([lifecycle(ev, s, PRE, POST) for s in s2])
        cells.append(f"{sm['lock']:4.0f}%(${sm['epay']/1000:3.1f}k)")
    print(f"  {variant:>22} | " + " ".join(cells))

# ===================== BLOCK-BOOTSTRAP MC · momentum ON =====================
print("\n================ BLOCK-BOOTSTRAP MC (200 paths, 10-day blocks) · momentum ON ================")
print(f"  {'variant':>22} | {'lock med':>8} {'p5':>6} {'p95':>6} | {'E[pay] med':>10} {'p5':>8} {'p95':>8}")
print("  " + "-"*72)
mcres = {}
for variant in ["incumbent", "single1"]:
    ev, _, _ = rows[(variant, "mm ON")]
    lm, lp5, lp95, pm, pp5, pp95 = mc(ev, PRE, POST)
    mcres[variant] = (lm, lp5, lp95, pm, pp5, pp95)
    print(f"  {variant:>22} | {lm:8.1f} {lp5:6.1f} {lp95:6.1f} | ${pm:9,.0f} ${pp5:7,.0f} ${pp95:7,.0f}")

# ===================== $1k DAILY-KILL INTERACTION =====================
print("\n================ $1k APEX INTRADAY DAILY-KILL interaction · momentum ON ================")
print("  re-run lifecycle WITH salvage -$850 / hard-kill -$1000 (vs baseline no-kill):")
print(f"  {'variant':>22} | {'lock no-kill':>12} {'lock +kill':>10} | {'E[pay] no-kill':>14} {'E[pay] +kill':>12} | {'hardkill busts':>14}")
print("  " + "-"*92)
for variant in ["incumbent", "single1"]:
    ev, st, sm0 = rows[(variant, "mm ON")]
    outk = [lifecycle(ev, s, PRE, POST, daily_kill=(-850.0, -1000.0)) for s in st]
    smk = summarize(outk)
    hk = sum(1 for o in outk if o.get("killmode") == "hardkill")
    print(f"  {variant:>22} | {sm0['lock']:12.1f} {smk['lock']:10.1f} | "
          f"${sm0['epay']:13,.0f} ${smk['epay']:11,.0f} | {hk:5d}/{len(outk)} ({100*hk/len(outk):.1f}%)")

# direct day-level breach census at POST sizing (worst case, mm6)
print("\n  --- day-level census: realized & intraday-trough day P&L breaches (POST sizing A6/B3/mm6) ---")
print(f"  {'variant':>22} | {'kill-risk days <=-1000(real)':>28} {'<=-1000(introu)':>16} {'<=-850 salvage':>15}  /day-rows")
for variant in ["incumbent", "single1"]:
    for wm, post, tag in [(True, POST, "mm ON "), (False, POST_OFF, "mm OFF")]:
        ev = merged(variant, wm)
        by = {}
        for e in ev:
            by.setdefault(T(e["ts"]).normalize(), []).append(e)
        nreal = nintr = nsalv = 0; ndays = 0
        for d, evs in by.items():
            ndays += 1; dreal = 0.0; introu = 0.0; halted = False
            for e in evs:
                if halted or dreal <= F.DAILY_STOP:
                    break
                sc = post.get(e["src"], 0)
                if sc == 0:
                    continue
                introu = min(introu, dreal + min(0.0, e["mae"]) * sc)
                dreal += e["pnl"] * sc
                if dreal <= -850.0:
                    halted = True
            if dreal <= -1000.0: nreal += 1
            if introu <= -1000.0: nintr += 1
            if dreal <= -850.0: nsalv += 1
        print(f"  {variant+' '+tag:>22} | {nreal:28d} {nintr:16d} {nsalv:15d}  /{ndays}")
print("\n  [note] -$550 self-stop halts NEW entries first; momentum is one daily-aggregate event so its")
print("  intraday trough lands within a single event (the known mm risk the salvage cannot pre-empt).")
