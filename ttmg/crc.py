"""Conformal Risk Control / Selective Risk Control layer.

The β round-2 read-time decision rule replaces Path D's heuristic
all-optima MWIS abstention with a *theoretically backed* selective-risk
threshold, calibrated once on a held-out Memora train split with:
  - pre-frozen candidate thresholds per group (no adaptive grid search)
  - exact one-sided Clopper-Pearson UCB per (g, α, τ)
  - Bonferroni multiple-testing correction over |G_eff|·|A|·|T_cand|
  - answer-rate floor `N_min`
  - hierarchical group merging when n_g < N_min

Theorem (informal): under exchangeability of Cal with the test split, with
probability ≥ 1 − δ over the draw of Cal, for every g ∈ G_eff and every
α ∈ A, the true conditional selective risk at the locked threshold is ≤ α.

References:
  - Clopper & Pearson 1934 (exact binomial CI)
  - Geifman & El-Yaniv 2017 (Selective Classification)
  - Angelopoulos et al. 2022 (Conformal Risk Control)
  - Bates et al. 2021 (Distribution-free Risk-Controlling Prediction Sets)

This module is deliberately self-contained — it depends only on `math` /
`statistics` from the stdlib and on `scipy.stats.beta` for the exact
Clopper-Pearson upper bound. The math is short; we re-derive it inline for
clarity rather than depending on a heavy CP library.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Hashable, List, Mapping, Optional, Sequence, Tuple

# Use scipy for exact Clopper-Pearson (beta-distribution inverse CDF).
# If unavailable, fall back to a self-contained implementation that uses
# the relationship between the binomial tail and the regularised incomplete
# beta function via math.lgamma — slower but no extra dependency.
try:
    from scipy.stats import beta as _scipy_beta  # type: ignore

    def _clopper_pearson_upper(k: int, n: int, conf: float) -> float:
        """One-sided upper Clopper-Pearson bound at confidence `conf`.

        Returns p_upper such that Pr[ true rate ≤ p_upper ] ≥ conf
        when k successes out of n Bernoulli trials are observed.
        """
        if n <= 0:
            return 1.0
        if k >= n:
            return 1.0
        # Codex-fix MINOR: clamp `conf` strictly below 1.0 for ppf stability.
        conf = min(max(conf, 0.0), 1.0 - 1e-15)
        # CP upper = beta.ppf(conf, k+1, n-k)
        return float(_scipy_beta.ppf(conf, k + 1, n - k))

except Exception:  # pragma: no cover

    def _log_beta(a: float, b: float) -> float:
        return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)

    def _regularised_incomplete_beta(x: float, a: float, b: float) -> float:
        """Continued-fraction expansion of I_x(a,b). Slow but dependency-free."""
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        # Use symmetry to keep continued fraction stable
        if x > (a + 1.0) / (a + b + 2.0):
            return 1.0 - _regularised_incomplete_beta(1.0 - x, b, a)
        # Lentz continued-fraction
        eps = 1e-15
        max_iter = 500
        front = math.exp(
            a * math.log(x) + b * math.log(1.0 - x) - _log_beta(a, b)
        ) / a
        f = 1.0
        c = 1.0
        d = 0.0
        for m in range(max_iter):
            for j in (2 * m + 1, 2 * m + 2):
                if j == 2 * m + 1:
                    aj = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
                else:
                    aj = (m + 1) * (b - m - 1) * x / ((a + 2 * m + 1) * (a + 2 * m + 2))
                d = 1.0 + aj * d
                if abs(d) < eps:
                    d = eps
                c = 1.0 + aj / c
                if abs(c) < eps:
                    c = eps
                d = 1.0 / d
                delta = c * d
                f *= delta
                if abs(delta - 1.0) < eps:
                    return front * (f - 1.0)
        return front * (f - 1.0)

    def _clopper_pearson_upper(k: int, n: int, conf: float) -> float:
        if n <= 0:
            return 1.0
        if k >= n:
            return 1.0
        # Codex-fix MINOR: clamp `conf` strictly below 1.0.
        conf = min(max(conf, 0.0), 1.0 - 1e-15)
        # bisection on I_p(k+1, n-k) = conf
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if _regularised_incomplete_beta(mid, k + 1, n - k) < conf:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

GroupKey = Tuple[Hashable, ...]
ALPHA_GRID = (0.05, 0.10, 0.15, 0.20, 0.25)


@dataclass
class CalibrationSample:
    """One labelled calibration question.

    `score` is the scalar S(q) the operator computes pre-decision (higher =
    more confident). `correct` is True iff the system would answer correctly
    if it answered at this score-threshold inclusive.

    `group` is the inference-time group label tuple (e.g. (pmi_bin,
    update_pattern)). `meta` carries diagnostic info (question_id, etc.).
    """

    score: float
    correct: bool
    group: GroupKey
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CRCConfig:
    alpha_grid: Tuple[float, ...] = ALPHA_GRID
    delta: float = 0.10  # paper-default 1−δ overall coverage = 0.90
    n_min: int = 30  # minimum answered count per (g, α, τ) cell
    n_candidates_per_group: int = 5  # |T_cand(g)| — pre-frozen on dev


# ---------------------------------------------------------------------------
# Pre-freezing candidate thresholds on a *dev* split
# ---------------------------------------------------------------------------

def freeze_candidate_thresholds(
    dev_samples: Sequence[CalibrationSample],
    *,
    config: Optional[CRCConfig] = None,
) -> Dict[GroupKey, List[float]]:
    """Per-group fixed candidate threshold set (e.g. quantiles of S on dev).

    Called once on the dev split *before* calibration; output is locked and
    consumed by `calibrate_thresholds` on the calibration split.
    """
    cfg = config or CRCConfig()
    by_group: Dict[GroupKey, List[float]] = defaultdict(list)
    for s in dev_samples:
        by_group[s.group].append(s.score)

    cand: Dict[GroupKey, List[float]] = {}
    for g, scores in by_group.items():
        if len(scores) < cfg.n_min:
            # Will be merged in calibration; pre-fill with global quantiles.
            scores = sorted(scores)
        else:
            scores = sorted(scores)
        n = len(scores)
        if n == 0:
            cand[g] = []
            continue
        # Choose `n_candidates_per_group` quantiles. Default 5 → 50, 60, 70, 80, 90.
        m = cfg.n_candidates_per_group
        qs = [
            scores[max(0, min(n - 1, int(n * (0.5 + 0.4 * (i / max(1, m - 1))))))]
            for i in range(m)
        ]
        # De-duplicate while preserving ascending order
        seen: List[float] = []
        for q in qs:
            if not seen or q > seen[-1] + 1e-12:
                seen.append(q)
        cand[g] = seen
    return cand


# ---------------------------------------------------------------------------
# Hierarchical merging fallback
# ---------------------------------------------------------------------------

def hierarchical_merge(
    cal_samples: Sequence[CalibrationSample],
    *,
    n_min: int,
    axis_priority: Sequence[int] = (1, 0),
) -> Tuple[Dict[GroupKey, GroupKey], List[GroupKey]]:
    """Merge under-populated groups along axes in priority order.

    Returns:
      - `merge_map`: original_group → effective merged group (G_eff label)
      - `g_eff_keys`: deduplicated list of merged group identifiers

    The default `axis_priority = (1, 0)` means: first try merging along axis 1
    (e.g. update_pattern), then along axis 0 (pmi_bin). Per the FINAL_PROPOSAL
    we want to PRESERVE the temporal-forgetting interpretation, so axis 0 =
    pmi_bin and axis 1 = update_pattern, and we merge update_pattern first
    (NB: paper text says "merge along update_pattern axis first" — i.e. when
    a (pmi_bin, update_pattern) cell is sparse, we collapse update_pattern
    distinctions within that pmi_bin first; only as a second resort do we
    collapse pmi_bin distinctions). To match that intent, callers should pass
    `axis_priority=(1, 0)`.
    """
    counts = Counter(s.group for s in cal_samples)
    merge_map: Dict[GroupKey, GroupKey] = {g: g for g in counts}

    def merge_axis(axis: int) -> None:
        # Group by all-other-axes; within each, fold sparse cells into the
        # "wildcard" group that drops `axis`.
        bucket: Dict[GroupKey, List[GroupKey]] = defaultdict(list)
        for g in list(counts.keys()):
            other = tuple(v for i, v in enumerate(g) if i != axis)
            bucket[other].append(g)
        for other_key, groups in bucket.items():
            # Build a merged identifier for the bucket: replace axis position with "*"
            merged = list(groups[0])
            merged[axis] = "*"
            merged_g: GroupKey = tuple(merged)
            total = sum(counts[g] for g in groups)
            if total >= n_min and any(counts[g] < n_min for g in groups):
                for g in groups:
                    # Re-route any group whose chain points to a sparse cell
                    chained = merge_map.get(g, g)
                    counts[merged_g] = counts.get(merged_g, 0) + counts.pop(chained, 0)
                    merge_map[g] = merged_g
                    # Also re-route anyone who was previously routed to chained.
                    for orig in list(merge_map.keys()):
                        if merge_map[orig] == chained:
                            merge_map[orig] = merged_g

    for axis in axis_priority:
        merge_axis(axis)

    # Final cleanup: groups that are still under N_min collapse to the
    # universal "marginal" cell.
    for g in list(merge_map.keys()):
        eff = merge_map[g]
        if counts.get(eff, 0) < n_min:
            merge_map[g] = ("*",) * (len(g) if isinstance(g, tuple) else 1)
    g_eff_keys = sorted(set(merge_map.values()), key=lambda x: tuple(str(v) for v in x))
    return merge_map, g_eff_keys


# ---------------------------------------------------------------------------
# Calibration: lock one threshold per (g, α)
# ---------------------------------------------------------------------------

def calibrate_thresholds(
    cal_samples: Sequence[CalibrationSample],
    candidate_thresholds: Mapping[GroupKey, Sequence[float]],
    *,
    config: Optional[CRCConfig] = None,
) -> Dict[str, Any]:
    """Lock per-(g, α) thresholds via Clopper-Pearson exact UCB.

    Returns a dict suitable for git-hashed serialisation:
        {
          "threshold_table": {"<g_eff_str>|<alpha>": tau_or_inf, ...},
          "g_eff_to_origs": {"<g_eff_str>": [["bin", "pat"], ...]},
          "n_candidates_total": int,
          "delta": float,
          "delta_corr": float,
          "alpha_grid": [...],
          "per_cell_audit": [{"g_eff": ..., "alpha": ..., "tau": ..., "k": ..., "n": ..., "ucb": ...}, ...],
          "n_min": int,
        }
    """
    cfg = config or CRCConfig()

    merge_map, g_eff_keys = hierarchical_merge(
        cal_samples, n_min=cfg.n_min, axis_priority=(1, 0)
    )
    samples_by_eff: Dict[GroupKey, List[CalibrationSample]] = defaultdict(list)
    for s in cal_samples:
        eff = merge_map.get(s.group, s.group)
        samples_by_eff[eff].append(s)

    # Bonferroni denominator: |G_eff| · |A| · sum_g |T_cand(g)|.
    # Conservative choice: take the *worst-case* per-cell candidate count.
    n_alpha = len(cfg.alpha_grid)
    n_groups = max(1, len(g_eff_keys))
    # Pull per-eff candidate sets by mapping originals into eff buckets:
    cand_per_eff: Dict[GroupKey, List[float]] = {}
    for orig_g, taus in candidate_thresholds.items():
        eff = merge_map.get(orig_g, orig_g)
        # Union of candidate thresholds across origs that share this eff
        merged = sorted(set(cand_per_eff.get(eff, [])) | set(taus))
        cand_per_eff[eff] = merged
    # Codex-fix CRITICAL (round-2): NO calibration-derived backfill of
    # candidate thresholds. If a merged effective group has no dev-derived
    # candidates, leave `cand_per_eff[eff] = []` and the per-(g, α) result
    # will be `+inf` (always-abstain). Building candidates from the cal
    # split would leak the calibration sample into T_cand and break
    # theorem-exactness for that cell.
    for eff in g_eff_keys:
        cand_per_eff.setdefault(eff, [])
    n_cand_max = max(1, max(len(t) for t in cand_per_eff.values()) if cand_per_eff else 1)

    delta_corr = cfg.delta / max(1, n_groups * n_alpha * n_cand_max)
    confidence = 1.0 - delta_corr

    threshold_table: Dict[str, float] = {}
    audit: List[Dict[str, Any]] = []

    for eff in g_eff_keys:
        bucket = samples_by_eff.get(eff, [])
        # Pre-sort scores for fast counting.
        sorted_scores = sorted(((s.score, s.correct) for s in bucket), key=lambda x: x[0])
        for alpha in cfg.alpha_grid:
            chosen_tau: Optional[float] = None
            chosen_k = chosen_n = -1
            chosen_ucb = float("inf")
            for tau in cand_per_eff.get(eff, []):
                # Count answered = #{S >= tau} and wrong = #{S >= tau AND not correct}.
                # Use linear scan; bucket sizes are small (typically <= 200).
                n = 0
                k = 0
                for sc, ok in sorted_scores:
                    if sc >= tau:
                        n += 1
                        if not ok:
                            k += 1
                if n < cfg.n_min:
                    continue
                ucb = _clopper_pearson_upper(k, n, confidence)
                if ucb <= alpha:
                    chosen_tau = tau
                    chosen_k = k
                    chosen_n = n
                    chosen_ucb = ucb
                    break
            key = f"{_g_str(eff)}|{alpha:.2f}"
            threshold_table[key] = chosen_tau if chosen_tau is not None else float("inf")
            audit.append(
                {
                    "g_eff": _g_str(eff),
                    "alpha": alpha,
                    "tau": chosen_tau if chosen_tau is not None else None,
                    "k_wrong": chosen_k if chosen_tau is not None else None,
                    "n_answered": chosen_n if chosen_tau is not None else None,
                    "ucb": chosen_ucb if chosen_tau is not None else None,
                    "n_candidates_searched": len(cand_per_eff.get(eff, [])),
                    "abstain_everywhere": chosen_tau is None,
                }
            )

    return {
        "threshold_table": threshold_table,
        "g_eff_to_origs": {
            _g_str(eff): sorted({_g_str(o) for o, e in merge_map.items() if e == eff})
            for eff in g_eff_keys
        },
        "merge_map": {_g_str(o): _g_str(e) for o, e in merge_map.items()},
        "candidate_thresholds": {_g_str(g): list(taus) for g, taus in cand_per_eff.items()},
        "n_candidates_max_per_group": n_cand_max,
        "n_groups_eff": n_groups,
        "alpha_grid": list(cfg.alpha_grid),
        "delta": cfg.delta,
        "delta_corr": delta_corr,
        "n_min": cfg.n_min,
        "per_cell_audit": audit,
    }


def _g_str(g: GroupKey) -> str:
    """Stable string serialisation of a group tuple for JSON keys."""
    return "::".join(str(v) for v in g)


# ---------------------------------------------------------------------------
# Inference-time threshold lookup
# ---------------------------------------------------------------------------

class CRCThresholdTable:
    """Loaded, locked threshold table consumed at inference time."""

    def __init__(self, table: Dict[str, Any]):
        self._table: Dict[str, float] = {
            k: (float("inf") if v is None else float(v))
            for k, v in table["threshold_table"].items()
        }
        self._merge_map: Dict[str, str] = dict(table.get("merge_map", {}))
        self.alpha_grid: Tuple[float, ...] = tuple(table.get("alpha_grid", ALPHA_GRID))
        self.delta: float = float(table.get("delta", 0.10))
        self.delta_corr: float = float(table.get("delta_corr", self.delta))
        self.commit_hash: Optional[str] = table.get("commit_hash")

    def lookup(self, group: GroupKey, alpha: float) -> float:
        """Threshold for (group, α). Returns +inf when group always abstains.

        Codex-fix CRITICAL #2: when an inference-time group is not in the
        calibration-time merge_map (unseen combination of bins), fall through
        to progressively-coarser cells:
            (b1, b2) → ("*", b2) → (b1, "*") → ("*", "*")
        These intermediate cells are guaranteed to exist when the marginal
        cell was populated at calibration, ensuring no silent always-abstain
        for novel groups.
        """
        eff = self._merge_map.get(_g_str(group), _g_str(group))
        key = f"{eff}|{alpha:.2f}"
        if key in self._table:
            return self._table[key]
        # Defensive fall-through over progressively-coarser cells
        if isinstance(group, tuple):
            for fallback in self._fallback_groups(group):
                fb_eff = self._merge_map.get(_g_str(fallback), _g_str(fallback))
                fb_key = f"{fb_eff}|{alpha:.2f}"
                if fb_key in self._table:
                    return self._table[fb_key]
        return float("inf")

    @staticmethod
    def _fallback_groups(group: Tuple[Any, ...]) -> List[Tuple[Any, ...]]:
        """Yield progressively-coarser groups by replacing axes with '*'."""
        n = len(group)
        out: List[Tuple[Any, ...]] = []
        # Single-axis wildcards (last-axis first to preserve update_pattern)
        for i in range(n - 1, -1, -1):
            wc = list(group)
            wc[i] = "*"
            out.append(tuple(wc))
        # All-axis wildcard
        out.append(("*",) * n)
        return out

    @classmethod
    def from_file(cls, path: str) -> "CRCThresholdTable":
        with open(path, "r") as fh:
            data = json.load(fh)
        return cls(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CRCThresholdTable":
        return cls(data)


# ---------------------------------------------------------------------------
# Empirical evaluation helpers (used by experiments/eval_memora.py)
# ---------------------------------------------------------------------------

def empirical_selective_risk(
    samples: Sequence[CalibrationSample],
    table: CRCThresholdTable,
    alpha: float,
) -> Dict[GroupKey, Dict[str, float]]:
    """Per-group empirical selective risk + Wilson UCB band on a held-out split.

    Returns {group: {answered: n, wrong: k, risk: k/n, ucb: ...}}.
    """
    out: Dict[GroupKey, Dict[str, float]] = {}
    by_group: Dict[GroupKey, List[CalibrationSample]] = defaultdict(list)
    for s in samples:
        by_group[s.group].append(s)
    for g, bucket in by_group.items():
        tau = table.lookup(g, alpha)
        answered = [s for s in bucket if s.score >= tau and tau != float("inf")]
        n = len(answered)
        k = sum(1 for s in answered if not s.correct)
        risk = (k / n) if n > 0 else 0.0
        ucb = _clopper_pearson_upper(k, n, 1 - 0.10) if n > 0 else 1.0
        out[g] = {
            "answered": n,
            "wrong": k,
            "risk": risk,
            "ucb_90": ucb,
            "tau": tau if tau != float("inf") else None,
        }
    return out


def risk_coverage_curve(
    samples: Sequence[CalibrationSample],
    *,
    n_points: int = 50,
) -> List[Tuple[float, float]]:
    """Sweep a single-method confidence threshold; return [(answer_rate, risk)].

    The samples must all come from the SAME method. Used to plot one curve
    per system (TTMG-β + each baseline) on the temporal-forgetting subset.
    """
    if not samples:
        return []
    sorted_scores = sorted({s.score for s in samples})
    if len(sorted_scores) < 2:
        sorted_scores = [sorted_scores[0] - 1e-6, sorted_scores[0] + 1e-6]
    grid = [
        sorted_scores[int(i * (len(sorted_scores) - 1) / (n_points - 1))]
        for i in range(n_points)
    ]
    out: List[Tuple[float, float]] = []
    total = len(samples)
    for tau in grid:
        answered = [s for s in samples if s.score >= tau]
        n = len(answered)
        if n == 0:
            continue
        k = sum(1 for s in answered if not s.correct)
        out.append((n / total, k / n))
    return out


def aurc(curve: Sequence[Tuple[float, float]]) -> float:
    """Area Under (sorted-by-answer-rate) Risk Coverage curve. Lower is better."""
    if not curve:
        return 1.0
    pts = sorted(curve, key=lambda p: p[0])
    area = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        area += 0.5 * (x1 - x0) * (y0 + y1)
    return area


@dataclass(frozen=True)
class ScoreWeights:
    w_h: float = 0.5
    w_u: float = 0.3
    w_p: float = 0.2

    def with_no_pmi(self) -> "ScoreWeights":
        # Re-balance when PMI signal is unavailable.
        return ScoreWeights(w_h=0.7, w_u=0.3, w_p=0.0)


def compute_S(
    *,
    hardness_mean: float,
    unique_value: bool,
    pmi: Optional[float],
    pmi_scale: float,
    weights: ScoreWeights,
) -> float:
    """β scalar confidence score; same function used at both calibration and inference time.

    `S = w_h · mean(hardness in ⋃Opts) + w_u · 1[|Vals|==1] + w_p · clip(PMI / scale, 0, 1)`
    """
    pmi_term = 0.0
    if pmi is not None and pmi_scale > 0:
        pmi_term = max(0.0, min(1.0, pmi / pmi_scale))
    return (
        weights.w_h * float(hardness_mean)
        + weights.w_u * (1.0 if unique_value else 0.0)
        + weights.w_p * pmi_term
    )


__all__ = [
    "CRCConfig",
    "CalibrationSample",
    "CRCThresholdTable",
    "ScoreWeights",
    "compute_S",
    "freeze_candidate_thresholds",
    "calibrate_thresholds",
    "hierarchical_merge",
    "empirical_selective_risk",
    "risk_coverage_curve",
    "aurc",
    "ALPHA_GRID",
]
