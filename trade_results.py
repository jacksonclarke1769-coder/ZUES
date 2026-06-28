"""Per-day trade-results ledger that feeds the ZEUS dashboard P&L calendar.

Append-only CSV (out/ares/trade_results.csv) — one row per RESOLVED trade. The dashboard
calendar (/api/calendar) aggregates these by date. Display / reporting only: recording a
trade here never places, modifies, or cancels an order. The bot appends to it as trades
resolve (auto_live), so paper and live sessions land on the calendar automatically.
"""
import csv
import os

PATH = "out/ares/trade_results.csv"
COLS = ["date", "mode", "account", "strategy", "direction", "contracts", "pnl", "note"]
DOLLARS_PER_POINT = 2.0   # MNQ = $2 per point per contract


HYPO_TAG = "HYPOTHETICAL"   # note prefix for projected/un-filled P&L (dashboard must not call it realised)
# CONFIGLOCK: a row counts as REALISED only if its note explicitly proves a fill/resolution.
# Everything else (modeled, pending, synthetic full-qty +2R, blank) is HYPOTHETICAL — so even a
# fresh clone (without the locally-corrected CSV) never shows synthetic P&L as realised.
_REALISED_MARKERS = ("fill-backed", "broker fill", "broker-confirmed", "confirmed fill",
                     "resolution-backed")
_HYPO_MARKERS = (HYPO_TAG.lower(), "modeled", "pending", "synthetic", "tp hit (gross)")


def is_realised(note):
    n = (note or "").lower()
    if any(m in n for m in _HYPO_MARKERS):
        return False
    return any(m in n for m in _REALISED_MARKERS)


def pnl_from_r(result_r, entry, stop, contracts, dpp=DOLLARS_PER_POINT):
    """Realised $ for a trade from its R-multiple outcome and bracket geometry.
    Returns None for an unfilled/unresolved trade (result_r is None)."""
    if result_r is None:
        return None
    return float(result_r) * abs(float(entry) - float(stop)) * dpp * float(contracts)


def exit3_split(qty):
    q = int(qty); tp1 = q // 2; return tp1, q - tp1


def pnl_exit3(entry, stop, qty, r_tp1=1.0, r_tp2=2.0, dpp=DOLLARS_PER_POINT):
    """EXITFORGE: Exit #3 integer-split FULL-WIN $ — tp1_qty @ +r_tp1 R, tp2_qty @ +r_tp2 R,
    shared stop. This is the official live/eval model's full-win value (NOT full-qty @ 2R)."""
    tp1, tp2 = exit3_split(qty)
    risk = abs(float(entry) - float(stop))
    return (r_tp1 * tp1 + r_tp2 * tp2) * risk * dpp


def record(date, mode, account, strategy, direction, contracts, pnl, note="",
           fill_backed=True, path=PATH):
    """Append one resolved trade to the ledger. `fill_backed=False` tags the row HYPOTHETICAL
    so the dashboard never reports a projected/un-filled result as realised P&L."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    is_new = not os.path.exists(path)
    if fill_backed and not is_realised(note):
        note = f"fill-backed · {note}".rstrip(" ·")          # mark genuine broker-confirmed P&L
    elif not fill_backed and HYPO_TAG not in note:
        note = f"{HYPO_TAG} · {note}".rstrip(" ·")
    row = [date, mode, account, strategy, direction, contracts, round(float(pnl), 2), note]
    with open(path, "a", newline="") as fh:
        w = csv.writer(fh)
        if is_new:
            w.writerow(COLS)
        w.writerow(row)
    return dict(zip(COLS, row))


def record_resolved(rows, start_n, mode, account, contracts, strategy="A", path=PATH):
    """Append PaperTracker rows[start_n:] that are RESOLVED (result_R not None) to the ledger,
    converting each trade's R outcome to $. Returns the new high-water mark (== len(rows)) so
    the caller passes it back next bar — append-once, no duplicates. Unfilled/missed signals
    (result_R is None) are skipped (no position, no P&L)."""
    n = start_n
    while n < len(rows):
        r = rows[n]; n += 1
        rr = r.get("result_R")
        if rr is None:
            continue
        pnl = pnl_from_r(rr, r["entry"], r["stop"], contracts)
        nz = r.get("notes")
        nz = ",".join(nz) if isinstance(nz, (list, tuple)) else (nz or "")
        tag = "modeled · pending broker recon" if mode == "live" else "paper · modeled fill"
        # modeled fills are NOT broker-confirmed -> hypothetical until a recon step proves the fill
        record(date=r["date"], mode=mode, account=account, strategy=strategy,
               direction=r["direction"], contracts=contracts, pnl=pnl, fill_backed=False,
               note=f"{tag} · {rr:+.2f}R gross" + (f" · {nz}" if nz else ""), path=path)
    return n


def by_day(path=PATH, live_only=False):
    """Aggregate the ledger by calendar date -> {date: {pnl, trades, mode}}. One shared
    implementation for the dashboard API and tests. A day with any live trade reads LIVE.

    live_only=True drops every paper-mode row before aggregating, so the live dashboard
    never shows a paper/demo trade. (Default False keeps the full ledger for tests/back-compat.)"""
    days = {}
    if os.path.exists(path):
        with open(path) as fh:
            for r in csv.DictReader(fh):
                d = (r.get("date") or "").strip()
                if not d:
                    continue
                if live_only and (r.get("mode") or "paper").strip().lower() != "live":
                    continue
                try:
                    pnl = float(r.get("pnl") or 0)
                except ValueError:
                    continue
                e = days.setdefault(d, {"pnl": 0.0, "hypo": 0.0, "trades": 0, "modes": set()})
                if is_realised(r.get("note")):
                    e["pnl"] += pnl                        # fill/resolution-backed only
                else:
                    e["hypo"] += pnl                       # modeled/synthetic -> NOT realised
                e["trades"] += 1
                e["modes"].add((r.get("mode") or "paper").strip().lower())
    return {d: {"pnl": round(v["pnl"], 2),                  # fill-backed / realised only
                "hypothetical_pnl": round(v["hypo"], 2),    # projected, labelled separately
                "trades": v["trades"],
                "mode": "live" if "live" in v["modes"] else "paper"}
            for d, v in days.items()}


def live_trades(path=PATH, account=None):
    """Every LIVE-mode trade as an individual row, newest-first — the dashboard review list.
    Each row carries `confirmed` (True = broker/operator-verified fill, False = bot-modeled,
    pending eye-confirm) so the review screen can flag what still needs a manual fill check.
    Optionally filter to one `account` (e.g. 'APEX-50K-1')."""
    rows = []
    if os.path.exists(path):
        with open(path) as fh:
            for r in csv.DictReader(fh):
                if (r.get("mode") or "").strip().lower() != "live":
                    continue
                if account and (r.get("account") or "").strip() != account:
                    continue
                try:
                    pnl = round(float(r.get("pnl") or 0), 2)
                except ValueError:
                    pnl = 0.0
                rows.append({"date": (r.get("date") or "").strip(),
                             "account": (r.get("account") or "").strip(),
                             "strategy": (r.get("strategy") or "").strip(),
                             "direction": (r.get("direction") or "").strip(),
                             "contracts": (r.get("contracts") or "").strip(),
                             "pnl": pnl,
                             "confirmed": is_realised(r.get("note")),
                             "note": (r.get("note") or "").strip()})
    rows.sort(key=lambda x: x["date"], reverse=True)
    return rows
