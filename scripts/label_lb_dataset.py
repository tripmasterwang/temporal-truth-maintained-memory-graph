"""LLM-label (q, item) pairs on PerLTQA / QAConv / LoCoMo-SSU for domain CalLB.

Writes the same JSONL schema as ``scripts/label_lb_pairs.py`` so
``scripts/calibrate_lb.py`` can consume it. Only processes ``question_id`` in
the cal split from ``--split-json`` (or builds split and writes it).

Example:
  python scripts/label_lb_dataset.py --dataset perltqa \\
    --split-json results/dataset_exp/perltqa/split_s0.json \\
    --eval-set cal --max-questions 80 \\
    --out results/dataset_exp/perltqa/lb_labels.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sentence_transformers import SentenceTransformer

from experiments.dataset_lb_items import (
    list_locomo_ssu_items_ordered,
    list_perltqa_items_ordered,
    list_qaconv_items_ordered,
    load_split,
    save_split,
    split_cal_test_qids,
)
from experiments.transfer_items import (
    DEFAULT_DATASET_ROOT,
    load_perltqa_pair,
    load_qaconv_rows,
    load_qaconv_segment_map,
)
from ttmg import TTMGConfig, TTMGSystem
from ttmg.lb_features import FEATURE_NAMES_FULL, extract_features
from ttmg.lb_retrieval import gather_candidates
from ttmg.maas_client import DEFAULT_MODEL, chat_json

_JUDGE_SYS = (
    "You are a careful annotator labelling whether a retrieved memory item "
    "is Load-Bearing, Supporting, or Distractor for answering a question. "
    "Respond ONLY with strict JSON."
)

_JUDGE_USER_TMPL = """GIVEN:
  - Question: {question}
  - Gold answer: {gold}
  - Candidate retrieved item:
      content: {item}
      source: {source}
      uttered_at: {ts}

Judge whether the item, *taken on its own*, supports the gold answer:

(A) LOAD-BEARING — the item by itself contains (or directly entails) the gold-answer information. A reader given just this item could produce the gold answer.
(B) SUPPORTING — the item is topically related to the question or gold answer (same person, place, event, or theme) but does NOT by itself contain the gold answer. Safe context.
(C) DISTRACTOR — the item is on-topic enough to be retrieved but would mislead a reader: it mentions a different entity / wrong value / outdated state / superseded preference, OR it invites the reader to add unsupported adjacent detail (over-specification).

Important:
- Judge each item *self-sufficiently*; do not assume what other items the reader will see.
- If the item is the user/assistant simply discussing the topic without stating the gold value → SUPPORTING.
- If the item mentions a SIMILAR-BUT-DIFFERENT entity / value than the gold → DISTRACTOR.

Return strict JSON:
{{
  "label": "LB" | "S" | "D",
  "rationale": "one sentence",
  "confidence": "high" | "low"
}}"""

_JUDGE_FAILURE_SENTINELS = ("judge_failed", "judge_exception")


def _sessions_from_item(item: Dict[str, Any], max_sessions: Optional[int]) -> List[Dict[str, Any]]:
    sessions: List[Dict[str, Any]] = []
    for sid, sts, sess in zip(
        item["haystack_session_ids"], item["haystack_dates"], item["haystack_sessions"]
    ):
        turns = []
        for turn in sess:
            if not isinstance(turn, dict):
                continue
            sp = turn.get("role") or turn.get("speaker") or "user"
            tx = (turn.get("content") or turn.get("text") or "").strip()
            if tx:
                turns.append({"speaker": str(sp), "text": tx})
        sessions.append({"session_id": sid, "session_ts": sts or "", "turns": turns})
    if max_sessions is not None and max_sessions > 0 and len(sessions) > max_sessions:
        sessions = sessions[:max_sessions]
    return sessions


def _ingest_item(
    item: Dict[str, Any],
    embed_model: SentenceTransformer,
    *,
    writer_model: str,
    disable_writer_claims: bool,
    max_sessions: Optional[int],
) -> TTMGSystem:
    cfg = TTMGConfig(
        enable_beta=False,
        raw_turn_fallback=True,
        batch_writer_per_session=True,
        disable_writer_claims=disable_writer_claims,
        disable_contradict=disable_writer_claims,
        writer_model=writer_model,
        linker_model=writer_model,
    )
    sys_obj = TTMGSystem(config=cfg, embed_model=embed_model)
    sessions = _sessions_from_item(item, max_sessions)
    sys_obj.ingest_conversation(sessions, verbose=False)
    return sys_obj


def _load_existing_labels(out_path: Path) -> Set[Tuple[str, str]]:
    seen: Set[Tuple[str, str]] = set()
    if not out_path.exists():
        return seen
    with open(out_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                seen.add((rec["question_id"], rec["item_id"]))
            except Exception:
                continue
    return seen


def _load_all_items(
    dataset: str,
    *,
    dataset_root: Optional[Path],
    locomo_path: Path,
    locomo_max_convs: Optional[int],
    locomo_max_qa_per_conv: Optional[int],
    qaconv_split: str,
) -> List[Tuple[str, Dict[str, Any]]]:
    dr = Path(dataset_root) if dataset_root else DEFAULT_DATASET_ROOT
    if dataset == "perltqa":
        mem, qa = load_perltqa_pair(dataset_root=dr)
        return list_perltqa_items_ordered(mem, qa)
    if dataset == "qaconv":
        rows = load_qaconv_rows(qaconv_split, dataset_root=dr)
        seg = load_qaconv_segment_map(dataset_root=dr)
        return list_qaconv_items_ordered(rows, seg)
    if dataset == "locomo-ssu":
        raw = json.loads(Path(locomo_path).read_text(encoding="utf-8"))
        if locomo_max_convs is not None:
            raw = raw[: locomo_max_convs]
        return list_locomo_ssu_items_ordered(raw, max_qa_per_conv=locomo_max_qa_per_conv)
    raise ValueError(dataset)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", choices=("perltqa", "qaconv", "locomo-ssu"), required=True)
    ap.add_argument("--dataset-root", default=None)
    ap.add_argument("--split-json", required=True, help="Write or read cal/test qid split.")
    ap.add_argument("--write-split-only", action="store_true",
                    help="Only compute cal/test qids from full corpus and exit.")
    ap.add_argument("--cal-frac", type=float, default=0.70)
    ap.add_argument("--split-seed", type=int, default=0)
    ap.add_argument("--eval-set", choices=("cal", "test"), default="cal",
                    help="Which qids to label (default: cal pool for calibration).")
    ap.add_argument("--out", default=None, help="JSONL label output (required unless --write-split-only).")
    ap.add_argument("--max-questions", type=int, default=None,
                    help="Cap labelled questions from the eval-set pool.")
    ap.add_argument("--max-sessions", type=int, default=3)
    ap.add_argument("--k-per-substrate", type=int, default=10)
    ap.add_argument("--max-candidates", type=int, default=30)
    ap.add_argument("--judge-model", default="deepseek-v3.2")
    ap.add_argument("--writer-model", default=None)
    ap.add_argument("--embed-model", default="all-MiniLM-L6-v2")
    ap.add_argument("--disable-writer-claims", action="store_true")
    ap.add_argument("--qaconv-split", default="test", help="Which QAConv JSON split to index.")
    ap.add_argument("--locomo-data", default=str(DEFAULT_DATASET_ROOT / "locomo-main" / "data" / "locomo10.json"))
    ap.add_argument("--locomo-max-convs", type=int, default=None)
    ap.add_argument("--locomo-max-qa-per-conv", type=int, default=None)
    args = ap.parse_args()

    writer_model = args.writer_model or DEFAULT_MODEL
    dr = Path(args.dataset_root) if args.dataset_root else None

    split_path = (PROJECT_ROOT / args.split_json).resolve()

    if split_path.exists():
        cal_qids, test_qids, _meta = load_split(split_path)
        if args.dataset == "qaconv":
            rows_trn = load_qaconv_rows("train", dataset_root=dr)
            rows_tst = load_qaconv_rows("test", dataset_root=dr)
            seg = load_qaconv_segment_map(dataset_root=dr)
            all_items = list_qaconv_items_ordered(rows_trn, seg) + list_qaconv_items_ordered(rows_tst, seg)
        else:
            all_items = _load_all_items(
                args.dataset,
                dataset_root=dr,
                locomo_path=Path(args.locomo_data),
                locomo_max_convs=args.locomo_max_convs,
                locomo_max_qa_per_conv=args.locomo_max_qa_per_conv,
                qaconv_split=args.qaconv_split,
            )
    else:
        if args.dataset == "qaconv":
            rows_trn = load_qaconv_rows("train", dataset_root=dr)
            rows_tst = load_qaconv_rows("test", dataset_root=dr)
            seg = load_qaconv_segment_map(dataset_root=dr)
            items_trn = list_qaconv_items_ordered(rows_trn, seg)
            items_tst = list_qaconv_items_ordered(rows_tst, seg)
            cal_qids = {q for q, _ in items_trn}
            test_qids = {q for q, _ in items_tst}
            all_items = items_trn + items_tst
            save_split(
                split_path,
                dataset=args.dataset,
                cal_frac=1.0,
                seed=args.split_seed,
                cal_qids=cal_qids,
                test_qids=test_qids,
                meta={"split_mode": "qaconv_trn_tst", "n_cal_items": len(items_trn), "n_test_items": len(items_tst)},
            )
            print(f"[label_ds] wrote QAConv disjoint split -> {split_path} "
                  f"(cal=trn {len(cal_qids)} qids, test=tst {len(test_qids)} qids)")
        else:
            all_items = _load_all_items(
                args.dataset,
                dataset_root=dr,
                locomo_path=Path(args.locomo_data),
                locomo_max_convs=args.locomo_max_convs,
                locomo_max_qa_per_conv=args.locomo_max_qa_per_conv,
                qaconv_split=args.qaconv_split,
            )
            all_qids = [qid for qid, _ in all_items]
            cal_qids, test_qids = split_cal_test_qids(all_qids, cal_frac=args.cal_frac, seed=args.split_seed)
            save_split(
                split_path,
                dataset=args.dataset,
                cal_frac=args.cal_frac,
                seed=args.split_seed,
                cal_qids=cal_qids,
                test_qids=test_qids,
                meta={"n_items": len(all_items)},
            )
            print(f"[label_ds] wrote split -> {split_path} (cal={len(cal_qids)} test={len(test_qids)})")

    if args.write_split_only:
        print("[label_ds] --write-split-only: done.")
        return 0

    if not args.out:
        print("[label_ds] ERROR: --out required for labelling.", file=sys.stderr)
        return 2

    pool = cal_qids if args.eval_set == "cal" else test_qids
    items = [(q, it) for q, it in all_items if q in pool]
    if args.max_questions is not None and args.max_questions < len(items):
        items = items[: args.max_questions]

    out_path = (PROJECT_ROOT / args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = _load_existing_labels(out_path)
    fail_path = out_path.with_name(out_path.stem + "_failures.jsonl")

    print(f"[label_ds] dataset={args.dataset} eval_set={args.eval_set} to_label={len(items)} "
          f"resume_pairs={len(seen)}")

    embed_model = SentenceTransformer(args.embed_model)
    n_new = 0
    n_fail = 0
    n_judge = 0
    t0 = time.time()
    skip_threshold = 10
    qid_counts: Dict[str, int] = {}
    for q, _ in seen:
        qid_counts[q] = qid_counts.get(q, 0) + 1

    for wi, (qid, item) in enumerate(items, 1):
        question = str(item.get("question") or "").strip()
        gold = str(item.get("answer") or "").strip()
        ts_q = item.get("question_date")
        if not question or not gold:
            continue
        if qid_counts.get(qid, 0) >= skip_threshold:
            continue
        try:
            sys_obj = _ingest_item(
                item, embed_model,
                writer_model=writer_model,
                disable_writer_claims=args.disable_writer_claims,
                max_sessions=args.max_sessions,
            )
        except Exception as e:
            print(f"  [{wi}] {qid} ingest failed: {e}")
            continue
        try:
            cands = gather_candidates(
                question, sys_obj,
                k_per_substrate=args.k_per_substrate,
                max_candidates=args.max_candidates,
            )
        except Exception as e:
            print(f"  [{wi}] {qid} candidates failed: {e}")
            continue
        if not cands:
            print(f"  [{wi}] {qid} 0 candidates")
            continue

        n_q_new = 0
        for c in cands:
            key = (qid, c.id)
            if key in seen:
                continue
            feats = extract_features(
                question, c, sys_obj.graph, ts_q=ts_q,
                feature_names=FEATURE_NAMES_FULL,
            )
            prompt = _JUDGE_USER_TMPL.format(
                question=question,
                gold=gold,
                item=c.content[:600],
                source=c.source_type,
                ts=(
                    c.claim.provenance.session_ts
                    if (c.claim and c.claim.provenance)
                    else (c.raw_turn.get("session_ts") if c.raw_turn else "?")
                ),
            )
            judge_failed = False
            try:
                payload = chat_json(
                    prompt, system=_JUDGE_SYS, model=args.judge_model,
                    default={"label": "S", "rationale": "judge_failed", "confidence": "low"},
                    temperature=0.0, max_tokens=200,
                )
                rationale_lower = (payload.get("rationale") or "").lower()
                if any(s in rationale_lower for s in _JUDGE_FAILURE_SENTINELS):
                    judge_failed = True
            except Exception as e:
                judge_failed = True
                payload = {"label": "S", "rationale": f"judge_exception:{e}"[:200], "confidence": "low"}
            n_judge += 1

            if judge_failed:
                n_fail += 1
                with open(fail_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"question_id": qid, "item_id": c.id, "ts": time.time()}) + "\n")
                continue

            label = (payload.get("label") or "S").strip().upper()
            if label not in ("LB", "S", "D"):
                up = label
                if "LB" in up or "LOAD" in up or up.startswith("A"):
                    label = "LB"
                elif "DIS" in up or up.startswith("C"):
                    label = "D"
                elif "SUPP" in up or up.startswith("B"):
                    label = "S"
                else:
                    n_fail += 1
                    with open(fail_path, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"question_id": qid, "item_id": c.id, "rationale": f"bad:{label}"}) + "\n")
                    continue

            rec = {
                "question_id": qid,
                "question": question[:400],
                "gold": gold[:200],
                "item_id": c.id,
                "content": c.content[:500],
                "source_type": c.source_type,
                "in_topk": dict(c.in_topk),
                "substrate_scores": {k: (float(v) if v is not None else None) for k, v in c.score.items()},
                "label": label,
                "rationale": (payload.get("rationale") or "")[:300],
                "confidence": (payload.get("confidence") or "low").lower(),
                "features": [float(x) for x in feats.tolist()],
                "feature_names": list(FEATURE_NAMES_FULL),
            }
            with open(out_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            seen.add(key)
            qid_counts[qid] = qid_counts.get(qid, 0) + 1
            n_new += 1
            n_q_new += 1

        elapsed = time.time() - t0
        print(f"  [{wi}/{len(items)}] {qid} +{n_q_new} pairs | total_new={n_new} fail={n_fail} "
              f"judge={n_judge} {elapsed:.0f}s")

    print(f"[label_ds] done new_pairs={n_new} judge_calls={n_judge} failures={n_fail} -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
