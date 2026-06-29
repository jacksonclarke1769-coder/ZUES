# Adding an account to the live fleet (paste-and-go)

The bot runs **one process** that computes the A/B/Momentum signal once and fans it out to every
account at that account's own size + webhook. Adding an account is 3 steps. No code changes.

## The model
- **Primary** = `--account X --tier Y`, routes to `TRADERSPOST_LIVE_URL`.
- **Each extra account** = a `--apex-book ACCOUNT:TIER`, routes to `TRADERSPOST_<ACCOUNT>_URL`
  (account name, dashes → underscores, UPPERCASE: `APEX-50K-2` → `TRADERSPOST_APEX_50K_2_URL`).
- Same signal, each account's **own size** (from its tier) to its **own broker** (via its own webhook).

## Tiers (sizes)
| Stage | `--tier` value | Size A/B/Mom |
|---|---|---|
| Eval | `Apex-50K-eval` | 10 / 5 / 6 |
| Funded phase 1 | `Apex-50K` | 4 / 2 / 2 |
| Funded scaled | `Apex-50K-scaled` | 6 / 3 / 6 |

## Steps to add account #N
1. **On TradersPost**: create a Strategy for that account, connect it to *that account's* Tradovate
   connection, and copy its **Webhook URL**.
2. **In `.env`**: uncomment the matching `TRADERSPOST_<ACCOUNT>_URL=` line and paste the URL.
3. **On the launch command**: add `--apex-book ACCOUNT:TIER`.

First time you add ANY book that must route live, create the live-routing flag once:
```bash
echo "apex fan-out live routing approved $(date)" > evidence/approvals/apex-approved.flag
```
Without it, books run SHADOW (log, no live orders) even with `--live`.

## Launch examples
**Now (1 account, the eval):**
```bash
python3 auto_live.py --account APEX-50K-1 --tier Apex-50K-eval \
  --profile-momentum --feed tradingview-1m --live --confirm
```

**Later (3 accounts: eval + funded + scaled):**
```bash
python3 auto_live.py --account APEX-50K-1 --tier Apex-50K-eval \
  --apex-book APEX-50K-2:Apex-50K \
  --apex-book APEX-50K-3:Apex-50K-scaled \
  --profile-momentum --feed tradingview-1m --live --confirm
```

## Safety latches (automatic)
- **Routing guard**: the launch REFUSES if any two accounts resolve to the same webhook URL
  (catches a copy-paste slip before any order fires).
- **Per-account signalId**: the same signal hashes to a different id per account — orders can't merge.
- **Per-account daily-stop + Apex $1k kill-guard**: each book halts on its own limits, never the others.
- **Startup print**: each book logs `webhook set` / `⚠ NO webhook` and `LIVE-ROUTING` / `SHADOW` — read it.

## What the bot CANNOT check (on you)
Each webhook URL must be wired to the **correct** Apex account *inside TradersPost*. The bot guarantees
the right signal/size reaches the right URL; it can't see which broker account a URL is connected to.
