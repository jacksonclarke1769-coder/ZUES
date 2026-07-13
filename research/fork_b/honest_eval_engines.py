"""ZEUS Fork B — can the HONEST edges (Momentum V4, VPC) carry an Apex-50K EOD eval?

READ-ONLY on the bot repo (imports only; writes ONLY under reports/fork_b + research/fork_b).
Nothing armed. Research/sim measurement only.

Premise (from Fork A): Profile A's certified PF is a fill mirage — the live-achievable cut is
394 trades / PF 1.037 (breakeven). So: do the genuinely-honest edges clear an Apex eval on their own?

Honest edges (fills are honest — no resting-limit-at-a-price artifact):
  * Momentum V4: Zarattini noise-band, canonical FROZEN params = 4-bar confirm + ~15:30 last-entry
    (= ProfileMomentumEngine defaults confirm_bars=4, last_entry_slot=72). Flat-at-EOD position;
    daily P&L is bar close-to-close in POINTS × contracts × $2/pt (MNQ), minus per-flip cost.
  * VPC: nq_vwap_pullback locked config, honest next-5m-open fills, per-trade pts → $.

Profile A (item 3): honest-achievable-394 = honest_d1c_stream.csv rows with kept==True AND
ts ∈ achievable_keys.csv → 394 trades, PF 1.037 (reproduced exactly). Real fills, breakeven.

Eval engine (PRIMARY, items 1-3): tools_account_size_research (day_rows + eval_run + funded_paid)
— the CERTIFIED Apex-50K EOD-drawdown harness (EOD close-set threshold ratchet/lock, intraday
DOWNSIDE liquidation via marked trough, $550 realized daily stop, $1,000 DLL flatten, 30-day clock,
rolling 1-eval/trading-day starts). Reused BY IMPORT so bookkeeping is byte-identical to the certified
machine. Canary: recert A-only cap6/$900 must reproduce ~3.4% pass.

Item 4 (EOD vs intraday-trail): apex_eval_eod.eval_eod (EOD) vs apex_eval_deployed.eval_from
(FR.ApexAcct intraday-trailing peak ratchet) on the SAME momentum event list.

Data: single vendor = Databento NQ 1m→5m RTH (2022-01+ to match VPC recert window) for ALL three
edges → vendor-consistent portfolio (no Dukascopy/Databento cross-vendor mixing).

Economics (LOW-CONFIDENCE / PLACEHOLDER per test_apex_terms_canary — never laundered as certified):
  E[$/att] = P(pass) × funded_paid(same-config events) − fee_mo×1.5 (= $67.5 attempt cost).
"""
import os, sys, json, hashlib, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))

import nq_vwap_pullback as v                       # VPC signals + RT_COST
import tools_account_size_research as H            # CERTIFIED EOD harness: day_rows/eval_run/funded_paid
import apex_eval_eod as AE                          # eval_eod (EOD) for item-4 contrast
import apex_eval_deployed as AD                     # eval_from (intraday-trail via FR.ApexAcct)
import funded_rules as FR
from profile_momentum_engine import ProfileMomentumEngine as PME

NY = "America/New_York"
DPP = 2.0                                            # $/index-pt/MNQ
DBNT = os.path.expanduser("~/trading-team/data/real_futures/NQ_databento_1m_5y.parquet")
SPEC_H = H.SPECS["50K"]                              # day-level EOD harness spec (stop/dll/ladder/fee)
SPEC_FR = FR.APEX_ACCOUNTS["50K"]                    # ApexAcct spec (for intraday-trail contrast)
STOP, DLL = SPEC_H["stop"], SPEC_H["dll"]            # 550 / 1000
FEE_ATT = SPEC_H["fee_mo"] * 1.5                     # $67.5 attempt cost (recert convention)
START_DATE = pd.Timestamp("2022-01-01", tz=NY)
M_FLIP_COST = 1.0                                    # $/contract per flip (~2-tick round-turn)
OUT = os.path.join(REPO, "reports", "fork_b")
os.makedirs(OUT, exist_ok=True)


# ============================ shared Databento 5m RTH ============================
def databento_5m_rth():
    d1 = pd.read_parquet(DBNT)
    d1.index = d1.index.tz_convert(NY) if d1.index.tz else d1.index.tz_localize("UTC").tz_convert(NY)
    d1 = d1.sort_index(); d1 = d1[~d1.index.duplicated(keep="first")]
    g = lambda c, h: getattr(d1[c].resample("5min", label="left", closed="left"), h)()
    df = pd.DataFrame({"Open": g("open", "first"), "High": g("high", "max"), "Low": g("low", "min"),
                       "Close": g("close", "last"), "Volume": g("volume", "sum")}).dropna(subset=["Open"])
    t = df.index
    df = df[((t.hour > 9) | ((t.hour == 9) & (t.minute >= 30))) & (t.hour < 16)]
    df["date"] = df.index.normalize()
    df["slot"] = df.groupby("date").cumcount()
    return df[df.index >= START_DATE]


# ============================ MOMENTUM V4 events (Databento) ============================
def momentum_daily_pts(df5):
    """One row/day: momentum daily P&L in POINTS (close-to-close on held position) + intraday
    peak/trough in points + flip count. Canonical FROZEN params via PME defaults (cb=4, last=72)."""
    d = df5.copy()
    d["date_n"] = d["date"].dt.tz_localize(None)
    comp = d[["date_n", "slot", "Open", "High", "Low", "Close"]].rename(columns={"date_n": "date"}).assign(Volume=0)
    pos = PME.compute(comp)                          # +1/-1/0 target position per bar (V4 defaults)
    d["ts"] = d.index
    d = d.reset_index(drop=True)
    d["pos"] = pos
    rows = []
    for day, g in d.groupby("date"):
        g = g.reset_index(drop=True)
        cum = peak = trough = 0.0; flips = 0; prev = 0.0
        for i in range(1, len(g)):
            held = g.pos.iloc[i - 1]
            cum += held * (g.Close.iloc[i] - g.Close.iloc[i - 1])      # POINTS
            peak = max(peak, cum); trough = min(trough, cum)
            if g.pos.iloc[i] != prev:
                flips += 1; prev = g.pos.iloc[i]
        rows.append(dict(ts=g.ts.iloc[-1], pnl_pts=cum, peak_pts=peak, trough_pts=trough, flips=flips))
    return pd.DataFrame(rows).sort_values("ts").reset_index(drop=True)


def momentum_events(mom, contracts):
    """POINTS × contracts × $2 − per-flip cost (flip cost hits both realized and the marked trough).
    mae is stored as the ADVERSE excursion RELATIVE TO the realized close (trough_$ − pnl), so the
    harness's `bal + mae` reproduces the intraday marked low. mfe = intraday peak (no cost)."""
    ev = []
    for r in mom.itertuples():
        cost = r.flips * M_FLIP_COST * contracts
        pnl = r.pnl_pts * DPP * contracts - cost
        trough_d = r.trough_pts * DPP * contracts - cost      # net intraday marked low ($)
        peak_d = r.peak_pts * DPP * contracts                 # gross intraday marked high ($)
        if abs(pnl) < 1e-9 and peak_d == 0 and trough_d == 0:
            continue
        ev.append(dict(ts=pd.Timestamp(r.ts), src="M", pnl=pnl,
                       mfe=max(0.0, peak_d),
                       mae=min(0.0, trough_d - pnl)))          # adverse excursion vs realized close
    return ev


# ============================ VPC events (Databento, honest fills) ============================
CFG = dict(atr_stop=2.5, trail_atr=5.0, slot_min=6, slot_max=66, max_trades=2,
           slope_mult=0.3, trend_mult=0.5, daily_stop=120)


def vpc_trades_rich(feats):
    sig_kw = {k: CFG[k] for k in ("atr_stop", "slot_min", "slot_max", "slope_mult", "trend_mult")}
    trail_atr, max_trades, daily_stop = CFG["trail_atr"], CFG["max_trades"], CFG["daily_stop"]
    out = []
    for day, g in feats.groupby("date"):
        g = g.sort_values("slot"); idx = g.index
        sigs = v.vpc_signals(g.reset_index(drop=True), **sig_kw)
        O, Hh, L, C, A = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.atr.values
        n = len(g); busy_until = -1; taken = 0; day_pnl = 0.0
        for (ei, d, stopdist) in sigs:
            if ei >= n or ei <= busy_until or taken >= max_trades:
                continue
            if daily_stop and day_pnl <= -daily_stop:
                break
            entry = O[ei]; stop = entry - stopdist if d == 1 else entry + stopdist
            peak = entry; exit_px = None; exit_i = n - 1; mae = 0.0; mfe = 0.0
            for j in range(ei, n):
                mae = min(mae, d * (L[j] - entry) if d == 1 else d * (Hh[j] - entry))
                mfe = max(mfe, d * (Hh[j] - entry) if d == 1 else d * (L[j] - entry))
                if d == 1:
                    if L[j] <= stop: exit_px = stop; exit_i = j; break
                    peak = max(peak, Hh[j]); ns = peak - trail_atr * A[j]
                    stop = max(stop, ns) if not np.isnan(A[j]) else stop
                else:
                    if Hh[j] >= stop: exit_px = stop; exit_i = j; break
                    peak = min(peak, L[j]); ns = peak + trail_atr * A[j]
                    stop = min(stop, ns) if not np.isnan(A[j]) else stop
            if exit_px is None: exit_px = C[n - 1]; exit_i = n - 1
            pnl = d * (exit_px - entry) - v.RT_COST
            out.append(dict(ts=idx[ei], pnl_pts=pnl, mae_pts=mae, mfe_pts=mfe, stop_pts=stopdist))
            busy_until = exit_i; taken += 1; day_pnl += pnl
    return pd.DataFrame(out).sort_values("ts").reset_index(drop=True)


def vpc_events_risk(tr, budget=600.0, cap=3):
    ev = []
    for r in tr.itertuples():
        c = int(np.clip(round(budget / (r.stop_pts * DPP)), 1, cap)) if r.stop_pts > 0 else 1
        ev.append(dict(ts=pd.Timestamp(r.ts), src="V", pnl=r.pnl_pts * DPP * c,
                       mfe=max(0.0, r.mfe_pts) * DPP * c, mae=min(0.0, r.mae_pts) * DPP * c))
    return ev


# ============================ Profile-A honest-394 events ============================
def a394_rows():
    s = pd.read_csv(os.path.join(REPO, "reports", "emergency_recert_d1c_lookahead", "honest_d1c_stream.csv"))
    keys = set(pd.read_csv(os.path.join(REPO, "reports", "inc_20260707_recert", "achievable_keys.csv"))["key"].astype(str))
    s["key"] = pd.to_datetime(s["ts"], utc=True).apply(lambda t: t.tz_convert(NY).isoformat())
    kept = s[(s["kept"] == True) & (s["key"].isin(keys))].copy()
    kept = kept.dropna(subset=["R", "risk_usd", "mae_r"])
    return [dict(ts=pd.Timestamp(r.ts), R=float(r.R), risk_usd=float(r.risk_usd), mae_r=float(r.mae_r))
            for r in kept.itertuples()]


def a_events(rows, budget=900.0, cap=6):
    ev = []
    for t in rows:
        q = min(cap, int(budget // t["risk_usd"]))
        if q < 1:
            continue
        ev.append(dict(ts=pd.Timestamp(t["ts"]), src="A", pnl=t["R"] * t["risk_usd"] * q,
                       mfe=0.0, mae=min(0.0, t["mae_r"]) * t["risk_usd"] * q))
    return ev


# ============================ CERTIFIED EOD funnel (items 1-3) ============================
def rolling_starts(days):
    starts, seen = [], set()
    last = days[-1][0]
    for i, (d, _, _) in enumerate(days):
        if d not in seen and (last - d).days > H.EXPIRE_DAYS:
            seen.add(d); starts.append(i)
    return starts


def eval_funnel(events, label):
    """Run events (list of dict ts/pnl/mae) through the certified day-level EOD harness."""
    ev = sorted([dict(ts=e["ts"], pnl=e["pnl"], mae=e["mae"]) for e in events], key=lambda e: e["ts"])
    days = H.day_rows(ev, STOP, DLL)
    if len(days) < 2:
        return dict(label=label, n=0)
    starts = rolling_starts(days)
    res = [H.eval_run(days, s, SPEC_H) for s in starts]
    n = len(res)
    npass = sum(1 for r in res if r[0] == "PASS")
    nbust = sum(1 for r in res if r[0] == "BUST")
    nexp = sum(1 for r in res if r[0] == "EXPIRE")
    pdays = [r[1] for r in res if r[0] == "PASS"]
    fp = H.funded_paid(days, SPEC_H)                 # same-config funded value (LOW-CONFIDENCE)
    p = 100 * npass / n
    e_att = (p / 100.0) * fp - FEE_ATT
    # trades/wk from the underlying event stream (normalize tz for mixed-offset safety)
    ts = pd.to_datetime([pd.Timestamp(e["ts"]).tz_convert("UTC") if pd.Timestamp(e["ts"]).tzinfo
                         else pd.Timestamp(e["ts"], tz="UTC") for e in ev])
    wk = max(1.0, (ts.max() - ts.min()).days / 7.0)
    return dict(label=label, n_starts=n,
                pass_pct=round(p, 1), bust_pct=round(100 * nbust / n, 1), exp_pct=round(100 * nexp / n, 1),
                med_days=(int(np.median(pdays)) if pdays else None),
                funded_paid=round(fp), e_per_att=round(e_att),
                trades_per_wk=round(len(ev) / wk, 2), n_events=len(ev))


# ============================ item 4: EOD vs intraday-trail (momentum) ============================
def eod_vs_intraday(mom_events_unit_scaled):
    """Both rules on the SAME momentum event list. EOD = apex_eval_eod.eval_eod; intraday-trail =
    apex_eval_deployed.eval_from (FR.ApexAcct ratchets floor on running peak incl. intraday MFE)."""
    ev = AD.apply_daily_stop(sorted(mom_events_unit_scaled, key=lambda e: e["ts"]))
    # day starts (>30d room), reuse AE.day_starts
    starts = AE.day_starts(ev)
    eod = [AE.eval_eod(ev, s, SPEC_FR) for s in starts]
    itr = [AD.eval_from(ev, s, SPEC_FR) for s in starts]
    def summ(res, idx1=1):
        n = len(res)
        return dict(n=n,
                    pass_pct=round(100 * sum(1 for r in res if r[0] == "PASS") / n, 1),
                    bust_pct=round(100 * sum(1 for r in res if r[0] == "BUST") / n, 1),
                    exp_pct=round(100 * sum(1 for r in res if r[0] == "EXPIRE") / n, 1))
    return dict(eod=summ(eod), intraday_trail=summ(itr))


def daily_series(events):
    """Collapse an event list to a per-day realized-$ Series (for correlation/overlap)."""
    s = {}
    for e in events:
        d = pd.Timestamp(e["ts"]).normalize()
        s[d] = s.get(d, 0.0) + e["pnl"]
    return pd.Series(s).sort_index()


def md5_of(obj):
    return hashlib.md5(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def main():
    print("loading Databento 5m RTH (2022+)…", flush=True)
    df5 = databento_5m_rth()
    print(f"  bars {df5.index.min().date()} → {df5.index.max().date()} ({len(df5):,})", flush=True)

    print("building momentum V4 daily points…", flush=True)
    mom = momentum_daily_pts(df5)
    net_pts = mom.pnl_pts.sum()
    print(f"  momentum days={len(mom)}  net={net_pts:.0f}pt  (unit)", flush=True)

    print("building VPC trades…", flush=True)
    feats = v.features(df5)
    feats = feats[feats.date >= START_DATE]
    vpc = vpc_trades_rich(feats)
    print(f"  VPC trades={len(vpc)}  net={vpc.pnl_pts.sum():.0f}pt", flush=True)

    print("building Profile-A honest-394…", flush=True)
    arows = a394_rows()
    ar = np.array([r["R"] for r in arows])
    a_pf = ar[ar > 0].sum() / max(1e-9, -ar[ar <= 0].sum())
    print(f"  A-394 n={len(arows)}  PF={a_pf:.3f}  totR={ar.sum():.2f}", flush=True)

    out = {"meta": dict(vendor="Databento NQ 1m→5m RTH", window=str(START_DATE.date()) + "→" + str(df5.index.max().date()),
                        engine="tools_account_size_research EOD (day_rows+eval_run+funded_paid), $550 stop, $1000 DLL, 30d clock",
                        momentum_params="V4 canonical: confirm_bars=4, last_entry_slot=72(15:30), k=1.0, nd=14, trend=50",
                        econ="E[$/att]=P(pass)×funded_paid(same-config) − $67.5 ; LOW-CONFIDENCE placeholder",
                        flip_cost_per_contract=M_FLIP_COST)}

    # ---- CANARY: reproduce recert A-only cap6/$900 ~3.4% pass ----
    can = eval_funnel(a_events(arows, budget=900, cap=6), "CANARY A-only cap6/$900")
    out["canary_A_cap6_900"] = can
    print(f"\n[CANARY] A-only cap6/$900 → pass {can['pass_pct']}% bust {can['bust_pct']}% exp {can['exp_pct']}% "
          f"(recert = 3.4/8.9/87.6)", flush=True)

    # ---- ITEM 1: momentum standalone at mm ∈ {2,3,4,6,8} ----
    print("\n=== ITEM 1: MOMENTUM STANDALONE (EOD) ===", flush=True)
    item1 = []
    for mm in [2, 3, 4, 6, 8]:
        r = eval_funnel(momentum_events(mom, mm), f"Momentum mm={mm}")
        r["mm"] = mm
        item1.append(r)
        print(f"  mm={mm}: pass {r['pass_pct']}% bust {r['bust_pct']}% exp {r['exp_pct']}% "
              f"med {r['med_days']}d  E[$/att] {r['e_per_att']}  tr/wk {r['trades_per_wk']}", flush=True)
    out["item1_momentum_standalone"] = item1
    # best standalone mm = max pass with pass>bust and E[$]>0, else max E[$]
    ok = [r for r in item1 if r["pass_pct"] > r["bust_pct"] and r["e_per_att"] > 0]
    best = (max(ok, key=lambda r: r["e_per_att"]) if ok else max(item1, key=lambda r: r["e_per_att"]))
    best_mm = best["mm"]
    out["best_standalone_mm"] = best_mm
    print(f"  → best standalone mm={best_mm} (E[$/att]={best['e_per_att']})", flush=True)

    # ---- ITEM 2: Momentum(best) + VPC$600/cap3 ----
    print("\n=== ITEM 2: MOMENTUM + VPC ===", flush=True)
    mom_ev = momentum_events(mom, best_mm)
    vpc_ev = vpc_events_risk(vpc, budget=600, cap=3)
    r_mom = eval_funnel(mom_ev, f"Momentum mm={best_mm}")
    r_vpc = eval_funnel(vpc_ev, "VPC $600/cap3")
    r_mv = eval_funnel(mom_ev + vpc_ev, f"Momentum{best_mm}+VPC")
    out["item2_mom_vpc"] = dict(momentum=r_mom, vpc=r_vpc, portfolio=r_mv)
    # correlation / overlap of daily realized P&L
    sm, sv = daily_series(mom_ev), daily_series(vpc_ev)
    aligned = pd.concat([sm.rename("M"), sv.rename("V")], axis=1)
    both = aligned.dropna()
    corr_all = float(aligned.fillna(0.0).corr().loc["M", "V"])
    corr_both = float(both.corr().loc["M", "V"]) if len(both) > 2 else None
    overlap_days = int(len(both))
    out["item2_independence"] = dict(corr_all_days=round(corr_all, 3),
                                     corr_overlap_days=(round(corr_both, 3) if corr_both is not None else None),
                                     mom_active_days=int(len(sm)), vpc_active_days=int(len(sv)),
                                     both_active_days=overlap_days)
    print(f"  VPC standalone: pass {r_vpc['pass_pct']}% bust {r_vpc['bust_pct']}% E[$/att] {r_vpc['e_per_att']}")
    print(f"  PORTFOLIO: pass {r_mv['pass_pct']}% bust {r_mv['bust_pct']}% exp {r_mv['exp_pct']}% "
          f"med {r_mv['med_days']}d E[$/att] {r_mv['e_per_att']} tr/wk {r_mv['trades_per_wk']}")
    print(f"  independence: corr(all)={corr_all:.3f} corr(overlap)={corr_both} both-active-days={overlap_days}")

    # ---- ITEM 3: + honest-Profile-A-394 ----
    print("\n=== ITEM 3: MOMENTUM + VPC + honest-A-394 ===", flush=True)
    a_ev_full = a_events(arows, budget=900, cap=6)
    # restrict A to the common 2022+ window so the Δ isolates A's contribution (not pre-2022 A-only starts)
    a_ev = [e for e in a_ev_full if pd.Timestamp(e["ts"]).tz_convert("UTC") >= START_DATE.tz_convert("UTC")]
    r_3 = eval_funnel(mom_ev + vpc_ev + a_ev, f"Momentum{best_mm}+VPC+A394")
    out["item3_three_edge"] = dict(portfolio=r_3, a394_standalone=eval_funnel(a_ev, "A-394 cap6/$900"))
    print(f"  A-394 standalone: pass {out['item3_three_edge']['a394_standalone']['pass_pct']}% "
          f"bust {out['item3_three_edge']['a394_standalone']['bust_pct']}%")
    print(f"  THREE-EDGE: pass {r_3['pass_pct']}% bust {r_3['bust_pct']}% exp {r_3['exp_pct']}% "
          f"med {r_3['med_days']}d E[$/att] {r_3['e_per_att']} tr/wk {r_3['trades_per_wk']}")
    print(f"  Δ vs Mom+VPC: pass {r_3['pass_pct']-r_mv['pass_pct']:+.1f}pp  "
          f"E[$/att] {r_3['e_per_att']-r_mv['e_per_att']:+d}")

    # ---- ITEM 4: EOD vs intraday-trail on momentum, bust gradient across sizes ----
    print("\n=== ITEM 4: EOD vs INTRADAY-TRAIL (momentum, both rules on same events) ===", flush=True)
    item4 = {}
    for mm in [2, 4, 6]:
        cmp4 = eod_vs_intraday(momentum_events(mom, mm))
        item4[f"mm={mm}"] = cmp4
        db = cmp4['intraday_trail']['bust_pct'] - cmp4['eod']['bust_pct']
        print(f"  mm={mm}: EOD bust {cmp4['eod']['bust_pct']}% | intraday-trail bust {cmp4['intraday_trail']['bust_pct']}% "
              f"| Δbust(intraday−EOD) {db:+.1f}pp  (EOD exp {cmp4['eod']['exp_pct']}%)")
    out["item4_eod_vs_intraday"] = item4

    # determinism hash over the numeric payload
    payload = {k: v for k, v in out.items() if k != "meta"}
    out["md5"] = md5_of(payload)
    with open(os.path.join(OUT, "01_honest_eval_engines.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n[md5] {out['md5']}", flush=True)
    print(f"[saved] reports/fork_b/01_honest_eval_engines.json", flush=True)
    return out


if __name__ == "__main__":
    main()
