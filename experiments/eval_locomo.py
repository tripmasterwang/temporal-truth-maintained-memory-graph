"""Evaluate on LoCoMo (cross-domain test with identical TTMG hyper-parameters).

Each LoCoMo conversation has multiple sessions (`session_1`, `session_2`, ...) and a
list of QA pairs. We ingest every session into a fresh memory per conversation,
then answer each QA by the target method, scoring with an LLM judge and
token-level F1 (the two metrics LoCoMo uses most often in practice).

Usage (same flags as LongMemEval):
  python -m experiments.eval_locomo --method ttmg --output results/locomo_ttmg.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentence_transformers import SentenceTransformer

from ttmg import TTMGConfig, TTMGSystem  # noqa: E402
from ttmg.baseline_amem import AMemBaseline, AMemBaselineConfig  # noqa: E402
from ttmg.maas_client import DEFAULT_MODEL, chat_json  # noqa: E402

from experiments.eval_longmemeval import judge_answer, token_f1  # noqa: E402

LOCOMO_PATH = "/home/workspace/lww/project0412/projects/dataset/locomo-main/data/locomo10.json"


def _locomo_sessions(conv: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    # Sessions are keyed session_1, session_2, ... with session_N_date_time siblings
    c = conv.get("conversation", {})
    keys = sorted([k for k in c.keys() if k.startswith("session_") and not k.endswith("_date_time")],
                  key=lambda k: int(k.split("_")[1]))
    for k in keys:
        ts_key = f"{k}_date_time"
        turns = []
        for t in c.get(k) or []:
            if not isinstance(t, dict):
                continue
            text = t.get("text") or ""
            turns.append({"speaker": t.get("speaker", "user"), "text": text})
        out.append({"session_id": k, "session_ts": c.get(ts_key), "turns": turns})
    return out


def _iter_qas(conv: Dict[str, Any]) -> List[Dict[str, Any]]:
    return conv.get("qa") or []


def run_one(
    conv: Dict[str, Any],
    method: str,
    embed_model: SentenceTransformer,
    max_sessions: Optional[int],
    writer_model: str,
    reader_model: str,
    parser_model: str,
    max_qa: Optional[int] = None,
) -> List[Dict[str, Any]]:
    sessions = _locomo_sessions(conv)
    if max_sessions is not None:
        sessions = sessions[:max_sessions]
    if method == "ttmg":
        cfg = TTMGConfig(
            writer_model=writer_model, linker_model=writer_model,
            parser_model=parser_model, reader_model=reader_model,
            batch_writer_per_session=True, top_keep=3,
        )
        sys_obj = TTMGSystem(cfg, embed_model=embed_model)
    elif method == "amem":
        cfg = AMemBaselineConfig(writer_model=writer_model, reader_model=reader_model,
                                 k=8, use_analysis=True)
        sys_obj = AMemBaseline(cfg, embed_model=embed_model)
    elif method == "amem_flat":
        cfg = AMemBaselineConfig(writer_model=writer_model, reader_model=reader_model,
                                 k=8, use_analysis=False)
        sys_obj = AMemBaseline(cfg, embed_model=embed_model)
    else:
        raise ValueError(method)
    t0 = time.time()
    sys_obj.ingest_conversation(sessions, max_sessions=None)
    t_ingest = time.time() - t0
    print(f"  [locomo] ingested {len(sessions)} sessions in {t_ingest:.1f}s", flush=True)

    rows: List[Dict[str, Any]] = []
    qas = _iter_qas(conv)
    if max_qa is not None:
        qas = qas[:max_qa]
    for qi, qa in enumerate(qas, 1):
        q = qa.get("question") or ""
        gold = str(qa.get("answer") or "")
        try:
            ans = sys_obj.answer(q)
            pred = ans.get("answer", "")
        except Exception as e:  # noqa: BLE001
            pred = ""
        correct, reason = judge_answer(q, gold, pred, abstention=False)
        f1 = token_f1(pred, gold)
        rows.append({
            "sample_id": conv.get("sample_id"),
            "category": qa.get("category"),
            "question": q, "gold": gold, "pred": pred,
            "correct": correct, "f1": f1, "judge_reason": reason,
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["ttmg", "amem", "amem_flat"], required=True)
    ap.add_argument("--limit-convs", type=int, default=3)
    ap.add_argument("--max-sessions", type=int, default=5)
    ap.add_argument("--max-qa-per-conv", type=int, default=20)
    ap.add_argument("--writer-model", default=DEFAULT_MODEL)
    ap.add_argument("--reader-model", default=DEFAULT_MODEL)
    ap.add_argument("--parser-model", default=DEFAULT_MODEL)
    ap.add_argument("--embed-model", default="all-MiniLM-L6-v2")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    with open(LOCOMO_PATH) as fh:
        data = json.load(fh)

    convs = data[: args.limit_convs]
    embed = SentenceTransformer(args.embed_model)

    all_rows: List[Dict[str, Any]] = []
    for ci, conv in enumerate(convs, 1):
        print(f"[locomo] conv {ci}/{len(convs)} sample_id={conv.get('sample_id')}", flush=True)
        try:
            rows = run_one(
                conv, method=args.method, embed_model=embed,
                max_sessions=args.max_sessions,
                writer_model=args.writer_model, reader_model=args.reader_model,
                parser_model=args.parser_model, max_qa=args.max_qa_per_conv,
            )
        except Exception as e:
            traceback.print_exc()
            rows = []
        all_rows.extend(rows)

    def _avg(xs):
        return sum(xs) / len(xs) if xs else 0.0

    summary = {
        "n": len(all_rows),
        "accuracy": _avg([r["correct"] for r in all_rows]),
        "f1": _avg([r["f1"] for r in all_rows]),
    }
    payload = {"args": vars(args), "summary": summary, "rows": all_rows}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"[locomo] wrote {out}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
