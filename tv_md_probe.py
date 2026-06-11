"""
Tradovate market-data CONNECTIVITY PROBE (run this FIRST, once your sim creds are in config.py).

DATA ONLY — authenticates, resolves the front-month contract, and pulls a few 5m bars. It
places NO orders. Use it to confirm: (1) auth works, (2) the account has real-time market-data
entitlement, (3) get_bars actually returns bars. If get_bars comes back empty/errored, the
REST chart path isn't available on this account and we'll switch the live feed to WebSocket.

    python tv_md_probe.py
"""
import sys
import config
from tradovate_client import TradovateClient
from paper_live import normalize_bars

if "YOUR_" in (config.TRADOVATE.get("cid", "") + config.TRADOVATE.get("sec", "")):
    print("Fill in config.TRADOVATE (env='demo', name, password, cid, sec) first — placeholders detected.")
    sys.exit(1)

c = TradovateClient(config.TRADOVATE, config.HOSTS)
print(f"env = {config.TRADOVATE['env']}  ·  host = {c.rest}")
try:
    c.authenticate()
    print(f"[1] auth OK  ·  account_id = {c.account_id}  ·  mdAccessToken = {'yes' if c.md_token else 'NO'}")
except Exception as e:
    print(f"[1] AUTH FAILED: {e}"); sys.exit(1)

contract = c.resolve_front_month(getattr(config, "SYMBOL_ROOT", "MNQ"))
print(f"[2] front-month {config.SYMBOL_ROOT} -> {contract.get('name') if contract else 'NONE'} (id {contract.get('id') if contract else '-'})")
if not contract:
    print("    could not resolve contract — check SYMBOL_ROOT / account."); sys.exit(1)

try:
    raw = c.get_bars(contract["id"], unit="MinuteBar", size=5, count=10)
    bars = normalize_bars(raw)
    print(f"[3] get_bars -> {len(bars)} usable 5m bars")
    if bars:
        for ts, o, h, l, cl in bars[-3:]:
            print(f"      {ts}  O{o} H{h} L{l} C{cl}")
        print("\nRESULT: real-time bar feed WORKS. Run:  python paper_live.py --live")
    else:
        print("\nRESULT: auth/contract OK but get_bars returned NO bars.")
        print("  -> likely no market-data entitlement on this account, OR REST chart unsupported.")
        print("  -> tell me and I'll switch the live feed to the WebSocket md/getChart path.")
except Exception as e:
    print(f"[3] get_bars ERROR: {e}")
    print("\nRESULT: REST chart path failed -> we'll use the WebSocket market-data path. Send me this error.")
