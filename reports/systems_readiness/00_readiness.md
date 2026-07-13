# ZEUS Full Systems Readiness Audit — GO / NO-GO

**Question posed:** "Are all systems tested and ready as if any watchlist asset were going live tonight?"
**Verdict (headline):** **NO — nothing is GO tonight.** Zero of the six assets can go live tonight
without a prohibited action. Only ONE asset (Profile A) even has a sanctioned live-arming path, and
that path is `go-live-recert.sh` (operator-typed confirmation) which this audit is forbidden to run;
its currently-locked config fails all three stress families and the system is STOOD DOWN. The other
five are disarmed, benched, unbuilt, or have no live lane at all.

Audit is **read-only** (this report is the only file written). Nothing was armed; no recert script
was run; no config/live/bridge file was touched; no merge/push.

---

## Repo / branch / tree state (ground truth)

- Repo: `~/trading-team/bot/nq-liq-bot`
- **Branch checked out: `vpc-execution-lane`**
- **Working tree: CLEAN** (`git status --short` empty)
- Branch is **17 commits AHEAD of `main`, 0 behind** (`git rev-list --left-right --count main...HEAD` → `0  17`).
- The 17-commit delta is entirely the **additive, SHADOW-guarded VPC execution lane** (auto_live.py
  +172, bridge_traderspost.py +124, strategy_engine_vpc.py new, config_relock_v2_staged.py new, 11
  new VPC test files, 3 build reports). **On `main`, VPC has NO code path at all** — the lane exists
  only on this branch and is disarmed even here.

## Test suite result (ground truth)

Ran `python3 -m pytest -q` on the checked-out branch (`vpc-execution-lane`):

```
962 passed, 1 skipped, 3 warnings in 165.08s
```

- **0 failures.** 1 skip (single skipped case in the suite, not a failure).
- Warnings are non-fatal: (1) APEX TERMS CANARY — 2 placeholder + 15 unverified Apex contract terms
  remain unconfirmed against a live contract (informational canary, by design); (2) `datetime.utcnow()`
  deprecation in `store.py` (cosmetic).
- **`main` not separately run.** Working tree is CLEAN (does not differ from HEAD), so the "run on
  main if the working state differs" condition is not triggered. The branch delta is purely the
  disarmed VPC lane + its tests; on `main` those VPC tests simply do not exist (the lane is absent),
  so `main`'s suite would be a strict subset. The checked-out branch is the relevant state and is green.

---

## GO / NO-GO table

| System | Class | Live lane exists? | Armed / Disarmed | Tests | Cert status | Blocks-to-live | GO-TONIGHT? |
|---|---|---|---|---|---|---|---|
| **Profile A** (ICT OTE) | Alpha (conditional on EMIT-001) | **EXISTS-WIRED** — full lane in `auto_live.py` + `bridge_traderspost.py`; `go-live-recert.sh` is the sole arming path | **DISARMED** — bots STOOD DOWN; `emission_mode` defaults to `certified_gate` (EMIT-001 `emit_at_fill` NOT armed); arming needs operator-typed `GO LIVE RECERT` + passing preflight | GREEN (in 962) | CERTIFIED (EC-1 2026.2). BUT the currently-locked live config (CERTIFIED-394 / A@1200 cap-10) **fails all 3 stress families** (2×cost 0.876, slip 0.978, 75%-fill 0.778; MC p5 −29.8R) | Operator `go-live-recert.sh` (typed confirm + feed-GREEN/broker-panel/dead-man preflight). LIVE HOLD active. The only *healthy* config (A900/6+VPC600/3) is **conditional on EMIT-001**, which is **unsigned**. Self-cert prohibited (constitution) | **NO** — auditor cannot arm; requires operator recert action (forbidden here). Currently-locked config is stress-failing + stood down; healthy config blocked on unsigned EMIT-001 |
| **VPC** (600,4) | Portfolio | **EXISTS-DISARMED** — lane wired additively on THIS branch only (absent on `main`), SHADOW-guarded | **DISARMED (SHADOW)** — `resolve_vpc_emission_mode()` returns SHADOW because `VPC_LANE_EMISSION_MODE` is **absent from the live config authority** (`config_defaults.py`); `arm_live` only via recert promoting the staged block; every V call-site guards on `v_emission == arm_live` | GREEN (in 962) | CERTIFIED (EC-1 2026.2 + standalone audit) | **LIVE HOLD ACTIVE.** Needs: (a) `go-live-recert.sh` to promote `config_relock_v2_staged.py` (STAGED, imported by NO live path — header says so) adding the arming field; (b) EMIT-001 armed + Profile A N≥30 live fills; (c) branch not merged. Exit convention (5m-native vs 1m-truth) unpinned | **NO** — disarmed SHADOW, config staged-not-promoted, on a feature branch, depends on EMIT-001 + A live-fill evidence |
| **Profile B** (ORB) | Watchlist (BENCHED) | **EXISTS-DISARMED** — `ProfileBEngine` + tracker wired in `auto_live.py`, but `go-live-recert.sh` forces `--no-profile-b` | **DISARMED** — OFF everywhere; recert hard-codes `--no-profile-b`; reachable only if launched without that flag | GREEN (in 962) | CERTIFIED-benched (seat displaced by VPC) | Benched by TITAN; no seat in any healthy config; NY-AM session overlap with A is the disqualifier. Re-admission requires beating the A+VPC frontier, preregistered | **NO** — benched, disarmed, session-overlap disqualifier |
| **Momentum** (Zarattini frozen) | Watchlist | **EXISTS-WIRED (reachable)** — full lane (engine+executor+bridge) behind `--profile-momentum` + tier phase gate; `go-live-single1r.sh` actually passes `--profile-momentum`; `momentum_active_for_tier()` = ON for Apex eval/funded & MFFU funded | **DISARMED by default** — OFF unless `--profile-momentum` AND tier gate pass; NOT in the main `go-live-recert.sh` launcher | GREEN (in 962) | WATCHLIST (HERMES-P re-cert). **Fails simultaneous-stress** (combined-worst 0.632). **2 open reconciliations** | 2 unresolved reconciliations (tooling drift: frozen 3-bar/15:00 vs deployed 4-bar/15:30; slippage convention). Only the frozen param is re-certified; the production funnel uses a *different* 4-bar param. Fails stress bar. Illustrative-only, not armed | **NO** — watchlist, fails stress, 2 open reconciliations, unresolved "which momentum?" param ambiguity |
| **Sweep→OTE** | Watchlist | **NO-LIVE-LANE** — appears ONLY as a label string `sig.get("liq","sweep-OTE")` tagging Profile A setups. No engine file, no bridge builder, no gate, no `auto_live` wiring. Never live at any point in lineage | N/A — nothing to arm | N/A — no lane code exists | CERTIFIED-measurement / WATCHLIST-verdict. PF_R 1.149–1.154; **fails cost + fill stress families** | Structural: no execution lane exists; **no build authorized** (DEC). Forward/cost resolution required first | **NO** — no live code path exists at all; not built |
| **AEG-DT-1** (damp/tail-truncation) | Watchlist (sizing overlay) | **NO-LIVE-LANE** — zero references in `auto_live.py`/engines/launchers; no engine or lane file exists | N/A — nothing to arm | N/A — no lane code exists | SUGGESTIVE-UNDERPOWERED (AEGIS Phase 2). **0/64 cells certify**; 17 point-improving cells all die at CI | Not built; nothing certifies; needs a new-data window (Court docket) before any advancement | **NO** — not built, nothing certifies, underpowered |

---

## Cross-cutting facts that make tonight a NO for everything

1. **Bots are STOOD DOWN.** Portfolio dashboard: "bots STOOD DOWN." The live read-back guard
   (`readback_tradingview.py`) keeps the bot stood down when the broker panel is unconfigured
   (fail-closed). Nothing is running.
2. **`go-live-recert.sh` is the SOLE sanctioned arming path** and requires a human to type
   `GO LIVE RECERT` plus a passing preflight (feed GREEN, broker panel open, dead-man). This audit is
   explicitly forbidden to run it. No agent message authorizes self-certification (ZEUS constitution).
3. **The only signable business case is blocked.** Per the dashboard, Profile A (Alpha) + VPC
   (Portfolio) + the only healthy config all hang from **EMIT-001**, which is package-complete but
   **awaiting the operator arming ruling — unsigned.** Until signed, the only *locked* Profile A
   config is the stress-failing C3 (A@1200 cap-10), which the dashboard itself recommends retiring.
4. **VPC's lane lives only on an unmerged feature branch** (`vpc-execution-lane`) and is SHADOW even
   there; `config_relock_v2_staged.py` is explicitly inert ("imported by NO live path").
5. **Sweep→OTE and AEG-DT-1 have no live code whatsoever** — they cannot "go live tonight" in any
   sense; there is nothing to arm.

## Ambiguities / flags for the operator (not guessed into GO)

- **Momentum has a genuinely reachable live path** (`go-live-single1r.sh` + Apex tier gate), unlike
  Sweep→OTE/AEG-DT-1. It is disarmed by default and blocked by 2 open reconciliations + a stress
  failure, but it is NOT merely research code — flagging so it is not mistaken for "no lane."
- **Two different "Momentum" parameterizations** exist under one name (frozen 3-bar/15:00 re-cert vs
  deployed 4-bar/15:30 funnel). Only the frozen one is re-certified. Do not arm until reconciled.
- **Profile A's live-config split**: the CERTIFIED asset (EC-1 2026.2) and the currently-LOCKED live
  config (CERTIFIED-394, stress-failing) are not the same thing. "Certified" in the dashboard refers
  to the asset; the machine that would actually arm tonight is the stress-failing one.
- **APEX TERMS CANARY** warns 2 placeholder + 15 unverified Apex contract terms remain unconfirmed
  against a live contract — an independent reason not to arm real capital tonight.
