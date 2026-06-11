"""
Funded-account campaign sim for the dashboard — MyFundedFutures-style EOD-trailing rules.
Produces the full sizing MATRIX: 4 account sizes x 10 contract sizes (1-5 MNQ, 1-5 NQ), with
accounts passed / didn't-pass, net, per-account, funded blows, and AVG TIME TO PASS (days).
Pure/offline (no broker). Run over the FULL 2019+ sample for a conservative read.

$ convention matches the validated framework (r_result nets slip + $4 RT comm at NQ scale):
  N MNQ -> dpp=2N, comm_extra=1.5N ;  N NQ -> dpp=20N, comm_extra=0.
"""
import numpy as np

RNG = np.random.default_rng(909)

ACCOUNTS = {            # start, target, EOD trailing DD, payout buffer, payout cap, eval fee/attempt
    "50K":  dict(start=50_000,  tgt=3_000,  dd=2_000, buf=2_100, cap=5_000,  fee=165),
    "100K": dict(start=100_000, tgt=6_000,  dd=3_000, buf=4_200, cap=10_000, fee=265),
    "150K": dict(start=150_000, tgt=9_000,  dd=4_500, buf=6_300, cap=15_000, fee=375),
    "200K": dict(start=200_000, tgt=12_000, dd=6_000, buf=8_400, cap=20_000, fee=500),   # extrapolated
}
CONTRACTS = [("1 MNQ", 2, 1.5), ("2 MNQ", 4, 3.0), ("3 MNQ", 6, 4.5), ("4 MNQ", 8, 6.0), ("5 MNQ", 10, 7.5),
             ("1 NQ", 20, 0.0), ("2 NQ", 40, 0.0), ("3 NQ", 60, 0.0), ("4 NQ", 80, 0.0), ("5 NQ", 100, 0.0)]
WIN_DAY, MIN_WIN, ECONS, MIN_DAYS = 200.0, 5, 0.5, 2


class Acct:
    def __init__(s, R, funded=False):
        s.R = R; s.bal = s.peakE = float(R["start"]); s.maxday = s.bestday = 0.0
        s.td = s.wd = 0; s.funded = funded; s.dead = False; s.payouts = 0; s.paid = 0.0
    def line(s):
        return min(s.peakE - s.R["dd"], s.R["start"])
    def day(s, g):
        if s.dead: return None
        ds = eq = s.bal
        for pnl, mae, _ in g:
            if eq + mae <= s.line(): s.dead = True; return "BREACH"
            eq += pnl
        dp = eq - ds
        s.bal = eq; s.peakE = max(s.peakE, s.bal); s.td += 1
        if dp >= WIN_DAY: s.wd += 1
        s.maxday = max(s.maxday, dp); s.bestday = max(s.bestday, dp)
        if not s.funded:
            if s.bal >= s.R["start"] + s.R["tgt"] and s.maxday <= ECONS * (s.bal - s.R["start"]) and s.td >= MIN_DAYS:
                return "PASS"
        else:
            prof = s.bal - s.R["start"]
            if s.wd >= MIN_WIN and prof >= s.R["buf"]:
                amt = min(prof, s.R["cap"])
                if amt >= 250:
                    s.payouts += 1; s.paid += amt; s.bal -= amt
                    s.peakE = max(float(s.R["start"]), s.bal); s.wd = 0; s.bestday = 0.0; return "PAYOUT"
        return None


def daygroups(tr, dpp, comm):
    out = []
    for _, g in tr.groupby("date"):
        out.append([(t.r_result * abs(t.entry - t.stop) * dpp - comm,
                     t.mae_r * abs(t.entry - t.stop) * dpp, 0.0) for _, t in g.iterrows()])
    return out


def campaign(days, R):
    """Continuous: eval -> on PASS a funded account + a fresh eval; on BREACH restart the eval."""
    eval_starts = 1; passed = failed = blows = 0
    ev = Acct(R); funded = []; ev_start = 0; pass_times = []
    for k, g in enumerate(days):
        for fa in funded:
            if fa.day(g) == "BREACH": blows += 1
        r = ev.day(g)
        if r == "PASS":
            passed += 1; pass_times.append(k - ev_start + 1)
            funded.append(Acct(R, True)); ev = Acct(R); ev_start = k + 1; eval_starts += 1
        elif r == "BREACH":
            failed += 1; ev = Acct(R); ev_start = k + 1; eval_starts += 1
    paid = sum(f.paid for f in funded)
    return dict(passed=passed, failed=failed, blows=blows, payouts=sum(f.payouts for f in funded),
                paid=paid, fees=eval_starts * R["fee"],
                avg_pass_td=(float(np.mean(pass_times)) if pass_times else None))


def pass_prob(days, R, n=1500):
    """Bootstrap per-attempt chance of PASSING one eval (resolves to pass or breach)."""
    L = len(days)
    if L == 0:
        return None
    pas = bre = 0
    for _ in range(n):
        ev = Acct(R)
        for k in RNG.integers(0, L, L):
            r = ev.day(days[k])
            if r == "PASS":
                pas += 1; break
            if r == "BREACH":
                bre += 1; break
    tot = pas + bre
    return round(100 * pas / tot, 1) if tot else None


def sizing_matrix(tr):
    """tr = Profile A v2 ny_am trades (use the FULL 2019+ sample). Returns {account: [rows]}."""
    horizon = max(1, tr.date.nunique())
    cal_per_td = max(1.0, (tr.ts.max() - tr.ts.min()).days) / horizon
    years = max(1e-9, (tr.ts.max() - tr.ts.min()).days / 365.0)
    risk_pts = (tr.entry - tr.stop).abs().mean()
    out = {}
    for acc, R in ACCOUNTS.items():
        rows = []
        for label, dpp, comm in CONTRACTS:
            days = daygroups(tr, dpp, comm)
            c = campaign(days, R)
            net = round(c["paid"] - c["fees"])
            rows.append(dict(size=label, passed=c["passed"], failed=c["failed"],
                             funded_blows=c["blows"], payouts=c["payouts"],
                             net=net, net_yr=round(net / years),
                             per_account=(round(net / c["passed"]) if c["passed"] else 0),
                             avg_pass_days=(round(c["avg_pass_td"] * cal_per_td) if c["avg_pass_td"] else None),
                             pass_pct=pass_prob(days, R),
                             risk=round(risk_pts * dpp), fee=R["fee"], dd=R["dd"]))
        out[acc] = rows
    return out
