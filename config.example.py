"""
NQ Liq-Session bot configuration. Copy to config.py and fill in credentials.
config.py is gitignored — never commit live keys.
"""
# ---------------- Tradovate API ----------------
# Tradovate uses appId/cid/secret + user/password OAuth. Demo vs live host below.
TRADOVATE = dict(
    # 'live' for funded/eval real-sim accounts, 'demo' for paper. Eval accounts are 'live' host.
    env          = "demo",                       # "demo" | "live"
    name         = "YOUR_TRADOVATE_USERNAME",
    password     = "YOUR_TRADOVATE_PASSWORD",
    app_id       = "NQLiqBot",
    app_version  = "1.0",
    cid          = "YOUR_CID",                    # from Tradovate API app registration
    sec          = "YOUR_API_SECRET",             # the API key/secret you'll provide
    device_id    = "nq-liq-bot-001",
    account_spec = "YOUR_ACCOUNT_NAME",           # e.g. "DEMOXXXXXX" or the Apex account id
)
HOSTS = dict(
    demo = dict(rest="https://demo.tradovateapi.com/v1", ws="wss://demo.tradovateapi.com/v1/websocket",
                md="wss://md.tradovateapi.com/v1/websocket"),
    live = dict(rest="https://live.tradovateapi.com/v1", ws="wss://live.tradovateapi.com/v1/websocket",
                md="wss://md.tradovateapi.com/v1/websocket"),
)

# ---------------- Instrument ----------------
SYMBOL_ROOT = "NQ"           # front-month resolved at runtime (e.g. NQM6)
TICK        = 0.25
POINT_VALUE = 20.0           # $/point for NQ (MNQ = 2.0)

# ---------------- Strategy (mirrors NQ_LiqSession_Phased.pine) ----------------
STRAT = dict(
    tz            = "America/New_York",
    asia_start_min= 18*60,   # 18:00 ET
    asia_end_min  = 2*60,    # 02:00 ET (wraps)
    ent_start_min = 9*60+15, # 09:15
    eval_ent_end  = 9*60+45, # 09:45  (EVAL entry window end)
    fund_ent_end  = 11*60+30,# 11:30  (FUNDED entry window end)
    flat_min      = 15*60+55,# 15:55 EOD flat
    min_sweep     = 10.0,  # require break >=10pt beyond Asian high (filters weak whipsaws; +PF, +pass, robust)
    need_fvg      = True,
    use_vgate     = True,    # daily ATR14 >= SMA20
    long_only     = True,
    # EVAL ruleset — tuned for MAX single-attempt pass% (≈40%): full killzone + multi/day
    eval_stop_pts   = 30.0,
    eval_qty        = 1,       # 1 NQ
    eval_ent_end_kz = 11*60+30,# EVAL uses the FULL killzone (09:15–11:30)
    eval_one_per_day= False,   # EVAL takes every qualifying break
    # FUNDED ruleset
    fund_stop_pad = 2.0,       # structure stop = Asian low - pad
    fund_rr       = 3.0,
    fund_qty      = 1,         # set to MNQ-equivalent in live
)

# ---------------- Funding plan (single eval can't hit 80%; SPRAY to 80%+) ----------------
FUNDING = dict(
    single_pass   = 0.40,      # measured single-attempt pass on green-light starts
    target_prob   = 0.80,
    plan_attempts = 4,         # 1-0.6^4 = 87% funded
    auto_spray    = True,      # on bust/expire, log attempt & reset to a fresh $50k eval
)

# ---------------- Account / eval rules (Apex $50k) ----------------
EVAL = dict(
    start_balance = 50_000.0,
    pass_target   = 53_000.0,   # +$3,000
    trail_dd      = 2_500.0,
    lock_at       = 50_100.0,   # threshold locks here once peak >= 52,600
    window_days   = 30,
)

# ---------------- Safety / ops ----------------
SAFETY = dict(
    enabled        = True,      # MASTER kill-switch; False = read-only / no orders
    paper          = True,      # True = simulate fills locally even if connected (no real orders)
    max_daily_loss = 1_200.0,   # hard stop the bot for the day if down this much ($)
    require_greenlight = True,  # only trade when vol-gate is ON (green-light)
    one_trade_per_day  = True,
)
DB_PATH = "data/bot.db"
