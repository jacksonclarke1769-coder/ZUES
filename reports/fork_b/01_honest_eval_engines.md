# Fork B — Can the HONEST edges (Momentum V4, VPC) carry an Apex-50K EOD eval?

**Research / sim measurement ONLY. READ-ONLY bot repo (imports only). Writes confined to
`research/fork_b/` + `reports/fork_b/`. Nothing armed, no strategy change, no hold lift, no VPC
wiring change. LIVE HOLD remains in force.**

Harness: `research/fork_b/honest_eval_engines.py` · JSON: `reports/fork_b/01_honest_eval_engines.json`
· determinism md5 `65fbd5bd100cbe7fc0af428ad60f1f8a` (identical over two runs; full JSON md5 `864d9da7…` both runs).

---

## Setup (fidelity)

| element | choice |
|---|---|
| Vendor / window | **Databento** NQ 1m→5m RTH, **2022-01-03 → 2026-06-22** — single source for ALL three edges (no Dukascopy/Databento cross-vendor mixing) |
| Eval engine (items 1-3) | **certified** `tools_account_size_research` (`day_rows`+`eval_run`+`funded_paid`), reused BY IMPORT — EOD close-set threshold ratchet/lock, intraday-**downside** liquidation via marked trough, **$550** realized daily stop, **$1,000 DLL** flatten, **30-day** clock, rolling 1-eval/trading-day starts |
| Momentum params | **V4 canonical FROZEN**: `confirm_bars=4`, `last_entry_slot=72` (15:30 ET), k=1.0, nd=14, trend=50 (= `ProfileMomentumEngine` defaults). Flat-at-EOD. **Fills honest** — close-to-close on held position, no resting-limit artifact |
| Momentum sizing model | **fixed `mm` contracts** (flat), daily P&L = Σ(close-to-close in **points**) × mm × **$2/pt** − flips×**$1**×mm. Momentum has **no per-trade stop** (it is a flip-at-signal position, flat at close) — so per-trade risk is *not* in the ledger and is not needed; sizing is contract-count, not size-to-risk |
| VPC | `nq_vwap_pullback` locked config, honest next-5m-open fills, per-trade pts→$, **$600 budget / cap-3** size-to-risk |
| Profile-A honest-394 | `honest_d1c_stream.csv` rows with `kept==True` ∩ `achievable_keys.csv` → **394 trades, PF 1.037, +7.37R reproduced exactly**; sized cap-6/$900 (the arm-able A config) |
| Economics | `E[$/att] = P(pass) × funded_paid(same-config events) − $67.5` (fee_mo×1.5). **LOW-CONFIDENCE / PLACEHOLDER** per `test_apex_terms_canary` — never laundered as certified funded $ |

**Canary (fidelity gate):** A-only cap-6/$900 through this harness → **PASS 3.4% / BUST 8.9% / EXPIRE
87.6%**, exactly reproducing the INC-20260707 recert (3.4 / 8.9 / 87.6). The engine is faithful.

---

## ITEM 1 — Momentum STANDALONE (all mm) · certified EOD funnel

| mm | PASS% | BUST% | EXPIRE% | med days | E[$/att] | tr/wk |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | **0.0** | 11.4 | 88.6 | — | **−68** | 2.0 |
| 3 | 1.1 | 37.9 | 60.9 | 22 | **−68** | 2.0 |
| 4 | 0.4 | 62.9 | 36.6 | 28 | **−68** | 2.0 |
| 6 | 0.0 | 92.2 | 7.8 | — | **−68** | 2.0 |
| 8 | 0.0 | 98.2 | 1.8 | — | **−68** | 2.0 |

**No sizing clears pass > bust with +E[$]. Not one.** Momentum standalone is **structurally
incompatible with the 30-day Apex eval**: at survivable size (mm=2) it **EXPIRES 88.6%** of the time
(too slow — ~$36/day vs the ~$100/day needed to reach +$3,000 in 30 days), and every increment of size
to speed it up simply converts expiry into **BUST** (11→38→63→92→98%) without ever buying pass rate
(peaks at 1.1%). E[$/att] is pinned at −$68 (≈ the bare attempt fee) at every size because it
essentially never passes. This is the same "30-day eval incompatible" wall already on record —
**re-confirmed under the honest Databento/EOD engine.**

## ITEM 2 — Momentum(mm=2) + VPC ($600/cap-3)

| config | PASS% | BUST% | EXPIRE% | med days | E[$/att] | tr/wk |
|---|---:|---:|---:|---:|---:|---:|
| Momentum mm=2 | 0.0 | 11.4 | 88.6 | — | −68 | 2.0 |
| **VPC $600/cap-3** | **12.6** | **3.6** | 83.8 | 19 | **+58** | 1.77 |
| **Momentum2 + VPC** | **20.8** | 24.3 | 54.9 | 17 | **+221** | 3.76 |

**Independence:** daily-P&L correlation **0.224** (all days) / 0.527 (the 171 both-active days).
Momentum trades ~every RTH day (461 active days); VPC is selective (401). They are **largely
independent in coverage but positively correlated when both fire** (both are long-biased NQ
directional edges, so shared trend days co-move) — not a clean diversifier.

**Read:** momentum standalone contributes **zero** pass on its own, but as a **portfolio accelerant**
it nearly doubles VPC's pass (12.6→20.8%) by adding daily P&L that speeds the run to +$3,000 — and the
modeled E[$/att] rises +58→+221. **BUT** it drags BUST 3.6→**24.3%**, flipping the book to **pass <
bust**. The positive E[$] there rests entirely on the (low-confidence) modeled funded value; a config
that busts the account more often than it passes is fragile and I do **not** classify it "deployable"
on a pass>bust safety basis.

## ITEM 3 — Momentum + VPC + honest-Profile-A-394 (breakeven, real fills)

| config | PASS% | BUST% | EXPIRE% | med days | E[$/att] | tr/wk |
|---|---:|---:|---:|---:|---:|---:|
| A-394 standalone (cap6/$900) | 4.0 | 10.2 | 85.8 | 19 | −38 | 1.48 |
| Mom2 + VPC | 20.8 | 24.3 | 54.9 | 17 | **+221** | 3.76 |
| **Mom2 + VPC + A-394** | 25.5 | **34.5** | 40.0 | 15 | **−33** | 5.22 |

**Adding breakeven-A HURTS.** Δ vs Mom+VPC: PASS +4.7pp but BUST **+10.2pp** and **E[$/att] +221 →
−$33** (a −$254 swing; modeled funded value collapses $1,389 → $136 as A's extra variance busts the
funded account earlier). This is the direct portfolio confirmation of Fork A: **the PF-1.037 A cut is a
diluting passenger** — it adds trades and variance without adding edge, so it degrades every honest
book it touches. Do not wire mirage-A in.

## ITEM 4 — KEY EOD INSIGHT: is momentum's variance genuinely LESS punished under EOD?

Both rules on the **same** momentum event stream (EOD = `apex_eval_eod.eval_eod`; intraday-trail =
`ApexAcct`, floor ratchets on the intraday unrealized high). SPEC without DLL to isolate the **rule**.

| mm | EOD BUST% | intraday-trail BUST% | Δ (intraday − EOD) | EOD EXPIRE% |
|---:|---:|---:|---:|---:|
| 2 | 8.5 | 8.5 | **+0.0** | 86.8 |
| 4 | 39.3 | 49.1 | **+9.8** | 48.9 |
| 6 | 70.8 | 70.3 | −0.5 | 15.4 |

**The hypothesis is only *partly* true, and it does not rescue momentum.** EOD is genuinely gentler
than the old intraday-trailing rule **only in a mid-size band** (mm=4: **−9.8pp** busts, because the
intraday ratchet punishes momentum's within-day give-back that the EOD close-set floor ignores). But:
- at **survivable size (mm=2)** the two rules bust *identically* (8.5%) — momentum's failure mode there
  is **EXPIRY (86.8%)**, which no drawdown rule touches; EOD's gentleness is **irrelevant**.
- at **large size (mm=6)** momentum busts ~70% under *both* rules — the variance is large enough to hit
  even the fixed EOD floor.

So the old "momentum hurts the eval via intraday ratcheting" story is real but **second-order**: the
first-order killer is that momentum is **too slow to pass in 30 days at any size that survives**. EOD
does not change that verdict.

---

## BLUNT VERDICT

**Is there a deployable +EV eval configuration among the honest edges? — Marginally YES, and it is
VPC, NOT momentum.**

- **VPC standalone ($600 / cap-3): PASS 12.6% · BUST 3.6% · EXPIRE 83.8% · median 19d · E[$/att] ≈
  +$58 · ~1.8 tr/wk.** This is the **only** config that is simultaneously **pass > bust** *and*
  **+E[$]**. It wins by rarely busting the account (3.6%) — you mostly just expire (lose the fee) and
  occasionally pass. It carries the eval by *survival*, not by speed.
- **Momentum STANDALONE: NO — at any size.** Expiry-bound below, bust-bound above; E[$/att] −$68
  throughout; peak pass 1.1%. Under EOD it is no better rescued (Item 4).
- **Momentum + VPC:** higher *modeled* E[$/att] (+$221) but **pass (20.8) < bust (24.3)** — fragile,
  bust-heavy, and its E[$] leans entirely on the low-confidence funded model. Momentum is a
  pass-speed accelerant bought with a large bust tax. Not recommended as "deployable"; flagged.
- **Add breakeven-A: NO — it hurts** (E[$/att] +221 → −33). Confirms the mirage-A dilutes.

### HONEST CAVEATS (ride with every number above)
1. **(a) STRESS BAR NOT CLEARED — this is decisive.** Momentum V4 is **WATCHLIST**: it FAILS the
   institutional simultaneous-stress bar (3×-cost + slip + 75%-fill → **PF 0.68**). A good eval pass
   rate **does not override that.** Any config here that "passes eval" is **"passes eval but NOT
   stress-certified for arming."** Nothing here justifies arming momentum. VPC's own standalone audit
   (`reports/vpc_standalone_audit/`) is its separate gate; this fork tested eval-carry, not stress.
2. **(b) Momentum P&L is points × contracts** (no per-trade risk in the ledger). Momentum has no fixed
   stop — it is a flip-at-signal position flat at EOD — so contract-count sizing (not size-to-risk) is
   the faithful model; stated explicitly so the reader knows there is no per-trade stop being assumed.
3. **E[$/att] is LOW-CONFIDENCE / PLACEHOLDER** (repo Apex-terms canary). `funded_paid` swings wildly
   with book variance ($1,389 → $136 across configs) — treat E[$] as *directional ranking*, not a
   point estimate. The pass/bust/expire percentages are the robust part.
4. **Still sim.** Faithful engine replay, not a live measurement. Per-trade sequential marking is
   slightly optimistic vs the true joint intraday tick path. N≥30 live-fill parity still gates
   everything.
5. **(c) Determinism:** two full runs → identical numeric md5 `65fbd5bd…` and identical JSON.

### BLOCKED / not done
- **Live-fill / parity confirmation** of any config — out of scope (sim only, LIVE HOLD active).
- **Momentum stress-certification** — momentum stays WATCHLIST; no path to arming from an eval pass.
- **VPC cross-vendor / Tradovate-fill basis** — the 241pt Dukascopy/Databento gap and the VPC emission
  path (same surface-lag question as A) are unresolved arming preconditions, not addressed here.
- **Funded-account economics** beyond the placeholder `funded_paid` model — a real funded-$ study
  (per-edge funded survival, payout ladder) was not run; E[$] is directional only.
