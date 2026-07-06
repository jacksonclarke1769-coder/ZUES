# 07 — Live Blocker Checklist (Re-Lock Cycle)

RESEARCH/DECISION-PREP ONLY. LIVE HOLD ACTIVE. No code changes in this document. This is a status
snapshot of every item that must clear before ANY live arming — it does not authorize or schedule
any of the work below.

| # | Blocker | Status | Evidence |
|---|---|---|---|
| 1 | `latest_signal()` timestamp defect fix | **NOT STARTED** — ticketed, operator-gated | INC-20260706-1141 scope addendum: identical UTC-relocalized-as-NY pattern found in live `strategy_engine_profileA.py latest_signal()`; live A has never entered on it (zero realized harm) but the fix is mandatory before any arming. Research-side fix + permanent canaries are DONE; the LIVE fix is not. |
| 2 | VPC live ATR-trail management | **NOT STARTED** — no order-modify path in `bridge_sender.py`/`bridge_traderspost.py` | `reports/vpc_standalone_audit/07_vpc_execution_lane_requirements.md`: "Grep across every live-execution file in this repo for a `trail` implementation outside backtest/research code returns nothing"; "no modify/replace/amend-stop function exists anywhere in the order-building or sending code." |
| 3 | Order modify path | **NOT STARTED** | Same source as #2 — this is the underlying primitive #2 depends on; neither a bot-side cancel-and-resend loop nor a broker-native trailing-stop integration exists or has been verified available. |
| 4 | A-vs-VPC conflict arbitration | **NOT STARTED** — note: R0 naive union means arbitration policy = "allow both," but margin/position accounting still needs to be built | `07_vpc_execution_lane_requirements.md`: "A same-instrument (MNQ, netting account) same-direction-vs-opposite-direction policy decision... is a business/risk decision, not a coding task" — flagged BLOCKS-ARMING: YES, undocumented policy gap. |
| 5 | Trail-aware kill switch | **NOT STARTED** | `07_vpc_execution_lane_requirements.md`: existing kill-switch design assumes "block new entries only"; VPC has ongoing post-entry stop-management activity the kill-switch was never designed around. Explicit decision needed on whether kill freezes trail updates or lets them continue (trail only ever tightens risk). |
| 6 | Index-derived timestamps | **PARTIAL** — research-side DONE (commit `818cda8`); live lane must inherit the pattern | `07_vpc_execution_lane_requirements.md`: `vpc_apex_eval_sim.py` already derives `ts=idx[ei]` from the tz-aware index (the exact pattern INC-20260706-1141 mandates); any new live engine (`ProfileVEngine`) must copy this discipline and must never reconstruct timestamps via string date+time parsing — the exact defect class that hit live Profile A. |
| 7 | Two-lane signal/fill/missed-fill journals | **PARTIAL** — telemetry schema 2 exists for A/B lanes; VPC lane NOT STARTED | `07_vpc_execution_lane_requirements.md`: `exec_telemetry.py`/`fill_telemetry.py`/`journal.py`/`trade_journal.py` already take free-text `strategy=`/`profile=` fields (generic across N lanes), but no VPC-specific engine, journal calls, or dashboard aggregation has been built or verified not to hardcode an `{A,B}` set. |
| 8 | Touch-without-fill telemetry | **DONE for A** — armed, N≥30 gate; **VPC N/A** (VPC is a market-entry strategy, no resting-order touch-without-fill concept applies) | Fill telemetry default-ON per Ops Cycle 1 (vault memory); VPC's market-style entry (`nq_vwap_pullback.py:96`) has no limit-order touch concept to telemeter. |
| 9 | Two-lane watchdog parity | **NEEDS AUDIT** — aggregate-net design likely lane-agnostic per exec-lane report, but tests must prove 2-lane (A+V) and 3-lane (A+B+V) scenarios | `07_vpc_execution_lane_requirements.md`: `check_position_parity`/`watchdog_belief.publish_belief`/`ReadbackSentinel.on_entry` are already strategy-agnostic by design (one aggregate net vs one `belief_expected`), but "no hidden assumption of 'at most 2 concurrent lanes'... not found in this reading, but not exhaustively checked" — a `test_watchdog_replay.py`-pattern 3-lane concurrent scenario must be run and pass before arming. |
| 10 | Paper shadow | **NOT STARTED** — criteria to be set in the DEC | `07_vpc_execution_lane_requirements.md`: `ProfileBPaperTracker` is a strong copy-adapt precedent for a `ProfileVPaperTracker`, but must first confirm the tracker's fill-timing model matches VPC's certified next-bar-open MARKET fill (not B's possibly limit-fill assumption) before copying verbatim. No dry-run/paper period has been run for VPC. |
| 11 | Final operator approval | **BLOCKED on all above** | Sequencing per `reports/vpc_standalone_audit/08_vpc_relock_recommendation.md` answer 14: operator re-lock DEC → live `latest_signal()` fix → VPC execution lane built + line-audited + full test harness → paper shadow → separate arming approval. Nothing on this list has cleared. |

## Effort classification (context, not a schedule)

Per `07_vpc_execution_lane_requirements.md`: engine registration, bar dispatch, telemetry/journal
calls, sizing-tier key extension, and watchdog/readback integration are all copy-adapt from the
existing Profile B lane (established, low-effort pattern). The genuinely new work — with no existing
live-code precedent — is exactly items #2, #3, #4, and #5 above, plus the VPC-specific signal-parity
test (item #6/#7 territory). Item #2 (live ATR-trailing-stop management) is explicitly called out as
"the single biggest new piece" and "the one item that has no analog anywhere in this codebase."

## LIVE ELIGIBLE: NO.
