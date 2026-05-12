"""Evaluate A-Mem baseline and TTMG on LongMemEval_S.

Reads the LongMemEval_S json, selects a stratified subset (or all), ingests
each question's haystack sessions into a fresh memory, asks the question,
and scores the answer with an LLM judge (identical to LongMemEval paper's
`evaluate_qa.py`-style judge but routed through MAAS).

Usage:
  python -m experiments.eval_longmemeval \
      --method ttmg \
      --limit 30 \
      --stratify \
      --output results/pilot_ttmg.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentence_transformers import SentenceTransformer

from ttmg import TTMGConfig, TTMGSystem  # noqa: E402
from ttmg.baseline_amem import AMemBaseline, AMemBaselineConfig  # noqa: E402
from ttmg.maas_client import DEFAULT_MODEL, chat_json  # noqa: E402

LME_PATH = "/home/workspace/lww/project0412/projects/dataset/LongMemEval-main/data/longmemeval_s.json"


_JUDGE_SYS = (
    "You are a strict grader. Decide whether a model's answer correctly "
    "answers the question, given the reference answer. Respond in JSON only."
)

_JUDGE_USER_TMPL = """Question: {question}
Reference answer: {gold}
Model answer: {pred}

For abstention questions (the reference says the user did NOT mention something), the model answer is correct iff it also abstains or explicitly says the information is not present.

Grade:
- "correct": 0 or 1.
- "reason": short justification (<=20 words).

Return JSON: {{"correct": 0|1, "reason": "..."}}"""


def judge_answer(question: str, gold: str, pred: str, *, abstention: bool) -> Tuple[int, str]:
    prompt = _JUDGE_USER_TMPL.format(question=question, gold=gold, pred=pred)
    payload = chat_json(
        prompt,
        system=_JUDGE_SYS,
        default={"correct": 0, "reason": "judge_failed"},
        temperature=0.0,
        max_tokens=120,
    )
    try:
        v = int(payload.get("correct", 0))
    except Exception:
        v = 0
    return (1 if v else 0), str(payload.get("reason", ""))[:200]


def token_f1(pred: str, gold: str) -> float:
    """Simple word-level F1 used as a secondary metric."""
    import re

    def tok(s: str) -> List[str]:
        return [w for w in re.findall(r"[A-Za-z0-9]+", s.lower()) if w]

    p = tok(pred)
    g = tok(gold)
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    common: Dict[str, int] = {}
    pc: Dict[str, int] = defaultdict(int)
    gc: Dict[str, int] = defaultdict(int)
    for w in p:
        pc[w] += 1
    for w in g:
        gc[w] += 1
    overlap = sum(min(pc[w], gc[w]) for w in pc if w in gc)
    if overlap == 0:
        return 0.0
    prec = overlap / len(p)
    rec = overlap / len(g)
    return 2 * prec * rec / (prec + rec)


def load_dataset(
    limit: Optional[int] = None,
    stratify: bool = True,
    types: Optional[List[str]] = None,
    seed: int = 0,
    include_abs: bool = True,
    only_abs: bool = False,
) -> List[Dict[str, Any]]:
    with open(LME_PATH, "r") as fh:
        data = json.load(fh)
    if only_abs:
        data = [d for d in data if "_abs" in d["question_id"]]
    elif not include_abs:
        data = [d for d in data if "_abs" not in d["question_id"]]
    if types:
        data = [d for d in data if d["question_type"] in types]
    if limit is None or limit >= len(data):
        return data
    if not stratify:
        rng = random.Random(seed)
        rng.shuffle(data)
        return data[:limit]
    # Stratified: proportional per question_type
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for d in data:
        buckets[d["question_type"]].append(d)
    rng = random.Random(seed)
    for k in buckets:
        rng.shuffle(buckets[k])
    total = len(data)
    out: List[Dict[str, Any]] = []
    for qt, items in buckets.items():
        share = max(1, round(limit * len(items) / total))
        out.extend(items[:share])
    rng.shuffle(out)
    return out[:limit]


def convert_sessions(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    sessions: List[Dict[str, Any]] = []
    for sid, sts, sess in zip(
        item["haystack_session_ids"], item["haystack_dates"], item["haystack_sessions"]
    ):
        turns = []
        for turn in sess:
            if not isinstance(turn, dict):
                continue
            txt = turn.get("content") or ""
            role = turn.get("role") or "user"
            turns.append({"speaker": role, "text": txt})
        sessions.append({"session_id": sid, "session_ts": sts, "turns": turns})
    return sessions


def run_one(
    item: Dict[str, Any],
    method: str,
    embed_model: SentenceTransformer,
    max_sessions: Optional[int],
    writer_model: str,
    reader_model: str,
    parser_model: str,
    ablation_flags: Dict[str, bool],
) -> Dict[str, Any]:
    sessions = convert_sessions(item)
    if max_sessions is not None:
        # Always keep answer sessions; fill the rest with early haystack
        answer_ids = set(item.get("answer_session_ids", []) or [])
        core = [s for s in sessions if s["session_id"] in answer_ids]
        rest = [s for s in sessions if s["session_id"] not in answer_ids]
        keep = core + rest[: max(0, max_sessions - len(core))]
        sessions = keep[:max_sessions]
    question = str(item["question"])
    gold = str(item["answer"])  # LongMemEval has 32/500 int answers (years/counts)
    is_abs = "_abs" in item["question_id"]
    t_ing0 = time.time()
    if method == "ttmg":
        cfg = TTMGConfig(
            writer_model=writer_model,
            linker_model=writer_model,
            parser_model=parser_model,
            reader_model=reader_model,
            batch_writer_per_session=True,
            linker_min_similarity=0.55,
            linker_candidate_k=4,
            knn_k_read=8,
            top_keep=3,
            hard_threshold=0.7,
            **ablation_flags,
        )
        sys_obj = TTMGSystem(cfg, embed_model=embed_model)
    elif method == "amem":
        cfg = AMemBaselineConfig(
            writer_model=writer_model, reader_model=reader_model, k=8, use_analysis=True
        )
        sys_obj = AMemBaseline(cfg, embed_model=embed_model)
    elif method == "amem_flat":
        cfg = AMemBaselineConfig(
            writer_model=writer_model, reader_model=reader_model, k=8, use_analysis=False
        )
        sys_obj = AMemBaseline(cfg, embed_model=embed_model)
    elif method == "ttmg_beta":
        # Pivot β v2: enable_beta + beta writer + 3-call linker + applicability gate
        # + canonical-key fetch + all-optima MWIS + value-level decision rule + CRC
        # threshold (when crc_table_path is provided).
        beta_overrides = {
            k: v for k, v in ablation_flags.items()
            if k in ("crc_table_path", "crc_alpha", "score_w_h", "score_w_u",
                     "score_w_p", "pmi_scale", "pmi_model", "enable_pmi",
                     "beta_no_groups", "beta_no_canonical_key", "beta_no_3call")
        }
        # Path-D ablation flags filtered out for β (they don't apply to β path).
        cfg = TTMGConfig(
            writer_model=writer_model,
            linker_model=writer_model,
            parser_model=parser_model,
            reader_model=reader_model,
            batch_writer_per_session=True,
            linker_min_similarity=0.55,
            linker_candidate_k=4,
            knn_k_read=8,
            top_keep=3,
            hard_threshold=0.7,
            enable_beta=True,
            enable_beta_writer=True,
            enable_beta_linker=True,
            **beta_overrides,
        )
        sys_obj = TTMGSystem(cfg, embed_model=embed_model)
    else:
        raise ValueError(f"unknown method {method}")
    print(f"  [ingest] {len(sessions)} sessions, starting...", flush=True)
    verbose_ing = method == "ttmg"
    if method == "ttmg":
        sys_obj.ingest_conversation(sessions, max_sessions=None, verbose=verbose_ing)
    else:
        sys_obj.ingest_conversation(sessions, max_sessions=None)
    t_ingest = time.time() - t_ing0
    print(f"  [ingest] done in {t_ingest:.1f}s", flush=True)

    t_ans0 = time.time()
    try:
        ans = sys_obj.answer(question)
    except Exception as e:
        ans = {"answer": f"(error: {e})", "abstain": False, "retrieve_time": 0.0, "reader_time": 0.0}
    t_answer = time.time() - t_ans0

    pred = str(ans.get("answer", ""))
    correct, reason = judge_answer(question, gold, pred, abstention=is_abs)
    f1 = token_f1(pred, gold)

    return {
        "question_id": item["question_id"],
        "question_type": item["question_type"],
        "is_abstention": is_abs,
        "question": question,
        "gold": gold,
        "pred": pred,
        "correct": correct,
        "judge_reason": reason,
        "f1": f1,
        "abstained": bool(ans.get("abstain", False)),
        "retrieve_time": float(ans.get("retrieve_time", 0.0)),
        "reader_time": float(ans.get("reader_time", 0.0)),
        "ingest_time": t_ingest,
        "answer_time": t_answer,
        "metrics": getattr(sys_obj, "metrics", {}),
        "n_sessions": len(sessions),
    }


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    def _avg(xs):
        return sum(xs) / len(xs) if xs else 0.0

    out: Dict[str, Any] = {
        "n": len(rows),
        "accuracy": _avg([r["correct"] for r in rows]),
        "f1": _avg([r["f1"] for r in rows]),
        "abstain_rate": _avg([1.0 if r["abstained"] else 0.0 for r in rows]),
        "ingest_time_mean": _avg([r["ingest_time"] for r in rows]),
        "answer_time_mean": _avg([r["answer_time"] for r in rows]),
    }
    by_type = defaultdict(list)
    for r in rows:
        by_type[r["question_type"]].append(r)
    out["by_type"] = {
        qt: {
            "n": len(rs),
            "accuracy": _avg([r["correct"] for r in rs]),
            "f1": _avg([r["f1"] for r in rs]),
            "abstain_rate": _avg([1.0 if r["abstained"] else 0.0 for r in rs]),
        }
        for qt, rs in by_type.items()
    }
    # Abstention metrics: precision/recall over the `_abs` subset
    abs_rows = [r for r in rows if r["is_abstention"]]
    if abs_rows:
        # Treat abstention as positive class
        tp = sum(1 for r in abs_rows if r["abstained"] or r["correct"])
        out["abstention_correct"] = tp / len(abs_rows)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["ttmg", "amem", "amem_flat", "ttmg_beta"], required=True)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--stratify", action="store_true")
    ap.add_argument("--types", nargs="*", default=None)
    ap.add_argument("--only-abs", action="store_true")
    ap.add_argument("--include-abs", action="store_true", default=True)
    ap.add_argument("--max-sessions", type=int, default=10)
    ap.add_argument("--writer-model", default=DEFAULT_MODEL)
    ap.add_argument("--reader-model", default=DEFAULT_MODEL)
    ap.add_argument("--parser-model", default=DEFAULT_MODEL)
    ap.add_argument("--embed-model", default="all-MiniLM-L6-v2")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output", required=True)
    ap.add_argument("--progress-every", type=int, default=1)
    # Ablation flags (Path D)
    ap.add_argument("--disable-temporal", action="store_true")
    ap.add_argument("--disable-contradict", action="store_true")
    ap.add_argument("--disable-consistent-subgraph", action="store_true")
    ap.add_argument("--disable-supersede-flag", action="store_true")
    ap.add_argument("--disable-writer-claims", action="store_true")
    ap.add_argument("--disable-abstention", action="store_true")
    # β-specific knobs
    ap.add_argument("--crc-table-path", default=None)
    ap.add_argument("--crc-alpha", type=float, default=0.10)
    ap.add_argument("--score-w-h", type=float, default=0.5)
    ap.add_argument("--score-w-u", type=float, default=0.3)
    ap.add_argument("--score-w-p", type=float, default=0.0)  # 0 until PMI verified
    ap.add_argument("--pmi-scale", type=float, default=5.0)
    ap.add_argument("--pmi-model", default=None)
    ap.add_argument("--enable-pmi", action="store_true")
    ap.add_argument("--beta-no-groups", action="store_true")
    ap.add_argument("--beta-no-canonical-key", action="store_true")
    ap.add_argument("--beta-no-3call", action="store_true")
    args = ap.parse_args()

    ablation_flags: Dict[str, Any] = dict(
        disable_temporal=args.disable_temporal,
        disable_contradict=args.disable_contradict,
        disable_consistent_subgraph=args.disable_consistent_subgraph,
        disable_supersede_flag=args.disable_supersede_flag,
        disable_writer_claims=args.disable_writer_claims,
        enable_abstention=not args.disable_abstention,
        # β-specific (consumed only when method=ttmg_beta)
        crc_table_path=args.crc_table_path,
        crc_alpha=args.crc_alpha,
        score_w_h=args.score_w_h,
        score_w_u=args.score_w_u,
        score_w_p=args.score_w_p,
        pmi_scale=args.pmi_scale,
        pmi_model=args.pmi_model,
        enable_pmi=args.enable_pmi,
        beta_no_groups=args.beta_no_groups,
        beta_no_canonical_key=args.beta_no_canonical_key,
        beta_no_3call=args.beta_no_3call,
    )

    items = load_dataset(
        limit=args.limit,
        stratify=args.stratify,
        types=args.types,
        seed=args.seed,
        include_abs=args.include_abs,
        only_abs=args.only_abs,
    )
    print(f"[eval] method={args.method} items={len(items)} max_sessions={args.max_sessions}")

    print("[eval] loading embedding model...")
    embed = SentenceTransformer(args.embed_model)

    rows: List[Dict[str, Any]] = []
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = out_path.with_suffix(out_path.suffix + ".part")
    t_start = time.time()
    for i, item in enumerate(items, 1):
        try:
            row = run_one(
                item,
                method=args.method,
                embed_model=embed,
                max_sessions=args.max_sessions,
                writer_model=args.writer_model,
                reader_model=args.reader_model,
                parser_model=args.parser_model,
                ablation_flags=ablation_flags,
            )
        except Exception as e:
            traceback.print_exc()
            row = {
                "question_id": item["question_id"],
                "question_type": item["question_type"],
                "is_abstention": "_abs" in item["question_id"],
                "error": str(e),
                "correct": 0,
                "f1": 0.0,
                "abstained": False,
                "ingest_time": 0.0,
                "answer_time": 0.0,
                "retrieve_time": 0.0,
                "reader_time": 0.0,
                "metrics": {},
                "pred": "",
                "gold": item["answer"],
                "n_sessions": 0,
            }
        rows.append(row)
        if i % args.progress_every == 0:
            with open(part_path, "w") as fh:
                json.dump({"args": vars(args), "rows": rows}, fh, indent=2, ensure_ascii=False)
            acc = sum(r["correct"] for r in rows) / len(rows)
            print(
                f"[{i}/{len(items)}] {row['question_type']:<26s} corr={row['correct']} "
                f"ingest={row['ingest_time']:.1f}s ans={row['answer_time']:.1f}s running_acc={acc:.3f}"
            )
    summary = summarise(rows)
    elapsed = time.time() - t_start
    payload = {
        "args": vars(args),
        "n_items": len(items),
        "elapsed_sec": elapsed,
        "summary": summary,
        "rows": rows,
    }
    with open(out_path, "w") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print(f"[eval] wrote {out_path}")
    print("[eval] summary:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
