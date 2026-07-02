> **OBSOLETE — 2026-07-02:** This checklist describes the ARES manual-trading mode which ran on
> an older machine configuration. The current system is ZEUS Rev B (Profile A · Exit#3 · D1c ·
> automated via `./go-live-recert.sh`). See `AGENTS.md` and `README.md` for the current spec.

# ARES — Daily Operating Checklist

One account, one session (NY-AM, 09:30–11:30 ET). Manual/supervised execution.
Print this. Tick every box. If any pre-session box fails → no trading today.

## BEFORE SESSION (by 09:25 ET / 21:25 Perth winter)

- [ ] Mode confirmed = **ARES** (dashboard chip + `ares_mode.py status`)
- [ ] D1c production = **OFF** (shadow only) · no live bot · only approved manual/copier tools
- [ ] Account balance recorded → tracker
- [ ] **Drawdown buffer** recorded (equity − trailing floor). Buffer ≥ 1.5× daily stop?
      If NO → trade ZEUS-normal size today, not ARES size.
- [ ] Today's size set per AGENTS.md machine: A10·Exit#3·D1c·$1,600 size-to-risk (eval, B OFF, mm OFF) — confirm contract count
- [ ] Daily loss stop set (50K −$700 / 150K −$1,600) — known cold
- [ ] Profit lock set (30% of target) — known cold
- [ ] News check: any Tier-1 event in the window? (avoid the ±15 min spread spike)
- [ ] Session quality: is there a clean draw-on-liquidity for A? (no A setup = no A trade)
- [ ] Feed fresh · platform stable · not tired/tilted

## DURING SESSION

- [ ] Only frozen A (sweep→MSS→OTE) or B (ORB retest) setups — nothing else
- [ ] Max 2 trades. Each one logged to the tracker the moment it fills
- [ ] Server-side stop on every position (manual: stop order placed WITH entry)
- [ ] Hit daily loss stop (−$700 / −$1,600)? → **STOP. Flat. Done for the day.**
- [ ] Hit profit lock (+30% of target)? → **STOP. Bank it. Done for the day.**
- [ ] 2 full losers? → STOP (kill switch). Any rule breach/tilt/instability → STOP.
- [ ] Flat by 14:30 ET regardless

## AFTER SESSION

- [ ] Record every trade's result + PnL → tracker
- [ ] New account balance → tracker
- [ ] **Distance to target** updated (target − cumulative profit)
- [ ] **Distance to breach** updated (equity − trailing floor) — the number that matters most
- [ ] Mistake flag / rule-breach flag honestly marked
- [ ] Trading days count updated (need ≥2 to be eligible)
- [ ] Consistency check: is any single day > 50% of total profit? (if near target, may need
      one more modest day to satisfy the 50% rule before the pass counts)
- [ ] Decide tomorrow's size: strong green + healthy buffer → hold ARES size · thin buffer
      → drop a tier · near target → ZEUS-normal size to glide in under the consistency rule
- [ ] If **passed** → STOP. Do not trade the account again today. Open
      `reports/ares-to-zeus-transition.md` and execute it.

## The one rule above all

Distance-to-breach is the only number that can end you. Protect it. A missed day costs
nothing — the eval has no time limit beyond the firm's reset window. One bad day with no
stop costs the whole account. **The gods do not chase losses.**

## D1c Active Eval Filter (if selected)

Before session:
- [ ] Confirm D1c mode (OFF / SHADOW / ACTIVE_EVAL_FILTER) — `auto_runner.py ... --d1c-mode`
- [ ] If ACTIVE_EVAL_FILTER selected: confirm it is an EVAL account (never funded)
- [ ] Confirm D1c cannot increase size (size comes from the tier only — unchanged by D1c)
- [ ] Confirm Profile B is unaffected by D1c
- [ ] Confirm fail-closed behaviour (stale/missing/zero drift → suspend Profile A)
- [ ] Confirm D1c log path: `out/ares/d1c_eval_log.csv`

During session:
- [ ] If D1c BLOCKS a Profile A trade → do NOT override manually. Skip it.
- [ ] If D1c SUSPENDS → do NOT force the trade. Skip it.
- [ ] If D1c is unavailable/stale → skip the Profile A trade (Profile B continues normally).
- [ ] Do NOT increase size because D1c is active. D1c removes risk; it never grants more.

After session:
- [ ] Record allowed / blocked / suspended A trades (from the D1c log)
- [ ] Compare with the raw Profile A signal count
- [ ] Record whether D1c reduced risk this session (blocked losers vs blocked winners)
