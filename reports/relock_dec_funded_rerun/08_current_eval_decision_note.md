# 08 — Current Eval Account: Decision Note (Options, Not a Recommendation)

RESEARCH/DECISION-PREP ONLY. LIVE HOLD ACTIVE. This note lays out the current live eval account's
honest situation and four operator options with numbers attached. It does not recommend one — per
the operator's own framing, the auditor writes the recommendation in the decision pack, not this
document.

## Operator framing (verbatim)

Expired = failed. Bust = failed. No emotional rescue.

## The facts

The live eval's last honest conditional read (`reports/emergency_recert_d1c_lookahead/
09_forecaster_rebuild.md`, section 4), as-of **2026-07-07**:

| | value |
|---|---|
| P(PASS) | 13.2% |
| P(BUST) | 33.0% |
| P(EXPIRE) | 53.8% |
| median days-to-target (of passes) | 12 |
| balance | $49,404.80 |
| floor (start-trail, unratcheted) | $47,500.00 |
| cushion | $1,904.80 |
| days left (as-of 2026-07-07) | ~18 |

**REQUIRES FORECASTER REFRESH before any action.** Days have passed since 2026-07-07; the days-left
figure above is stale and must be re-run (`tools_eval_forecast.py --as-of <today>`) against the
current campaign state before any of the four options below are acted on. The read itself (13.2/
33.0/53.8) is not being disputed here — only its currency. The edge (stream) underneath this
forecast is unchanged; only the clock and the cushion move as time passes.

For scale: the fresh-seed honest cap-10/$1,200 row (full 30 days, full $2,500 cushion) reads 31.4%
pass / 37.3% bust / 31.4% expire (`09_forecaster_rebuild.md` section 2) — the live account's 13.2%
conditional read is materially worse than the fresh-seed number because it starts down cushion
(~$595 already spent) and has ~18 of its 30 days remaining, not a full clock. The mechanism, not the
edge, explains the gap.

## Rescue-worthiness at 13% honest, framed against the sunk fee

$131 is sunk regardless of what happens next — it is not part of any forward-looking decision. The
actual question is the **option value of the ~19 remaining days** (accounting for the pending
forecaster refresh) at a 13.2% honest pass probability, not "was the $131 well spent." Framed this
way, the decision is a small forward bet (time + attention, not new capital) on a ~1-in-8 outcome,
weighed against three no-cost-to-hold alternatives below.

## The four options (numbers, not a verdict)

**Option 1 — Dormant under hold (the default).**
The live hold already prevents this account from trading at all. Doing nothing costs nothing beyond
the clock continuing to run down toward the 2026-07-25 expiry. If the clock expires while dormant,
the account fails by expiry (per the operator's own "expired = failed" framing) with certainty,
foreclosing the 13.2% pass path entirely. This is the status quo and requires no operator action.

**Option 2 — Recycle after re-lock (the R1 policy path).**
Per the existing R1 recycle operator policy (`DEC-20260705-2102-r1-recycle-operator-policy`, vault),
a bust or expiry on this account feeds into the standing recycle process — a fresh eval attempt is
bought at the next re-lock cycle, running the (pending-approval) A900/6+VPC600/3 candidate instead
of whatever config produced the current account's honest 13.2%. This treats the current account as
disposable and routes value into the next, better-specified attempt rather than trying to extend
this one's life.

**Option 3 — Paper/dry-run validation use (viable, zero incremental cost).**
The live account, while under hold, costs nothing extra to use as a shadow-validation vehicle: e.g.
running the new VPC engine's signal-parity checks, timestamp-integrity assertions, or paper-shadow
harness tests against this account's real market conditions without submitting orders (hold
enforces no live trading regardless). This extracts residual value from the ~19 remaining days
without touching the 13.2%/33.0%/53.8% forecast at all — it is an orthogonal use of the account's
remaining clock, not an attempt to pass it.

**Option 4 — Let it ride to its own conclusion (pass/bust/expire, unmanaged).**
If the hold is lifted for this specific account only (a decision the operator would need to make
explicitly, separate from any re-lock DEC) and it is allowed to keep trading under its current
(pre-re-lock) configuration, it resolves on its own 13.2/33.0/53.8 odds. This option accepts the
worst honest odds of the four, in exchange for preserving the small chance of an early real payout
before the next re-lock cycle would even be ready to deploy.

## Evidence

- `reports/emergency_recert_d1c_lookahead/09_forecaster_rebuild.md` (section 2 fresh-seed row,
  section 4 live conditional read)
- `reports/emergency_recert_d1c_lookahead/05_honest_machine_certification.md` (honest cap-10/$1,200
  eval row underlying the fresh-seed comparison)
- Vault: `DEC-20260705-2102-r1-recycle-operator-policy` (Option 2 mechanism)
- `reports/relock_dec_funded_rerun/DEC_DRAFT_relock_A9006_VPC6003.md` (the re-lock candidate Option 2
  would recycle into)

Firewall: `test_funded_config_firewall.py` green before and after (2 passed, no config files touched).
