"""Evaluate on LoCoMo (cross-domain test with identical TTMG hyper-parameters).

Each LoCoMo conversation has multiple sessions (`session_1`, `session_2`, ...) and a
list of QA pairs. We ingest every session into a fresh memory per conversation,
then answer each QA by the target method, scoring with an LLM judge and
token-level F1 (the two metrics LoCoMo uses most often in practice).

Single-session mode (--single-session-only):
  Filter QAs to those whose evidence comes entirely from a single session.
  For each such QA, ingest ONLY that one session — directly comparable to
  LongMemEval-S single-session-user questions.

Usage:
  python -m experiments.eval_locomo --method ttmg --output results/locomo_ttmg.json
  python -m experiments.eval_locomo --method callb --single-session-only \\
      --callb-model results/lb_mlp_ssu.json --callb-crc results/lb_crc_ssu.json \\
      --callb-alpha 0.20 --output results/locomo_callb_ssu.json
"""

from __future__ import annotations

import argparse
import json
import re
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

from ttmg import TTMGConfig, TTMGSystem
from ttmg.baseline_amem import AMemBaseline, AMemBaselineConfig
from ttmg.maas_client import DEFAULT_MODEL, chat_json

from experiments.eval_longmemeval import judge_answer, token_f1

LOCOMO_PATH = "/home/workspace/lww/project0412/projects/dataset/locomo-main/data/locomo10.json"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _locomo_sessions(conv: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return {session_key: {session_id, session_ts, turns}} for all sessions."""
    c = conv.get("conversation", {})
    keys = sorted(
        [k for k in c.keys() if k.startswith("session_") and not k.endswith("_date_time")],
        key=lambda k: int(k.split("_")[1]),
    )
    result = {}
    for k in keys:
        ts_key = f"{k}_date_time"
        turns = []
        for t in c.get(k) or []:
            if not isinstance(t, dict):
                continue
            text = t.get("text") or ""
            turns.append({"speaker": t.get("speaker", "user"), "text": text})
        result[k] = {"session_id": k, "session_ts": c.get(ts_key), "turns": turns}
    return result


def _answer_session_key(qa: Dict[str, Any]) -> Optional[str]:
    """Return the session key if all evidence references a single session, else None.

    LoCoMo evidence format: ['D{n}:{turn}', ...] where D{n} maps to session_{n}.
    """
    ev = qa.get("evidence") or []
    sess_ids: set = set()
    for e in ev:
        m = re.match(r"D(\d+):", e)
        if m:
            sess_ids.add(f"session_{m.group(1)}")
    if len(sess_ids) == 1:
        return sess_ids.pop()
    return None


def _iter_qas(conv: Dict[str, Any]) -> List[Dict[str, Any]]:
    return conv.get("qa") or []


# ---------------------------------------------------------------------------
# System builders
# ---------------------------------------------------------------------------

def _build_system(
    sessions: List[Dict[str, Any]],
    method: str,
    embed_model: SentenceTransformer,
    writer_model: str,
    reader_model: str,
    parser_model: str,
    callb_model_path: str = "",
    callb_crc_path: str = "",
    callb_alpha: float = 0.20,
) -> Any:
    if method in ("ttmg", "callb", "no_crc"):
        cfg = TTMGConfig(
            writer_model=writer_model,
            linker_model=writer_model,
            parser_model=parser_model,
            reader_model=reader_model,
            batch_writer_per_session=True,
            top_keep=3,
            raw_turn_fallback=True,
            enable_callb=(method == "callb"),
            callb_model_path=callb_model_path if method == "callb" else "",
            callb_crc_path=callb_crc_path if method == "callb" else "",
            callb_alpha=callb_alpha,
            callb_k_per_substrate=10,
            callb_max_candidates=30,
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
    sys_obj.ingest_conversation(sessions)
    return sys_obj


# ---------------------------------------------------------------------------
# Multi-session mode: ingest all sessions, evaluate all QAs
# ---------------------------------------------------------------------------

def run_one_multisession(
    conv: Dict[str, Any],
    method: str,
    embed_model: SentenceTransformer,
    max_sessions: Optional[int],
    writer_model: str,
    reader_model: str,
    parser_model: str,
    max_qa: Optional[int] = None,
    callb_model_path: str = "",
    callb_crc_path: str = "",
    callb_alpha: float = 0.20,
) -> List[Dict[str, Any]]:
    sessions_dict = _locomo_sessions(conv)
    sessions = list(sessions_dict.values())
    if max_sessions is not None:
        sessions = sessions[:max_sessions]

    t0 = time.time()
    sys_obj = _build_system(sessions, method, embed_model, writer_model, reader_model,
                            parser_model, callb_model_path, callb_crc_path, callb_alpha)
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
            abstained = bool(ans.get("abstain", False))
        except Exception:
            pred = ""
            abstained = False
        correct, reason = judge_answer(q, gold, pred, abstention=False)
        f1 = token_f1(pred, gold)
        rows.append({
            "sample_id": conv.get("sample_id"),
            "category": qa.get("category"),
            "answer_session": _answer_session_key(qa),
            "question": q, "gold": gold, "pred": pred,
            "correct": correct, "f1": f1, "judge_reason": reason,
            "abstained": abstained,
            "mode": "multi_session",
        })
    return rows


# ---------------------------------------------------------------------------
# Single-session mode: per-QA fresh system from its single evidence session
# ---------------------------------------------------------------------------

def run_one_singlesession(
    conv: Dict[str, Any],
    method: str,
    embed_model: SentenceTransformer,
    writer_model: str,
    reader_model: str,
    parser_model: str,
    max_qa: Optional[int] = None,
    callb_model_path: str = "",
    callb_crc_path: str = "",
    callb_alpha: float = 0.20,
) -> List[Dict[str, Any]]:
    """For each QA resolvable from a single session, ingest only that session."""
    sessions_dict = _locomo_sessions(conv)
    qas = _iter_qas(conv)
    if max_qa is not None:
        qas = qas[:max_qa]

    # Group QAs by answer session key (skip multi-session QAs)
    by_sess: Dict[str, List[Tuple[int, Dict[str, Any]]]] = defaultdict(list)
    skipped = 0
    for qi, qa in enumerate(qas):
        sk = _answer_session_key(qa)
        if sk is None:
            skipped += 1
            continue
        by_sess[sk].append((qi, qa))

    print(f"  [locomo-ssu] {len(qas)} QAs: {sum(len(v) for v in by_sess.values())} single-session, "
          f"{skipped} multi-session (skipped)", flush=True)

    rows: List[Dict[str, Any]] = []
    for sk, qa_list in sorted(by_sess.items()):
        sess_info = sessions_dict.get(sk)
        if sess_info is None:
            print(f"  [locomo-ssu] WARN: session {sk} not in conversation, skipping {len(qa_list)} QAs")
            continue

        t0 = time.time()
        try:
            sys_obj = _build_system([sess_info], method, embed_model, writer_model,
                                    reader_model, parser_model,
                                    callb_model_path, callb_crc_path, callb_alpha)
        except Exception:
            traceback.print_exc()
            continue
        t_ingest = time.time() - t0
        print(f"  [locomo-ssu] {sk}: ingested 1 session in {t_ingest:.1f}s, "
              f"answering {len(qa_list)} QAs", flush=True)

        for qi, qa in qa_list:
            q = qa.get("question") or ""
            gold = str(qa.get("answer") or "")
            try:
                ans = sys_obj.answer(q)
                pred = ans.get("answer", "")
                abstained = bool(ans.get("abstain", False))
            except Exception:
                pred = ""
                abstained = False
            correct, reason = judge_answer(q, gold, pred, abstention=False)
            f1 = token_f1(pred, gold)
            rows.append({
                "sample_id": conv.get("sample_id"),
                "category": qa.get("category"),
                "answer_session": sk,
                "question": q, "gold": gold, "pred": pred,
                "correct": correct, "f1": f1, "judge_reason": reason,
                "abstained": abstained,
                "mode": "single_session",
            })
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

METHODS = ("ttmg", "callb", "amem", "amem_flat")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--method", choices=METHODS, required=True)
    ap.add_argument("--locomo-data", default=LOCOMO_PATH)
    ap.add_argument("--limit-convs", type=int, default=3)
    ap.add_argument("--max-sessions", type=int, default=5,
                    help="Max sessions to ingest per conversation (multi-session mode only).")
    ap.add_argument("--max-qa-per-conv", type=int, default=None)
    ap.add_argument("--single-session-only", action="store_true",
                    help="Filter QAs to single-session-resolvable; ingest 1 session per QA group.")
    # CalLB args
    ap.add_argument("--callb-model", default="results/lb_mlp_ssu.json")
    ap.add_argument("--callb-crc", default="results/lb_crc_ssu.json")
    ap.add_argument("--callb-alpha", type=float, default=0.20)
    # LLM models
    ap.add_argument("--writer-model", default=DEFAULT_MODEL)
    ap.add_argument("--reader-model", default=DEFAULT_MODEL)
    ap.add_argument("--parser-model", default=DEFAULT_MODEL)
    ap.add_argument("--embed-model", default="all-MiniLM-L6-v2")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    with open(args.locomo_data) as fh:
        data = json.load(fh)

    convs = data[: args.limit_convs]
    embed = SentenceTransformer(args.embed_model)

    all_rows: List[Dict[str, Any]] = []
    for ci, conv in enumerate(convs, 1):
        print(f"[locomo] conv {ci}/{len(convs)} sample_id={conv.get('sample_id')}", flush=True)
        try:
            if args.single_session_only:
                rows = run_one_singlesession(
                    conv, method=args.method, embed_model=embed,
                    writer_model=args.writer_model, reader_model=args.reader_model,
                    parser_model=args.parser_model, max_qa=args.max_qa_per_conv,
                    callb_model_path=args.callb_model, callb_crc_path=args.callb_crc,
                    callb_alpha=args.callb_alpha,
                )
            else:
                rows = run_one_multisession(
                    conv, method=args.method, embed_model=embed,
                    max_sessions=args.max_sessions,
                    writer_model=args.writer_model, reader_model=args.reader_model,
                    parser_model=args.parser_model, max_qa=args.max_qa_per_conv,
                    callb_model_path=args.callb_model, callb_crc_path=args.callb_crc,
                    callb_alpha=args.callb_alpha,
                )
        except Exception:
            traceback.print_exc()
            rows = []
        all_rows.extend(rows)

    def _avg(xs):
        return sum(xs) / len(xs) if xs else 0.0

    summary = {
        "n": len(all_rows),
        "accuracy": _avg([r["correct"] for r in all_rows]),
        "f1": _avg([r["f1"] for r in all_rows]),
        "abstain_rate": _avg([int(r.get("abstained", False)) for r in all_rows]),
        "mode": "single_session" if args.single_session_only else "multi_session",
    }
    payload = {"args": vars(args), "summary": summary, "rows": all_rows}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"[locomo] wrote {out}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
