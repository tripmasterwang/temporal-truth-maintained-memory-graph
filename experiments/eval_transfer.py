"""Evaluate CalLB / TTMG methods on PerLTQA and QAConv (single-session style).

Reuses ``experiments.eval_callb.run_one`` and the same JSONL resume format as
``eval_longmemeval`` / ``eval_callb``.

LoCoMo single-session subset: ``--bench locomo-ssu`` (same judge + JSONL format as
PerLTQA/QAConv). Alternatively ``python -m experiments.eval_locomo --single-session-only``.

Domain eval (hold-out test qids): pass ``--split-json`` + ``--eval-set test``.

Examples:
  python -m experiments.eval_transfer --bench perltqa --method ttmg \\
      --out results/transfer_perltqa_ttmg.jsonl
  python -m experiments.eval_transfer --bench perltqa --method callb \\
      --callb-model results/lb_mlp.json --callb-crc results/lb_crc.json \\
      --out results/transfer_perltqa_callb.jsonl
  python -m experiments.eval_transfer --bench qaconv --qaconv-split test \\
      --method callb --limit 200 --seed 0 --out results/transfer_qaconv.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentence_transformers import SentenceTransformer

from experiments.eval_callb import (  # noqa: E402
    METHODS,
    judge_answer,
    run_one,
    summarise,
    token_f1,
)
from experiments.eval_callb import _load_existing  # noqa: E402
from experiments.dataset_lb_items import (  # noqa: E402
    list_locomo_ssu_items_ordered,
    list_perltqa_items_ordered,
    list_qaconv_items_ordered,
    load_split,
)
from experiments.transfer_items import (  # noqa: E402
    DEFAULT_DATASET_ROOT,
    iter_perltqa_items,
    iter_qaconv_items,
    load_perltqa_pair,
    load_qaconv_rows,
    load_qaconv_segment_map,
)


def _iter_benchmark(
    bench: str,
    *,
    dataset_root: Optional[Path],
    qaconv_split: str,
    limit: Optional[int],
    seed: int,
) -> Iterator[Tuple[str, Dict[str, Any]]]:
    bench = bench.lower().strip()
    if bench == "perltqa":
        mem, qa = load_perltqa_pair(dataset_root=dataset_root)
        yield from iter_perltqa_items(mem, qa, limit=limit, seed=seed)
    elif bench == "qaconv":
        rows = load_qaconv_rows(qaconv_split, dataset_root=dataset_root)
        seg = load_qaconv_segment_map(dataset_root=dataset_root)
        yield from iter_qaconv_items(rows, seg, limit=limit, seed=seed)
    elif bench == "locomo-ssu":
        root = dataset_root if dataset_root else DEFAULT_DATASET_ROOT
        path = Path(root) / "locomo-main" / "data" / "locomo10.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = list_locomo_ssu_items_ordered(raw, max_qa_per_conv=None)
        lst = list(items)
        rng = random.Random(seed)
        rng.shuffle(lst)
        if limit is not None and limit < len(lst):
            lst = lst[:limit]
        yield from lst
    else:
        raise ValueError(f"Unknown --bench {bench!r}; use perltqa|qaconv|locomo-ssu")


def _planned_from_split(
    bench: str,
    *,
    dataset_root: Optional[Path],
    split_json: Path,
    eval_set: str,
    limit: Optional[int],
    locomo_path: Path,
    locomo_max_convs: Optional[int],
    locomo_max_qa_per_conv: Optional[int],
) -> List[Tuple[str, Dict[str, Any]]]:
    cal_qids, test_qids, _meta = load_split(split_json)
    pool = cal_qids if eval_set == "cal" else test_qids
    dr = dataset_root
    if bench == "perltqa":
        mem, qa = load_perltqa_pair(dataset_root=dr)
        items = list_perltqa_items_ordered(mem, qa)
    elif bench == "qaconv":
        if eval_set == "cal":
            rows = load_qaconv_rows("train", dataset_root=dr)
        else:
            rows = load_qaconv_rows("test", dataset_root=dr)
        seg = load_qaconv_segment_map(dataset_root=dr)
        items = list_qaconv_items_ordered(rows, seg)
    elif bench == "locomo-ssu":
        raw = json.loads(Path(locomo_path).read_text(encoding="utf-8"))
        if locomo_max_convs is not None:
            raw = raw[: locomo_max_convs]
        items = list_locomo_ssu_items_ordered(raw, max_qa_per_conv=locomo_max_qa_per_conv)
    else:
        raise ValueError(bench)
    planned = [(q, it) for q, it in items if q in pool]
    if limit is not None and limit < len(planned):
        planned = planned[:limit]
    return planned


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bench", choices=("perltqa", "qaconv", "locomo-ssu"), required=True)
    ap.add_argument("--dataset-root", default=None, help="Override DATASET_PROJECT_ROOT")
    ap.add_argument("--qaconv-split", default="test", help="train | validation | test (ignored if --split-json)")
    ap.add_argument("--split-json", default=None, help="Split file from label_lb_dataset.py (domain hold-out).")
    ap.add_argument("--eval-set", choices=("cal", "test"), default="test",
                    help="With --split-json: evaluate only this qid pool.")
    ap.add_argument("--locomo-data", default=str(DEFAULT_DATASET_ROOT / "locomo-main" / "data" / "locomo10.json"))
    ap.add_argument("--locomo-max-convs", type=int, default=None)
    ap.add_argument("--locomo-max-qa-per-conv", type=int, default=None)
    ap.add_argument("--method", choices=METHODS, required=True)
    ap.add_argument("--out", required=True, help="JSONL (resumable by question_id)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--callb-model", default="results/lb_mlp.json")
    ap.add_argument("--callb-crc", default="results/lb_crc.json")
    ap.add_argument("--callb-alpha", type=float, default=0.20)
    ap.add_argument("--no-crc-threshold", type=float, default=0.5)
    ap.add_argument("--rerank-top-k", type=int, default=3)
    ap.add_argument("--writer-model", default=None)
    ap.add_argument("--reader-model", default=None)
    ap.add_argument("--parser-model", default=None)
    ap.add_argument("--embed-model", default="all-MiniLM-L6-v2")
    args = ap.parse_args()

    from ttmg.maas_client import DEFAULT_MODEL

    if args.writer_model is None:
        args.writer_model = DEFAULT_MODEL
    if args.reader_model is None:
        args.reader_model = DEFAULT_MODEL
    if args.parser_model is None:
        args.parser_model = DEFAULT_MODEL

    dataset_root = Path(args.dataset_root).expanduser() if args.dataset_root else None

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = _load_existing(out_path)
    print(f"[transfer] resume: {len(seen)} already in {out_path}")

    run_args = argparse.Namespace(
        method=args.method,
        callb_model=args.callb_model,
        callb_crc=args.callb_crc,
        callb_alpha=args.callb_alpha,
        no_crc_threshold=args.no_crc_threshold,
        rerank_top_k=args.rerank_top_k,
        writer_model=args.writer_model,
        reader_model=args.reader_model,
        parser_model=args.parser_model,
    )

    print("[transfer] loading embedding model...")
    embed_model = SentenceTransformer(args.embed_model)

    if args.split_json:
        planned = _planned_from_split(
            args.bench,
            dataset_root=dataset_root,
            split_json=(PROJECT_ROOT / args.split_json).resolve(),
            eval_set=args.eval_set,
            limit=args.limit,
            locomo_path=Path(args.locomo_data),
            locomo_max_convs=args.locomo_max_convs,
            locomo_max_qa_per_conv=args.locomo_max_qa_per_conv,
        )
    else:
        planned = list(
            _iter_benchmark(
                args.bench,
                dataset_root=dataset_root,
                qaconv_split=args.qaconv_split,
                limit=args.limit,
                seed=args.seed,
            )
        )
    print(f"[transfer] bench={args.bench} planned={len(planned)} method={args.method} "
          f"split={args.split_json or 'none'} eval_set={args.eval_set}")

    all_rows: List[Dict[str, Any]] = list(seen.values())
    t0 = time.time()
    for qi, (qid, item) in enumerate(planned, 1):
        if qid in seen:
            continue
        print(f"[{qi}/{len(planned)}] {qid}  ", end="", flush=True)
        try:
            r = run_one(item, run_args, embed_model)
        except Exception as e:
            traceback.print_exc()
            r = {
                "answer": f"(run_one error: {e})",
                "abstain": False,
                "retrieve_time": 0.0,
                "reader_time": 0.0,
                "ingest_time": 0.0,
            }
        question = str(item["question"])
        gold = str(item["answer"])
        pred = str(r.get("answer", ""))
        correct, reason = judge_answer(question, gold, pred)
        f1 = token_f1(pred, gold)
        row = {
            "question_id": qid,
            "question_type": item.get("question_type", args.bench),
            "question": question[:500],
            "gold": gold[:400],
            "pred": pred[:500],
            "correct": correct,
            "judge_reason": reason,
            "f1": f1,
            "abstained": bool(r.get("abstain", False)),
            "route": r.get("route", args.method),
            "callb_tier_size": r.get("callb_tier_size"),
            "callb_threshold": r.get("callb_threshold"),
            "callb_tier_fallback": r.get("callb_tier_fallback"),
            "callb_n_candidates": r.get("callb_n_candidates"),
            "retrieve_time": float(r.get("retrieve_time", 0.0)),
            "reader_time": float(r.get("reader_time", 0.0)),
            "ingest_time": float(r.get("ingest_time", 0.0)),
            "method": args.method,
            "seed": args.seed,
        }
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        seen[qid] = row
        all_rows.append(row)
        acc = sum(x["correct"] for x in all_rows) / len(all_rows)
        print(f"corr={correct} acc={acc:.3f}", flush=True)

    # Reload full file for summary (includes resumed rows)
    final_rows = list(_load_existing(out_path).values())
    summary = summarise(final_rows)
    elapsed = time.time() - t0
    summary_path = out_path.with_suffix(out_path.suffix + ".summary.json")
    payload = {
        "bench": args.bench,
        "args": vars(args),
        "elapsed_sec": elapsed,
        "n_written_this_run": len(all_rows),
        "summary": summary,
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[transfer] summary -> {summary_path}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
