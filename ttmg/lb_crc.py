"""CalLB Conformal Risk Control via Clopper-Pearson + grid + union bound.

Implements the FINAL_PROPOSAL theorem:

    Fix λ-grid Λ = {λ_1, ..., λ_m}, m=100, chosen INDEPENDENTLY of cal sample.
    For each λ_j, R̂(λ_j) = (1/n_cal) Σ_{q ∈ cal} R(λ_j; q) where
        R(λ_j; q) = 𝟙[ ∃ item ∈ L_λ_j(q) with label = D ].
    U_j = U_CP(R̂(λ_j); n_cal, δ/m)  one-sided Clopper-Pearson UCB.
    λ̂_α = inf { λ_j ∈ Λ : U_j ≤ α }.
    Under exchangeability of cal/test queries:
        Pr_{cal split}[ R(λ̂_α) ≤ α ] ≥ 1 − δ.

The risk is monotone non-increasing in λ for each q (larger λ → smaller tier
→ {∃ D in tier} only weakens). Hence inf is well-defined; union bound makes
threshold selection valid.

Public surface:
  - LBCRCConfig (dataclass)
  - calibrate_lb(scores_per_q, labels_per_q, alpha_grid, ...) -> LBCRCTable
  - LBCRCTable.threshold(alpha) -> λ̂_α
  - LBCRCTable.save(path), load(path)
  - empirical_clean_set_risk(scores_per_q, labels_per_q, lambda_) -> float
  - non_vacuity_metrics(scores_per_q, labels_per_q, lambda_) -> dict
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# Reuse the validated Clopper-Pearson UCB from ttmg/crc.py — same machinery,
# same scipy/lgamma fallback.
from .crc import _clopper_pearson_upper


@dataclass(frozen=True)
class LBCRCConfig:
    alpha_grid: Tuple[float, ...] = (0.10, 0.20, 0.30, 0.40)
    delta: float = 0.05
    n_grid: int = 100
    grid_lo: float = 0.0
    grid_hi: float = 1.0  # MLP scores are sigmoids → [0, 1]


@dataclass
class LBCRCTable:
    """Locked threshold table.

    `lambdas[α]` is `λ̂_α` (None if no λ_j on the grid achieved U ≤ α).
    `grid` is the locked λ-grid.
    `r_hat`, `ucb` are the per-grid-point statistics on the cal split.
    `n_cal`, `delta` reproduce the bound parameters.
    """
    lambdas: Dict[float, Optional[float]]
    grid: List[float]
    r_hat: List[float]
    ucb: List[float]
    n_cal: int
    delta: float
    alpha_grid: List[float]
    feature_names: List[str] = field(default_factory=list)

    def threshold(self, alpha: float) -> float:
        """Return λ̂_α; +inf if no grid point cleared U ≤ α."""
        v = self.lambdas.get(float(alpha))
        if v is None:
            return float("inf")
        return float(v)

    def save(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "lambdas": {str(k): (None if v is None else float(v)) for k, v in self.lambdas.items()},
            "grid": [float(x) for x in self.grid],
            "r_hat": [float(x) for x in self.r_hat],
            "ucb": [float(x) for x in self.ucb],
            "n_cal": int(self.n_cal),
            "delta": float(self.delta),
            "alpha_grid": [float(x) for x in self.alpha_grid],
            "feature_names": list(self.feature_names),
        }
        with open(p, "w") as fh:
            json.dump(payload, fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "LBCRCTable":
        with open(path) as fh:
            payload = json.load(fh)
        lambdas = {float(k): (None if v is None else float(v)) for k, v in payload["lambdas"].items()}
        return cls(
            lambdas=lambdas,
            grid=[float(x) for x in payload["grid"]],
            r_hat=[float(x) for x in payload["r_hat"]],
            ucb=[float(x) for x in payload["ucb"]],
            n_cal=int(payload["n_cal"]),
            delta=float(payload["delta"]),
            alpha_grid=[float(x) for x in payload["alpha_grid"]],
            feature_names=list(payload.get("feature_names", [])),
        )


def _per_query_risk(
    scores_q: np.ndarray, labels_q: np.ndarray, lam: float
) -> int:
    """R(λ; q) = 1[∃ item with score ≥ λ AND label = D].

    `labels_q[i] = 1` iff item i is a Distractor.
    Vacuously 0 if no item meets the threshold (clean tier is empty).
    """
    mask = scores_q >= lam
    if not np.any(mask):
        return 0
    return int(np.any(labels_q[mask] == 1))


def calibrate_lb(
    scores_per_q: List[np.ndarray],
    is_distractor_per_q: List[np.ndarray],
    config: Optional[LBCRCConfig] = None,
    feature_names: Optional[Sequence[str]] = None,
) -> LBCRCTable:
    """Compute the Clopper-Pearson CRC threshold table.

    Args:
      scores_per_q: list of length n_cal; each entry is a (n_candidates_q,)
                    array of MLP sigmoid scores.
      is_distractor_per_q: same shape; 1 iff item is labelled D, else 0.
                          Items labelled S or LB count as 0 (the risk only
                          tracks distractor presence in the load-bearing tier).
      config: LBCRCConfig (defaults: 4 alphas, δ=0.05, 100-pt grid in [0,1]).
      feature_names: optional, recorded into the table for reproducibility.
    """
    cfg = config or LBCRCConfig()
    n_cal = len(scores_per_q)
    if n_cal != len(is_distractor_per_q):
        raise ValueError("scores_per_q and is_distractor_per_q must align")
    if n_cal == 0:
        raise ValueError("empty calibration set")

    grid = np.linspace(cfg.grid_lo, cfg.grid_hi, cfg.n_grid).tolist()
    m = len(grid)
    delta_per = cfg.delta / m  # union-bound budget

    r_hat: List[float] = []
    ucb: List[float] = []
    for lam in grid:
        # Per-query risk → empirical Bernoulli mean
        successes = sum(
            _per_query_risk(s, y, lam)
            for s, y in zip(scores_per_q, is_distractor_per_q)
        )
        r = successes / n_cal
        # CP UCB at confidence (1 - δ_per)
        u = _clopper_pearson_upper(successes, n_cal, conf=1.0 - delta_per)
        r_hat.append(r)
        ucb.append(u)

    # For each α, find smallest λ_j with U_j ≤ α (R is monotone non-increasing
    # so U inherits monotonicity in expectation; we still use inf to be safe).
    lambdas: Dict[float, Optional[float]] = {}
    for alpha in cfg.alpha_grid:
        chosen: Optional[float] = None
        for lam, u in zip(grid, ucb):
            if u <= alpha:
                chosen = float(lam)
                break
        lambdas[float(alpha)] = chosen
    return LBCRCTable(
        lambdas=lambdas,
        grid=grid,
        r_hat=r_hat,
        ucb=ucb,
        n_cal=n_cal,
        delta=cfg.delta,
        alpha_grid=list(cfg.alpha_grid),
        feature_names=list(feature_names or []),
    )


def empirical_clean_set_risk(
    scores_per_q: List[np.ndarray],
    is_distractor_per_q: List[np.ndarray],
    lam: float,
) -> float:
    """Test-time evaluation: empirical R̂(λ) on a held-out split."""
    n = len(scores_per_q)
    if n == 0:
        return 0.0
    successes = sum(
        _per_query_risk(s, y, lam)
        for s, y in zip(scores_per_q, is_distractor_per_q)
    )
    return successes / n


def non_vacuity_metrics(
    scores_per_q: List[np.ndarray],
    labels_per_q: List[np.ndarray],   # 0=S, 1=D, 2=LB
    lam: float,
) -> Dict[str, float]:
    """Utility metrics on the load-bearing tier L_λ at threshold λ.

    Returns:
      non_empty_fraction: Pr_q[|L| ≥ 1]
      mean_size: E_q[|L|]
      lb_recall: Pr_q[L contains ≥1 LB-labelled item]
      lb_precision: E_q[#LB / max(1,|L|)]
      mean_distractor_fraction: descriptive (the old non-monotone risk)
    """
    n = len(scores_per_q)
    if n == 0:
        return {"non_empty_fraction": 0.0, "mean_size": 0.0, "lb_recall": 0.0,
                "lb_precision": 0.0, "mean_distractor_fraction": 0.0}
    sizes = []
    has_lb = []
    lb_prec = []
    distractor_frac = []
    for s, y in zip(scores_per_q, labels_per_q):
        mask = s >= lam
        size = int(mask.sum())
        sizes.append(size)
        if size == 0:
            has_lb.append(0)
            lb_prec.append(0.0)
            distractor_frac.append(0.0)
            continue
        in_tier = y[mask]
        n_lb = int((in_tier == 2).sum())
        n_d = int((in_tier == 1).sum())
        has_lb.append(1 if n_lb >= 1 else 0)
        lb_prec.append(n_lb / size)
        distractor_frac.append(n_d / size)
    sizes = np.asarray(sizes)
    return {
        "non_empty_fraction": float((sizes >= 1).mean()),
        "mean_size": float(sizes.mean()),
        "lb_recall": float(np.mean(has_lb)),
        "lb_precision": float(np.mean(lb_prec)),
        "mean_distractor_fraction": float(np.mean(distractor_frac)),
    }
