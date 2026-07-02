> ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
> that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
> **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
> `reports/apex_validation.json`. Kept for historical reference only.

# 150K Account Onboarding Checklist (repeat ×8 → ZEUS-MAX)
_run this once per new 150K account · ~30–45 min of operator setup + the 1-MNQ bracket proof_

## Firm rotation (do in this order)
ZEUS-MAX = **3× MFFU Pro 150K + 5× Topstep XFA 150K**. Onboard **Topstep first** (payouts ~15d vs MFFU ~64d), e.g.:
`T1 · T2 · M1 · T3 · M2 · T4 · M3 · T5`  (5 Topstep, 3 MFFU, interleaved so no single firm dominates early).

## One-time pre-reqs (already done after the 50K proof)
- [ ] `exit-model-approved.flag` exists (live arming gate) — created once, stays.
- [ ] Bridge + Exit #3 routing proven on the 50K. Suite green.

---

## Per-account steps (every new 150K)

### 1 — Buy the eval
- [ ] Purchase the **150K eval** from the next firm in the rotation (Topstep XFA 150K / MFFU Pro 150K).
- [ ] Record: **firm · account ID · eval target (+$9k) · trailing DD ($4,500) · contract limits.**

### 2 — Broker connection
- [ ] Confirm the account is live in **Tradovate** (the platform TradersPost routes to).
- [ ] Note the **front-month contract** (e.g. `MNQU2026`) — used in the bracket proof.

### 3 — TradersPost → Tradovate
- [ ] In **TradersPost**: connect this Tradovate account; create a **strategy + dedicated webhook URL** for it.
- [ ] Store the URL **locally only** (env var, never in git/chat).
- [ ] Map check: the URL routes to THIS account (verify in Stage 1 below).

### 4 — Bracket proof (Stages 1–3, 1 MNQ — bounded, ~$ trivial)
Prove the bridge actually attaches a bracket at this account before any auto trading:
```
# Stage 1 — ping (account + routing + strategy mapping)
TRADERSPOST_TEST_URL='<test url>' python3 bridge_test.py --account <ACCT> --ping
#   PASS = 2xx, correct account mapping, evidence saved

# Stage 2 — 1 MNQ bracket (qty hard-forced to 1), watching Tradovate
TRADERSPOST_LIVE_URL='<live url>' python3 bridge_test.py --account <ACCT> \
  --one-mnq --ref <price> --mode live --confirm
#   PASS = reaches the account · correct symbol/side · limit + STOP + TARGET ATTACH · no dup

# Stage 3 — flatten / cancel
TRADERSPOST_LIVE_URL='<live url>' python3 bridge_test.py --account <ACCT> --flatten
#   PASS = position flat, working orders cancelled, no orphan
```
- [ ] Stage 1 ✓  - [ ] Stage 2 ✓ (stop+target attached, eyes on Tradovate)  - [ ] Stage 3 ✓

### 5 — Config the eval
- [ ] Tier = **`150K-balanced`** (eval = **A8 / B4**, daily stop −$1,600, worst-day $3,841 < $4,500 buffer).
      *(150K-aggressive A10/B6 needs the approval flag — skip unless you want it hot.)*
- [ ] Account id passed to the runner: `--account <ACCT>`.
- [ ] **Account-spec assert:** confirm the runner's account id == the TradersPost-mapped account (no cross-wiring).

### 6 — Run the eval (live, supervised)
```
export TV_REALTIME_CONFIRMED=1
export TRADERSPOST_LIVE_URL='<this account url>'
python3 auto_live.py --account <ACCT> --tier 150K-balanced \
  --feed tradingview-1m --d1c-mode active-eval-filter --execution traderspost --live --confirm
```
- [ ] First A fill: **both two-leg brackets attach** in Tradovate. First B fill: **bracket attaches.**
- [ ] −$1,600 daily stop + kill switch ready (`Store().set_state(auto_live_kill='1')`).
- [ ] Goal: **+$9k** without breaching $4,500. Pass rate ~74%; ~42 days median.

### 7 — Track
- [ ] Add to the dashboard / eval tracker (`out/ares/` + calendar). ARGUS logs every decision.
- [ ] `python3 tools/audit_live_engine_session.py --date today` each day → `SESSION CLEAN`.

### 8 — After PASS → switch to FUNDED survival
- [ ] `python3 ares_mode.py switch-funded <ACCT>` (or run `--mode funded`).
- [ ] Funded tier = **150K funded = A4 / B2 + P3**, daily stop −$800, worst-day $1,921.
- [ ] **Retention:** keep cushion ≥ trailing DD; withdraw excess each payout (Topstep ~15d / MFFU ~64d).
- [ ] If FAIL: re-buy the eval (back in the queue) — ~26% of attempts; budget ~3 re-runs across the 8.

---

## ⚠️ The concurrency blocker (account #2 onward)
The single-instance lock (`data/bot.lock`) means **one `auto_live` per machine**. Running **several 150K accounts at once** needs ONE of:
- **the multi-account copier** (1 signal → all accounts) — *NOT BUILT yet*, **or**
- per-account isolation (separate lock path + Store + TradersPost URL per process) — a smaller build.

**Account #1 (the first 150K) runs fine standalone.** Account #2+ on the weekly cadence is **blocked until the copier (or per-account isolation) is built.** Budget that build before the cadence ramps past one concurrent account.

## Per-account time/cost
~30–45 min onboarding + ~42-day eval (74% pass). Eval fee ~$500. Across 8: ~$5,500, ~4.6 months at 1/week (see the eval-attrition sim).
