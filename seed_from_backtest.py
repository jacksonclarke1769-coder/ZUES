"""
Seed the dashboard DB by replaying the strategy through local NQ data (paper fills).
This populates trades / equity / daily P&L exactly as the live bot would record them.

  python seed_from_backtest.py            # full history demo (rich calendar + equity)
  python seed_from_backtest.py --days 120 # fresh eval over the last 120 days
  python seed_from_backtest.py --reset    # wipe the DB only

For LIVE: don't seed — `python bot.py --live` starts a fresh $50k eval and records the
real account forward from your first trade.
"""
import argparse
from bot import run_sim
from store import Store
import config

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None, help="limit to last N days (fresh eval view)")
    ap.add_argument("--reset", action="store_true", help="wipe DB and exit")
    a = ap.parse_args()
    if a.reset:
        Store(config.DB_PATH).reset(); print("DB reset."); raise SystemExit
    st = run_sim(speed=0.0, days=a.days, reset=True)
    s = st.get_state()
    print(f"Seeded: {len(st.trades())} trades · phase={s.get('phase')} · "
          f"balance=${s.get('balance'):,.0f} · {len(st.daily_pnl())} P&L days")
    print("Start dashboard:  python dashboard_server.py   ->  http://127.0.0.1:8000")
