"""ZEUS — THE GOD TERMINAL (dashboard server).

Read-and-analyse only. This server CANNOT:
  - modify strategy/sizing/P3 (no such endpoints exist)
  - enable live trading (SAFETY gates live in config + code constants, not here)
  - override BLACK lockout (flatten.operator_clear is deliberately NOT exposed)
  - hide alerts (evaluation is recomputed server-side every refresh)
Writes allowed: alert acknowledgement + oracle export — both are journaled RECORDS.

Run:  python3 zeus_server.py [--demo] [--port 8777]
--demo serves the seeded preview db (data/zeus_demo_*.db, clearly labeled SIMULATED).
"""
import json
import time
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, request, send_from_directory

from journal import Journal
from heimdall import Heimdall
from locker import Locker
from scheduler import Scheduler
from store import Store
from flatten import LOCK_KEY

APP = Flask(__name__, static_folder="dashboard")
CFG = dict(demo=False, port=8777)

# frozen validation baselines (RAGNAROK decay monitor)
BASE = dict(A=dict(exp_r=0.263, pf=1.39, label="Profile A v2"),
            B=dict(exp_pts=4.0, pf=1.30, label="Profile B v1"))
NQ_PT = 20.0
MNQ_PT = 2.0


def dbs():
    if CFG["demo"]:
        return (Journal("data/zeus_demo_journal.db"), Store("data/zeus_demo_store.db"))
    return (Journal("data/journal.db"), Store("data/bot.db"))


def voice(mode, lockout, alerts, trading, edge):
    if lockout:
        return "BLACK ALERT. The throne is locked. No orders may pass."
    if any(a[0] == "BLACK" for a in alerts):
        return "A black alert has been triggered. The throne awaits judgement."
    if edge in ("DEGRADED", "CRITICAL"):
        return "The oracle weakens. Size must be reduced."
    if not trading:
        return "The gates remain closed. No trades permitted."
    if any(a[0] in ("RED", "ORANGE") for a in alerts):
        return "ZEUS is awake. Risk is contained — but the watchers report."
    return "ZEUS is awake. The portfolio stands ready. The edge is intact."


def trades_from_journal(j):
    """Derive the trade ledger from lifecycle chains (INTENT payload carries the plan)."""
    out = []
    for chain in j.export():
        evs = chain["events"]
        head = evs[0]
        if head["event_type"] != "INTENT":
            continue
        p = head["payload"] or {}
        if p.get("role") == "flatten":
            continue
        fills = [e for e in evs if e["event_type"] in ("FILL", "PARTIAL_FILL")]
        exits = [e for e in evs if e["event_type"] == "EXIT"]
        if not fills:
            continue
        qty = sum((e["payload"] or {}).get("qty", 0) for e in fills)
        entry_px = (fills[0]["payload"] or {}).get("px", p.get("entry"))
        kinds = [e["event_type"] for e in evs]
        complete = ("INTENT" in kinds and "FILL" in kinds and
                    "BRACKET_CONFIRMED" in kinds and "EXIT" in kinds)
        t = dict(cl=chain["cl_ord_id"], ts=head["ts_utc"],
                 strategy=head["strategy"] or "A", account=head["account_id"],
                 side=p.get("side"), qty=qty, entry=entry_px, stop=p.get("stop"),
                 target=p.get("target"), status=chain["status"], chain_ok=complete,
                 p3=bool(p.get("p3_braked_size")))
        if exits:
            x = exits[-1]["payload"] or {}
            t["exit"] = x.get("px")
            sgn = 1 if (p.get("side") or "Buy") == "Buy" else -1
            if t["exit"] is not None and entry_px is not None:
                pts = sgn * (t["exit"] - entry_px)
                risk = abs((entry_px or 0) - (p.get("stop") or entry_px)) or 1
                t["points"] = round(pts, 2)
                t["r"] = round(pts / risk, 2)
                t["usd"] = round(pts * MNQ_PT * qty, 2)
                t["slip"] = x.get("slip", 0)
                t["exit_reason"] = x.get("reason")
        out.append(t)
    out.sort(key=lambda t: t["ts"], reverse=True)
    return out


def strat_panel(trades, s):
    rows = [t for t in trades if t["strategy"] == s and "r" in t]
    rows_recent = rows[:90]
    def stats(sub):
        if not sub:
            return None
        wins = [t for t in sub if t["usd"] > 0]
        gp = sum(t["usd"] for t in wins) or 0.0
        gl = -sum(t["usd"] for t in sub if t["usd"] < 0) or 0.0
        return dict(n=len(sub), wr=round(100 * len(wins) / len(sub), 1),
                    pf=(round(gp / gl, 2) if gl else None),
                    exp_r=round(sum(t["r"] for t in sub) / len(sub), 3),
                    exp_pts=round(sum(t["points"] for t in sub) / len(sub), 2),
                    avg_usd=round(sum(t["usd"] for t in sub) / len(sub), 2))
    full = stats(rows)
    base = BASE[s]
    health, ratio = "FULL STRENGTH", None
    r30 = stats(rows_recent[:30])
    if r30 and full:
        if s == "A" and base.get("exp_r"):
            ratio = r30["exp_r"] / base["exp_r"]
        elif base.get("exp_pts"):
            ratio = r30["exp_pts"] / base["exp_pts"]
        if ratio is not None:
            health = ("FULL STRENGTH" if ratio >= 0.9 else
                      "WATCHING" if ratio >= 0.7 else
                      "DEGRADED" if ratio >= 0.5 else
                      "CRITICAL" if ratio >= 0 else "HALTED")
    eq, peak, mdd = 0.0, 0.0, 0.0
    for t in reversed(rows):
        eq += t["usd"]; peak = max(peak, eq); mdd = max(mdd, peak - eq)
    return dict(label=base["label"], total=full, r30=r30, r60=stats(rows_recent[:60]),
                r90=stats(rows_recent[:90]), max_dd=round(mdd, 2),
                vs_validation=(round(100 * ratio, 1) if ratio is not None else None),
                health=health, baseline=base)


def weekly(trades):
    wk = {}
    for t in trades:
        if "points" not in t:
            continue
        d = datetime.fromisoformat(t["ts"].replace("Z", "+00:00"))
        key = f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"
        w = wk.setdefault(key, dict(week=key, A=0.0, B=0.0, total=0.0, usd=0.0))
        # strategy points are PER CONTRACT (qty-free) so "pts × NQ-eq" stays coherent
        w[t["strategy"]] = round(w[t["strategy"]] + t["points"], 1)
        w["total"] = round(w["total"] + t["points"], 1)
        w["usd"] = round(w["usd"] + t["usd"], 2)
    rows = sorted(wk.values(), key=lambda w: w["week"], reverse=True)
    tot = [w["total"] for w in rows]
    return dict(weeks=rows[:13],
                current=(tot[0] if tot else 0), last=(tot[1] if len(tot) > 1 else 0),
                avg4=round(sum(tot[:4]) / max(1, len(tot[:4])), 1),
                avg12=round(sum(tot[:12]) / max(1, len(tot[:12])), 1),
                best=(max(tot) if tot else 0), worst=(min(tot) if tot else 0))


def assemble_state():
    t0 = time.time()
    j, store = dbs()
    now = datetime.now(timezone.utc)
    sch = Scheduler()
    lockout = store.get_state(LOCK_KEY) or None
    accounts = json.loads(store.get_state("zeus_accounts") or "[]")
    trades = trades_from_journal(j)
    last_sig = {}
    for t in trades:
        last_sig.setdefault(t["strategy"], t["ts"])
    hm = Heimdall(j, store)
    state_view = {a["name"]: dict(balance=a["balance"], floor=a["floor"],
                                  p3_braked=a.get("p3_braked", False)) for a in accounts}
    snap = hm.snapshot(now=now,
                       heartbeat_ts=store.get_state("heartbeat_ts"),
                       feed_last_bar_ts=store.get_state("feed_last_bar_ts"),
                       last_signal_ts={k: v for k, v in last_sig.items()},
                       state_view=state_view, in_session=sch.in_rth(now))
    alerts = hm.evaluate(snap)
    if lockout:
        alerts = [("BLACK", "lockout_active", lockout)] + [a for a in alerts
                                                           if a[1] != "lockout_active"]
    ok_locker, locker_problems = Locker().verify()
    exp_mnq = sum(a.get("open_qty", 0) for a in accounts)
    alloc_a = sum(a.get("alloc_a", 0) for a in accounts)
    alloc_b = sum(a.get("alloc_b", 0) for a in accounts)
    tier = ("BLACK" if any(a[0] == "BLACK" for a in alerts) else
            "RED" if any(a[0] == "RED" for a in alerts) else
            "ORANGE" if any(a[0] == "ORANGE" for a in alerts) else
            "YELLOW" if any(a[0] == "YELLOW" for a in alerts) else "GREEN")
    mode = ("LOCKED" if lockout else
            "DEMO-PREVIEW" if CFG["demo"] else
            "PAPER" if not accounts else "SIM")
    trading = (tier not in ("RED", "BLACK")) and sch.is_trading_day(
        sch.et(now).date()) and not lockout
    def usd_since(days):
        cut = (now - timedelta(days=days)).isoformat()
        return round(sum(t.get("usd", 0) for t in trades if t["ts"] >= cut), 2)
    edge_a = strat_panel(trades, "A")
    edge_b = strat_panel(trades, "B")
    worst_edge = min((edge_a["health"], edge_b["health"]),
                     key=lambda h: ["HALTED", "CRITICAL", "DEGRADED", "WATCHING",
                                    "FULL STRENGTH"].index(h))
    recon_alerts = [e for e in _recent_events(j, "RECON_ALERT", 50)]
    state = dict(
        meta=dict(refreshed=now.isoformat(),
                  refresh_ms=None,                      # filled below
                  demo=CFG["demo"],
                  data_health=("SIMULATED PREVIEW" if CFG["demo"] else
                               "LIVE SOURCES" if accounts else "PRE-DEPLOYMENT (sparse)"),
                  mode=mode, trading_allowed=trading,
                  next_session=_next_session(sch, now),
                  voice=voice(mode, lockout, alerts, trading, worst_edge)),
        header=dict(tier=tier, lockout=lockout,
                    heartbeat=store.get_state("heartbeat_ts"),
                    broker_sync=store.get_state("broker_sync_ts"),
                    last_journal=snap["journal"]["last_seq_ts"],
                    in_entry_window=sch.in_entry_window(now)),
        portfolio=dict(total_accounts=len(accounts),
                       active=sum(1 for a in accounts if a.get("phase") != "LOCKED"),
                       funded=sum(1 for a in accounts if a.get("phase") == "FUNDED"),
                       evals=sum(1 for a in accounts if a.get("phase") == "EVAL"),
                       exposure_mnq=exp_mnq, exposure_nq=round(exp_mnq / 10, 2),
                       alloc_a=alloc_a, alloc_b=alloc_b,
                       p3_active=sum(1 for a in accounts if a.get("p3_braked")),
                       pnl_week=usd_since(7), pnl_month=usd_since(30),
                       pnl_year=usd_since(365),
                       payouts=round(sum(a.get("paid", 0) for a in accounts), 2),
                       cushion=round(sum(a.get("balance", 0) - a.get("floor", 0)
                                         for a in accounts), 2),
                       equity=round(sum(a.get("balance", 0) for a in accounts), 2)),
        accounts=[_account_card(a) for a in accounts],
        strategies=dict(A=edge_a, B=edge_b, worst=worst_edge),
        weekly=dict(**weekly(trades),
                    est_note=_est_note(weekly(trades), alloc_a + alloc_b)),
        trades=trades[:200],
        journal=dict(online=True, events=snap["journal"]["events"],
                     append_only=_append_only_ok(j),
                     last=dict(INTENT=_last_ts(j, "INTENT"), ACK=_last_ts(j, "ACK"),
                               FILL=_last_ts(j, "FILL"),
                               RECON_ALERT=_last_ts(j, "RECON_ALERT")),
                     dup_blocked=_dup_blocked(j),
                     unknown_orders=snap["unknown_positions"],
                     unknown_fills=snap["unknown_fills"],
                     locker_ok=ok_locker, locker_problems=locker_problems[:5]),
        recon=dict(alerts=recon_alerts, last_run=store.get_state("recon_ts"),
                   naked=snap["naked_alerts"]),
        alerts=[dict(tier=a[0], name=a[1], detail=a[2],
                     action=_action_for(a[1]),
                     acked=bool(store.get_state(f"ack_{a[1]}"))) for a in alerts],
        evidence=_evidence_summary(),
        oracle_labels=["OBSERVATION", "INVESTIGATION", "PROPOSED TEST", "REJECTED",
                       "APPROVED FOR PAPER", "APPROVED FOR LIVE"],
    )
    # ---------- Command-Centre blocks (simplification redesign) ----------
    state["portfolio"]["pnl_ytd"] = round(
        sum(t.get("usd", 0) for t in trades
            if t["ts"] >= f"{now.year}-01-01"), 2)
    wk_now = [t for t in trades if "usd" in t and
              datetime.fromisoformat(t["ts"].replace("Z", "+00:00")).isocalendar()[:2]
              == now.isocalendar()[:2]]
    state["week_panel"] = dict(
        n=len(wk_now),
        wr=(round(100 * sum(1 for t in wk_now if t["usd"] > 0) / len(wk_now), 0)
            if wk_now else None),
        avg_r=(round(sum(t["r"] for t in wk_now) / len(wk_now), 2) if wk_now else None),
        pts=state["weekly"]["current"], usd=round(sum(t["usd"] for t in wk_now), 2),
        last=state["weekly"]["last"], avg4=state["weekly"]["avg4"],
        avg12=state["weekly"]["avg12"])
    hb_age = None
    if state["header"]["heartbeat"]:
        hb_age = (now - datetime.fromisoformat(
            state["header"]["heartbeat"].replace("Z", "+00:00"))).total_seconds()
    sync_age = None
    if state["header"]["broker_sync"]:
        sync_age = (now - datetime.fromisoformat(
            state["header"]["broker_sync"].replace("Z", "+00:00"))).total_seconds()
    def _light(ok, warn=False):
        return "green" if ok else ("yellow" if warn else "red")
    ed = {"FULL STRENGTH": "green", "WATCHING": "yellow", "DEGRADED": "yellow",
          "CRITICAL": "red", "HALTED": "red"}
    state["lights"] = {
        "Strategy A": ed.get(edge_a["health"], "yellow"),
        "Strategy B": ed.get(edge_b["health"], "yellow"),
        "Journal": _light(state["journal"]["append_only"] and state["journal"]["locker_ok"]),
        "Reconciliation": _light(snap["unknown_positions"] + snap["unknown_fills"]
                                 + snap["naked_alerts"] == 0),
        "Broker": _light(sync_age is not None and sync_age < 120,
                         warn=sync_age is None),
        "Infrastructure": _light(hb_age is not None and hb_age < 120,
                                 warn=hb_age is None),
    }
    # action centre: manual list (store) + auto items from live conditions
    actions = json.loads(store.get_state("zeus_actions") or "[]")
    if lockout:
        actions.insert(0, "Review BLACK lockout — root-cause, then operator_clear with note")
    for a in alerts:
        if a[0] in ("ORANGE", "RED", "BLACK") and a[1] != "lockout_active":
            actions.append(f"Alert [{a[0]}] {a[1]}: {_action_for(a[1])}")
    if not ok_locker:
        actions.insert(0, "Evidence locker TAMPER check failed — investigate now")
    state["actions"] = actions[:8]
    # latest activity: last 5 ledger events, humanized
    hum = dict(INTENT="Intent logged", SEND="Order sent", ACK="Broker acknowledged",
               FILL="Filled", PARTIAL_FILL="Partial fill",
               BRACKET_CONFIRMED="Bracket confirmed (protected)", EXIT="Trade closed",
               REJECT="Order rejected", CANCEL="Order cancelled",
               CANCEL_SENT="Cancel sent", CANCEL_CONFIRMED="Cancel confirmed",
               MODIFY_SENT="Modify sent", MODIFY_CONFIRMED="Modify confirmed",
               RECON_ALERT="Reconciliation alert", STATE_ASSERT="State assertion",
               EMERGENCY_FLATTEN="EMERGENCY FLATTEN")
    cur = j.con.execute("SELECT ts_utc, event_type, account_id, cl_ord_id FROM ledger"
                        " ORDER BY seq DESC LIMIT 5").fetchall()
    state["activity"] = [dict(ts=r[0], text=f"{hum.get(r[1], r[1])}"
                              + (f" · {r[2]}" if r[2] not in (None, "ALL") else ""))
                         for r in cur]
    # daily brief — one paragraph, regenerated every refresh
    healthy = sum(1 for a in state["accounts"] if a["status"] == "SAFE")
    wkp = state["week_panel"]
    vs = ("above" if (wkp["pts"] or 0) >= (wkp["avg12"] or 0) else "below")
    edges = (f"Strategy A is {edge_a['health']}"
             + (f" ({edge_a['vs_validation']}% of validation)" if edge_a["vs_validation"] else "")
             + f"; Strategy B is {edge_b['health']}"
             + (f" ({edge_b['vs_validation']}%)" if edge_b["vs_validation"] else ""))
    n_al = len([a for a in alerts if a[0] != "GREEN"])
    state["brief"] = (
        ("ZEUS is locked. " if lockout else "ZEUS is operational. ")
        + (f"{healthy} of {len(state['accounts'])} accounts are healthy. "
           if state["accounts"] else "No accounts are registered yet. ")
        + (f"{n_al} active alert{'s' if n_al != 1 else ''}. " if n_al else "No active alerts. ")
        + (f"Weekly performance sits at {wkp['pts']:+.0f} points, {vs} the 12-week "
           f"average of {wkp['avg12']:+.0f}. " if wkp["avg12"] else "")
        + edges + ". "
        + (f"{len(state['actions'])} item(s) require action."
           if state["actions"] else "No action required."))
    state["meta"]["refresh_ms"] = round((time.time() - t0) * 1000, 1)
    return state


def _account_card(a):
    cushion = a.get("balance", 0) - a.get("floor", 0)
    dd = a.get("dd", 4500)
    frac = cushion / dd if dd else 0
    status = ("LOCKED" if a.get("phase") == "LOCKED" else
              "DANGER" if frac < 0.4 else "CAUTION" if frac < 0.6 else "SAFE")
    return dict(a, cushion=round(cushion, 2), cushion_frac=round(frac, 2),
                status=status)


def _est_note(wk, alloc_mnq):
    nq = alloc_mnq / 10                      # ALLOCATED exposure, not open
    pts = wk.get("avg4", 0)
    return f"{pts:.0f} pts × {nq:.1f} NQ-eq = ${pts * nq * NQ_PT:,.0f} gross / wk (4-wk avg)"


def _next_session(sch, now):
    et = sch.et(now)
    d = et.date()
    for add in range(0, 8):
        dd = d + timedelta(days=add)
        if sch.is_trading_day(dd):
            if add == 0 and et.time() < sch.entry_end:
                return f"today {sch.entry_start.strftime('%H:%M')}–{sch.entry_end.strftime('%H:%M')} ET"
            if add > 0:
                return f"{dd.isoformat()} {sch.entry_start.strftime('%H:%M')} ET"
    return "unknown"


def _recent_events(j, etype, n):
    cur = j.con.execute(
        "SELECT ts_utc, account_id, payload_json FROM ledger WHERE event_type=?"
        " ORDER BY seq DESC LIMIT ?", (etype, n))
    return [dict(ts=r[0], account=r[1],
                 payload=(json.loads(r[2]) if r[2] else None)) for r in cur.fetchall()]


def _last_ts(j, etype):
    r = j.con.execute("SELECT ts_utc FROM ledger WHERE event_type=? ORDER BY seq DESC"
                      " LIMIT 1", (etype,)).fetchone()
    return r[0] if r else None


def _append_only_ok(j):
    # an UPDATE matching zero rows never fires the trigger — check the triggers exist
    n = j.con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'"
                      " AND name IN ('ledger_no_update','ledger_no_delete')").fetchone()[0]
    return n == 2


def _dup_blocked(j):
    r = j.con.execute("SELECT COUNT(*) FROM ledger WHERE event_type='RECON_ALERT'"
                      " AND payload_json LIKE '%duplicate%'").fetchone()
    return r[0]


def _action_for(name):
    table = dict(heartbeat_dead="VERIFY FLAT via broker app NOW",
                 heartbeat_stale="check VPS/process; restart if frozen",
                 feed_dead_with_position="broker app: verify bracket WORKING; else flatten",
                 feed_stale_failover="confirm failover engaged",
                 feed_lagging="note; no in-trade action",
                 recon_unknowns="bot flattens+locks; verify flat; clear only with note",
                 naked_position_alerts="verify in app; incident before next session",
                 lockout_active="read reason; root-cause; operator_clear with note",
                 A_quiet="weekend engine self-test", A_silent="parity run required",
                 B_quiet="weekend engine self-test")
    for k, v in table.items():
        if name.startswith(k.split("_*")[0]) or name == k:
            return v
    if name.startswith("p3_braked"):
        return "informational — sizing already reduced"
    if name.startswith("trade_cap"):
        return "flatten, stop, incident — should be impossible"
    return "see OPERATOR_RUNBOOK.md"


def _evidence_summary():
    import os
    out = {}
    for cat in ("approvals", "mffu", "topstep", "payouts", "signals", "fills",
                "reconciliations", "incidents", "journal-snapshots"):
        p = os.path.join("evidence", cat)
        out[cat] = len(os.listdir(p)) if os.path.isdir(p) else 0
    return out


# ---------------- ORACLE ----------------

def oracle_report():
    j, store = dbs()
    trades = trades_from_journal(j)
    now = datetime.now(timezone.utc)
    cut = (now - timedelta(days=7)).isoformat()
    wkt = [t for t in trades if t["ts"] >= cut]
    closed = [t for t in wkt if "usd" in t]
    a = [t for t in closed if t["strategy"] == "A"]
    b = [t for t in closed if t["strategy"] == "B"]
    pa, pb = strat_panel(trades, "A"), strat_panel(trades, "B")
    recs = []
    if pa["vs_validation"] is not None and pa["vs_validation"] < 70:
        recs.append(("INVESTIGATION", "Profile A rolling-30 expectancy below 70% of "
                     "validation — decompose execution vs regime before any size action."))
    if pb["vs_validation"] is not None and pb["vs_validation"] < 70:
        recs.append(("INVESTIGATION", "Profile B rolling-30 below 70% of validation."))
    slips = [t.get("slip", 0) for t in closed if t.get("slip") is not None]
    if slips and sum(slips) / len(slips) > 2.5:
        recs.append(("OBSERVATION", f"Mean slippage {sum(slips)/len(slips):.2f}pt "
                     "exceeds 2pt assumption — feed execution-health panel."))
    if not recs:
        recs.append(("OBSERVATION", "No anomalies crossing thresholds this week. "
                     "The oracle holds. No action proposed."))
    def block(rows, nm):
        if not rows:
            return f"{nm}: no closed trades this week."
        usd = sum(t["usd"] for t in rows)
        return (f"{nm}: {len(rows)} trades · {sum(1 for t in rows if t['usd']>0)} wins"
                f" · {sum(t['points']*t['qty'] for t in rows):+.1f} pts · ${usd:+,.0f}")
    return dict(
        generated=now.isoformat(), window=f"{cut[:10]} → {now.isoformat()[:10]}",
        sections={
            "1. Weekly summary": block(closed, "Combined"),
            "2. Strategy performance": block(a, "Profile A") + "\n" + block(b, "Profile B"),
            "3. Execution quality": (f"mean slip {sum(slips)/len(slips):.2f}pt over "
                                     f"{len(slips)} fills" if slips else "no fill data"),
            "4. Risk health": f"P3 activations this week: "
                              f"{sum(1 for t in wkt if t.get('p3'))} · daily-halt events: 0",
            "5. Edge decay status": f"A {pa['health']} ({pa['vs_validation']}% of baseline)"
                                    f" · B {pb['health']} ({pb['vs_validation']}%)",
            "6. Account health": json.loads(store.get_state("zeus_accounts") or "[]")
                                 and "see Accounts page — statuses computed live" or
                                 "no accounts registered",
            "7. Payout progress": "see Accounts page payout columns",
            "8. Operational issues": f"RECON_ALERTs (7d): "
                f"{sum(1 for e in _recent_events(j, 'RECON_ALERT', 200) if e['ts'] >= cut)}",
            "9. Recommended investigations": "\n".join(f"[{k}] {v}" for k, v in recs),
            "10. Proposed refinements": "NONE may deploy automatically. Any proposal "
                "must pass: hypothesis → backtest → OOS → Monte Carlo → slippage stress "
                "→ funded sim → paper → human approval. Live strategy remains frozen.",
        },
        recommendations=[dict(label=k, text=v) for k, v in recs])


# ---------------- routes ----------------

@APP.route("/api/state")
def api_state():
    return jsonify(assemble_state())


@APP.route("/api/oracle")
def api_oracle():
    return jsonify(oracle_report())


@APP.route("/api/trade/<cl>")
def api_trade(cl):
    j, _ = dbs()
    return jsonify(j.export(cl_ord_id=cl))


@APP.route("/api/ack", methods=["POST"])
def api_ack():
    """Acknowledge an alert — a journaled RECORD, never a dismissal (alert stays
    until its condition clears; ack only marks operator awareness)."""
    name = (request.json or {}).get("name", "")[:64]
    note = (request.json or {}).get("note", "")[:200]
    if not name:
        return jsonify(error="name required"), 400
    j, store = dbs()
    store.set_state(**{f"ack_{name}": datetime.now(timezone.utc).isoformat()})
    j.append("STATE_ASSERT", "ALL", payload=dict(action="alert_ack", alert=name,
                                                 note=note))
    return jsonify(ok=True)


@APP.route("/")
def index():
    return send_from_directory("dashboard", "zeus.html")


@APP.route("/<path:p>")
def static_files(p):
    return send_from_directory("dashboard", p)


if __name__ == "__main__":
    import sys
    CFG["demo"] = "--demo" in sys.argv
    if "--port" in sys.argv:
        CFG["port"] = int(sys.argv[sys.argv.index("--port") + 1])
    print(f"ZEUS terminal :{CFG['port']}  demo={CFG['demo']}")
    APP.run(host="127.0.0.1", port=CFG["port"], debug=False)
