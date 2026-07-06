DRAFT — not a decision until Jackson signs

# DEC DRAFT — re-lock eval research candidate A900/6 + VPC600/3

## Decision (proposed, not yet made)

Re-lock the eval-side **research candidate** machine: **A@$900/cap-6 + VPC@$600/cap-3** (the
"balanced" auditor pick from the A+VPC frontier). Status: **research-certified-eval-candidate-only —
NOT LIVE ELIGIBLE.** This is a sizing/config selection among research alternatives, not an arming
decision.

## Reason

This row dominates the old baseline (A600/6+VPC600/4) on every axis the operator cares about:
- pass/expiry: 37.4% pass / 44.6% expire vs baseline 28.7% / 54.4% (+8.7pp pass, −9.8pp expire)
- funded-per-slot-year: 5.89 vs baseline 4.22 (+40%)
- E$/attempt: $2,861 vs baseline $2,165 (+32%, placeholder pending honest funded re-run at this row)
- slippage tolerance (flip point): 0.068R vs baseline 0.055R — MORE damage-tolerant, not less

Bust rises modestly (18.0% vs 17.0%, +1.0pp) — an acceptable exchange rate given the pass/expire
gain (source: `reports/a_vpc_portfolio_optimisation/09_frontier_report.md`,
`10_relock_recommendation.md`).

## Full eval machine spec (research-certified, not armed)

- **Profile A leg:** budget $900/trade-risk, quantity cap 6, current/certified variant, D1c unfiltered
  (eval-phase choice — unfiltered dominates on eval throughput per the salvage program).
- **VPC leg:** budget $600/trade-risk, quantity cap 3, certified locked parameters
  (`slope_mult=0.3, trend_mult=0.5, atr_stop=2.5, trail_atr=5.0, max_trades=2, slot 6-66`).
- **VPC window:** FULL 10:00-15:00 ET — every tested restriction starves the calendar-widening
  mechanism that is VPC's whole value (07_top_cell_stress.md; 10_relock_recommendation.md answer 15).
- **Conflict rule:** R0 naive union — no arbitration; A and VPC run independently. 11 alternative
  conflict rules were tested; all were either denominator artifacts or null
  (`09_frontier_report.md` conflict-rule line).
- **Daily risk:** shared $550 stop, unchanged; 25 variants tested, none beat it without artifact.
- **DLL:** $1,000 clamp, unchanged.
- **Exit model:** certified Exit#3 (50%@+1R / 50%@+2R). A certified fixed-1.5R alternative lifts
  pass ~+4pp at baseline sizing with worse maxDD — genuine but NOT bundled into this row; it is a
  separate certification event if the operator wants it (`09_frontier_report.md` line 23-24;
  `10_relock_recommendation.md` answer 17).
- **VPC trailing exit:** certified 5.0×ATR trail (locked, `vpc_recert_real.py`), never loosening,
  ratchets every closed 5m bar in the backtest — this is a BACKTEST-CERTIFIED mechanic; no live
  trail-management code exists yet (see live blockers below).

## Rejected alternatives

- **Conservative row** (A700/4+VPC600/6, 30.7/11.7/57.6, flip 0.067R): rejected — too low-pass for
  the operator's stated eval objective (pass/not-pass optimisation); bust reduction doesn't
  compensate for the pass-rate given the 30-day clock.
- **Old baseline** (A600/6+VPC600/4, 28.7/17.0/54.4, flip 0.055R): rejected — dominated by the
  balanced row on pass, expiry, funded-per-slot-year, E$, and slippage tolerance simultaneously
  (`10_relock_recommendation.md` answer 4).
- **Mirage concern:** ABSENT at this row. The prior cap-10-A throughput mirages died at
  0.015-0.019R flip (fill-mirage signature); this frontier's finalists flip at 0.048-0.081R —
  the mirage signature (0-0.015R fill-fragile deaths) is not present anywhere on this frontier
  (`09_frontier_report.md` line 3-6, 17; `07_top_cell_stress.md` line 8-14).
- **Max-pass row** (A900/6+VPC700/3, 39.3/19.6/41.1, flip 0.076R): **NOT rejected** — this is the
  "throughput" class alternative and survives the same stress bar as the balanced pick, but 2025
  carries 47% of its advantage (a single-year concentration flag). Status: **WATCHLIST, pending a
  mini-audit** of the 2025 concentration before it could be considered instead of the balanced pick
  (`09_frontier_report.md` line 13; `reports/relock_dec_funded_rerun/00_preflight.md` watch-row note).

## Operator objective (verbatim)

Eval optimises pass/not-pass, expired = failed, funded is a separate survival machine.

## Live blockers (must clear before ANY arming — none of these are touched by this re-lock)

1. `latest_signal()` timestamp defect fix (live, ticketed, operator-gated — INC-20260706-1141 scope
   addendum).
2. VPC execution-lane build (second live strategy lane in `auto_live.py`, certification event).
3. Live ATR trail management (no order-modify/replace path exists in `bridge_sender.py`/
   `bridge_traderspost.py` today).
4. A-vs-VPC conflict arbitration (same-instrument opposite-direction policy — undocumented gap,
   explicit business/risk decision needed).
5. Trail-aware kill switch (existing kill-switch semantics assume "block new entries only";
   insufficient for a strategy with ongoing post-entry stop management).
6. Index-derived timestamps (the exact defect class behind INC-20260706-1141 — must be inherited by
   any new live lane, non-negotiable).
7. Two-lane signal/fill/missed-fill journals (VPC lane not started; A/B telemetry schema exists).
8. Two-lane watchdog parity (aggregate-net design is likely lane-agnostic but must be proven under a
   3-lane scenario).
9. Paper shadow validation period (before any live routing).
10. Final operator approval.

## The three mandatory sentences

This re-lock does not lift the hold. This re-lock does not arm live. This re-lock does not modify
funded config.

## Evidence pointers

- `reports/a_vpc_portfolio_optimisation/09_frontier_report.md`
- `reports/a_vpc_portfolio_optimisation/10_relock_recommendation.md`
- `reports/a_vpc_portfolio_optimisation/07_top_cell_stress.md`
- `reports/vpc_standalone_audit/01_what_is_vpc.md`
- `reports/vpc_standalone_audit/07_vpc_execution_lane_requirements.md`
- `reports/vpc_standalone_audit/08_vpc_relock_recommendation.md`
- `reports/new_edge_salvage_program/E_final_verdict.md`
- `reports/relock_dec_funded_rerun/00_preflight.md`
- Vault: `07 Bugs & Incidents/INC-20260706-1141-...md` (scope addendum, latest_signal() defect)
- Commits: `caf7b44` (A+VPC portfolio optimisation), `e6766a8` (VPC standalone certification-prep),
  `818cda8` (emergency D1c timestamp recertification)

Firewall: `test_funded_config_firewall.py` green before and after this drafting task (2 passed, no
config files touched).


## AUDITOR ADDENDA (post-draft, same session)
- Max-pass watch row A900/6+VPC700/3: mini-audit CLEAN — status upgraded to
  PROMOTABLE-PENDING-OPERATOR (all 4 mechanical legs hold; one leg at boundary; the swap is a
  one-line operator choice at DEC signing; evidence 06_max_pass_watch_row_audit.md).
- FUNDED LINE of this DEC: default A-kept 300/4 + VPC 150/1 ($8,974 E[paid] model-observed,
  bust 2.4%, stress-survivor); watchlist A250/4+VPC300/2 ($10,291/14.3%); disabled:
  unfiltered-funded, eval-sizing-funded (negative control bust 54.8%). Wide-CI caveat applies.
