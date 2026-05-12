"""Memora benchmark runner with FAMA scoring.

Loads Memora data (weekly / monthly / quarterly × 10 personas), ingests each
persona's conversation history into the chosen memory system, runs every
evaluation question, and scores every response with the FAMA metric:

    FAMA = max(0, MPA − λ · (1 − FAA))
    λ    = N_forget / (N_presence + N_forget)

where MPA / FAA are the fractions of memory-presence / forgetting-absence
binary criteria the response satisfies, judged independently by a single
LLM (Memora's published protocol uses a 3-judge majority vote; we document
the deviation in IMPLEMENTATION_REPORT.md).

Per-task FAMA is summed across questions and normalised to [0, 100], per
the Memora paper. Per-question rich fields (MPA, FAA, λ, fama, n_*) are
also persisted for risk-coverage curves + cluster-bootstrap CIs.

CPU note: single-process by default; set `--max-parallel-questions 1` (the
default) to keep one in-flight MAAS call at a time. Do NOT raise without
checking server load.

Methods supported (one per `--method`):
    flat        — Path D Flat hybrid-RAG baseline (no claim graph)
    amem        — A-Mem reimpl in `ttmg/amem_base/`
    ttmg_pathd  — Path D's TTMG (claim graph + greedy MCS abstention)
    ttmg_beta   — β: enable_beta + (CRC table optional)

Usage:
    python -m experiments.eval_memora \\
        --memora-root /path/to/Memora/data \\
        --duration weekly \\
        --personas academic_researcher \\
        --method ttmg_beta \\
        --crc-table crc_calibration/locked_table_v1.json \\
        --output results/memora_weekly_ttmg_beta_seed0.json \\
        --seed 0

Output JSON shape:
    {
      "method": "...",
      "duration": "...",
      "personas": [...],
      "seed": 0,
      "per_question": [{"persona": ..., "task": ..., "question_id": ...,
                        "fama": 0.83, "mpa": ..., "faa": ..., "lambda": ...,
                        "score": ..., "group": [...], "route": ...,
                        "answer": "...", "abstain": false}, ...],
      "task_aggregates": {"remembering": <FAMA·100/N>, ...},
      "duration_aggregates": {...},
      "metrics": {"writer_calls": ..., ...},
      "config": {...},
      "elapsed_sec": ...
    }
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# Re-use loader / FAMA scoring helpers from the calibration script.
from scripts.calibrate_crc import (  # noqa: E402  (after sys.path insert)
    _convert_session_to_ttmg,
    _flatten_question_groups,
    _load_memora_persona,
    _question_correct_overall,
)


def _build_system(method: str, args: argparse.Namespace):
    """Construct the appropriate memory system for `method`."""
    if method in ("ttmg_pathd", "ttmg_beta"):
        from ttmg.system import TTMGConfig, TTMGSystem

        cfg = TTMGConfig(
            reader_model=args.reader_model,
            writer_model=args.writer_model or args.reader_model,
            linker_model=args.linker_model or args.reader_model,
            parser_model=args.parser_model or args.reader_model,
        )
        if method == "ttmg_beta":
            cfg = TTMGConfig(
                reader_model=args.reader_model,
                writer_model=args.writer_model or args.reader_model,
                linker_model=args.linker_model or args.reader_model,
                parser_model=args.parser_model or args.reader_model,
                enable_beta=True,
                enable_beta_writer=True,
                enable_beta_linker=not args.beta_no_3call,
                enable_pmi=args.enable_pmi,
                crc_table_path=args.crc_table,
                crc_alpha=args.crc_alpha,
                score_w_h=args.score_w_h,
                score_w_u=args.score_w_u,
                score_w_p=args.score_w_p,
                pmi_scale=args.pmi_scale,
                beta_no_groups=args.beta_no_groups,
                beta_no_canonical_key=args.beta_no_canonical_key,
                beta_no_3call=args.beta_no_3call,
            )
        return TTMGSystem(cfg)
    if method == "flat":
        # Reuse Path D Flat path: TTMG with disable_writer_claims=True is the
        # cheapest in-tree way to get a no-claim-graph hybrid RAG. The reader
        # is given raw turns only.
        from ttmg.system import TTMGConfig, TTMGSystem

        cfg = TTMGConfig(
            reader_model=args.reader_model,
            writer_model=args.writer_model or args.reader_model,
            parser_model=args.parser_model or args.reader_model,
            disable_writer_claims=True,
            disable_contradict=True,
            disable_consistent_subgraph=True,
            enable_abstention=False,
        )
        return TTMGSystem(cfg)
    if method == "amem":
        # Use the project's A-Mem reimpl. We expose only its same `answer()`
        # interface so the eval loop is method-agnostic.
        from ttmg.baseline_amem import AMemBaseline, AMemBaselineConfig  # type: ignore

        cfg = AMemBaselineConfig(
            reader_model=args.reader_model,
            writer_model=args.writer_model or args.reader_model,
        )
        return AMemBaseline(config=cfg)
    raise ValueError(f"unknown method: {method}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memora-root", required=True, type=Path)
    parser.add_argument(
        "--duration", choices=["weekly", "monthly", "quarterly"], default="weekly"
    )
    parser.add_argument("--personas", default="academic_researcher")
    parser.add_argument(
        "--method",
        choices=["flat", "amem", "ttmg_pathd", "ttmg_beta"],
        required=True,
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reader-model", default=os.environ.get("TTMG_MODEL", "deepseek-v3.2"))
    parser.add_argument("--writer-model", default=None)
    parser.add_argument("--linker-model", default=None)
    parser.add_argument("--parser-model", default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--max-questions-per-persona", type=int, default=0)
    parser.add_argument(
        "--max-sessions-per-persona",
        type=int,
        default=0,
        help="Cap conversation ingestion at first N sessions (smoke-test friendly).",
    )
    # β-specific
    parser.add_argument("--crc-table", default=None)
    parser.add_argument("--crc-alpha", type=float, default=0.10)
    parser.add_argument("--score-w-h", type=float, default=0.5)
    parser.add_argument("--score-w-u", type=float, default=0.3)
    parser.add_argument("--score-w-p", type=float, default=0.0)
    parser.add_argument("--pmi-scale", type=float, default=5.0)
    parser.add_argument("--enable-pmi", action="store_true")
    parser.add_argument("--beta-no-groups", action="store_true")
    parser.add_argument("--beta-no-canonical-key", action="store_true")
    parser.add_argument("--beta-no-3call", action="store_true")
    # Concurrency safety: keep at 1 unless server is idle.
    parser.add_argument(
        "--max-parallel-questions",
        type=int,
        default=1,
        help="Sequential by default. Do NOT raise without checking uptime/load.",
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.personas.lower() == "all":
        personas = sorted(
            d.name for d in (args.memora_root / args.duration).iterdir() if d.is_dir()
        )
    else:
        personas = [p.strip() for p in args.personas.split(",") if p.strip()]

    judge_model = args.judge_model or args.reader_model
    t_start = time.time()

    # FAMA aggregation: per-persona sum-then-normalise per task, per Memora paper.
    per_question: List[Dict[str, Any]] = []
    fama_sum_by_task: Dict[str, float] = {"remembering": 0.0, "reasoning": 0.0, "recommending": 0.0}
    n_by_task: Dict[str, int] = {"remembering": 0, "reasoning": 0, "recommending": 0}
    metrics_total: Dict[str, Any] = {}

    for persona in personas:
        print(f"[memora-eval] persona={persona} duration={args.duration} method={args.method}", flush=True)
        sessions, questions_blob = _load_memora_persona(args.memora_root, args.duration, persona)
        if not sessions:
            print(f"  (skip: no sessions for {persona})", flush=True)
            continue

        sys_inst = _build_system(args.method, args)
        # Ingestion (single-pass; no parallelism)
        if args.max_sessions_per_persona > 0:
            sessions = sessions[: args.max_sessions_per_persona]
        sys_inst.ingest_conversation(
            [_convert_session_to_ttmg(s) for s in sessions], verbose=False
        )

        flat = _flatten_question_groups(questions_blob)
        if args.max_questions_per_persona > 0:
            flat = flat[: args.max_questions_per_persona]

        for task, q in flat:
            t0 = time.time()
            try:
                resp = sys_inst.answer(q.get("question") or "")
            except Exception as e:
                resp = {"answer": "", "abstain": True, "_error": str(e), "route": "error"}
            elapsed = time.time() - t0
            ok, fama_fields = _question_correct_overall(
                resp.get("answer") or "", q, judge_model=judge_model
            )
            fama = float(fama_fields.get("fama", 0.0)) if fama_fields else 0.0
            qp_raw = resp.get("query_parse") if isinstance(resp.get("query_parse"), dict) else {}
            # Capture parser output for diagnostics — keeps the rich β-parser
            # fields (claim_key, slot_type, asks_truth_of_fact, _applicable,
            # _fallback_used, _canonical_claim_key_str, etc.).
            qp_compact = {
                "claim_key": qp_raw.get("claim_key"),
                "slot_type": qp_raw.get("slot_type"),
                "asks_truth_of_fact": qp_raw.get("asks_truth_of_fact"),
                "asks_history": qp_raw.get("asks_history"),
                "intent": qp_raw.get("intent"),
                "applicable": qp_raw.get("_applicable"),
                "canonical_key_str": qp_raw.get("_canonical_claim_key_str"),
                "fallback_used": qp_raw.get("_fallback_used"),
            }
            row = {
                "persona": persona,
                "duration": args.duration,
                "task": task,
                "question_id": q.get("question_id"),
                "question_text": q.get("question"),
                "answer": (resp.get("answer") or "")[:1000],
                "abstain": bool(resp.get("abstain", False)),
                "abstain_reason": resp.get("abstain_reason"),
                "route": resp.get("route"),
                "score": float(resp.get("score", 0.0)) if "score" in resp else None,
                "group": list(resp.get("group", [])) if "group" in resp else None,
                "threshold": resp.get("threshold"),
                "vals": resp.get("vals"),
                "value": resp.get("value"),
                "query_parse": qp_compact,
                "answered_correctly": ok,
                "elapsed": elapsed,
                **(fama_fields or {}),
            }
            per_question.append(row)
            if task in fama_sum_by_task:
                fama_sum_by_task[task] += fama
                n_by_task[task] += 1

        # Carry forward metrics
        m = getattr(sys_inst, "metrics", None)
        if isinstance(m, dict):
            for k, v in m.items():
                if isinstance(v, (int, float)):
                    metrics_total[k] = metrics_total.get(k, 0) + v

    # Memora paper aggregation: sum per-question FAMA per task, normalise to [0, 100]
    task_aggregates = {
        t: (100.0 * fama_sum_by_task[t] / n_by_task[t]) if n_by_task[t] > 0 else 0.0
        for t in ("remembering", "reasoning", "recommending")
    }
    duration_total = sum(task_aggregates.values())  # sum of three task scores; max 300

    out = {
        "method": args.method,
        "duration": args.duration,
        "personas": personas,
        "seed": args.seed,
        "per_question": per_question,
        "task_aggregates": task_aggregates,
        "duration_total_max300": duration_total,
        "metrics": metrics_total,
        "config": vars(args),
        "elapsed_sec": time.time() - t_start,
    }
    args.output.write_text(json.dumps(out, indent=2, default=str))
    print(f"[memora-eval] wrote {args.output} | task_aggregates={task_aggregates}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
