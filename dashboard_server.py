"""
Dashboard backend — FastAPI. Serves the static dashboard and a JSON API backed entirely
by REAL backtest results in the bot's SQLite store (built by build_real_backtest.py).
Nothing simulated or random — every trade is an actual historical trade.

  python dashboard_server.py    ->  http://127.0.0.1:8000
"""
import os, csv as _csv
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from store import Store
try:
    import config; DB = config.DB_PATH; PAPER_DB = getattr(config, "PAPER_DB_PATH", "data/paper.db")
except Exception:
    DB = "data/bot.db"; PAPER_DB = "data/paper.db"

HERE = os.path.dirname(os.path.abspath(__file__))


def paper_payload(store, here=HERE, csv_name="paper_fill_log.csv"):
    """Assemble the paper-live panel: the aggregate metrics (store state) + recent ledger
    rows (paper_fill_log.csv). Pure/testable — no FastAPI needed."""
    panel = store.get_state("paper") or {}
    path = os.path.join(here, csv_name)
    if not os.path.exists(path):
        path = csv_name                        # fall back to cwd
    log = []
    if os.path.exists(path):
        with open(path, newline="") as f:
            log = list(_csv.DictReader(f))
    return dict(panel=panel, log=log[-200:])
app = FastAPI(title="NQ Liq-Session — Backtest Dashboard")
store = Store(DB)              # backtest / overview
paper_store = Store(PAPER_DB)  # paper-live panel (separate DB)

@app.get("/api/overview")
def overview():
    s = store.get_state()
    return JSONResponse(dict(
        strategy_name=s.get("strategy_name", "Profile A"),
        config=s.get("config", ""), status=s.get("status", ""), data_note=s.get("data_note", ""),
        summary=s.get("summary", {}), validation=s.get("validation", {}),
        walkforward=s.get("walkforward", []), recent=s.get("recent", {}),
        edge=s.get("edge", {}), funded=s.get("funded", {}), risk=s.get("risk", {}),
        live=s.get("live", {}),
        sizing_matrix=s.get("sizing_matrix", {}), sizing_matrix_note=s.get("sizing_matrix_note", ""),
        sizing_matrix_notes=s.get("sizing_matrix_notes", {}),
    ))


@app.get("/api/monthly")
def monthly():
    # aggregate the daily P&L into months for the calendar/bar view
    rows = store.daily_pnl()
    agg = {}
    for r in rows:
        mo = r["d"][:7]
        a = agg.setdefault(mo, {"month": mo, "pnl": 0.0, "trades": 0, "wins": 0})
        a["pnl"] += r["pnl"] or 0; a["trades"] += r["n"]; a["wins"] += r["wins"]
    return JSONResponse(sorted(agg.values(), key=lambda x: x["month"]))

@app.get("/api/trades")
def trades():
    return JSONResponse(store.trades())

@app.get("/api/daily")
def daily():
    return JSONResponse(store.daily_pnl())

@app.get("/api/equity")
def equity():
    return JSONResponse(store.equity())

@app.get("/api/paper")
def paper():
    return JSONResponse(paper_payload(paper_store))   # reads the separate paper-live DB

@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "dashboard", "index.html"),
                        headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

app.mount("/static", StaticFiles(directory=os.path.join(HERE, "dashboard")), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
