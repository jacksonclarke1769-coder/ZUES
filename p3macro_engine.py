"""
ZEUS P3 — Macro Liquidity Reversal · LIVE STREAMING ENGINE (per-level).
Distinct from p3_brake.py (the unrelated cushion brake). Single-bracket model (entry+stop+100pt),
routes like Profile B. Validated on REAL CME 5yr 1m: PF ~2.84 (cost B), every year +, OOS>IS.

Causal, streaming, PER-LEVEL (emit every score>=80 setup, not one-shot). Levels are built from a
rolling 5m buffer strictly from data BEFORE each session — no look-ahead. Feed it COMPLETED 5m bars.
"""
from datetime import timedelta
import numpy as np
import pandas as pd

ET = "America/New_York"
SWEEP_MIN, CLEAN_MAX, DEEP_MAX, DRAW_MIN = 3.0, 25.0, 30.0, 40.0
RECLAIM_WIN, STOP_BUF, TARGET_PTS, SCORE_MIN = 90, 5.0, 100.0, 80
GOOD = {"london_l": 25, "london_h": 22, "pdl": 12, "nyam_l": 8, "pdh": 4}
BAD = {"nyam_h": -20, "pwh": -10, "pwl": -10, "asia_h": -6, "asia_l": 2}
HIGH = ["london_h", "pdh"]        # sweep up -> short   (P3-B level set: London + prior-day)
LOW = ["london_l", "pdl"]
# valid scan sessions per level (post-formation; no look-ahead)
LEVEL_SESS = {"pdh": ["london", "nyam", "nymid"], "pdl": ["london", "nyam", "nymid"],
              "london_h": ["nyam", "nymid"], "london_l": ["nyam", "nymid"]}


def score(sw, draw, lvl, sess, direction, recl):
    s = 50
    s += 20 if sw <= 15 else 12 if sw <= 25 else 4 if sw <= 40 else -8
    if pd.notna(draw):
        s += 16 if draw >= 80 else 10 if draw >= 50 else 3 if draw >= 30 else -6
    s += GOOD.get(lvl, 0) + BAD.get(lvl, 0)
    s += {"nypm": -15, "london": -6, "nyam": 4, "nymid": 2}.get(sess, 0)
    if direction == "long":
        s += 4
    if recl <= 30:
        s += 3
    return int(np.clip(s, 0, 100))


def sess_of(ts):
    h, m = ts.hour, ts.minute
    t = h * 60 + m
    if 0 <= t < 510:
        return "london"            # 00:00-08:30
    if 510 <= t < 690:
        return "nyam"              # 08:30-11:30
    if 690 <= t < 810:
        return "nymid"             # 11:30-13:30
    if 810 <= t < 960:
        return "nypm"              # 13:30-16:00
    return None


class P3MacroEngine:
    """Feed completed 5m bars via on_bar(); returns a list of signal dicts (possibly empty)."""

    def __init__(self, score_min=SCORE_MIN, target=TARGET_PTS):
        self.score_min = score_min
        self.target = target
        self.buf = []              # list of (ts, o,h,l,c)
        self._day = None
        self._levels = {}
        self._watch = {}           # (level,dir) -> state
        self._london_done = False

    def _buf_df(self):
        return pd.DataFrame(self.buf, columns=["ts", "o", "h", "l", "c"]).set_index("ts")

    def _compute_pd(self, date):
        """Prior-day RTH high/low — available at day start (causal)."""
        D = pd.Timestamp(date, tz=ET); b = self._buf_df()
        prior = b[(b.index < D) & (b.index >= D - timedelta(days=5))]
        if len(prior):
            days = sorted(set(prior.index.normalize()))
            if days:
                rth = prior[(prior.index >= days[-1] + timedelta(hours=9, minutes=30)) &
                            (prior.index < days[-1] + timedelta(hours=16))]
                if len(rth):
                    self._levels["pdh"], self._levels["pdl"] = float(rth.h.max()), float(rth.l.min())

    def _compute_london(self, date):
        """London 00:00-08:30 high/low — only valid AFTER 08:30 (causal). Called once at NY-AM."""
        D = pd.Timestamp(date, tz=ET); b = self._buf_df()
        lon = b[(b.index >= D) & (b.index < D + timedelta(hours=8, minutes=30))]
        if len(lon):
            self._levels["london_h"], self._levels["london_l"] = float(lon.h.max()), float(lon.l.min())

    def _add_watch(self, ln, direction):
        if (ln, direction) not in self._watch:
            self._watch[(ln, direction)] = dict(swept=False, ext=None, st=None, dead=False, emitted=False)

    def _reset(self, date):
        self._day = date
        self._levels = {}
        self._watch = {}                            # fresh per-day state (was leaking across days)
        self._london_done = False
        self._compute_pd(date)                      # prior-day levels available now
        for ln in HIGH:
            if ln in self._levels:
                self._add_watch(ln, "short")
        for ln in LOW:
            if ln in self._levels:
                self._add_watch(ln, "long")

    def _ensure_london(self, ts, date):
        """Once we're at/after 08:30, finalize London levels + add their watches (one time)."""
        if self._london_done:
            return
        if ts >= pd.Timestamp(date, tz=ET) + timedelta(hours=8, minutes=30):
            self._compute_london(date)
            self._london_done = True
            if "london_h" in self._levels:
                self._add_watch("london_h", "short")
            if "london_l" in self._levels:
                self._add_watch("london_l", "long")

    def on_bar(self, ts, o, h, l, c):
        ts = pd.Timestamp(ts).tz_convert(ET) if pd.Timestamp(ts).tz else pd.Timestamp(ts, tz=ET)
        self.buf.append((ts, o, h, l, c))
        if len(self.buf) > 6000:
            self.buf = self.buf[-6000:]
        d = ts.date()
        if d != self._day:
            self._reset(d)
        self._ensure_london(ts, d)                 # finalize London levels once 08:30 passes (causal)
        sess = sess_of(ts)
        if sess is None:
            return []
        sigs = []
        for (ln, direction), w in self._watch.items():
            if w["dead"] or w["emitted"] or sess not in LEVEL_SESS[ln]:
                continue
            level = self._levels[ln]
            if not w["swept"]:
                if (direction == "short" and h > level + SWEEP_MIN) or \
                   (direction == "long" and l < level - SWEEP_MIN):
                    w["swept"] = True
                    w["ext"] = h if direction == "short" else l
                    w["st"] = ts
                continue
            # swept: update extreme, check deep / reclaim
            w["ext"] = max(w["ext"], h) if direction == "short" else min(w["ext"], l)
            sweep_size = (w["ext"] - level) if direction == "short" else (level - w["ext"])
            recl_min = (ts - w["st"]).total_seconds() / 60
            if sweep_size > DEEP_MAX or recl_min > RECLAIM_WIN:
                w["dead"] = True
                continue
            reclaim = (c < level) if direction == "short" else (c > level)
            if not reclaim:
                continue
            # candidate -> ENTRY at next bar (live: fill ~current close/next open). Use c as entry ref.
            entry = float(c)
            sgn = 1.0 if direction == "long" else -1.0
            if direction == "short":
                opp = [self._levels[k] for k in LOW if k in self._levels and self._levels[k] < entry]
                draw = entry - max(opp) if opp else np.nan
            else:
                opp = [self._levels[k] for k in HIGH if k in self._levels and self._levels[k] > entry]
                draw = min(opp) - entry if opp else np.nan
            q = score(sweep_size, draw, ln, sess, direction, recl_min)
            stop = w["ext"] - sgn * STOP_BUF
            risk = (entry - stop) * sgn
            w["emitted"] = True   # one per (level,direction)/day
            if (sweep_size > CLEAN_MAX or pd.isna(draw) or draw < DRAW_MIN or
                    q < self.score_min or risk < 20 or risk > 120):
                continue          # logged as skip by the runner if desired; not a trade
            target = entry + sgn * self.target
            sigs.append(dict(ts=str(ts), level=ln, side=direction, entry=round(entry, 2),
                             stop=round(stop, 2), target=round(target, 2), risk_pts=round(risk, 1),
                             sweep_size=round(sweep_size, 1), draw=round(float(draw), 1), score=q,
                             session=sess, signal_ts=str(ts)))
        return sigs
