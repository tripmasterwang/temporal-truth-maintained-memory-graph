"""Offline smoke for the CalLB pipeline (NO MAAS calls).

Verifies on a single LongMemEval-S question:
  1. LME-S timestamp parsing (`_parse_iso` handles "YYYY/MM/DD (DOW) HH:MM").
  2. TTMGSystem with `disable_writer_claims=True` (so no MAAS during ingest).
  3. `gather_candidates` returns a non-empty pool with 4 substrate flags.
  4. `extract_features` produces a finite 13-d vector with non-zero
     temporal/recency features (regression-test for the CRITICAL fix).
  5. `LBReranker` forward + `lb_crc.calibrate_lb` on synthetic scores.
  6. Stable candidate ids: gather twice and verify ids match.

Run: python scripts/smoke_lb_offline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sentence_transformers import SentenceTransformer

from ttmg.lb_crc import LBCRCConfig, calibrate_lb, empirical_clean_set_risk, non_vacuity_metrics
from ttmg.lb_features import (
    FEATURE_NAMES_FULL, _parse_iso, extract_features, feature_dim,
)
from ttmg.lb_model import LBReranker, score, train_mlp
from ttmg.lb_retrieval import gather_candidates
from ttmg.schema import Provenance
from ttmg.system import TTMGConfig, TTMGSystem


LME_PATH = "/home/workspace/lww/project0412/projects/dataset/LongMemEval-main/data/longmemeval_s.json"


def _check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"  FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


def main() -> int:
    print("[smoke] === 1. LME-S timestamp parsing ===")
    p1 = _parse_iso("2023/05/30 (Tue) 23:40")
    _check(p1 is not None, "_parse_iso 'YYYY/MM/DD (DOW) HH:MM'")
    _check(p1.year == 2023 and p1.month == 5 and p1.day == 30 and p1.hour == 23,
           "parsed components match (2023-05-30 23:40)")
    p2 = _parse_iso("2023-05-30T23:40:00Z")
    _check(p2 is not None and p2.year == 2023, "_parse_iso ISO with Z")
    p3 = _parse_iso("2023-05-30")
    _check(p3 is not None, "_parse_iso bare date")

    print("\n[smoke] === 2. Load LME-S + ingest one question (no MAAS) ===")
    lme = json.load(open(LME_PATH))
    print(f"  LME-S size: {len(lme)}")
    rec = lme[0]
    print(f"  question_id: {rec.get('question_id')}, type: {rec.get('question_type')}")
    print(f"  question: {rec.get('question')[:100]}")
    print(f"  question_date: {rec.get('question_date')}")

    embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    cfg = TTMGConfig(disable_writer_claims=True, disable_contradict=True, raw_turn_fallback=True)
    sys_obj = TTMGSystem(config=cfg, embed_model=embed_model)
    sids = rec.get("haystack_session_ids", []) or []
    sessions = rec.get("haystack_sessions", []) or []
    dates = rec.get("haystack_dates", []) or []
    n_turns = 0
    for sid, sdate, sess in zip(sids[:5], dates[:5], sessions[:5]):
        for ti, t in enumerate(sess):
            if not isinstance(t, dict):
                continue
            text = (t.get("content") or "").strip()
            if not text:
                continue
            prov = Provenance(session_id=sid, turn_id=f"{sid}#{ti}",
                              speaker=t.get("role"), session_ts=sdate)
            sys_obj.ingest_turn(text, prov)
            sys_obj._register_turn(text, prov)
            n_turns += 1
    print(f"  ingested {n_turns} turns; #claims={len(sys_obj.graph.claims)}; #raw={len(sys_obj._raw_turns)}")
    _check(len(sys_obj.graph.claims) > 0, "claims present")
    _check(len(sys_obj._raw_turns) > 0, "raw turns present")

    print("\n[smoke] === 3. Multi-substrate candidate gathering ===")
    question = rec.get("question").strip()
    cands = gather_candidates(question, sys_obj, k_per_substrate=10, max_candidates=30)
    print(f"  got {len(cands)} candidates")
    _check(len(cands) > 0, "non-empty candidate pool")
    sub_counts = {s: 0 for s in ("semantic", "lexical", "claim", "raw")}
    for c in cands:
        for s, v in c.in_topk.items():
            if v:
                sub_counts[s] += 1
    print(f"  substrate hit counts: {sub_counts}")
    _check(sub_counts["semantic"] > 0, "semantic substrate hit ≥ 1")
    _check(sub_counts["lexical"] > 0, "lexical substrate hit ≥ 1")
    _check(sub_counts["raw"] > 0, "raw substrate hit ≥ 1")

    print("\n[smoke] === 4. Feature extraction (with τ_q from LME-S) ===")
    ts_q = rec.get("question_date")
    feats_list = []
    n_pos_recency = 0
    for c in cands:
        f = extract_features(question, c, sys_obj.graph, ts_q=ts_q,
                             feature_names=FEATURE_NAMES_FULL)
        _check(np.all(np.isfinite(f)), "all features finite")
        _check(len(f) == feature_dim(FEATURE_NAMES_FULL), "feature dim = 13")
        feats_list.append(f)
        # CRITICAL-1 regression: at least some items must have non-zero
        # recency_baseline (depends on session_ts being parsed correctly).
        if f[3] > 0:  # recency_baseline is index 3
            n_pos_recency += 1
    print(f"  recency_baseline > 0 on {n_pos_recency}/{len(cands)} candidates "
          f"(target: >0; was 0 before CRITICAL-1 fix)")
    _check(n_pos_recency > 0, "CRITICAL-1 regression: recency feature non-zero")

    print("\n[smoke] === 5. CRITICAL-2 regression: stable candidate ids ===")
    # Re-build a fresh system + ingest the same question; ids must match.
    cfg2 = TTMGConfig(disable_writer_claims=True, raw_turn_fallback=True)
    sys_obj2 = TTMGSystem(config=cfg2, embed_model=embed_model)
    for sid, sdate, sess in zip(sids[:5], dates[:5], sessions[:5]):
        for ti, t in enumerate(sess):
            if not isinstance(t, dict):
                continue
            text = (t.get("content") or "").strip()
            if not text:
                continue
            prov = Provenance(session_id=sid, turn_id=f"{sid}#{ti}",
                              speaker=t.get("role"), session_ts=sdate)
            sys_obj2.ingest_turn(text, prov)
            sys_obj2._register_turn(text, prov)
    cands2 = gather_candidates(question, sys_obj2, k_per_substrate=10, max_candidates=30)
    ids1 = {c.id for c in cands}
    ids2 = {c.id for c in cands2}
    overlap = len(ids1 & ids2)
    print(f"  candidate id overlap: {overlap}/{len(ids1)} (target: ≥ 90 %)")
    _check(overlap >= 0.9 * len(ids1), "CRITICAL-2 regression: ≥ 90 % id overlap on re-ingest")

    print("\n[smoke] === 6. MLP + CRC sanity ===")
    n = len(cands)
    X = np.stack(feats_list)
    # Synthetic labels (only sanity; not a real test of the model)
    y_bin = np.array([1 if (c.in_topk.get("semantic") and c.score.get("semantic", 0) > 0.5) else 0 for c in cands], dtype=np.float32)
    y_int = np.array([2 if y == 1 else 0 for y in y_bin], dtype=np.int64)  # 2=LB, 0=S, no D
    if y_bin.sum() == 0:
        y_bin[:1] = 1
        y_int[:1] = 2
    if y_bin.sum() == len(y_bin):
        y_bin[-1] = 0
        y_int[-1] = 0
    print(f"  synth label distribution: LB={int(y_bin.sum())}/{len(y_bin)}")
    model, hist = train_mlp(X, y_bin, X, y_bin, hidden_dim=32, epochs=2, seed=0)
    print(f"  MLP train_loss={hist['train_loss']}; dev_loss={hist['dev_loss']}")
    s = score(model, X)
    _check(s.shape == (n,) and np.all((0 <= s) & (s <= 1)), "MLP scores in [0,1]")

    # Synthetic CRC (one query group → marginal)
    table = calibrate_lb([s], [np.zeros(n, dtype=np.int64)], LBCRCConfig(alpha_grid=(0.10, 0.20, 0.99)))
    print(f"  CRC λ̂: {table.lambdas}")
    util = non_vacuity_metrics([s], [y_int], lam=table.threshold(0.99))
    print(f"  utility @ λ̂_0.99: {util}")
    _check(0.0 <= util["non_empty_fraction"] <= 1.0, "non_empty_fraction in [0,1]")

    print("\n[smoke] ALL CHECKS PASS — pipeline ready for MAAS smoke (~150 calls).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
