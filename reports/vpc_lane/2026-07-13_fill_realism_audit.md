# VPC Lane — Fill-Realism Adversarial Audit (2026-07-13)

RESEARCH ONLY. LIVE HOLD ACTIVE. Read-only audit; nothing armed, no certified sim modified.
New file only: `research/vpc_slippage_stress.py`. Mandate: assume a hidden fill artifact and try to
refute VPC as a deployable +EV lane, the way Profile A's "recovery" was shown to be a fill mirage.

## TOP-LINE VERDICT: **DEPLOYABLE-+EV-CONFIRMED (fill-artifact hunt: NEGATIVE)**

Every one of the four canonical artifact classes that killed the other lanes was checked and
**none of them is present in VPC**. VPC is structurally the OPPOSITE of Profile A: it is a
market-order, trailing-runner strategy whose edge lives in the right tail, so it is nearly immune
to the per-fill quality problems that sink limit-fill / scalp strategies.

- Honest standalone VPC PF (0.75pt base RT cost): **1.294 points-PF / 1.366 R-PF (5m native)**;
  **1.318 / 1.396 (1m-truth re-walk)**; dollar trade-level PF **1.33–1.37** across the eval funnel.
- Emit-vs-fill timing gap: **0 minutes / 0 bars** (signal emits AT bar i close; fill is bar i+1
  open, a market order). No Profile-A stale-limit gap.
- Trailing-stop same-bar sequencing: **CONSERVATIVE** (stop checked before peak update, both sims).
- Slippage breakeven: PF crosses 1.0 only at **~24 ticks/side (+12.25pt RT)**. At a realistic
  +1/+2 ticks/side the PF is 1.28 / 1.27.

Suite: `968 passed, 1 skipped` (`.venv/bin/python -m pytest -q`, 164s).

---

## FAILURE MODE 1 — Stale / delayed emission (the Profile A parallel): **CLOSED**

Profile A's mirage was a resting limit that emitted ~40min stale so the intended fill was already
gone. VPC cannot have that failure mode by construction:

- The trigger fires on the just-closed bar `i = n-1` and the intended fill is bar i+1's **market**
  order at open — `strategy_engine_vpc.py:163-217` (`i = n - 1` at line 178; `entry_bar_offset=1`
  at line 213). This exactly matches the certified generator, which appends `(i+1, d, stop)` and
  fills `entry = O[ei]` (`nq_vwap_pullback.py:66-72, 92-95`).
- Live emission is **synchronous with bar close**: the live loop calls `add_bar(...)` then
  `latest_signal()` in the same per-closed-5m-bar handler that drives Profiles A and B —
  `auto_live.py:1358-1359`. There is no batching, no resting order, no re-poll delay. The
  emit-time == the signal-bar close; the fill window to the next 5m open is 0–5 minutes for a
  market order.
- Timing/causality of `_day_features` verified causal: grouped-by-date cumulative VWAP, `rolling(14)`
  ATR, `shift(6)` vwap6 — all backward-looking (`strategy_engine_vpc.py:151-161`,
  `nq_vwap_pullback.py:24-42`). Timestamp derived only from the tz-aware buffer index
  (`_derive_vpc_instant`, `strategy_engine_vpc.py:101-117`), the INC-20260706-1141 defect class is
  fenced off with a fail-closed raise.
- Benign indexing note: certified `vpc_signals` loops `for i in range(n-1)` (never the day's final
  bar) whereas live evaluates each closing bar as `i=n-1`. This difference is **inert** because the
  `slot_max=66` gate (`nq_vwap_pullback.py:52`, live `strategy_engine_vpc.py:183`) excludes the only
  bar where the ranges differ (day's last slot 77 >> 66). No signal-set divergence.

Quantified R in a late-emitting class: **0** — there is no class of VPC signals that emits after
its i+1 fill; the market-order model makes "next-bar open" attainable in every case.

## FAILURE MODE 2 — Trailing-stop intrabar artifact (the Asian-Range killer): **CLOSED**

The team's Asian-Range strategy collapsed (TV PF 2.026 → ~0.9) when a trailing stop turned out to
be an intrabar-fill artifact — finer resolution destroyed the edge. VPC is the inverse:

- **Same-bar sequencing is CONSERVATIVE, not optimistic.** In both exit loops the stop is checked
  against the stop level coming *into* the bar BEFORE that bar's high/low is folded into the peak:
  - Certified recert sim: `vpc_apex_eval_sim.py:60-70` — `if L[j] <= stop: exit` (line 64) executes
    *before* `peak = max(peak, H[j]); ns = peak - trail_atr*A[j]` (line 65). A single bar can
    NEVER both extend the trail to its own high and dodge the stop on that same high.
  - Certified generator: `nq_vwap_pullback.py:97-104`, identical ordering (docstring line 12:
    "check stop first (conservative)").
- **Finer resolution INCREASES PF, it does not collapse it.** The 1m-truth re-walk
  (`tools_vpc_1m_truth.py`, report `reports/vpc_standalone_audit/09_vpc_1m_truth_rewalk.md`) moves
  points-PF 1.294 → 1.318 and R-PF 1.366 → 1.396. This is the diagnostic signature of a NON-artifact:
  an intrabar mirage gets *worse* under finer fills; VPC gets marginally *better* (mechanism:
  1m-peak uses 1m close ≤ 5m high, so the trail ratchets slightly slower and lets winners run —
  a monotonic, look-ahead-free ratchet, runtime-asserted in the re-walk). Only 11/408 trades change
  win/loss outcome; delta-median 0.
- PF impact of imposing conservative sequencing: **none required** — the current logic already is
  conservative. There is no optimistic-sequencing PF to claw back.

## FAILURE MODE 3 — Cost / slippage realism: **ROBUST (breakeven ~24 ticks/side)**

- Cost model: a flat **0.75pt round-trip** (0.375/side, `HALF_COST` at `nq_zarattini_5m.py:17`,
  `RT_COST` at `nq_vwap_pullback.py:22`) is subtracted once per trade at exit
  (`nq_vwap_pullback.py:72`, `vpc_apex_eval_sim.py:72`). The market entry fills at the exact
  next-bar open and the trailing exit at the exact stop price, i.e. the 0.375/side is the ONLY
  slippage+commission modeled on each leg — a legitimate concern, so I stressed it directly.
- `research/vpc_slippage_stress.py` re-prices all 408 certified trades with extra slippage on BOTH
  legs:

  | extra RT | ticks/side | PF_pts | WR% | expR | net_pts |
  |---|---|---|---|---|---|
  | +0.00 | 0.0 | 1.294 | 44.9 | 0.1374 | 4919 |
  | +0.50 | 1.0 | 1.280 | 44.4 | 0.1316 | 4715 |
  | +1.00 | 2.0 | 1.266 | 44.1 | 0.1258 | 4511 |
  | +2.00 | 4.0 | 1.239 | 44.1 | 0.1142 | 4103 |
  | +4.00 | 8.0 | 1.186 | 42.6 | 0.0911 | 3287 |

- **PF crosses 1.0 only at +12.25pt RT ≈ 24.5 ticks/side (6.1pt/side).** Reason: VPC is a
  right-tail trailing runner (best trade +808pt, avg net +12.1pt/trade, WR 45% with avg win >> avg
  loss). A fixed per-fill cost is trivial against a large-winner distribution — the exact opposite
  of Profile A's fill-quality-is-everything mean-reversion. Even doubling to +2 ticks/side the lane
  is PF 1.27.

## FAILURE MODE 4 — Certified-numbers provenance: **COST-INCLUSIVE, CONFIRMED**

- The 0.75pt RT cost is baked into every certified number (`RT_COST` subtracted in
  `simulate_day`/`vpc_trades_rich`). These are NOT costless figures.
- Standalone VPC (`reports/vpc_standalone_audit/09_vpc_1m_truth_rewalk.md`): 408 trades, WR 45%,
  points-PF 1.29 (5m) / 1.32 (1m), R-PF 1.37 / 1.40, expR ~0.14.
- Eval funnel dollar-PF (`reports/new_edge_salvage_program/B4_vpc_reeval.md`, shortlist cells
  500–800 budget): 1.31–1.37; baseline reproduction (`.../a_vpc_portfolio_optimisation/
  01_baseline_reproduction.md`) VPC solo 600/4 = 10.8% pass / 3.1% bust, `pf_dollar` 1.33.
- Fork B's "only deployable +EV lane" claim **survives**: honest standalone VPC is a genuine
  positive-expectancy edge (PF 1.29–1.40 depending on metric) at realistic cost, and it stays >1.0
  out to ~24 ticks/side of added slippage and to the +2×/+3× cost probes in prior stress reports.
  Caveats that remain real but are NOT fill artifacts: thin sample/throughput (~1.5 tr/wk), a
  standalone eval pass-rate that is modest on its own (10.8%), and a right-tail-dependent edge whose
  by-year PF dips (2023 R-PF ~1.17). Deployability rests on the A+VPC *portfolio* combination, not
  VPC solo eval speed.

## FAILURE MODE 5 — Live vs certified parity: **EXACT, no divergence**

- The live engine imports the frozen certified config directly and never redefines it:
  `import vpc_apex_eval_sim as VS` then `_SIG_KW = {k: VS.CFG[k] ...}` (`strategy_engine_vpc.py:39,
  53-54`); `VpcDayGate` reads `VS.CFG["max_trades"]/["daily_stop"]` (`:231-232`). Same atr_stop 2.5,
  trail 5.0, slot 6–66, max 2/day, slope 0.3, trend 0.5, daily_stop 120. **No Profile-A-style
  slip=2-vs-8 parameter gap exists** — there is literally one source of the numbers.
- The per-bar arm/trigger body is a verbatim transcription of `vpc_signals`
  (`strategy_engine_vpc.py:183-201` vs `nq_vwap_pullback.py:52-72`), protected by
  `test_vpc_signal_parity.py` (truncation causality canary) and `test_vpc_trail_parity.py` (frozen
  stop-path hashes, n=408 / net +5319.67 / PF 1.318).
- Arming status: `resolve_vpc_emission_mode()` reads `VPC_LANE_EMISSION_MODE` from live
  `config_defaults` — the field **does not exist there** (only in `config_relock_v2_staged.py:72`,
  and even there set to "shadow"), so the lane resolves **SHADOW** and every call site guards on
  `arm_live` (`auto_live.py:167-181`). Nothing is armed; A/B are byte-equivalent with the lane wired.

---

## Residual honest caveats (not fill artifacts — flagged for the operator)
1. The 1m-truth PF *improvement* (1.294→1.318) is driven by a peak-on-close vs peak-on-high choice.
   It is honest and monotonic, but the LIVE trail manager (`vpc_trail.py` / `VpcTrailManager`) must
   use the SAME peak definition the certified 1m stream uses, or live exits will differ. This is a
   parity requirement to verify at ARM time, not a defect in the fill model.
2. Standalone eval throughput is thin (~1.5 tr/wk, 10.8% solo pass); the +EV case is the A+VPC
   portfolio, and portfolio bust-rate rises with sizing (B4 grid). That is a risk-sizing decision,
   not a fill mirage.
3. I could not drive a live market-order round-trip (lane is SHADOW-inert), so the claim "the live
   router places the i+1 market order promptly" is verified in code/design but not in a live fill
   log. The certified fill model itself is sound.

**Bottom line:** Unlike Profile A, VPC has no fill mirage. The market-order + trailing-runner
structure makes the certified next-bar-open fill attainable, the same-bar sequencing conservative,
and the edge robust to an order of magnitude more slippage than realistic. VPC's honest standalone
PF is ~1.3, and it holds.
