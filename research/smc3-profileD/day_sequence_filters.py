"""
Day-sequence / repeat-entry filter battery on the SMC3 NY-AM (09:30-12:00 ET)
ledger. Each rule is applied ISOLATED vs the same baseline via a CAUSAL,
sequential day-replay: walk each day's trades in entry-time order, and before
each trade decide skip/keep using ONLY the outcomes of trades ALREADY TAKEN
that day (a skipped trade contributes no outcome and is not "prior" for
later decisions — this matters for cooldown / stop-after-loss state, which
is why state is rebuilt from the TAKEN list, not the raw historical list).

Caveat (kept in the state, reported upstream): this is a DROP-ONLY replay.
It cannot add trades that the original single-position engine skipped while
a position was open — if a filter causes an earlier trade to be dropped, any
NEW signal that the original backtest was blocked from taking (because it
was in that now-hypothetically-absent position) is still absent here. This
biases filter results slightly conservative (can only remove R, never add
back R from newly-freed windows).

Writes reports/ifvg_optimisation/09_day_sequence_filters.csv and a compact .md.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

LEDGER = "/Users/jacksonclarke/trading-team/backtests/zeus-occ-optimize/smc3/reports/ifvg_optimisation/09_sequence_ledger.csv"
OUT_CSV = "/Users/jacksonclarke/trading-team/backtests/zeus-occ-optimize/smc3/reports/ifvg_optimisation/09_day_sequence_filters.csv"
OUT_MD = "/Users/jacksonclarke/trading-team/backtests/zeus-occ-optimize/smc3/reports/ifvg_optimisation/09_day_sequence_filters.md"

N_BASE = 1624


def load():
    t = pd.read_csv(LEDGER, parse_dates=["entry_time", "exit_time"])
    t["et_date"] = pd.to_datetime(t["et_date"])
    return t


def replay(t: pd.DataFrame, rule) -> pd.DataFrame:
    """rule(taken_list, row) -> True means SKIP this trade.
    taken_list: list of dicts {R, win, dir, entry_time, exit_time} for
    trades already taken THIS DAY, in order."""
    kept_rows = []
    for et_date, day in t.groupby("et_date", sort=False):
        taken = []
        for _, row in day.iterrows():
            if rule(taken, row):
                continue
            kept_rows.append(row)
            taken.append({
                "R": row["R"], "win": row["win"], "dir": row["dir"],
                "entry_time": row["entry_time"], "exit_time": row["exit_time"],
            })
    if not kept_rows:
        return t.iloc[0:0]
    return pd.DataFrame(kept_rows)


def metrics(sub: pd.DataFrame, full: pd.DataFrame) -> dict:
    n = len(sub)
    if n == 0:
        return dict(n=0, days=0, tpd=0, wr=np.nan, pf=np.nan, avgR=np.nan,
                     totR=0.0, maxdd=0.0, yrs_pos=0, ex2024=np.nan, exfri=np.nan,
                     exboth=np.nan, reduction=1.0, r_removed=full["R"].sum(),
                     r_kept=0.0, bleed_days_improved="n/a", gooddays_survive="n/a")
    days = sub["et_date"].nunique()
    wr = sub["win"].mean() * 100
    gw = sub.loc[sub.R > 0, "R"].sum()
    gl = -sub.loc[sub.R < 0, "R"].sum()
    pf = gw / gl if gl > 0 else np.inf
    avgR = sub["R"].mean()
    totR = sub["R"].sum()
    cum = sub.sort_values("entry_time")["R"].cumsum()
    dd = (cum - cum.cummax()).min()
    yr = sub["entry_time"].dt.tz_convert("UTC").dt.year
    yr_r = sub.groupby(yr)["R"].sum()
    yrs_pos = int((yr_r > 0).sum())
    ex2024 = sub.loc[yr != 2024, "R"].mean() if (yr != 2024).any() else np.nan
    exfri = sub.loc[sub["dow"] != "Friday", "R"].mean() if (sub["dow"] != "Friday").any() else np.nan
    both_mask = (yr != 2024) & (sub["dow"] != "Friday")
    exboth = sub.loc[both_mask, "R"].mean() if both_mask.any() else np.nan
    reduction = 1 - n / N_BASE
    r_removed = full["R"].sum() - totR
    r_kept = totR

    # bleed-days-reduced / good-days-preserved: compare worst-10 / best-10
    # days (by day R) of the FULL baseline — do those days' R improve
    # (less negative / preserved) under this filter?
    full_day_r = full.groupby("et_date")["R"].sum()
    worst10 = full_day_r.nsmallest(10).index
    best10 = full_day_r.nlargest(10).index
    sub_day_r = sub.groupby("et_date")["R"].sum()
    worst10_full = full_day_r.loc[full_day_r.index.isin(worst10)].sum()
    worst10_sub = sub_day_r.reindex(worst10).fillna(0).sum()
    best10_full = full_day_r.loc[full_day_r.index.isin(best10)].sum()
    best10_sub = sub_day_r.reindex(best10).fillna(0).sum()
    bleed_flag = "yes" if worst10_sub > worst10_full + 1e-9 else "no"
    good_flag = "yes" if best10_sub >= best10_full - 1e-9 else "no"

    return dict(n=n, days=days, tpd=n / days if days else np.nan, wr=wr, pf=pf,
                avgR=avgR, totR=totR, maxdd=dd, yrs_pos=yrs_pos, ex2024=ex2024,
                exfri=exfri, exboth=exboth, reduction=reduction * 100,
                r_removed=r_removed, r_kept=r_kept,
                bleed_days_improved=bleed_flag, gooddays_survive=good_flag)


def denom_flag(sub: pd.DataFrame, m: dict) -> str:
    if m["n"] == 0:
        return "REJECTED_DENOMINATOR_TRICK (n=0)"
    flags = []
    if m["reduction"] > 70:
        flags.append("reduction>70%")
    if m["n"] < 50:
        flags.append("n<50")
    yr = sub["entry_time"].dt.tz_convert("UTC").dt.year
    yr_r = sub.groupby(yr)["R"].sum()
    if m["totR"] > 0 and len(yr_r) and yr_r.max() > m["totR"]:
        flags.append("profit from one year")
    non_fri = sub[sub["dow"] != "Friday"]
    if m["totR"] > 0 and len(non_fri) and non_fri["R"].sum() <= 0:
        flags.append("Friday-only")
    return "REJECTED_DENOMINATOR_TRICK (" + ",".join(flags) + ")" if flags else "ok"


# --------------------------------------------------------------------- #
# Rule builders. Each returns a function(taken, row) -> bool (skip?)
# --------------------------------------------------------------------- #

def rule_max_trades(cap):
    def f(taken, row):
        return len(taken) >= cap
    return f


def rule_signal_only(max_sig):
    def f(taken, row):
        return (len(taken) + 1) > max_sig
    return f


def rule_signal_slice(sig_num):
    # standalone: keep ONLY the k-th signal of each day (not cumulative).
    # Uses the row's TRUE historical signal_num (not len(taken)+1) because
    # this rule causes an INTERIOR skip (signals before sig_num are
    # dropped), so the "trades taken so far" counter would under-count.
    def f(taken, row):
        return row["signal_num"] != sig_num
    return f


def rule_signal_slice_plus(sig_num_min):
    def f(taken, row):
        return row["signal_num"] < sig_num_min
    return f


def rule_stop_after_losses(n_losses):
    def f(taken, row):
        losses = sum(1 for x in taken if not x["win"])
        return losses >= n_losses
    return f


def rule_stop_after_cum(thresh):
    def f(taken, row):
        cum = sum(x["R"] for x in taken)
        return cum <= thresh
    return f


def rule_stop_day_if_first_loses():
    def f(taken, row):
        if not taken:
            return False
        return not taken[0]["win"]
    return f


def rule_stop_if_first_two_lose():
    def f(taken, row):
        if len(taken) < 2:
            return False
        return (not taken[0]["win"]) and (not taken[1]["win"])
    return f


def rule_first_loses_before_10_stop():
    def f(taken, row):
        if not taken:
            return False
        first = taken[0]
        if first["win"]:
            return False
        # 10:00 ET cutoff -- entry_time stored tz-aware UTC; convert
        et = first["entry_time"].tz_convert("America/New_York")
        return et.hour < 10 or (et.hour == 10 and et.minute == 0)
    return f


def rule_first_wins_allow_n_more(n_more):
    def f(taken, row):
        if not taken:
            return False
        first = taken[0]
        if not first["win"]:
            return True  # stop entirely after first loses
        return len(taken) > n_more  # allow n_more additional trades
    return f


def rule_profit_lock_R(thresh):
    def f(taken, row):
        cum = sum(x["R"] for x in taken)
        return cum >= thresh
    return f


def rule_profit_lock_wins(n_wins):
    def f(taken, row):
        wins = sum(1 for x in taken if x["win"])
        return wins >= n_wins
    return f


def rule_dir_lock_first():
    def f(taken, row):
        if not taken:
            return False
        return row["dir"] != taken[0]["dir"]
    return f


def rule_no_opp_after_loss():
    def f(taken, row):
        if not taken:
            return False
        last = taken[-1]
        return (not last["win"]) and (row["dir"] != last["dir"])
    return f


def rule_no_opp_within_min(minutes):
    def f(taken, row):
        if not taken:
            return False
        last = taken[-1]
        if row["dir"] == last["dir"]:
            return False
        mins = (row["entry_time"] - last["entry_time"]).total_seconds() / 60.0
        return mins < minutes
    return f


def rule_cooldown_exit(minutes):
    def f(taken, row):
        if not taken:
            return False
        last = taken[-1]
        mins = (row["entry_time"] - last["exit_time"]).total_seconds() / 60.0
        return mins < minutes
    return f


def rule_cooldown_entry(minutes):
    def f(taken, row):
        if not taken:
            return False
        last = taken[-1]
        mins = (row["entry_time"] - last["entry_time"]).total_seconds() / 60.0
        return mins < minutes
    return f


def build_rules():
    rules = []
    # A. Max trades/day
    for cap in (1, 2, 3, 4):
        rules.append((f"A.max_trades_{cap}", rule_max_trades(cap)))
    rules.append(("A.max_trades_unlimited(baseline)", lambda taken, row: False))

    # B. Signal-order cumulative + standalone
    rules.append(("B.signal_1_only", rule_signal_only(1)))
    rules.append(("B.signal_1-2", rule_signal_only(2)))
    rules.append(("B.signal_1-3", rule_signal_only(3)))
    rules.append(("B.standalone_sig#1", rule_signal_slice(1)))
    rules.append(("B.standalone_sig#2", rule_signal_slice(2)))
    rules.append(("B.standalone_sig#3", rule_signal_slice(3)))
    rules.append(("B.standalone_sig#4+", rule_signal_slice_plus(4)))

    # C. Stop-after-loss
    rules.append(("C.stop_after_1_loss", rule_stop_after_losses(1)))
    rules.append(("C.stop_after_2_losses", rule_stop_after_losses(2)))
    rules.append(("C.stop_daycum<=-1", rule_stop_after_cum(-1.0)))
    rules.append(("C.stop_daycum<=-1.5", rule_stop_after_cum(-1.5)))
    rules.append(("C.stop_daycum<=-2", rule_stop_after_cum(-2.0)))

    # D. Continue-only-after-win variants
    rules.append(("D.stop_day_if_first_loses", rule_stop_day_if_first_loses()))
    rules.append(("D.stop_if_first_two_lose", rule_stop_if_first_two_lose()))
    rules.append(("D.first_loses_before_10_stop", rule_first_loses_before_10_stop()))
    rules.append(("D.first_wins_allow_1_more", rule_first_wins_allow_n_more(1)))
    rules.append(("D.first_wins_allow_2_more", rule_first_wins_allow_n_more(2)))

    # E. Profit lock
    rules.append(("E.stop_day+1R", rule_profit_lock_R(1.0)))
    rules.append(("E.stop_day+1.5R", rule_profit_lock_R(1.5)))
    rules.append(("E.stop_day+2R", rule_profit_lock_R(2.0)))
    rules.append(("E.stop_after_1_win", rule_profit_lock_wins(1)))
    rules.append(("E.stop_after_2_wins", rule_profit_lock_wins(2)))

    # F. Direction lock
    rules.append(("F.dir_lock_first_sweep", rule_dir_lock_first()))
    rules.append(("F.no_opp_after_loss", rule_no_opp_after_loss()))
    rules.append(("F.no_opp_within_30min_entry", rule_no_opp_within_min(30)))
    rules.append(("F.no_opp_within_60min_entry", rule_no_opp_within_min(60)))

    # G. Cooldown
    for m in (5, 10, 20, 30, 45, 60):
        rules.append((f"G.cooldown_exit_{m}min", rule_cooldown_exit(m)))
    for m in (10, 20, 30, 60):
        rules.append((f"G.cooldown_entry_{m}min", rule_cooldown_entry(m)))

    return rules


def main():
    full = load()
    rules = build_rules()

    rows = []
    for name, rule in rules:
        sub = replay(full, rule)
        m = metrics(sub, full)
        flag = denom_flag(sub, m) if m["n"] else "REJECTED_DENOMINATOR_TRICK (n=0)"
        rows.append(dict(rule=name, **m, denom_flag=flag))

    res = pd.DataFrame(rows)
    res.to_csv(OUT_CSV, index=False)

    # sort by ex-2024 avgR for the .md (gate that killed the baseline)
    res_sorted = res.sort_values("ex2024", ascending=False)

    lines = []
    P = lines.append
    P("# 09 — Day-sequence / repeat-entry filter battery (SMC3 NY-AM, causal drop-only replay)\n")
    P(f"Baseline (unlimited/no filter): n={N_BASE}, sorted by **ex-2024 avgR** (the gate that killed the raw baseline).\n")
    P("| rule | n | days | tr/day | WR% | PF(R) | avgR | totR | maxDD(R) | yrs+/6 | ex2024_avgR | exFri_avgR | exBoth_avgR | reduc% | R_removed | R_kept | bleed_days_improved | gooddays_survive | flag |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in res_sorted.iterrows():
        pf_s = "inf" if r["pf"] == np.inf else f"{r['pf']:.3f}" if pd.notna(r["pf"]) else "-"
        P(f"| {r['rule']} | {r['n']:.0f} | {r['days']:.0f} | {r['tpd']:.2f} | "
          f"{r['wr']:.1f} | {pf_s} | {r['avgR']:+.3f} | {r['totR']:+.1f} | "
          f"{r['maxdd']:.1f} | {r['yrs_pos']:.0f}/6 | {r['ex2024']:+.3f} | "
          f"{r['exfri']:+.3f} | {r['exboth']:+.3f} | {r['reduction']:.1f}% | "
          f"{r['r_removed']:+.1f} | {r['r_kept']:+.1f} | {r['bleed_days_improved']} | "
          f"{r['gooddays_survive']} | {r['denom_flag']} |")
    P("")
    P("_Method: sequential per-ET-day replay; a rule's skip decision at each trade uses only "
      "the outcomes of trades ALREADY TAKEN that day (skipped trades are not 'prior' for later "
      "decisions). Drop-only: cannot recover R from windows the original single-position engine "
      "was blocked from trading. bleed_days_improved = do the historical worst-10 days (by day R) "
      "sum to a less-negative R under this filter? gooddays_survive = do the historical best-10 "
      "days retain at least their full R (i.e. none of their trades were skipped)?_")

    with open(OUT_MD, "w") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"[written] {OUT_CSV}")
    print(f"[written] {OUT_MD}")
    print(res_sorted.head(10).to_string())


if __name__ == "__main__":
    main()
