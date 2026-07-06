# 06 — VPC Artifact Audit (edge-killer checklist)

RESEARCH ONLY. LIVE HOLD ACTIVE. No code changes. Per-item evidence with file:line citations.
Where the repo has no artifact for a required check, that gap is stated plainly rather than filled in.

## 1. No-future-data (poison canary)

**PASS, quoted verbatim.** The re-cert poisons every price field on bars ≥ 2024-06-01 (multiplied
×3 + 99999) and re-runs the full backtest; a causal strategy's pre-cut trades must be byte-identical:

> `pre-cut trades base=217 poisoned=217 pnl identical=True -> CAUSAL (canary PASS)`
(mechanism at `vpc_recert_real.py:89-107`; result quoted from the vault's methodology note:
*"Look-ahead canary: PASS (217 pre-cut trades byte-identical after poisoning the future)"*
BT-20260704-1909:59). Vault also notes an earlier false-FAIL was a harness artifact (`sort_values`
instability on same-day ties), fixed with a stable mergesort compare (BT-20260704-1909:38,
implemented at `vpc_recert_real.py:101-105`) — the canary methodology itself was debugged, not the
strategy.

## 2. No timestamp lookahead (the INC-20260706-1141 defect class)

**PASS — VPC is structurally immune to the defect class, by construction, not by luck.** The
INC-20260706-1141 bug was: Profile A's model emits date/time as **strings**, and downstream code
(`run_d1c_real.attach_drift` for research, `strategy_engine_profileA.latest_signal()` for live)
re-parses those strings and re-localizes them to `America/New_York`, silently picking up future
wall-clock offset (INC-20260706-1141:22,38-45). VPC never does this:

- `grep -rin "attach_drift\|drift_gate\|run_d1c" nq_vwap_pullback.py vpc_recert_real.py
  vpc_apex_eval_sim.py vpc_combined_sim.py` → **zero matches** (confirmed live in this audit).
- VPC's own `simulate_day`/`vpc_trades_rich` never reconstruct a timestamp from a date+time string
  at all — trade rows carry `ts=idx[ei]` where `idx` is the **tz-aware DataFrame index itself**
  (`vpc_apex_eval_sim.py:48,73` — `idx = g.index`, `out.append(dict(ts=idx[ei], ...))`), i.e. the
  index-derived timestamp, exactly the fix pattern INC-20260706-1141 mandates for the live A lane
  (INC-20260706-1141:30: *"derive fill ts from the tz-aware index, not the strings"*).
- Explicitly confirmed in the salvage program's own canary #3: *"VPC engine
  (nq_vwap_pullback/vpc_apex_eval_sim) takes no A inputs; honest-A engine
  (strategy_engine_profileA/run_d1c_real) takes no VPC inputs; the two streams are computed
  independently and only combined post-hoc by ts-sort"* (A6_salvage_fill_slippage_stress.md:31,
  spot-check mechanism restated in `tools_salvage_vpc_reeval.py:38-42`).

**Conclusion: VPC is uncontaminated by INC-20260706-1141** — not merely "not yet audited," but
structurally outside the defect's code path (no string-date reconstruction anywhere in its chain).

## 3. No D1c dependence

**Confirmed.** D1c (`drift_gate.py` / `run_d1c_real`) is Profile-A-only machinery. Grep across all
four VPC modules (`nq_vwap_pullback.py`, `vpc_recert_real.py`, `vpc_apex_eval_sim.py`,
`vpc_combined_sim.py`) for `d1c|drift_gate|run_d1c` → zero references inside VPC's own signal/backtest
code (the only three hits in the salvage program are prose comments in
`tools_salvage_vpc_reeval.py` describing the *A* engine, not VPC's). VPC's signal and simulation path
(`features()` → `vpc_signals()` → `simulate_day()`, `nq_vwap_pullback.py:22-124`) takes only OHLCV +
`date`/`slot` columns; it has no drift/keep-filter stage at all.

## 4. Same-bar handling and adverse-first ordering

**Stated plainly: stop-first (conservative) on same-bar stop+target collisions**, exactly as
documented: *"Intrabar conservative: if both stop & target touched same bar, STOP fills first"*
(`nq_vwap_pullback.py:11`). Mechanically, `simulate_day` checks `L[j] <= stop` / `H[j] >= stop`
**before** updating the trailing peak/stop for that bar (`nq_vwap_pullback.py:104-115`) — the stop
check always runs first in the loop body, so a bar that would have both stopped-out and made a new
favourable extreme is resolved stop-first. There is no separate "target" leg to race against (VPC
has no fixed profit target — only a trailing stop), so the "adverse-first" question collapses to:
does a bar's stop-touch get evaluated before that same bar's peak/trail update? **Yes** — confirmed
by direct code order at lines 104-109 (long) / 110-115 (short).

**Known gap — surfaced plainly per the task brief: VPC's own backtest walks on 5m bars, not 1-minute
truth.** `simulate_day`'s stop/trail loop checks `H[j]`/`L[j]` at 5-minute bar resolution
(`nq_vwap_pullback.py:84,102-115`); the underlying data is resampled from Databento 1m to 5m before
the walker ever sees it (`vpc_recert_real.py:24,vpc_apex_eval_sim.py:32`: `resample("5min", ...)`).
This means: (a) the trailing-stop ratchet only re-evaluates every 5 minutes, so an intrabar spike-and-
reverse inside a 5m bar can be missed or mis-timed relative to true 1-minute price action, and
(b) the same-bar stop-vs-favourable-extreme ordering above is itself a 5m-bar-level convention, not a
1m-verified one. **Did salvage B4 re-walk VPC at 1-minute truth, or did it consume VPC's native 5m R
stream?** Checked directly: `B4_vpc_reeval.md`'s methodology line states *"Funnel =
tools_account_size_research.build_events / day_rows(550, 1000) / eval_run (Apex 50K spec), unchanged,
pinned"* — it consumes VPC's **native 5m-derived `(ts, R, mae_r, risk_usd)` stream** via
`vpc_apex_eval_sim.vpc_trades_rich()` (`tools_salvage_vpc_reeval.py:14-15`), not a re-walk at 1-minute
resolution. **No 1m-truth re-walk of VPC's own fill/trail logic exists anywhere in this repo** — this
is the same category of gap flagged for Profile A in `tools_1m_truth_recert.py`'s history, but VPC has
had no equivalent 1m-truth pass. This is a real, currently-open gap, not resolved by any artifact
found in this audit.

## 5. No parameter-freeze question

CFG dates from `~/trading-team/backtests/nq_vpc_final.py:8-9` ("FINAL deliverable" script):
`atr_stop=2.5, trail_atr=5.0, slot_min=6, slot_max=66, max_trades=2, slope_mult=0.3, trend_mult=0.5,
daily_stop=120` — this exact dict is what `vpc_recert_real.py:15` and `vpc_apex_eval_sim.py:24-25`
lock in as "the exact locked VPC config."

**Genuine provenance gap, surfaced (not resolved) by this audit:** the only visible parameter-search
artifact in the repo is `nq_vwap_pullback.py`'s own `main()` grid screen
(`nq_vwap_pullback.py:170-180`), which sweeps `atr_stop ∈ {1.0, 1.5, 2.0}` × `trail_atr ∈ {1.5, 2.0,
3.0}` at `slot_min=6, slot_max=60`, **with `slope_mult`/`trend_mult` left at their defaults (0.0,
0.0)** — i.e. no trend/slope gating tested at all in that sweep. The locked config's actual values
(`atr_stop=2.5`, `trail_atr=5.0`, `slot_max=66`, `slope_mult=0.3`, `trend_mult=0.5`) **do not appear
in that sweep's tested grid** (2.5 and 5.0 are outside the tested ranges; 66 ≠ 60; slope/trend gating
wasn't tested at all). No other file in `~/trading-team/backtests/` or this repo contains a visible
grid search over `slope_mult`/`trend_mult`/`slot_max=66`/`daily_stop=120` — `nq_vpc_final.py` simply
hardcodes the "FINAL" dict with no accompanying sweep output. **This means the locked config's
specific parameter provenance cannot be traced to any surviving IS/OOS or walk-forward artifact in
this codebase** — it was evidently chosen in an untracked/interactive iteration. This is a real
audit gap that should be flagged to the operator, not resolved here (no code changes, no re-running
a "discovery" sweep — out of scope for a documentation audit).

**What IS traceable and reproducible:** the re-cert (`vpc_recert_real.py`) applies that already-locked
CFG to real Databento data and reports proper IS/OOS: *"IS/OOS @ cost 0.75pt (split 2024-09-10): IS
PF 1.21 / OOS PF 1.39"* (BT-20260704-1909:58) — OOS **outperforms** IS, which is evidence against
in-sample overfit of the parameters as applied (even though the parameters' own selection history
is untraceable). The 60/40 time-split itself is *observed*, not a truly blind holdout, and the vault
says so explicitly: *"this used an observed 60/40 split = semi-blind"* (BT-20260704-1909:65) — the
IS/OOS check is real but not a frozen-holdout in the strict sense.

## 6. No cherry-picked year

**PASS.** Per-year PF at base cost, all five years reported including the weak one: *"2022 PF 1.22 ·
2023 1.07 (weak) · 2024 1.40 · 2025 1.43 · 2026 1.34 — 5/5 positive"* (BT-20260704-1909:57). 2023 is
explicitly flagged as weak, not hidden — the report keeps it in the average rather than excluding it.

## 7. Direction confound check (long/short split)

**Not published in any existing report — this audit ran the pinned recert harness directly (its own
`v.features`/`v.backtest` with the exact locked `CFG` from `vpc_recert_real.py`, zero modifications)
to check.** Full history, real Databento, locked CFG:

| direction | n | net (pt) | PF | WR |
|---|---|---|---|---|
| long | 222 | +3,035.4 | 1.35 | 48.2% |
| short | 186 | +1,883.8 | 1.23 | 40.9% |
| **total** | **408** | **+4,919.2** | **—** | **—** |

(total n=408 and net=+4,919.18 reproduce the pinned 408-trade signature exactly — canary #1 in
A6_salvage_fill_slippage_stress.md:27 — confirming this ad-hoc split used the identical certified
stream, no drift.) **Both directions are independently net-positive with PF > 1.2** — the edge is not
a long-only bull-market artifact riding NQ's 2022-2026 uptrend; the short side (which would be the
first casualty of a pure directional-bias confound) still carries a real edge, though weaker (PF 1.23
vs 1.35, WR 41% vs 48%).

## 8. Denominator (n/a standalone)

Not applicable to VPC in isolation — the denominator-artifact concern (DEC-20260706-1108) is a
funnel-level (eligible-starts vs pass-count) question that applies to the combined/eval-sim reports,
not to VPC's own 408-trade backtest, which has a fixed, unambiguous trade count. The combined-portfolio
reports do report eligible_starts alongside pass/bust/exp counts throughout
(C_combined_portfolio_test.md, B4_vpc_reeval.md), and the final verdict explicitly checked this: *"Any
denominator artifact? No — pass counts rise with pass rates everywhere; count columns reported
throughout per DEC-20260706-1108"* (E_final_verdict.md:41-42).

## 9. Fill mirage (next-bar-open market entry = chase-class)

**Confirmed chase-class by construction** (entry = next bar's `Open`, unconditional — no limit/retest,
`nq_vwap_pullback.py:96`), and this is explicitly stress-tested, not ignored. A6's "VPC-chase" damage
family adds 0.5pt / 1.0pt of extra adverse entry slippage to VPC legs only:

> C5 (VPC(800,6) alone): baseline pass 20.1/bust 16.7 → +0.5pt chase: pass 19.5/bust 16.7 → +1.0pt
> chase: pass 18.8/bust 17.5 — **pass_gt_bust stays True at every tested chase level**
(A6_salvage_fill_slippage_stress.md:115,125-126). Headline interpolation: *"c_vpc_chase (pts): >1
(not observed within tested grid)"* for every combo cell (A6_salvage_fill_slippage_stress.md:150,153,
158) — i.e. the pass>bust margin never flips within the tested 0-1pt chase-slippage range. Table 3's
framing note: *"VPC prior cert... cost ladder's own 'survived 3pt flat costs' point"*
(A6_salvage_fill_slippage_stress.md:197) — VPC's PF stays >1 even at 3pt flat round-trip cost in the
original recert ladder (`vpc_recert_real.py:68`: cost ladder tested up to 3.0pt RT, PF 1.23 at 3.0pt
per BT-20260704-1909:56). **Verdict: chase-class fill risk is real but empirically mild** at the
damage levels tested; it has not been tested beyond 1.0pt extra slippage or against genuinely adverse
NQ-specific slippage regimes (news spikes, thin overnight-adjacent RTH open) — the stress grid itself
is the limit of what's been checked.

## 10. Hidden dependence on old (invalidated) machine

**None found — confirmed independent.** VPC's signal generation (`nq_vwap_pullback.py`) and its
eval-sim replay (`vpc_apex_eval_sim.py`) import only: `numpy`, `pandas`, `os`, `nq_zarattini_5m` (for
the original Dukascopy `HALF_COST`/`load()` — used only by the un-recert'd `nq_vwap_pullback.py:18`
module-level default path, not by the real-Databento recert path which builds its own `real_rth_5m()`),
`apex_eval_eod` (`AE`, the pinned eval engine — shared with Profile A but contains no D1c/A-specific
state), and `funded_rules` (`FR`, static account specs). None of `strategy_engine_profileA.py`,
`drift_gate.py`, or `run_d1c_real` (wherever that lives) appear anywhere in VPC's import graph. The
combined-portfolio harness (`vpc_combined_sim.py`) does import `apex_eval_deployed.a_events` (`H`) to
build the **separate** A-side stream for comparison, but VPC's own stream (`vpc_unit_events()`,
`vpc_combined_sim.py:28-33`) is built independently and only merged post-hoc by timestamp sort — the
same structural independence the A6 canary #3 formally verifies (see item 2 above).

## Summary table

| Check | Result |
|---|---|
| No-future-data (poison canary) | **PASS** (217/217 byte-identical) |
| No timestamp lookahead (INC-20260706-1141 class) | **PASS — structurally immune**, no string-date reconstruction anywhere |
| No D1c dependence | **PASS** — zero references in VPC's own code |
| Same-bar / adverse-first convention | Stop-first, documented and code-confirmed; **but walked on 5m bars, not 1m truth — open gap, B4 consumed the native 5m stream, no 1m re-walk exists** |
| Parameter freeze | **Open gap** — locked CFG values untraceable to any surviving grid-search artifact; IS/OOS itself is clean (1.21→1.39) but is a semi-blind observed split, not a frozen holdout |
| No cherry-picked year | **PASS** — 5/5 positive, weak 2023 (PF 1.07) disclosed not hidden |
| Direction confound | **PASS (derived here)** — long PF 1.35/n=222, short PF 1.23/n=186, both net-positive |
| Denominator | n/a standalone; combined-level checks passed per DEC-20260706-1108 |
| Fill mirage (chase-class entry) | **Confirmed chase-class; stress-tested mild** (pass>bust holds through 1pt extra slippage / 3pt flat cost) |
| Hidden dependence on old machine | **PASS — none found**, structurally independent import graph |

## 07-04 rejection re-adjudication (before/after)

| | 2026-07-04 (against contaminated machine) | Honest re-run (salvage program) |
|---|---|---|
| Comparison baseline | Profile A, D1c-kept, $1,200 size-to-risk, certified 58.2% pass / 29.1% bust | Profile A, honest post-fix, best standalone eval cell 23.4% pass / 20.7% bust (weak-viable, not a business) |
| VPC standalone eval | Best case (size-to-risk $1,200): 33.8% pass / 47.4% bust — a losing profile vs the (contaminated) A reference | Not independently re-run as a fresh eval-role question — its role shifted to *combined* with the honest-A leg |
| VPC + A combined (funded) | A4→6 + VPC@1: pass +2.4pp / -$804 payout / post-lock bust 43.5→50.7% — **"NOT worth deploying in any stage"** | Not the metric re-tested; salvage re-tested EVAL-side combined instead |
| VPC + A combined (eval) | Not tested at this framing in the 07-04 note | A@600/6 + VPC@600/4: pass 27.8% / bust 15.5% / expire 56.7%, beats honest-A-alone margin at every tested slippage level (A6_salvage_fill_slippage_stress.md:166) |
| Verdict | **Rejected** — no eval role, marginal-to-negative funded role | **Rescued** — "the missing second leg" of a two-edge honest eval portfolio (E_final_verdict.md:16,28-29) |

**Note on scope of the reversal:** the 07-04 rejection was about VPC's *incremental value against the
specific certified-A comparator that existed that day*; the honest re-run changed which comparator
exists (the honest A machine is structurally weaker standalone), which is what flips VPC from "not
worth it" to "the missing leg" — VPC's own standalone numbers (PF ~1.29 base / 1.23 harsh, 408 trades,
5/5 years, OOS>IS, corr +0.11 to +0.29 depending on window) did not change between the two dates; only
the yardstick did.
