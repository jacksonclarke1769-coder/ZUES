"""WP-F statistics primitives (PREREG_PHASE3.md §4-§5, git hash cd652ea81093).

numpy/scipy/pandas ONLY (SPEC.md hard rule: no new heavy deps; sklearn/statsmodels are
NOT installed and must not be added). Everything the harness needs is implemented here:

  * weekly calendar-week ids + the 4 IS-year buckets,
  * the VECTORIZED weekly block bootstrap for contrast means/proportions (per-week sums
    precomputed once; 2,000 draws = one (draws x weeks) multiplicity matrix @ per-week
    vectors -- never a per-row loop),
  * OLS / logistic (IRLS) B-residualization for the G2 ICT-free incrementality gate,
  * logistic regression (IRLS) + blocked-by-week 5-fold out-of-fold AUC for F2,
  * a vectorized weekly-block AUC-uplift bootstrap (the c^T U c quadratic form over a
    precomputed cross-week Mann-Whitney U matrix -- exact, matches roc_auc on c=ones),
  * Benjamini-Hochberg (G4).

NO PF/WR/expectancy anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

IS_START = pd.Timestamp("2021-06-22", tz="America/New_York")
# 4 IS-year bucket boundaries (annual windows from the IS start; IS end = start + 4y).
IS_YEAR_BOUNDS = [IS_START + pd.DateOffset(years=k) for k in range(5)]  # 5 edges -> 4 buckets


# --- calendar keys ------------------------------------------------------------------


def week_ids(t0: pd.Series) -> Tuple[np.ndarray, int]:
    """Dense 0..W-1 calendar-week index (ISO year-week) for each t0. Returns
    (week_id_array, W)."""
    ts = pd.to_datetime(t0)
    iso = ts.dt.isocalendar()
    key = iso["year"].to_numpy().astype(np.int64) * 54 + iso["week"].to_numpy().astype(np.int64)
    uniq, inv = np.unique(key, return_inverse=True)
    return inv.astype(np.int64), int(len(uniq))


def is_year_bucket(t0: pd.Series) -> np.ndarray:
    """1..4 IS-year bucket (annual window from IS_START). Rows outside [start, start+4y)
    get 0 (should not occur in an IS file)."""
    ts = pd.to_datetime(t0)
    edges = np.array([b.value for b in IS_YEAR_BOUNDS], dtype=np.int64)
    v = ts.astype("int64").to_numpy()
    return np.searchsorted(edges, v, side="right").astype(np.int64)


# --- draw matrix for the weekly block bootstrap -------------------------------------


def make_draw_matrix(W: int, n_draws: int, seed: int) -> np.ndarray:
    """(n_draws x W) week-multiplicity matrix: each draw resamples W weeks with
    replacement from the W calendar weeks (block bootstrap). Built once, reused across
    every statistic in a family so draws are comparable. float32 for the @-products."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, W, size=(n_draws, W))  # each row: W week picks with replacement
    C = np.zeros((n_draws, W), dtype=np.float64)
    rows = np.repeat(np.arange(n_draws), W)
    np.add.at(C, (rows, idx.ravel()), 1.0)
    return C


# --- per-week accumulation ----------------------------------------------------------


def _week_sums(week: np.ndarray, mask: np.ndarray, outcome: np.ndarray, W: int) -> Tuple[np.ndarray, np.ndarray]:
    """Per-week (sum(outcome), count) over rows in `mask` with a finite outcome."""
    valid = mask & np.isfinite(outcome)
    s = np.zeros(W)
    c = np.zeros(W)
    np.add.at(s, week[valid], outcome[valid])
    np.add.at(c, week[valid], 1.0)
    return s, c


@dataclass
class ContrastResult:
    delta: float
    ci_lo: float
    ci_hi: float
    p_value: float
    n_a: int
    n_b: int
    mean_a: float
    mean_b: float


def contrast_bootstrap(
    week: np.ndarray,
    maskA: np.ndarray,
    maskB: np.ndarray,
    outcome: np.ndarray,
    W: int,
    C: np.ndarray,
) -> ContrastResult:
    """Δ = mean(outcome|A) - mean(outcome|B); 95% CI + two-sided p via the weekly block
    bootstrap (draw matrix `C`). Fully vectorized: bootstrap numerators/denominators are
    C @ per-week-sum vectors."""
    sA, cA = _week_sums(week, maskA, outcome, W)
    sB, cB = _week_sums(week, maskB, outcome, W)
    nA, nB = int(cA.sum()), int(cB.sum())
    mean_a = sA.sum() / nA if nA else np.nan
    mean_b = sB.sum() / nB if nB else np.nan
    delta = mean_a - mean_b

    numA = C @ sA
    denA = C @ cA
    numB = C @ sB
    denB = C @ cB
    with np.errstate(invalid="ignore", divide="ignore"):
        boot = np.where((denA > 0) & (denB > 0), numA / denA - numB / denB, np.nan)
    boot = boot[np.isfinite(boot)]
    if boot.size == 0:
        return ContrastResult(delta, np.nan, np.nan, np.nan, nA, nB, mean_a, mean_b)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    p = 2.0 * min((boot <= 0).mean(), (boot >= 0).mean())
    p = min(1.0, p)
    return ContrastResult(delta, float(lo), float(hi), float(p), nA, nB, mean_a, mean_b)


def per_year_deltas(
    is_year: np.ndarray, maskA: np.ndarray, maskB: np.ndarray, outcome: np.ndarray
) -> Dict[int, Tuple[float, int]]:
    """Per IS-year Δ (mean_A - mean_B) and combined n, for the G3 era-stability gate."""
    out: Dict[int, Tuple[float, int]] = {}
    fin = np.isfinite(outcome)
    for y in (1, 2, 3, 4):
        yr = is_year == y
        a = maskA & yr & fin
        b = maskB & yr & fin
        na, nb = int(a.sum()), int(b.sum())
        if na == 0 or nb == 0:
            out[y] = (np.nan, na + nb)
        else:
            out[y] = (float(outcome[a].mean() - outcome[b].mean()), na + nb)
    return out


# --- design matrix / regression (numpy only) ----------------------------------------


def build_design(
    df: pd.DataFrame,
    cat_cols: Sequence[str],
    num_cols: Sequence[str],
    fitted: Optional[dict] = None,
) -> Tuple[np.ndarray, dict]:
    """Design matrix (intercept + standardized numerics + drop-first one-hot cats),
    float32. `fitted` (levels + numeric mean/std) is learned when None (train fold) and
    reused on the val fold. Numeric NaNs imputed to the fitted mean."""
    n = len(df)
    cols: List[np.ndarray] = [np.ones(n, dtype=np.float32)]
    new_fit: dict = {"num": {}, "cat": {}}
    for c in num_cols:
        x = df[c].to_numpy(dtype=np.float64)
        if fitted is None:
            m = np.nanmean(x)
            s = np.nanstd(x)
            s = s if s > 0 else 1.0
            new_fit["num"][c] = (m, s)
        else:
            m, s = fitted["num"][c]
        x = np.where(np.isfinite(x), x, m)
        cols.append(((x - m) / s).astype(np.float32))
    for c in cat_cols:
        vals = df[c].astype("object").to_numpy()
        if fitted is None:
            levels = sorted({v for v in pd.unique(vals) if v is not None and not (isinstance(v, float) and np.isnan(v))}, key=str)
            new_fit["cat"][c] = levels
        else:
            levels = fitted["cat"][c]
        for lv in levels[1:]:  # drop first level
            cols.append((vals == lv).astype(np.float32))
    X = np.column_stack(cols).astype(np.float32)
    return X, (fitted if fitted is not None else new_fit)


def logistic_irls(X: np.ndarray, y: np.ndarray, l2: float = 1e-6, max_iter: int = 30, tol: float = 1e-7) -> np.ndarray:
    """Ridge-stabilized logistic regression via IRLS/Newton. X float32 (n x p),
    y in {0,1}. Returns beta (p,). Chunked X^T W X to bound memory on large n."""
    n, p = X.shape
    beta = np.zeros(p, dtype=np.float64)
    yv = y.astype(np.float64)
    reg = l2 * np.eye(p)
    reg[0, 0] = 0.0  # do not penalize intercept
    for _ in range(max_iter):
        eta = X @ beta
        eta = np.clip(eta, -30, 30)
        pmu = 1.0 / (1.0 + np.exp(-eta))
        w = np.maximum(pmu * (1.0 - pmu), 1e-6)
        grad = X.T @ (pmu - yv) + reg @ beta
        # H = X^T diag(w) X, accumulated in row-chunks (float64) to bound memory.
        H = np.zeros((p, p), dtype=np.float64)
        step = 200_000
        for a in range(0, n, step):
            b = min(n, a + step)
            Xb = X[a:b].astype(np.float64)
            H += Xb.T @ (w[a:b, None] * Xb)
        H += reg
        try:
            dbeta = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            dbeta = np.linalg.lstsq(H, grad, rcond=None)[0]
        beta -= dbeta
        if np.max(np.abs(dbeta)) < tol:
            break
    return beta


def logistic_predict(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    eta = np.clip(X @ beta, -30, 30)
    return 1.0 / (1.0 + np.exp(-eta))


def ols_residualize(df: pd.DataFrame, outcome: np.ndarray, cat_cols, num_cols) -> np.ndarray:
    """Residual of `outcome` after OLS on baseline set B (design = build_design). Used
    for the G2 gate on CONTINUOUS outcomes. Rows with non-finite outcome return NaN
    residuals (excluded downstream)."""
    fin = np.isfinite(outcome)
    X, _ = build_design(df, cat_cols, num_cols, fitted=None)
    Xf = X[fin].astype(np.float64)
    yf = outcome[fin].astype(np.float64)
    beta, *_ = np.linalg.lstsq(Xf, yf, rcond=None)
    resid = np.full(len(df), np.nan)
    resid[fin] = yf - Xf @ beta
    return resid


def logistic_residualize(df: pd.DataFrame, y: np.ndarray, mask: np.ndarray, cat_cols, num_cols) -> np.ndarray:
    """Residual (y - p_hat) after logistic on B, for the G2 gate on BINARY outcomes.
    Fit only on `mask` rows (the cell's population); residual NaN elsewhere."""
    resid = np.full(len(df), np.nan)
    sub = df[mask]
    X, _ = build_design(sub, cat_cols, num_cols, fitted=None)
    beta = logistic_irls(X, y[mask])
    resid[mask] = y[mask].astype(np.float64) - logistic_predict(X, beta)
    return resid


# --- AUC + blocked-CV OOF -----------------------------------------------------------


def auc_score(p: np.ndarray, y: np.ndarray) -> float:
    """ROC AUC via the Mann-Whitney U rank formula (ties -> 0.5). numpy only."""
    y = y.astype(np.int64)
    n_pos = int(y.sum())
    n_neg = int(len(y) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return np.nan
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), dtype=np.float64)
    sp = p[order]
    ranks_sorted = np.arange(1, len(p) + 1, dtype=np.float64)
    # average ranks for ties
    i = 0
    n = len(sp)
    while i < n:
        j = i + 1
        while j < n and sp[j] == sp[i]:
            j += 1
        if j - i > 1:
            ranks_sorted[i:j] = (i + 1 + j) / 2.0
        i = j
    ranks[order] = ranks_sorted
    sum_pos = ranks[y == 1].sum()
    u = sum_pos - n_pos * (n_pos + 1) / 2.0
    return float(u / (n_pos * n_neg))


def week_folds(W: int, n_folds: int = 5) -> np.ndarray:
    """Contiguous block assignment of the W weeks to `n_folds` folds (blocked CV by
    calendar week -- respects time order, no interleaving)."""
    return (np.arange(W) * n_folds // W).astype(np.int64)


def cv_oof_predict(
    df: pd.DataFrame,
    y: np.ndarray,
    week: np.ndarray,
    fold_of_week: np.ndarray,
    cat_cols,
    num_cols,
    n_folds: int = 5,
) -> np.ndarray:
    """Blocked-by-week 5-fold out-of-fold logistic predictions for the rows of `df`."""
    oof = np.full(len(df), np.nan)
    fold = fold_of_week[week]
    for k in range(n_folds):
        tr = fold != k
        va = fold == k
        if tr.sum() == 0 or va.sum() == 0:
            continue
        Xtr, fit = build_design(df[tr], cat_cols, num_cols, fitted=None)
        beta = logistic_irls(Xtr, y[tr])
        Xva, _ = build_design(df[va], cat_cols, num_cols, fitted=fit)
        oof[va] = logistic_predict(Xva, beta)
    return oof


# --- AUC weekly-block bootstrap (c^T U c) -------------------------------------------


def _cross_week_U(p: np.ndarray, y: np.ndarray, week: np.ndarray, W: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """U[i,j] = #{(x in pos of week i, z in neg of week j): x>z} + 0.5*ties. Also
    per-week pos/neg counts. AUC over any week-multiset with multiplicity vector c is
    (c^T U c)/((c.pos)(c.neg)); c=ones reproduces the global AUC exactly."""
    pos_by = [np.sort(p[(y == 1) & (week == w)]) for w in range(W)]
    neg_by = [p[(y == 0) & (week == w)] for w in range(W)]
    pos_cnt = np.array([len(a) for a in pos_by], dtype=np.float64)
    neg_cnt = np.array([len(a) for a in neg_by], dtype=np.float64)
    U = np.zeros((W, W), dtype=np.float64)
    for i in range(W):
        pi = pos_by[i]
        if pi.size == 0:
            continue
        for j in range(W):
            nj = neg_by[j]
            if nj.size == 0:
                continue
            left = np.searchsorted(pi, nj, side="left")
            right = np.searchsorted(pi, nj, side="right")
            greater = pi.size - right
            ties = right - left
            U[i, j] = greater.sum() + 0.5 * ties.sum()
    return U, pos_cnt, neg_cnt


@dataclass
class AucUpliftResult:
    auc_base: float
    auc_full: float
    uplift: float
    ci_lo: float
    ci_hi: float
    p_value: float
    n: int
    n_pos: int


def auc_uplift_bootstrap(
    p_base: np.ndarray,
    p_full: np.ndarray,
    y: np.ndarray,
    week: np.ndarray,
    W: int,
    C: np.ndarray,
) -> AucUpliftResult:
    """Point AUC uplift (full - base) + weekly-block-bootstrap CI/p via the c^T U c
    quadratic form. Vectorized across all draws."""
    Ub, pos_cnt, neg_cnt = _cross_week_U(p_base, y, week, W)
    Uf, _, _ = _cross_week_U(p_full, y, week, W)
    denom_pn = pos_cnt.sum() * neg_cnt.sum()
    auc_b = Ub.sum() / denom_pn
    auc_f = Uf.sum() / denom_pn
    # bootstrap: quad_b = sum_ij C_i U C_j ; vectorized as ((C@U)*C).sum(1)
    quadb = ((C @ Ub) * C).sum(axis=1)
    quadf = ((C @ Uf) * C).sum(axis=1)
    pos_tot = C @ pos_cnt
    neg_tot = C @ neg_cnt
    with np.errstate(invalid="ignore", divide="ignore"):
        pn = pos_tot * neg_tot
        aucb = np.where(pn > 0, quadb / pn, np.nan)
        aucf = np.where(pn > 0, quadf / pn, np.nan)
    up = aucf - aucb
    up = up[np.isfinite(up)]
    lo, hi = np.percentile(up, [2.5, 97.5])
    p = 2.0 * min((up <= 0).mean(), (up >= 0).mean())
    p = min(1.0, p)
    n = int(len(y))
    return AucUpliftResult(float(auc_b), float(auc_f), float(auc_f - auc_b), float(lo), float(hi), float(p), n, int(y.sum()))


def auc_uplift_per_year(
    p_base: np.ndarray, p_full: np.ndarray, y: np.ndarray, is_year: np.ndarray
) -> Dict[int, Tuple[float, int]]:
    out: Dict[int, Tuple[float, int]] = {}
    for yr in (1, 2, 3, 4):
        m = is_year == yr
        if m.sum() == 0 or y[m].sum() in (0, m.sum()):
            out[yr] = (np.nan, int(m.sum()))
            continue
        out[yr] = (auc_score(p_full[m], y[m]) - auc_score(p_base[m], y[m]), int(m.sum()))
    return out


# --- gates ---------------------------------------------------------------------------


def benjamini_hochberg(pvals: Sequence[float], q: float = 0.10) -> np.ndarray:
    """BH step-up: returns a boolean 'rejected' array aligned to `pvals` (NaN p -> not
    rejected). Controls FDR at q within the family."""
    p = np.asarray(pvals, dtype=np.float64)
    ok = np.isfinite(p)
    idx = np.where(ok)[0]
    m = len(idx)
    rej = np.zeros(len(p), dtype=bool)
    if m == 0:
        return rej
    order = idx[np.argsort(p[idx])]
    thresh = q * (np.arange(1, m + 1) / m)
    passed = p[order] <= thresh
    if passed.any():
        kmax = np.where(passed)[0].max()
        rej[order[: kmax + 1]] = True
    return rej


def g3_era_stability(overall_delta: float, per_year: Dict[int, Tuple[float, float]]) -> Tuple[bool, bool, float, Dict[int, float]]:
    """G3: sign consistent in >=3 of 4 IS years AND no single year contributes >60% of
    the aggregate (contribution = n_y*Δ_y share of Σ n_y*Δ_y). Returns
    (sign_ok, concentration_ok, max_share, per_year_signed_contrib)."""
    signs = 0
    contribs: Dict[int, float] = {}
    total = 0.0
    ov_sign = np.sign(overall_delta) if overall_delta == overall_delta else 0.0
    for y, (d, n) in per_year.items():
        if d != d:
            continue
        if np.sign(d) == ov_sign and ov_sign != 0:
            signs += 1
        contribs[y] = n * d
        total += n * d
    sign_ok = signs >= 3
    if total == 0 or not np.isfinite(total):
        return sign_ok, False, np.nan, contribs
    shares = {y: (c / total) for y, c in contribs.items()}
    # a year concentrates the effect if its SAME-sign share exceeds 60%
    max_share = max((s for s in shares.values()), default=np.nan)
    concentration_ok = max_share <= 0.60
    return sign_ok, concentration_ok, float(max_share), shares
