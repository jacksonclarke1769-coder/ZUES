"""Correlation matrix: survivors vs each other, vs Profile A OTE, vs VPC/Profile B.
Daily-R Pearson + fill-day Jaccard overlap, restricted to overlapping dates
(PREREG §5 item 3 / §7)."""
import json

import numpy as np
import pandas as pd

from survey_engine import SPLIT_TS, WINDOW_END

PA_CSV = "/Users/jacksonclarke/trading-team/research/atlas/profile_a_edge/outputs/signals_583_classified.csv"
VPC_CSV = "/Users/jacksonclarke/trading-team/research/regime_edge_stacking/leads/vpc_600_4_5m_native_ledger.csv"


def daily_r_series(dates, Rs, start, end):
    dt_index = pd.DatetimeIndex(pd.to_datetime(pd.Series(dates).to_numpy()))
    if dt_index.tz is None:
        dt_index = dt_index.tz_localize("UTC")
    else:
        dt_index = dt_index.tz_convert("UTC")
    df = pd.DataFrame({"date": dt_index.normalize(), "R": np.asarray(Rs)})
    g = df.groupby("date")["R"].sum()
    idx = pd.date_range(start.normalize(), end.normalize(), freq="D", tz="UTC")
    return g.reindex(idx, fill_value=0.0)


def load_cell_daily(key, start, end):
    tr = pd.read_json(f"trade_ledgers/holdout_{key}.json")
    if not len(tr):
        return daily_r_series([], [], start, end)
    fill_ts = pd.to_datetime(tr["fill_ts"], utc=True)
    return daily_r_series(fill_ts, tr["R"].to_numpy(float), start, end)


def load_profile_a_daily(start, end):
    df = pd.read_csv(PA_CSV)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, format="mixed")
    df = df[df["achievable"] == True]  # noqa: E712
    df = df[(df["ts"] >= start) & (df["ts"] < end)]
    return daily_r_series(df["ts"], df["R"].to_numpy(float), start, end), len(df)


def load_vpc_daily(start, end):
    df = pd.read_csv(VPC_CSV)
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True, format="mixed")
    df = df[(df["entry_time"] >= start) & (df["entry_time"] < end)]
    return daily_r_series(df["entry_time"], df["R"].to_numpy(float), start, end), len(df)


def jaccard(a: pd.Series, b: pd.Series) -> float:
    A = set(a[a != 0].index)
    B = set(b[b != 0].index)
    if not A and not B:
        return 0.0
    return len(A & B) / len(A | B) if (A | B) else 0.0


def pearson(a: pd.Series, b: pd.Series):
    if a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a.to_numpy(), b.to_numpy())[0, 1])


def main():
    with open("gate_abc_survivors.json") as f:
        survivors = json.load(f)

    start, end = SPLIT_TS, WINDOW_END
    series = {k: load_cell_daily(k, start, end) for k in survivors}
    pa_series, pa_n = load_profile_a_daily(start, end)
    vpc_series, vpc_n = load_vpc_daily(start, end)
    series["ProfileA_OTE"] = pa_series
    series["VPC_ProfileB"] = vpc_series

    keys = list(series.keys())
    mat_pearson = {a: {} for a in keys}
    mat_jaccard = {a: {} for a in keys}
    for a in keys:
        for b in keys:
            mat_pearson[a][b] = pearson(series[a], series[b])
            mat_jaccard[a][b] = round(jaccard(series[a], series[b]), 4)

    # decorrelation score per survivor = mean |corr| vs (other survivors + PA + VPC), excluding self
    decorr = {}
    for k in survivors:
        others = [x for x in keys if x != k]
        vals = [abs(mat_pearson[k][o]) for o in others if mat_pearson[k][o] is not None]
        decorr[k] = round(float(np.mean(vals)), 4) if vals else None

    out = dict(survivors=survivors, profile_a_n_achievable_in_window=pa_n, vpc_n_in_window=vpc_n,
               pearson_daily_R=mat_pearson, jaccard_fill_day=mat_jaccard,
               mean_abs_corr_vs_others=decorr)
    with open("correlation_result.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2)[:4000])


if __name__ == "__main__":
    main()
