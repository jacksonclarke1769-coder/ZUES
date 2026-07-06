# 02 — Funded Re-Run Philosophy: Why Eval and Funded Invert

RESEARCH/DECISION-PREP ONLY. LIVE HOLD ACTIVE. No code or live/config changes in this document.

## The phase-split doctrine

Eval and funded are not the same optimisation problem wearing different clothes — they are two
different machines with opposite objective functions, and treating them as one machine is the root
cause of the entire honest/contaminated confusion this repo has been digging out of since
INC-20260706-1141.

**Eval = a pass/not-pass sprint.**
- The only two outcomes that matter are PASS and NOT-PASS. Expiry counts as a full failure — there
  is no partial credit for "the edge was fine, we just ran out of days."
- Because expiry is failure, FREQUENCY is the dominant lever: a thinner, higher-quality edge that
  fires 1.8 times/week (VPC alone) cannot outrun a 30-day clock no matter how good its PF is
  (10.8% pass / 86% expiry standalone, `reports/vpc_standalone_audit/08_vpc_relock_recommendation.md`
  answer 3) — it needs a partner to widen the calendar.
- Sizing can be aggressive within honest stress bounds (the frontier work explicitly tests up to
  A@$1000-1200/cap-6-10 rows) because a bust in eval only costs the $131 attempt fee — the downside
  is capped and small, so the eval machine should be tuned to maximise pass rate, not minimise bust,
  subject to the machine still surviving realistic fill/slippage stress (flip point, winners-fill
  sensitivity, 2x/3x cost ladders).

**Funded = a survival extraction machine.**
- The only objective is: stay alive, reach the payout ladder, extract real dollars over months/years.
  There is no clock forcing action — slow is fine, arguably preferred.
- Bust here means losing the funded account and its future payout stream, not $131 — the asymmetry
  between eval-bust-cost and funded-bust-cost is why the same edge should be sized completely
  differently in each phase.
- Because there is no expiry pressure, the funded machine can afford to be selective: it should run
  the highest-QUALITY subset of the edge, not the highest-frequency subset.

## Why the phases invert (the D1c finding)

The D1c filter (Profile A's "kept" vs "dropped" signal classification) is the clearest demonstration
of the inversion, and it is exactly backwards from what the pre-incident certified numbers implied:

- **Eval:** unfiltered (all 705 signals) DOMINATES the D1c-kept subset (583 signals) at the eval
  funnel level. The extra frequency from trading the dropped signals too outweighs the PF
  improvement the filter buys (`reports/new_edge_salvage_program/E_final_verdict.md` answer 2:
  *"Evals: unfiltered dominates (frequency beats the +0.124 PF; the viability shortlist is mostly
  unfiltered rows)"*). The honest unfiltered-A-alone eval frontier tops out around 23.4% pass / 20.7%
  bust across 495 sizing combinations — weak alone, which is why the A+VPC combination exists at all.
- **Funded:** the exact opposite. Every unfiltered funded cell tested is NOT-VIABLE; D1c-kept is what
  funded survival is made of (`E_final_verdict.md` answer 2: *"Funded: kept dominates (every
  unfiltered funded cell NOT-VIABLE; D1c's quality is what survival is made of)"*). The honest kept-A
  stream at conservative funded sizing (250/4) produces $7,292 expected payout at 0% observed bust
  over ~31 months, robust through 0.05R slippage (`E_final_verdict.md` answer 5).

**Mechanism, stated plainly:** D1c is a quality filter. Quality filters always cost you frequency to
buy win-rate/PF. Eval's objective function is frequency-hungry (beat the clock) so it pays to trade
the unfiltered stream. Funded's objective function is drawdown-averse and patient (no clock) so it
pays to trade only the filtered, higher-quality stream and accept the lower frequency. Same signal
generator, same historical trades — the RIGHT SUBSET to trade depends entirely on which clock (or
absence of one) governs the account. This is why "D1c is a funded filter, not an eval filter" is the
one-line summary of the whole finding (`E_final_verdict.md` answer 2 verbatim phrase).

## The honest funded numbers (conservative cells)

- Kept-A alone, 250/4 sizing: **$7,292** expected payout, 0% observed bust, ~31 months, robust
  through 0.05R uniform slippage (`E_final_verdict.md` answer 5).
- Kept-A 250/4 + VPC@200/2 (small optional second leg): **$8,567** expected payout, 0% observed bust
  — improves the headline number but degrades faster under heavy slippage stress than the A-alone
  cell, so the VPC funded leg is framed as optional/small, an operator choice, not a requirement
  (`E_final_verdict.md` answer 5; `reports/vpc_standalone_audit/08_vpc_relock_recommendation.md`
  answer 6).
- Wide-CI caveat stands: these funded numbers are built on n=49 overlapping funded-window starts —
  real edges, honest process, but a small sample that should be treated as a range ($7.2-8.6k), not
  a point estimate.

## The negative-control rationale: why the re-lock DEC needs an eval-sizing-through-funded-sim row

The re-lock candidate (A@900/6+VPC@600/3) was chosen and stress-tested entirely on the EVAL side of
the funnel — pass/bust/expire at the 30-day clock. It has never been run through the FUNDED survival
machine. Running the eval-optimised sizing through the funded compute lane and reporting the
resulting bust/payout numbers serves as a **negative control**: it is expected to look materially
worse (more aggressive size, no quality filter, tuned for frequency not survival) than the
purpose-built conservative funded cells above. Computing this row numerically — rather than asserting
the inversion by argument alone — is what proves the phase-split doctrine rather than merely
asserting it. This is the compute lane's job: deliver the row, let the number itself demonstrate why
eval sizing must never be carried over unmodified into the funded account.

## Evidence

- `reports/new_edge_salvage_program/E_final_verdict.md` (answers 1, 2, 5; the one-paragraph honest
  business summary)
- `reports/vpc_standalone_audit/08_vpc_relock_recommendation.md` (answers 3, 6)
- `reports/emergency_recert_d1c_lookahead/05_honest_machine_certification.md` (honest kept vs
  unfiltered PF/WR numbers underlying the D1c finding)
- `reports/relock_dec_funded_rerun/DEC_DRAFT_relock_A9006_VPC6003.md` (the eval-side candidate this
  philosophy note explains the boundary for)

Firewall: `test_funded_config_firewall.py` green before and after (2 passed, no config files touched).
