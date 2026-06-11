"""
SQLite persistence for the NQ Liq-Session bot. Single source of truth for the
dashboard: trades, per-day P&L, rolling eval/account state, and event log.
"""
import sqlite3, json, os, datetime as dt
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_entry TEXT, ts_exit TEXT, direction TEXT, phase TEXT, qty REAL,
  entry_px REAL, stop_px REAL, exit_px REAL, pnl_usd REAL, pnl_pts REAL,
  reason TEXT, mae_pts REAL, mfe_pts REAL, account TEXT
);
CREATE TABLE IF NOT EXISTS state(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, level TEXT, msg TEXT
);
CREATE TABLE IF NOT EXISTS equity(
  ts TEXT PRIMARY KEY, balance REAL, peak REAL, threshold REAL, phase TEXT
);
CREATE INDEX IF NOT EXISTS ix_trades_exit ON trades(ts_exit);
"""

class Store:
    def __init__(self, path="data/bot.db"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        try:
            yield c; c.commit()
        finally:
            c.close()

    # ---- state (key/value json) ----
    def set_state(self, **kw):
        with self.conn() as c:
            for k, v in kw.items():
                c.execute("INSERT INTO state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                          (k, json.dumps(v)))

    def get_state(self, k=None, default=None):
        with self.conn() as c:
            if k is not None:
                r = c.execute("SELECT v FROM state WHERE k=?", (k,)).fetchone()
                return json.loads(r["v"]) if r else default
            return {row["k"]: json.loads(row["v"]) for row in c.execute("SELECT k,v FROM state")}

    # ---- trades ----
    def add_trade(self, **t):
        cols = ["ts_entry","ts_exit","direction","phase","qty","entry_px","stop_px",
                "exit_px","pnl_usd","pnl_pts","reason","mae_pts","mfe_pts","account"]
        vals = [t.get(c) for c in cols]
        with self.conn() as c:
            cur = c.execute(f"INSERT INTO trades({','.join(cols)}) VALUES({','.join('?'*len(cols))})", vals)
            return cur.lastrowid

    def trades(self, limit=None):
        with self.conn() as c:
            q = "SELECT * FROM trades ORDER BY ts_exit"
            if limit: q += f" LIMIT {int(limit)}"
            return [dict(r) for r in c.execute(q)]

    def daily_pnl(self):
        """list of {date, pnl, trades, wins} keyed off exit date."""
        with self.conn() as c:
            rows = c.execute("""
              SELECT substr(ts_exit,1,10) AS d, ROUND(SUM(pnl_usd),2) AS pnl,
                     COUNT(*) AS n, SUM(CASE WHEN pnl_usd>0 THEN 1 ELSE 0 END) AS wins
              FROM trades WHERE ts_exit IS NOT NULL GROUP BY d ORDER BY d""").fetchall()
            return [dict(r) for r in rows]

    # ---- equity snapshots ----
    def add_equity(self, ts, balance, peak, threshold, phase):
        with self.conn() as c:
            c.execute("INSERT INTO equity(ts,balance,peak,threshold,phase) VALUES(?,?,?,?,?) "
                      "ON CONFLICT(ts) DO UPDATE SET balance=excluded.balance,peak=excluded.peak,"
                      "threshold=excluded.threshold,phase=excluded.phase",
                      (ts, balance, peak, threshold, phase))

    def equity(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM equity ORDER BY ts")]

    # ---- events ----
    def log(self, level, msg):
        with self.conn() as c:
            c.execute("INSERT INTO events(ts,level,msg) VALUES(?,?,?)",
                      (dt.datetime.utcnow().isoformat(timespec="seconds"), level, msg))

    def events(self, limit=100):
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))]

    def reset(self):
        with self.conn() as c:
            for t in ("trades","state","events","equity"):
                c.execute(f"DELETE FROM {t}")
