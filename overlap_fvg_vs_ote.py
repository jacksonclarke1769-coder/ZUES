"""
RECERT edge #1 — is 'ICT sweep->FVG continuation' (fvg50 entry) an INDEPENDENT edge,
or 'Profile A in disguise'? Profile A live = model01 entry_type='ote' (ote_depth .705).
The register candidate = model01 entry_type='fvg50'. Same sweep->MSS->FVG signal, different
entry depth. Run BOTH on REAL Databento 5m, NY-AM, and measure trade overlap by trading day
+ direction (M2 'Judas' was killed at 80.2% overlap).
"""
import os, sys
import numpy as np
import pandas as pd

ICT = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")  # locate engine/models from anywhere
sys.path.insert(0, os.path.join(ICT, "engine"))
sys.path.insert(0, os.path.join(ICT, "models"))
import data as D, htf, trade_log as TL          # noqa
import model01_sweep_mss_fvg as M1              # noqa

NY = "America/New_York"
DBNT = os.path.expanduser("~/trading-team/data/real_futures/NQ_databento_1m_5y.parquet")

COMMON = dict(sessions={"asia", "london", "ny_am", "ny_lunch", "ny_pm"},
              target_mode="fixed_rr", rr=2.0, partial=[(1, 0.5)])  # Exit#3 (live)
OTE = dict(entry_type="ote", ote_depth=0.705)
FVG = dict(entry_type="fvg50")


def real_5m():
    d1 = pd.read_parquet(DBNT)
    d1.index = (d1.index.tz_convert(NY) if d1.index.tz else d1.index.tz_localize("UTC").tz_convert(NY))
    d1 = d1.sort_index(); d1 = d1[~d1.index.duplicated(keep="first")]
    g = lambda col, how: getattr(d1[col].resample("5min", label="left", closed="left"), how)()
    df = pd.DataFrame({"Open": g("open", "first"), "High": g("high", "max"), "Low": g("low", "min"),
                       "Close": g("close", "last"), "Volume": g("volume", "sum")}).dropna(subset=["Open"])
    return df


def stats(tr, label):
    tr = tr[tr.session == "ny_am"].copy()
    r = tr["r_result"].astype(float).values
    if len(r) == 0:
        return f"  {label}: 0 trades"
    pf = r[r > 0].sum() / abs(r[r < 0].sum()) if (r < 0).any() else float("inf")
    return (f"  {label}: n={len(r)} WR={100*(r>0).mean():.1f}% PF={pf:.2f} "
            f"expR={r.mean():.3f} totR={r.sum():.1f}")


def main():
    realdf = real_5m()
    _orig = D.load_spine
    D.load_spine = lambda inst="NQ", tf="5m": realdf.copy() if (inst == "NQ" and tf == "5m") else _orig(inst, tf)
    feats = htf.build_features("NQ", "5m"); feats.index.name = "timestamp"
    print(f"real 5m: {len(realdf):,} bars {realdf.index.min().date()} -> {realdf.index.max().date()}")

    ote = M1.run(feats, "NQ", {**COMMON, **OTE})
    fvg = M1.run(feats, "NQ", {**COMMON, **FVG})
    print("\ncolumns:", list(ote.columns))
    print(stats(ote, "OTE (Profile A live)"))
    print(stats(fvg, "FVG50 (candidate)"))

    # overlap on NY-AM by (trading day, direction)
    def keyset(tr):
        tr = tr[tr.session == "ny_am"].copy()
        dcol = "date" if "date" in tr.columns else tr.columns[0]
        # direction column
        dircol = next((c for c in ["dir", "direction", "side"] if c in tr.columns), None)
        d = pd.to_datetime(tr[dcol]).dt.date.astype(str)
        if dircol is not None:
            k = d + "|" + tr[dircol].astype(str)
        else:
            k = d
        return set(k), tr, dcol, dircol

    ko, tro, dc, dircol = keyset(ote)
    kf, trf, _, _ = keyset(fvg)
    inter = ko & kf
    union = ko | kf
    print(f"\nOVERLAP (trading-day{'+dir' if dircol else ''} basis):")
    print(f"  OTE days={len(ko)}  FVG days={len(kf)}  shared={len(inter)}  union={len(union)}")
    if ko: print(f"  Jaccard = {len(inter)/len(union):.1%}   OTE-covered-by-FVG = {len(inter)/len(ko):.1%}   FVG-covered-by-OTE = {len(inter)/len(kf):.1%}")

    D.load_spine = _orig


if __name__ == "__main__":
    main()
