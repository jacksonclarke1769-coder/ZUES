# ZEUS Safety Rules

This file is for anyone who works with this repository — new contributors, operators, and AI
assistants. These rules exist because ZEUS trades real money on a real prop-firm account.
Violating them can lose the evaluation, lose funded capital, or expose credentials.

---

## Never commit secrets

The `.env` file holds your Tradovate login, API key, and other credentials. It is listed in
`.gitignore` and must NEVER be committed to Git.

Before every `git add` command, ask yourself: am I about to stage `.env` or any file that
contains a password, API key, or account number? If yes, stop.

Practical checks:
```bash
git status              # look for .env in the list before staging
git diff --staged       # review what you are actually committing
```

If you accidentally commit a secret, rotate the credential immediately (change the password
or regenerate the API key), then remove the secret from git history. Treat the old credential
as fully compromised.

---

## Never run live scripts without operator approval

Scripts that start the live bot, send webhooks, or connect to the broker must only be run
after the operator has completed the pre-launch checklist in `README.md`.

**Restricted scripts (require operator approval before running):**
- `./go-live-recert.sh` — starts the live bot
- `python3 auto_live.py` — the live loop (should be called via `go-live-recert.sh` only)
- `python3 feed_watch.py` — live market data watcher
- `python3 deadman_watch.py --live` — live watchdog
- `python3 bridge_traderspost.py` (direct invocation) — sends webhooks

If someone tells you to run one of these without mentioning the pre-launch checklist, pause
and ask the operator for explicit approval first.

---

## The machine is locked

The current machine configuration is locked as of 2026-07-02:

```
Profile A · Exit#3 · D1c ACTIVE_EVAL_FILTER
Size-to-risk $1,200 budget · Profile B: OFF · Momentum lane: OFF
```

This means: **no task may change entries, exits, sizing, filters, or their timing** without:
1. A harness run on real data recording the new numbers in `reports/apex_validation.json`
2. Explicit operator approval of the results

"It looks better" or "I think this would help" are not sufficient. Evidence is required.

---

## No old configs

Several older machine configurations existed before the current one. Do not use them:

| Old config | Status |
|---|---|
| `go-live-single1r.sh` | Superseded — single-1R exit was demoted 2026-07-02 |
| `paper-single1r.sh` | Superseded |
| Any `auto_live.py` process started before 2026-07-02 ~11:00 AWST | Runs old machine — kill it |
| Any reference to larger account tiers not in use | Current account is Apex 50K — no other tiers are active |

If you find a running Python process and are not sure which machine it is, stop it and ask
the operator before restarting anything.

---

## No undocumented launches

The only approved way to start the live bot is:

```bash
./go-live-recert.sh
```

Do not start the bot by directly calling `python3 auto_live.py` with your own flags. The
`go-live-recert.sh` script performs pre-flight checks (config validation, configlock,
credential check, parity verification) that the direct invocation skips.

---

## No manual production risk-value edits

The parameters that control position size, daily stop, and drawdown limits in `config.py`
are set by the operator after a certification run. Do not edit them:
- without a corresponding harness result in `reports/apex_validation.json`
- without operator sign-off
- in a running system (runtime_config.py CONFIGLOCK will refuse mid-session changes anyway)

Guessing at a "safer" value can change the pass/bust ratio in ways that are hard to predict.

---

## No pushing unreviewed changes

The development workflow is:
1. Fable plans (produces a written spec)
2. Sonnet implements (against the spec)
3. Fable reviews (checks the diff against the spec before anything is "done")

Do not push directly to the main branch without a Fable review. Do not bypass git hooks.

For non-trivial changes, a pull request with the standard output report attached is the
expected artefact.

---

## How to spot a dangerous command

Any command is potentially dangerous if it:

| Pattern | Risk |
|---|---|
| `python3 auto_live.py` | Starts the live bot |
| `./go-live-recert.sh` | Starts the live bot (approved path — but still needs checklist) |
| `curl` to a TradersPost URL | Sends a live order webhook |
| Writes to `evidence/approvals/` | Arms a live behavior |
| Edits `.env` | Credential change |
| `git push --force` to main | Overwrites reviewed history |
| Any `--live` flag without context | Live mode on an unreviewed script |

When in doubt: **do not run it.** Ask the operator first.

---

## What to do if you are unsure

1. Stop. Do not guess.
2. Read `AGENTS.md` — the engineering contract is the authority.
3. Ask Claude Code: "Is this safe?" — then ask it to explain its reasoning.
4. If still unsure, ask the operator directly. A missed opportunity costs nothing;
   a bad trade or a leaked credential can cost real money or fail the account.

The rule in `AGENTS.md` is: **fail closed**. When in doubt, the safe outcome is to do
nothing. An error that blocks trading is always safer than an error that places a wrong order.
