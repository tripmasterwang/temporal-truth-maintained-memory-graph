"""Train the CalLB MLP and lock the Clopper-Pearson CRC threshold table.

Reads the JSONL labels produced by `scripts/label_lb_pairs.py`, splits by
question (no leakage), trains the MLP (BCE on `1[label=LB]`), and runs the
LBCRCConfig calibration to produce λ̂_α for α ∈ {0.10, 0.20, 0.30, 0.40}.

Outputs:
  - results/lb_mlp.json   — MLP weights + feature names + dev curve.
  - results/lb_crc.json   — locked CRC table (λ̂ per α, grid, R̂, UCB, n_cal, δ).
  - prints intrinsic acceptance gates (dev AUC, per-α dev coverage).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ttmg.lb_crc import LBCRCConfig, calibrate_lb, empirical_clean_set_risk, non_vacuity_metrics
from ttmg.lb_features import FEATURE_NAMES_FULL, FEATURE_NAMES_PORTABLE
from ttmg.lb_model import save as lb_save, score as lb_score, train_mlp


def _load_labels(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _split_by_question(rows: List[Dict[str, Any]], train_frac: float, seed: int) -> Tuple[List[Dict], List[Dict]]:
    """Deterministic split BY question_id (no leakage).

    `train_frac` ∈ (0, 1) is the fraction of QUESTIONS that go to the train
    side (used for MLP training). The remaining 1 − train_frac of questions
    are returned as `dev` (used for both MLP dev metric and CRC calibration).
    """
    qids = sorted({r["question_id"] for r in rows})
    rng = np.random.RandomState(seed)
    rng.shuffle(qids)
    n_train = max(1, int(round(len(qids) * train_frac)))
    train_qids = set(qids[:n_train])
    train = [r for r in rows if r["question_id"] in train_qids]
    dev = [r for r in rows if r["question_id"] not in train_qids]
    return train, dev


def _label_to_binary_lb(label: str) -> int:
    return 1 if label.upper() == "LB" else 0


def _label_to_int(label: str) -> int:
    """0=S, 1=D, 2=LB."""
    u = label.upper()
    if u == "D":
        return 1
    if u == "LB":
        return 2
    return 0


def _stack_features(rows: List[Dict[str, Any]], feature_names: tuple) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (X, y_binary_lb, label_int)."""
    # Map row's feature_names → indices for our feature set
    if not rows:
        return np.zeros((0, len(feature_names)), dtype=np.float32), np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.int64)
    src_names = list(rows[0]["feature_names"])
    name_to_idx = {n: i for i, n in enumerate(src_names)}
    sel_idx = [name_to_idx[n] for n in feature_names]
    X = np.asarray([[r["features"][i] for i in sel_idx] for r in rows], dtype=np.float32)
    y_bin = np.asarray([_label_to_binary_lb(r["label"]) for r in rows], dtype=np.float32)
    y_int = np.asarray([_label_to_int(r["label"]) for r in rows], dtype=np.int64)
    return X, y_bin, y_int


def _group_by_question(rows: List[Dict[str, Any]], scores: np.ndarray, y_int: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray]]:
    """Bucket scores + labels by question_id for CRC."""
    by_q: Dict[str, List[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        by_q[r["question_id"]].append(i)
    scores_per_q = []
    is_distractor_per_q = []
    labels_per_q = []
    for qid, idxs in by_q.items():
        s = scores[idxs]
        y = y_int[idxs]
        scores_per_q.append(s)
        is_distractor_per_q.append((y == 1).astype(np.int64))  # 1 iff D
        labels_per_q.append(y)
    return scores_per_q, is_distractor_per_q, labels_per_q


def _load_qtype_map(lme_path: str) -> Dict[str, str]:
    """Return {question_id: question_type} from LME-S JSON."""
    with open(lme_path) as fh:
        lme = json.load(fh)
    return {
        r.get("question_id") or f"q{i+1}": r.get("question_type", "unknown")
        for i, r in enumerate(lme)
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", default="results/lb_calibration_labels.jsonl")
    ap.add_argument("--feature-set", default="full", choices=["full", "portable"])
    ap.add_argument("--mlp-out", default="results/lb_mlp.json")
    ap.add_argument("--crc-out", default="results/lb_crc.json")
    ap.add_argument("--train-frac", type=float, default=0.8,
                    help="Fraction of QUESTIONS to use for MLP training; rest = dev/cal.")
    ap.add_argument("--cal-of-dev-frac", type=float, default=0.5,
                    help="Within the dev split: this fraction is held back as cal-of-cal for CRC.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--hidden-dim", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--question-type", default=None,
                    help="If set, restrict training to this question_type only "
                         "(e.g. 'single-session-user'). Requires --lme-data.")
    ap.add_argument("--lme-data",
                    default="/home/workspace/lww/project0412/projects/dataset/LongMemEval-main/data/longmemeval_s.json",
                    help="Path to LME-S JSON (needed when --question-type is set).")
    args = ap.parse_args()

    feature_names = FEATURE_NAMES_FULL if args.feature_set == "full" else FEATURE_NAMES_PORTABLE
    labels_path = (PROJECT_ROOT / args.labels).resolve()
    rows = _load_labels(labels_path)
    print(f"[cal] loaded {len(rows)} labelled (q, item) pairs from {labels_path.name}")

    if args.question_type:
        qtype_map = _load_qtype_map(args.lme_data)
        before = len(rows)
        rows = [r for r in rows if qtype_map.get(r["question_id"]) == args.question_type]
        print(f"[cal] filtered to question_type='{args.question_type}': "
              f"{before} -> {len(rows)} pairs "
              f"({len({r['question_id'] for r in rows})} unique qids)")
    if len(rows) < 50:
        print(f"[cal] WARNING: only {len(rows)} pairs; CRC bound will be very loose.")

    # Split by question (train vs dev/cal)
    train_rows, dev_rows = _split_by_question(rows, train_frac=args.train_frac, seed=args.seed)
    print(f"[cal] split (by question, seed={args.seed}): train={len(train_rows)} pairs, dev/cal={len(dev_rows)} pairs")

    # Stack features
    X_train, y_train_bin, _ = _stack_features(train_rows, feature_names)
    X_dev, y_dev_bin, y_dev_int = _stack_features(dev_rows, feature_names)
    print(f"[cal] X_train: {X_train.shape}, X_dev: {X_dev.shape}")
    print(f"[cal] feature_set={args.feature_set} ({len(feature_names)} features)")
    print(f"[cal] LB rate train={y_train_bin.mean():.3f}, dev={y_dev_bin.mean():.3f}")
    print(f"[cal] D rate train={(np.asarray([_label_to_int(r['label']) for r in train_rows]) == 1).mean():.3f}")

    if X_train.shape[0] < 5 or X_dev.shape[0] < 5:
        print("[cal] FAIL: too few pairs to train + calibrate.")
        return 2

    # Train MLP
    model, history = train_mlp(
        X_train, y_train_bin, X_dev, y_dev_bin,
        hidden_dim=args.hidden_dim, lr=args.lr, weight_decay=args.weight_decay,
        epochs=args.epochs, batch_size=args.batch_size, seed=args.seed,
    )
    print(f"[cal] MLP training history:")
    for ep in range(args.epochs):
        print(f"   ep{ep+1}: train_loss={history['train_loss'][ep]:.4f} "
              f"dev_loss={history['dev_loss'][ep]:.4f} dev_auc={history['dev_auc'][ep]:.4f}")
    final_dev_auc = history["dev_auc"][-1]
    print(f"[cal] final dev AUC = {final_dev_auc:.4f} (target ≥ 0.75)")

    # Save MLP
    mlp_out = (PROJECT_ROOT / args.mlp_out).resolve()
    lb_save(model, str(mlp_out), feature_names=feature_names)
    print(f"[cal] saved MLP → {mlp_out}")

    # Score dev pairs
    dev_scores = lb_score(model, X_dev)

    # Split dev into 'cal' and 'cal_of_cal' (CRC fits on cal_of_cal; we still
    # use the rest as a held-out smoke).
    # Group by question, then split question-wise.
    dev_qids = sorted({r["question_id"] for r in dev_rows})
    rng = np.random.RandomState(args.seed + 1)
    rng.shuffle(dev_qids)
    n_calofcal = max(1, int(round(len(dev_qids) * args.cal_of_dev_frac)))
    calofcal_qids = set(dev_qids[:n_calofcal])

    rows_calofcal = [(i, r) for i, r in enumerate(dev_rows) if r["question_id"] in calofcal_qids]
    rows_smoke = [(i, r) for i, r in enumerate(dev_rows) if r["question_id"] not in calofcal_qids]

    def _bucket(idx_rows):
        by_q: Dict[str, List[int]] = defaultdict(list)
        for i, r in idx_rows:
            by_q[r["question_id"]].append(i)
        s_list, d_list, lbl_list = [], [], []
        for qid, idxs in by_q.items():
            s_list.append(dev_scores[idxs])
            d_list.append((y_dev_int[idxs] == 1).astype(np.int64))
            lbl_list.append(y_dev_int[idxs])
        return s_list, d_list, lbl_list

    cc_scores, cc_distract, cc_labels = _bucket(rows_calofcal)
    sm_scores, sm_distract, sm_labels = _bucket(rows_smoke)
    print(f"[cal] cal-of-cal: {len(cc_scores)} questions; smoke held-out: {len(sm_scores)} questions")

    # Run CRC calibration
    cfg = LBCRCConfig()
    table = calibrate_lb(cc_scores, cc_distract, config=cfg, feature_names=feature_names)
    crc_out = (PROJECT_ROOT / args.crc_out).resolve()
    table.save(str(crc_out))
    print(f"[cal] saved CRC table → {crc_out}")

    # Report per-α thresholds + dev coverage on the smoke split
    print(f"\n[cal] === CRC table summary ===")
    for alpha in cfg.alpha_grid:
        lam = table.threshold(alpha)
        if not np.isfinite(lam):
            print(f"  α={alpha}: NO threshold cleared CP UCB (cal too small or risk too high).")
            continue
        # Smoke coverage at this λ̂
        if sm_scores:
            r_smoke = empirical_clean_set_risk(sm_scores, sm_distract, lam)
            util = non_vacuity_metrics(sm_scores, sm_labels, lam)
        else:
            r_smoke = float("nan")
            util = {}
        print(f"  α={alpha}: λ̂={lam:.4f}  smoke R̂={r_smoke:.4f}  "
              f"non_empty={util.get('non_empty_fraction', 0):.2f}  "
              f"|L|̄={util.get('mean_size', 0):.2f}  "
              f"LB_recall={util.get('lb_recall', 0):.2f}  "
              f"distract_frac={util.get('mean_distractor_fraction', 0):.3f}")

    # Intrinsic gates
    print("\n[cal] === Intrinsic acceptance gates ===")
    auc_pass = final_dev_auc >= 0.75
    print(f"  MLP dev AUC ≥ 0.75: {final_dev_auc:.3f} -> {'PASS' if auc_pass else 'FAIL'}")
    if sm_scores:
        all_pass = True
        for alpha in cfg.alpha_grid:
            lam = table.threshold(alpha)
            if not np.isfinite(lam):
                all_pass = False
                continue
            r = empirical_clean_set_risk(sm_scores, sm_distract, lam)
            ok = r <= alpha + 0.04
            if not ok:
                all_pass = False
            print(f"  α={alpha} smoke R̂ ≤ α+0.04: R̂={r:.3f} α+0.04={alpha+0.04:.3f} -> {'PASS' if ok else 'FAIL'}")
        print(f"  Smoke coverage all-α pass: {'PASS' if all_pass else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
