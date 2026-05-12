"""Compute Cohen's κ and confusion matrix for LLM-judge labels vs author manual.

Stratified-borderline sampler: takes 100 (q, item) pairs from
`results/lb_calibration_labels.jsonl`, oversampling `confidence=low` rows by
30%, prints them to a CSV the author labels by hand, and on re-run computes:
  - Cohen's κ on full 3-class agreement (LB / S / D).
  - D-vs-non-D binary collapse κ.
  - Full 3×3 confusion matrix (judge rows, author cols).
  - Class-conditional precision / recall for D.

Usage:
  # 1. Generate the audit batch
  python scripts/audit_judge_labels.py sample --n 100 --out audit/audit_batch.csv

  # 2. Author edits CSV: fills `author_label` column with LB / S / D.

  # 3. Compute κ + matrix
  python scripts/audit_judge_labels.py score --in audit/audit_batch.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_jsonl(path: Path) -> List[Dict]:
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


def cmd_sample(args) -> int:
    src = (PROJECT_ROOT / args.labels).resolve()
    rows = _load_jsonl(src)
    print(f"[audit] loaded {len(rows)} labelled pairs from {src.name}")
    rng = np.random.RandomState(args.seed)
    # Stratified-borderline: 30% from confidence=low, 70% from confidence=high
    low = [r for r in rows if (r.get("confidence", "low") == "low")]
    high = [r for r in rows if (r.get("confidence", "low") != "low")]
    n_low = int(round(args.n * 0.3))
    n_high = args.n - n_low
    n_low = min(n_low, len(low))
    n_high = min(n_high, len(high))
    sel_low = rng.choice(len(low), size=n_low, replace=False) if n_low > 0 else []
    sel_high = rng.choice(len(high), size=n_high, replace=False) if n_high > 0 else []
    selected = [low[int(i)] for i in sel_low] + [high[int(i)] for i in sel_high]
    rng.shuffle(selected)
    out_path = (PROJECT_ROOT / args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["question_id", "item_id", "question", "gold", "content",
                    "judge_label", "judge_confidence", "judge_rationale", "author_label"])
        for r in selected:
            w.writerow([
                r["question_id"], r["item_id"],
                (r.get("question") or "")[:200],
                (r.get("gold") or "")[:120],
                (r.get("content") or "")[:300],
                r.get("label", ""),
                r.get("confidence", ""),
                (r.get("rationale") or "")[:200],
                "",  # author fills in
            ])
    print(f"[audit] wrote {len(selected)} pairs to {out_path}")
    print(f"[audit] borderline (confidence=low) sampled: {n_low}; high: {n_high}")
    print(f"[audit] author should fill `author_label` (LB | S | D), then run `score`.")
    return 0


def _cohen_kappa(y1: List[str], y2: List[str], classes: Tuple[str, ...]) -> float:
    """Cohen's κ on the labels in `classes`. Drops pairs where either is unknown."""
    pairs = [(a, b) for a, b in zip(y1, y2) if a in classes and b in classes]
    if not pairs:
        return float("nan")
    n = len(pairs)
    cls_idx = {c: i for i, c in enumerate(classes)}
    cm = np.zeros((len(classes), len(classes)), dtype=np.int64)
    for a, b in pairs:
        cm[cls_idx[a], cls_idx[b]] += 1
    obs = float(np.trace(cm)) / n
    p_a = cm.sum(axis=1) / n
    p_b = cm.sum(axis=0) / n
    exp = float((p_a * p_b).sum())
    if exp >= 1.0:
        return float("nan")
    return (obs - exp) / (1.0 - exp)


def _confusion(y_judge: List[str], y_author: List[str], classes: Tuple[str, ...]) -> np.ndarray:
    cls_idx = {c: i for i, c in enumerate(classes)}
    cm = np.zeros((len(classes), len(classes)), dtype=np.int64)
    for j, a in zip(y_judge, y_author):
        if j not in cls_idx or a not in cls_idx:
            continue
        cm[cls_idx[j], cls_idx[a]] += 1
    return cm


def cmd_score(args) -> int:
    src = (PROJECT_ROOT / args.input).resolve()
    rows = []
    with open(src) as fh:
        r = csv.DictReader(fh)
        for row in r:
            rows.append(row)
    print(f"[audit] loaded {len(rows)} audit rows from {src.name}")
    y_judge = [r.get("judge_label", "").strip().upper() for r in rows]
    y_author = [r.get("author_label", "").strip().upper() for r in rows]
    n_filled = sum(1 for a in y_author if a in ("LB", "S", "D"))
    print(f"[audit] {n_filled}/{len(rows)} author labels present")
    if n_filled < 10:
        print(f"[audit] FAIL: insufficient author labels (need ≥ 10)")
        return 2

    classes_full = ("LB", "S", "D")
    kappa_3 = _cohen_kappa(y_judge, y_author, classes_full)
    print(f"[audit] Cohen's κ (3-class LB/S/D): {kappa_3:.4f}  (target ≥ 0.7)")

    # D vs non-D binary collapse
    def _collapse(lbl: str) -> str:
        return "D" if lbl == "D" else "X"
    yj = [_collapse(l) for l in y_judge]
    ya = [_collapse(l) for l in y_author]
    kappa_d = _cohen_kappa(yj, ya, ("D", "X"))
    print(f"[audit] Cohen's κ (D vs non-D):     {kappa_d:.4f}  (target ≥ 0.75)")

    # 3×3 confusion matrix (rows = judge, cols = author)
    cm = _confusion(y_judge, y_author, classes_full)
    print("\n[audit] 3×3 confusion matrix (rows=judge, cols=author):")
    header = "          " + "  ".join(f"A:{c:>3}" for c in classes_full) + "    row"
    print(header)
    for i, c in enumerate(classes_full):
        row = cm[i]
        print(f"  J:{c:>3}   " + "  ".join(f"{int(x):>5}" for x in row) + f"   {int(row.sum()):>5}")
    col_sums = cm.sum(axis=0)
    print(f"  col      " + "  ".join(f"{int(x):>5}" for x in col_sums) + f"   {int(cm.sum()):>5}")

    # Class-conditional D precision/recall
    if cm.sum() > 0:
        d_idx = classes_full.index("D")
        tp = cm[d_idx, d_idx]
        fp = cm[d_idx, :].sum() - tp  # judge said D but author didn't
        fn = cm[:, d_idx].sum() - tp  # author said D but judge didn't
        prec = tp / (tp + fp) if (tp + fp) > 0 else float("nan")
        rec = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
        print(f"\n[audit] D-class precision (judge): {prec:.3f}")
        print(f"[audit] D-class recall (judge):    {rec:.3f}")

    print("\n[audit] === Verdict ===")
    pass_3 = (kappa_3 >= 0.7)
    pass_d = (kappa_d >= 0.75)
    print(f"  3-class κ ≥ 0.7 : {'PASS' if pass_3 else 'FAIL'}")
    print(f"  D-vs-non-D κ ≥ 0.75 : {'PASS' if pass_d else 'FAIL'}")
    if pass_3 and pass_d:
        print("  → labels OK; proceed.")
    elif kappa_3 >= 0.65 or kappa_d >= 0.65:
        print("  → MARGINAL: re-run judge with 3-call self-consistency on disagreed items, then re-audit.")
    else:
        print("  → FAIL: fall back to binary `LB` vs `not-LB` label (Failure clause F4).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="Sample 100 pairs for author audit (CSV).")
    s.add_argument("--labels", default="results/lb_calibration_labels.jsonl")
    s.add_argument("--out", default="audit/audit_batch.csv")
    s.add_argument("--n", type=int, default=100)
    s.add_argument("--seed", type=int, default=0)
    s.set_defaults(func=cmd_sample)
    s2 = sub.add_parser("score", help="Score the author-filled audit CSV.")
    s2.add_argument("--input", default="audit/audit_batch.csv")
    s2.set_defaults(func=cmd_score)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
