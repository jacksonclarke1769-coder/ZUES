# 01 — What is VPC?

RESEARCH ONLY. LIVE HOLD ACTIVE. No code changes. All claims below are cited to file:line. Where the
literature/codebase is ambiguous or loose, that is flagged explicitly rather than resolved by inference.

## What does "VPC" stand for?

**VWAP-Pullback Continuation.** The name is used consistently across the codebase and vault:
- Module docstring: *"NEW NQ edge candidate: VWAP Pullback Trend-Continuation (VPC) + variants."*
  (`~/trading-team/backtests/nq_vwap_pullback.py:2`)
- Re-cert docstring: *"RECERT edge #2 — NQ VWAP-Pullback Continuation (VPC)."*
  (`bot/nq-liq-bot/vpc_recert_real.py:2`)
- Vault: *"NQ VWAP-Pullback Continuation (VPC) — buy-the-dip-to-VWAP in an established intraday RTH
  trend..."* (`Documents/Zues/03 Backtests/BT-20260704-1909-...md:28`)

**Caveat on acronym looseness:** the module comment header also compresses it to "buy the DIP back to
VWAP" (`nq_vwap_pullback.py:5-6`) without ever spelling "Continuation" inline — the C in VPC is only
made explicit in the docstring's first line and in the vault/memory notes, not in any in-code constant
or class name (there is no `class VPC` or `VPC_NAME` string anywhere in the repo — it is a file/report
naming convention only, e.g. `vpc_recert_real.py`, `vpc_apex_eval_sim.py`, `vpc_combined_sim.py`). So:
the acronym is real and consistently used in prose, but it is a documentation-only label, not a coded
identifier.

## Market behaviour

Buy (or sell) the **pullback to VWAP** inside an **already-established intraday trend** — i.e. enter
on the retracement, not the initial breakout. Distinguished explicitly in-code from the deployed
momentum/liq-session/ICT edges: *"Distinct from deployed edges (momentum noise-band breakout,
liq-session Asian-range, ICT sweep->FVG). Core idea: in an ESTABLISHED intraday trend, buy the DIP
back to VWAP (not the breakout)."* (`nq_vwap_pullback.py:4-6`)

## Exact mechanical trigger (`vpc_signals`, `nq_vwap_pullback.py:38-75`)

Per RTH trading day, bar index `i` (5m bars, `slot` = cumulative bar count from RTH open):

1. **Trend/selectivity gates** (all must hold at bar `i`), using the LOCKED re-cert config
   `slope_mult=0.3, trend_mult=0.5` (`vpc_recert_real.py:15`, `vpc_apex_eval_sim.py:24-25`):
   - `slope_ok = |vwap[i] - vwap6[i]| >= slope_mult * atr[i]` — VWAP must have moved by ≥0.3×ATR over
     the last 6 bars (30 min), i.e. a trending VWAP, not flat (`nq_vwap_pullback.py:57`).
   - `ext_ok = |Close[i] - dayopen| >= trend_mult * atr[i]` — price must be ≥0.5×ATR away from the
     day's RTH open, i.e. a "real trend day" (`nq_vwap_pullback.py:58`).
   - `vol_ok = atr[i]/Close[i] >= vol_gate` — a volatility-regime gate; **the locked CFG never sets
     `vol_gate`** (defaults to `0.0`, i.e. this gate is a no-op in the certified config —
     `nq_vwap_pullback.py:39,59`).
2. **Direction test at bar `i`:**
   `up = gates and Close[i] > vwap[i] and vwap[i] > vwap6[i] and Close[i] > dayopen`
   `dn` is the mirror-image short condition (`nq_vwap_pullback.py:61-62`).
3. **Arm on a pullback that pierces VWAP against the trend:** if `up` and `Low[i] <= vwap[i]`
   (price dipped to/through VWAP intrabar while still trend-up by the close test) → `armed_long = True`
   (mirror for short) (`nq_vwap_pullback.py:64-67`).
4. **Trigger:** once armed, the next bar (or a later bar) that closes back through VWAP in the trend
   direction with a small buffer (`Low[i] > vwap[i]*0.9995` long / `High[i] < vwap[i]*1.0005` short)
   fires a signal `(entry_bar_index = i+1, direction, stop_distance = atr_stop * atr[i])`
   (`nq_vwap_pullback.py:69-74`). `atr_stop` is locked at **2.5** (`vpc_recert_real.py:15`).

**Entry:** next bar's `Open` after the signal bar closes — a market-style fill, not a resting limit
(`simulate_day`, `nq_vwap_pullback.py:96`, comment "Entry at NEXT bar open after a signal bar closes
(no lookahead)" at `nq_vwap_pullback.py:10`).

**Stop:** `entry ∓ stopdist` where `stopdist = 2.5 × ATR[i]` at the signal bar (`atr_stop=2.5` locked;
`nq_vwap_pullback.py:97`, `vpc_recert_real.py:15`).

**Exit / trail:** an ATR-based trailing stop, `trail_atr = 5.0` (locked) — peak (favourable extreme)
updates every bar, and the stop ratchets to `peak ∓ 5.0×ATR[j]`, never loosening
(`nq_vwap_pullback.py:98-115`, `trail_atr=5.0` at `vpc_recert_real.py:15`). There is no fixed profit
target; the position runs until the trailing stop is hit or EOD.

**Slot window:** locked config `slot_min=6, slot_max=66` (`vpc_recert_real.py:15`). Bar 0 = the first
RTH 5m bar (09:30-09:35 ET, from the RTH-restriction logic in `real_rth_5m()`,
`vpc_recert_real.py:19-33`), so bar index `i` corresponds to ET time `09:30 + 5*i` minutes. Verified
numerically: **slot 6 = 10:00 ET, slot 66 = 15:00 ET.** So new signals only arm/trigger between
10:00 and 15:00 ET (entries therefore land ~10:05-15:05 ET), ahead of the 16:00 RTH close.
(Note: the un-recert'd original module default is `slot_max=60` = 14:30 ET, e.g.
`nq_vwap_pullback.py:38,173` — the certified/locked value that actually ran is 66, from
`vpc_recert_real.py`/`vpc_apex_eval_sim.py`, not the module's own default.)

**Max trades/day:** `max_trades=2` (locked, `vpc_recert_real.py:15`; enforced in `simulate_day`'s
`taken >= max_trades` check, `nq_vwap_pullback.py:90`).

**Daily stop:** `daily_stop=120` points (locked, `vpc_recert_real.py:15`). Enforced as a circuit breaker
on NEW trades only: `if daily_stop and day_pnl <= -daily_stop: break` (`nq_vwap_pullback.py:92-93`).
**Caveat, quoted directly from the vault:** *"the daily_stop=120pt gate is porous (open trades still
run to stop), so realized worst-days exceed it"* (BT-20260704-1909:67) — i.e. it only blocks a 3rd
entry attempt once realized day P&L is already ≤ -120pt; it does not cap an already-open trade's
in-progress loss, which can exceed 120pt before the trail catches it.

**Cost:** 0.75pt round-trip baked in as the base case (`RT_COST = 2 * HALF_COST = 0.75`,
`nq_vwap_pullback.py:20`), stress-tested up to 1.0/2.0/3.0pt in the re-cert cost ladder
(`vpc_recert_real.py:68`).

## Timeframe / data

5m bars built from real Databento **1-minute** NQ futures, resampled to 5m, RTH cash session only
(09:30-16:00 ET) (`vpc_recert_real.py:19-33`, `vpc_apex_eval_sim.py:28-38`). The original/prior
"validated" run used Dukascopy CFD 5m data at the same 0.75pt cost (`nq_vwap_pullback.py:9`,
BT-20260704-1909:28). Data path: `~/trading-team/data/real_futures/NQ_databento_1m_5y.parquet`.

## Frequency

Full history (2022-01-01 → real Databento window end): **408 trades over 1,152 RTH days**, ≈1.8
trades/week (BT-20260704-1909:50; `vpc_apex_eval_sim.py` cross-check print at line 104 expects
"~408 / +net"). Net = **+4,919.2pt** (`tools_salvage_stress.py` A6 canary #1, quoting exactly
`n=408 (expect 408), net=4919.178571pt` — A6_salvage_fill_slippage_stress.md:27).

## Why rejected on 2026-07-04

VPC's own standalone recert (this file's numbers above) never depended on the D1c/Profile-A stream —
the rejection was NOT "VPC's own numbers were wrong." Rather, VPC was rejected because it **failed to
earn a role relative to the machine that existed on 2026-07-04**, which was Profile A run through the
D1c-kept, `$1,200`-size-to-risk certified eval config:

- VPC's own eval-sim frontier sat strictly below Profile A's: *"Fixed 1 MNQ → 0% PASS (earns
  ~$43/wk/contract, +$3k/30d needs ~$700/wk); Fixed 5-6 MNQ → 30.8-32.6% PASS at 38-49% BUST;
  Size-to-risk $1,200 → 33.8% PASS at 47.4% BUST — vs Profile A (ref, certified): 58.2% PASS / 29.1%
  BUST"* (BT-20260704-1909:76-83, quoted verbatim from the table).
- Combined-portfolio funded test used that certified A@4→6 baseline and the same `$1,200`-style A
  sizing lineage as the comparison anchor: *"A4→6 alone: P(lock) 66.4%, E[payout] $10,023"* vs
  *"A4→6+VPC@1: P(lock) 69.8%... but corrected (shared-calendar) run flips it to a net negative:
  E[payout] −$804 and post-lock bust rises 43.5→50.7"* (BT-20260704-1909:96-126). Final line:
  *"VPC is NOT worth deploying in any stage"* (BT-20260704-1909:126).
- The rejection was measured **against the $1,200 D1c-kept A machine and its 58.2%/29.1% eval numbers**
  — the exact certified row later invalidated (see next section). The 07-04 note itself never
  disputed VPC's own PF/OOS quality; it disputed VPC's *incremental value against that specific A
  baseline*.

## Why rescued

The 2026-07-04 rejection's comparison baseline was invalidated by **INC-20260706-1141** (D1c
attachment timestamp look-ahead): *"the 47.8/15.9/36.2 row; the $1,200 size-to-risk selection (bust
now exceeds pass at that budget on the honest stream)... every research-sprint baseline reproduced
against the contaminated row (relative null conclusions likely stand; absolute numbers do not)"*
(INC-20260706-1141:26). The honest replacement A machine is materially weaker standalone: *"Alone for
EVALS: no — best cell across 495 combinations is 23.4/20.7 with 56% expiry (weak-viable, not a
business)"* (E_final_verdict.md:7-8).

Re-run on the honest baseline (salvage program, `B4_vpc_reeval.md` / `C_combined_portfolio_test.md`),
VPC is the one candidate that survives and is explicitly framed as the rescue:

> *"Did any new edge survive? One: VPC — the shelf rescue. Its 2026-07-04 rejection was measured
> against the contaminated machine and is void; on honest truth it is the missing second leg (PF
> 1.29/1.23-harsh, 5/5 yrs, OOS>IS, corr +0.11, uncontaminated by the incident)."* (E_final_verdict.md:27-29)

The combined result that "lifts the portfolio decisively": **A@600/6 + VPC@600/4** on the honest 2022-
2026 shared window: `pass 27.8% / bust 15.5% / expire 56.7%` at 684 eligible starts, vs the best
single-edge honest baseline (unfiltered-A@1200/6 alone) at `pass 23.4% / bust 20.7%`
(C_combined_portfolio_test.md:14,24; margin comparison in A6_salvage_fill_slippage_stress.md:166 —
`beats_honest_A_alone=True` at every tested slippage level for this cell). Quoted verdict: *"Sizing
class with pass > bust and positive EV? A@$600/cap-6 + VPC@$600/cap-4: pass 27.8 / bust 15.5 / expire
56.7 (2022-2026 window, n=684 starts)... positive every year, stress-robust to 0.042R uniform
slippage (≈3× every alternative) and never below A-alone anywhere in the damage grid"*
(E_final_verdict.md:16-20).

**Caveat — this "rescue" is a research verdict pending operator approval, not a certification.**
The E_final_verdict.md header states: *"HONEST-RECERT DRAFT — pending operator approval. LIVE HOLD
ACTIVE. Nothing armed, nothing promoted."* (E_final_verdict.md:3). Answer 15 explicitly: *"Eligible
to arm now? No."* (E_final_verdict.md:45).

## Difference vs Profile A

| | Profile A (live-routed edge) | VPC |
|---|---|---|
| Setup class | Liquidity-raid / OTE retest (ICT sweep→MSS→FVG, 70.5% OTE) | Trend-pullback-to-VWAP continuation |
| Entry order type | **Limit** (resting order at the OTE retest price), `strategy_engine_profileA.py` via `bridge_traderspost.build_entry(order_type="limit")` | **Market** (next-bar open, unconditional fill) — `nq_vwap_pullback.py:96` |
| Exit | Exit #3: 50% @ +1R / 50% @ +2R fixed R-multiples (`strategy_engine_profileA.py:22`) | ATR trailing stop (5.0×ATR), no fixed target (`nq_vwap_pullback.py:98-115`) |
| Session | NY-AM only (live), all sessions in some research variants | RTH slot 6-66 (10:00-15:00 ET) |
| Stop | Structural (swept-liquidity level derived) | 2.5×ATR from entry |

**Correlation / overlap:** daily-PnL correlation **+0.11** (union days) / **+0.29** (co-active days)
between VPC (points) and Profile A OTE+Exit#3 on the same real data, common trading days
(BT-20260704-1909:60). VPC fires on **196 days when Profile A is flat** (BT-20260704-1909:60,
repeated in E_final_verdict.md:33-34: *"VPC ~+1.7/wk on 196 A-flat days"*). Same-day unit-level stats
from the honest-baseline combined test (2022-2026 window, n_days=701): `same_day_corr=0.164`,
`dl_freq_pct=9.3` (both streams net-negative the same day), `tl_freq_pct=53.9` (combined day
net-negative) (C_combined_portfolio_test.md:7). Note this 0.164 figure is a different (honest-A,
narrower-window) measurement than the 0.11/0.29 figure quoted in the 07-04 vault note against the
contaminated A stream — both are reported here as they appear in their respective source documents;
they are not the same experiment and should not be treated as a single number.

## Overlap / risk-duplication answer

The two edges are not duplicative: they trade different mechanical triggers (raid-retest vs
trend-pullback), fire on largely non-overlapping days (196 A-flat days carry VPC signal), and the
measured daily correlation is low-positive (0.11-0.29 range depending on window/A-stream vintage,
0.164 on the shared honest 2022-2026 window) — consistent with a genuine, if modest, diversifier
rather than a relabeled duplicate of Profile A. The combined-portfolio evidence shows the pairing
adds real, non-overlapping frequency (≈1.7 tr/wk incremental) and lifts pass-minus-bust margin over
every tested single-edge honest baseline at every slippage level tested
(A6_salvage_fill_slippage_stress.md:166-193), which would not be possible if the two streams were
mostly re-trading the same setups.
