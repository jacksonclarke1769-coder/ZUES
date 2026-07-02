> **OBSOLETE — 2026-07-02:** This kill-switch document describes the ARES manual-trading mode
> which ran on an older machine configuration. The current system is ZEUS Rev B (Profile A ·
> Exit#3 · D1c · automated via `./go-live-recert.sh`). See `AGENTS.md` and `README.md` for truth.

# ARES — Kill Switch Rules

Two levels: stop the DAY, and end ARES MODE. When in doubt, the answer is always stop.

## STOP FOR THE DAY — flat, done, walk away

Any one of these ends trading for the session immediately:

- Daily loss stop hit (50K −$700 / 150K −$1,600)
- Two full-size losing trades (regardless of $)
- Daily profit lock hit (+30% of target) — bank it, protect the progress
- Rule breach of any kind (wrong session, wrong setup, oversize, missed stop)
- Emotional/tilt trading detected (chasing, revenge, "make it back" thinking)
- Data feed stale or unreliable
- Platform unstable or order issues
- Drawdown buffer dropped below 1.5× the daily stop mid-session
- You are unsure about anything

Stopping the day costs nothing — the eval has no daily deadline. One uncontrolled day
costs the whole account.

## END ARES MODE — disarm, reassess

Any one of these ends attack mode entirely (not just the day):

- **Account passed** → run `ares-to-zeus-transition.md` (this is the good ending)
- Drawdown risk too high to continue cleanly (buffer chronically thin)
- Firm-rule ambiguity appears (stop until resolved in writing)
- Execution environment fails (no reliable platform/feed)
- You cannot trade cleanly / sustained tilt
- Any sign the aggressive sizing is threatening the long-term plan

## The hard structural rule (enforced by the mode switch)

**ARES sizing may exist only during EVALUATION.** The moment an account is funded, ARES
mode is forbidden on it — `ares_mode.py` refuses to arm a funded account, and the ZEUS
dashboard raises a RED alert if ARES is ever found active on a funded account. No funded
account may stay in attack mode. This is not discipline alone — it is wired into the state.

## Recovery after a blown eval

A blown eval is a $165–375 rebuy, not a disaster (the Attack Plan priced ~19–30% blow at
the recommended tiers). Reset cleanly: new eval, ARES re-armed on the NEW account, same
plan, same size. No revenge sizing on the rebuy. The blow was a cost of speed, already
budgeted — not a reason to push harder.
