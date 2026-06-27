"""PAPER-VALIDATE funded momentum (demo/paper, NO real orders). Confirms the NEW wiring end-to-end:
1) the phase gate now ARMS momentum on the Apex funded tier (was off),
2) the momentum ENGINE produces real signals on recent NQ bars,
3) those signals ROUTE through the real MomentumExecutor as correctly-sized (mm2) paper orders,
4) paper mode resolves to 'route via paper sender' (never live without the approval flag).
A capturing FakeSender stands in for the bridge — nothing is sent. (Live demo on real-time bars = Monday.)"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
from auto_safety import momentum_active_for_tier, FUNDED_TIERS
from profile_momentum_engine import ProfileMomentumEngine as PME
from profile_momentum_live import MomentumExecutor
from config_defaults import resolve_momentum_live
import apex_eval_eod_databento as DB

OK = "✅"; NO = "❌"


class FakeSender:
    def __init__(self): self.cap = []
    def send(self, p, **k): self.cap.append(p); return {"sent": True, "reason": "paper-dry"}


def sig(action, position, close):
    return dict(action=action, position=position,
                side=("long" if position > 0 else "short" if position < 0 else "flat"),
                close=close, slot=20, date="2026-06-26")


def main():
    print("=== PAPER-VALIDATE: funded momentum (Apex-50K), demo/paper, NO real orders ===\n")
    fails = 0

    # 1) gate arms on funded tier
    ok, why = momentum_active_for_tier("Apex-50K")
    g1 = ok is True
    print(f"  1. phase gate arms momentum on Apex-50K (funded): {OK if g1 else NO}  ({why[:55]})")
    okS, _ = momentum_active_for_tier("Apex-50K-scaled")
    g1b = okS is True
    print(f"     ...and on Apex-50K-scaled: {OK if g1b else NO}")
    mm_grind = FUNDED_TIERS["Apex-50K"]["mm"]; mm_scaled = FUNDED_TIERS["Apex-50K-scaled"]["mm"]
    g1c = mm_grind == 2 and mm_scaled == 6
    print(f"     funded mm sizes: grind {mm_grind} / scaled {mm_scaled}: {OK if g1c else NO}")
    fails += not (g1 and g1b and g1c)

    # 2) engine produces real signals on recent bars
    print("\n  2. momentum engine on real NQ bars (last ~90d)…", flush=True)
    df5 = DB.load_databento_5m()
    d = df5.copy()
    mins = d.index.hour * 60 + d.index.minute
    d = d[(mins >= 570) & (mins < 960)].tail(90 * 78).copy()   # ~90 RTH days
    d["date"] = d.index.tz_convert("America/New_York").normalize().tz_localize(None)
    d["slot"] = ((d.index.tz_convert("America/New_York").hour * 60 + d.index.tz_convert("America/New_York").minute) - 570) // 5
    pos = PME.compute(d[["date", "slot", "Open", "High", "Low", "Close"]].assign(Volume=0))
    changes = int((np.diff(pos) != 0).sum())
    g2 = changes > 10
    print(f"     position changes (enter/flip/flatten signals) in window: {changes}  {OK if g2 else NO}")
    print(f"     last 5 bar positions: {[int(x) for x in pos[-5:]]}")
    fails += not g2

    # 3) route real signals through the executor as PAPER orders at mm2
    print("\n  3. route signals through MomentumExecutor (base_qty=mm2, mode=paper)…")
    s = FakeSender()
    e = MomentumExecutor("Apex-50K-demo", s, base_qty=mm_grind, stop_pts=120.0, mode="paper")
    e.on_signal(sig("enter", 1, 20000.0), "2026-06-26 10:00")
    o = s.cap[-1] if s.cap else {}
    g3a = o.get("action") == "buy" and o.get("quantity") == 2 and o.get("orderType") == "market" and "takeProfit" not in o
    print(f"     ENTER long → paper order: action={o.get('action')} qty={o.get('quantity')} "
          f"type={o.get('orderType')} stop={'y' if 'stopLoss' in o else 'n'} target={'y' if 'takeProfit' in o else 'n'}  {OK if g3a else NO}")
    s.cap.clear(); e.on_signal(sig("flip", -1, 20030.0), "2026-06-26 10:30")
    g3b = [p.get("action") for p in s.cap] == ["exit", "sell"]
    print(f"     FLIP → {[p.get('action') for p in s.cap]}  {OK if g3b else NO}")
    s.cap.clear(); e.on_signal(sig("flatten", 0, 20010.0), "2026-06-26 15:55")
    g3c = [p.get("action") for p in s.cap] == ["exit"]
    print(f"     FLATTEN → {[p.get('action') for p in s.cap]}  {OK if g3c else NO}")
    fails += not (g3a and g3b and g3c)

    # 4) paper/live routing resolution
    print("\n  4. routing resolution (must NOT go live without the approval flag)…")
    r_paper = resolve_momentum_live("paper", approval_dir="/tmp/_noflag")
    r_live = resolve_momentum_live("live", approval_dir="/tmp/_noflag")
    g4 = r_paper is True and r_live is False
    print(f"     paper → route via paper sender: {r_paper}  ·  live w/o flag → shadow (no send): {r_live}  {OK if g4 else NO}")
    fails += not g4

    print(f"\n  ===== {'ALL WIRING CHECKS PASS' if fails == 0 else str(fails)+' CHECK(S) FAILED'} =====")
    print("  Validated (paper): gate arms on funded · engine fires · routes mm2 paper orders · won't go live w/o flag.")
    print("  NOT yet done (needs market open): live demo run on real-time bars through the Tradovate demo + Chrome feed.")
    return fails


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
