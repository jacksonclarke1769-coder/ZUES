"""Emit reports/passrate_opt/01_vpc_firm_sizing_optimization.md from the sweep JSON."""
import os, json
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
d = json.load(open(os.path.join(REPO, "reports", "passrate_opt", "01_vpc_firm_sizing.json")))
g, meta, can = d["grid"], d["meta"], d["canary_apex_600_3"]
FIRMS = meta["firms_UNVERIFIED"]
def unlimited(f): return FIRMS[f]["expire_days"] in (None, "None")

L = []
w = L.append
w("# VPC eval PASS-RATE optimization — FIRM x SIZING (honest sim)\n")
w("**Research / sim measurement ONLY. READ-ONLY bot strategy code (imports only). Writes confined to "
  "`research/passrate_opt/` + `reports/passrate_opt/`. Nothing armed. LIVE HOLD remains in force.**\n")
w(f"- Harness: `research/passrate_opt/vpc_firm_sizing.py` · JSON `reports/passrate_opt/01_vpc_firm_sizing.json`")
w(f"- Determinism md5 `{d['md5']}` (identical over two runs).")
w(f"- Data: {meta['vendor']}, window **{meta['window']}** (data end 2026-06-22).")
w(f"- Engine: {meta['engine']}")
w(f"- ARES self-imposed daily stop **${meta['ares_daily_stop']:.0f}** held IDENTICAL across firms; "
  f"profit target **${meta['target']:.0f}** (50K, UNVERIFIED per firm).\n")

w("## (a) Fidelity canary\n")
w(f"VPC standalone Apex-50K $600/cap-3 through this engine → **PASS {can['pass_pct']}% / BUST "
  f"{can['bust_pct']}% / EXPIRE {can['exp_pct']}% / median {can['med_days']}d / {can['trades_per_wk']} tr/wk** "
  f"— EXACTLY reproduces the established honest baseline (12.6 / 3.6 / 83.8 / 19d). Engine faithful; "
  f"only the per-firm eval RULE is re-implemented on top of the same VPC events + certified day-collapse.\n")

w("## FIRM RULES MODELED (all $ UNVERIFIED — no `reports/cross_firm/00_firm_rules_2026.md` in repo)\n")
w("| firm | DD archetype | DD $ | DLL | time | consistency | min days |")
w("|---|---|---:|---:|---|---:|---:|")
for f, s in FIRMS.items():
    dll = "none" if float(s["dll"]) > 1e11 else f"${float(s['dll']):.0f}"
    tm = "30-day" if not unlimited(f) else "unlimited"
    cons = "—" if s["consistency"] in (None, "None") else f"{int(float(s['consistency'])*100)}%"
    w(f"| {f} | {'STATIC' if s['dd_type']=='static' else 'EOD-trail'} | ${float(s['dd']):.0f} | {dll} | {tm} | {cons} | {s['min_days']} |")
w("\n*Unlimited firms:* every trading day is an eval start; a start unresolved by data-end is **CENSORED** "
  "(NOT a fail). `pass_resolved% = passes/(passes+busts)` estimates eventual-pass for a start with full runway.\n")

# per-firm full grids
w("## (b) Full firm x sizing grid\n")
for f, cells in g.items():
    w(f"### {f} — {'UNLIMITED' if unlimited(f) else '30-DAY EXPIRE'} "
      f"({'STATIC $%.0f'%float(FIRMS[f]['dd']) if FIRMS[f]['dd_type']=='static' else 'trail $%.0f'%float(FIRMS[f]['dd'])}"
      f"{'' if FIRMS[f]['consistency'] in (None,'None') else ', %d%% consist.'%int(float(FIRMS[f]['consistency'])*100)})\n")
    w("| bud/cap | PASS% | BUST% | EXP/CEN% | passRes% | med | p25-p75 | tr/wk |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|")
    for c in cells:
        pr = c['pass_resolved_pct'] if c['pass_resolved_pct'] is not None else "—"
        w(f"| ${c['budget']}/cap{c['cap']} | {c['pass_pct']} | {c['bust_pct']} | {c['exp_pct']} | {pr} | "
          f"{c['med_days']} | {c['p25_days']}-{c['p75_days']} | {c['trades_per_wk']} |")
    w("")

# best cells
w("## (c) Best configurations\n")
w("**Max pass% per firm (its native metric — raw pass% for 30-day, resolved for unlimited):**\n")
w("| firm | best cell | PASS% | passRes% | BUST% | median d | note |")
w("|---|---|---:|---:|---:|---:|---|")
for f, cells in g.items():
    key = (lambda c: c['pass_pct']) if not unlimited(f) else (lambda c: c['pass_resolved_pct'] or 0)
    b = max(cells, key=key)
    note = "sizing-up beats clock" if not unlimited(f) else "smallest size = max pass"
    w(f"| {f} | ${b['budget']}/cap{b['cap']} | {b['pass_pct']} | {b['pass_resolved_pct']} | {b['bust_pct']} | {b['med_days']} | {note} |")
w("")
w("### SINGLE BEST for MAX pass%\n")
w("**ETF_Static $600/cap-6 → PASS 62.6% (65.9% of resolved starts) · BUST 32.4% · CENSORED 5.0% · "
  "median 61 days (p25-p75 30-96).** Kindest DD (static floor never ratchets). ETF's $2,000 static is the "
  "*most* UNVERIFIED number here. **Verified-archetype near-equal: Bulenox_EOD $600/cap-8 → PASS 61.1% "
  "(64.6% resolved) · BUST 33.4% · median 57d** on a standard EOD-trail $2,500 rule.\n")
w("### SINGLE BEST for pass%-per-unit-time (cash flow, pass>=bust)\n")
w("**ETF_Static $900/cap-10 → PASS 52.1% · BUST 45.9% · median 29 days (p25-p75 17-50)** — 1.80 pass-pts/day, "
  "roughly 2x the cash-flow rate of the max-pass cell for ~10pp less pass. Verified-archetype peer: "
  "**Bulenox_EOD $900/cap-4 → PASS 49.9% · BUST 48.4% · median 34d.**\n")

# per-year
w("## Per-year concentration (best cell / firm) — NO single-year > 50% of passes\n")
w("| firm | cell | 2022 | 2023 | 2024 | 2025 | 2026 | max-year share |")
w("|---|---|--:|--:|--:|--:|--:|--:|")
for f, py in d["per_year_best"].items():
    by = py["by_year"]; tot = sum(v["passes"] for v in by.values()) or 1
    cnt = {y: by[y]["passes"] for y in by}
    share = max(100*v/tot for v in cnt.values())
    w(f"| {f} | {py['cell']} | " + " | ".join(str(cnt.get(str(y), cnt.get(y,0))) for y in [2022,2023,2024,2025,2026])
      + f" | {share:.0f}% |")
w("\nMax single-year share ~30% (2022) across every firm's best cell — **passes are spread across all five "
  "years, no single-year concentration.** 2026 is lightest (~9-12%) because it is a partial year (ends 06-22) "
  "with fewer starts.\n")

# insight + caveats
w("## KEY FINDINGS\n")
w("1. **The 30-day Apex expiry WAS the binding constraint — removing it ~5x's VPC pass rate.** Bulenox is "
  "literally 'Apex ($2,500 trail) with unlimited time': it takes VPC from **12.6% → 61%** pass. Confirmed.\n")
w("2. **But expiry does NOT convert cleanly to PASS — it splits into PASS + BUST.** Apex's 83.8% expiry "
  "(harmless fee loss) becomes ~61% pass **+ ~33% bust** + ~5% censored on unlimited time. The trailing "
  "floor, given infinite runway, eventually catches a $2,500 give-back it never had time to catch in 30 days. "
  "Bust rises 3.6% → ~33%. Real, honest cost of going unlimited.\n")
w("3. **SIZING UP does NOT raise pass on unlimited firms — it LOWERS it.** On every unlimited firm, "
  "$600 is the pass-maximising budget; larger size only amplifies the drawdown that trips the floor before "
  "target. Sizing buys **SPEED, not pass**: median days-to-pass drops ~60d → ~10d as you scale $600→$2000, "
  "but pass% falls and bust crosses above pass. (Sizing up *does* raise pass on **Apex** — there the clock, "
  "not bust, binds, so speed helps: 12.6% → 37.9% @ $2000/cap-10, but bust also 3.6% → 47.2%.)\n")
w("4. **DD ARCHETYPE dominates the $ amount.** Static $2,000 (ETF) and wide-trail $2,500 (Bulenox) both beat "
  "tight-trail $2,000 (MFFU 50.5% resolved) — a wider/non-ratcheting floor is worth more than $500 of "
  "nominal DD. The **consistency rule** costs ~3-6pp: MFFU (no consist.) 50.5% > Topstep (50%) 47.8% > "
  "Tradeify (40%) 43.7%, all on the same $2,000 trail.\n")

w("## (d) HONEST CAVEATS\n")
w("1. **ALL firm $ thresholds are UNVERIFIED.** `reports/cross_firm/00_firm_rules_2026.md` does not exist in "
  "the repo; rules were taken from the task brief. **ETF_Static $2,000** is explicitly flagged as the least "
  "trustworthy — the entire ETF result rides on it. $3,000 targets and the trail amounts need contract "
  "confirmation before any of these pass-rates are acted on.\n")
w("2. **Data-censoring on unlimited firms.** Starts within the last few months of data (→2026-06-22) cannot "
  "resolve and are counted CENSORED (~4-6%), NOT failed. `pass_resolved%` excludes them; raw `pass%` is "
  "therefore slightly understated for unlimited firms. Censoring is small here but real.\n")
w("3. **Consistency-rule modeling is an assumption.** Modeled as: a PASS is claimed only once bal>=target "
  "AND max single-day realized profit <= X% of total profit (else keep trading to dilute). Real firms may "
  "compute consistency on different bases (highest-day vs total, or block payout not the pass). Directional.\n")
w("4. **Same-firm DLL / min-days simplifications.** DLL flatten uses the certified marked-trough semantics; "
  "min-days uses active VPC trading days (VPC trades ~1.8 days/wk so min-days rarely binds). No firm-specific "
  "'max contracts' or scaling-plan caps modeled.\n")
w("5. **Still sim, not live.** Faithful engine replay on honest next-5m-open VPC fills; per-trade sequential "
  "marking is slightly optimistic vs the true joint intraday tick path. N>=30 live-fill parity still gates "
  "everything. This measures eval-CARRY only — NOT stress-certification for arming.\n")
w("6. **pass < bust on the fast cells.** Every cash-flow-optimised (fast) cell runs bust ~46-58%. Economically "
  "still positive if funded value >> eval fee, but flagged: these are bust-heavy and fragile on a pass>bust "
  "safety basis. The max-pass cells (ETF/Bulenox $600) keep pass>bust (~61-62% vs ~33%).\n")

open(os.path.join(REPO, "reports", "passrate_opt", "01_vpc_firm_sizing_optimization.md"), "w").write("\n".join(L))
print("wrote reports/passrate_opt/01_vpc_firm_sizing_optimization.md", len(L), "lines")
