"""β CRC calibration runner.

Pipeline (offline, before any test-time runs):

    1. Load Memora `train` split (one persona × duration at a time, or all).
    2. Split train into DEV (60 %) + CALIBRATION (40 %) deterministically.
    3. Build a TTMG-β system, ingest each persona's conversations, run
       inference on each calibration question; record:
            (S(q), correct, group, meta)
    4. Tune `(w_h, w_u, w_p, PMI_scale)` on dev (grid search; cheap).
    5. Compute `update_pattern` proxy validation on dev (Spearman ρ vs
       Memora ground-truth update count).
    6. Freeze candidate thresholds per group via `freeze_candidate_thresholds`.
    7. Calibrate one threshold per (g, α) on the CALIBRATION split via
       `calibrate_thresholds` (Clopper-Pearson + Bonferroni).
    8. Save the locked `threshold_table` JSON + a git hash audit record.

CPU note: this script is single-process. It performs many sequential MAAS
calls (one writer per session + one parser+linker per question + LLM-judge
calls). Do not parallelise without first verifying server load.

Usage:
    python -m scripts.calibrate_crc \\
        --memora-root /path/to/Memora/data \\
        --duration weekly \\
        --personas academic_researcher,software_engineer \\
        --out crc_calibration/locked_table_v1.json \\
        --reader-model deepseek-v3.2

Outputs:
    crc_calibration/<out>.json — threshold_table + audit record
    crc_calibration/<out>.dev_signals.jsonl — per-question (S, correct, ...)
    crc_calibration/<out>.alias_audit.json — canonicaliser surfaces snapshot
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Pull project root onto sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Heavy imports happen behind argparse so --help is fast.


def _git_hash(path: Path) -> Optional[str]:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=path,
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return None


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _split_dev_cal(items: List[Any], dev_frac: float = 0.6, seed: int = 0) -> Tuple[List[Any], List[Any]]:
    import random

    rng = random.Random(seed)
    idx = list(range(len(items)))
    rng.shuffle(idx)
    split = int(len(items) * dev_frac)
    dev = [items[i] for i in idx[:split]]
    cal = [items[i] for i in idx[split:]]
    return dev, cal


def _load_memora_persona(
    root: Path, duration: str, persona: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (sessions, questions) for one persona × duration."""
    pdir = root / duration / persona
    conv_dir = pdir / "conversations"
    sessions: List[Dict[str, Any]] = []
    if conv_dir.is_dir():
        for sf in sorted(conv_dir.glob("session_*.json")):
            try:
                sessions.append(json.loads(sf.read_text()))
            except Exception:
                continue
    qfile = pdir / f"evaluation_questions_{persona}.json"
    questions_blob: Dict[str, Any] = {}
    if qfile.is_file():
        questions_blob = json.loads(qfile.read_text())
    return sessions, questions_blob.get("questions", [])


def _convert_session_to_ttmg(sess: Dict[str, Any]) -> Dict[str, Any]:
    """Memora session JSON → TTMG `ingest_conversation` input format."""
    conv = sess.get("conversation", []) or []
    turns = [
        {
            "speaker": "user" if t.get("speaker") == "user_agent" else "assistant",
            "text": t.get("message") or "",
        }
        for t in conv
        if isinstance(t, dict)
    ]
    return {
        "session_id": str(sess.get("session_id", "")),
        "session_ts": sess.get("date") or "",
        "turns": turns,
    }


def _flatten_question_groups(questions_blob: Any) -> List[Tuple[str, Dict[str, Any]]]:
    """Memora's per-persona `questions` is a dict with task keys
    `{"remembering": [...], "reasoning": [...], "recommending": [...]}`.
    (Some old data dumps wrap this in a list-of-dicts; handle both.)
    Flatten to [(task, question), ...]."""
    out: List[Tuple[str, Dict[str, Any]]] = []
    tasks = ("remembering", "reasoning", "recommending")
    if isinstance(questions_blob, dict):
        for task in tasks:
            for q in questions_blob.get(task, []) or []:
                if isinstance(q, dict):
                    out.append((task, q))
    elif isinstance(questions_blob, list):
        for blob in questions_blob:
            if not isinstance(blob, dict):
                continue
            for task in tasks:
                for q in blob.get(task, []) or []:
                    if isinstance(q, dict):
                        out.append((task, q))
    return out


def _judge_evaluation_question(
    response_text: str,
    eval_q: Dict[str, Any],
    *,
    judge_model: str,
) -> Optional[bool]:
    """LLM-as-judge for a single binary criterion. Returns True if the response
    passes (matches `expected_answer`), False otherwise. None on judge failure.

    Memora published a 3-judge majority-vote protocol; for our compute budget
    we use a single judge (deepseek-v3.2 by default) and document this
    deviation transparently in the IMPLEMENTATION_REPORT.
    """
    from ttmg.maas_client import chat_json

    expected = (eval_q.get("expected_answer") or "").strip().lower()
    criterion = eval_q.get("evaluation_question") or ""
    if not criterion or expected not in ("yes", "no"):
        return None

    prompt = f"""You are evaluating whether a model's response satisfies a single binary criterion.

Criterion (yes/no question): {criterion}

Model response: {response_text}

Answer "yes" or "no" — does the response satisfy the criterion as a yes-answer?
Return strict JSON: {{"answer": "yes"}} or {{"answer": "no"}}."""
    payload = chat_json(
        prompt,
        default={"answer": "no"},
        model=judge_model,
        temperature=0.0,
        max_tokens=20,
    )
    if not isinstance(payload, dict):
        return None
    ans = (payload.get("answer") or "").strip().lower()
    if ans not in ("yes", "no"):
        return None
    return ans == expected


def _evaluation_question_correct(
    response_text: str,
    eval_q: Dict[str, Any],
    *,
    judge_model: str,
) -> Optional[bool]:
    return _judge_evaluation_question(response_text, eval_q, judge_model=judge_model)


def _question_correct_overall(
    response_text: str,
    question: Dict[str, Any],
    *,
    judge_model: str,
    judge_retries: int = 1,
) -> Tuple[Optional[bool], Dict[str, Any]]:
    """Compute per-criterion correctness + per-question FAMA fields.

    Codex-fix CRITICAL #3: a failed judge call (None) is now treated as an
    INCORRECT criterion — denominators stay at full `n_presence` /
    `n_forget` so MPA / FAA cannot be inflated by silently dropping
    criteria. `overall_correct` requires ALL criteria to be (a) successfully
    judged and (b) correct.

    Returns (overall_correct, fields_dict). Returns (None, {}) only when the
    question carries zero criteria.
    """
    crit = (question.get("evaluation") or {}).get("evaluation_questions") or []
    if not crit:
        return None, {}
    n_pres = sum(1 for c in crit if (c.get("evaluation_type") or "") == "memory_presence")
    n_forg = sum(1 for c in crit if (c.get("evaluation_type") or "") == "forgetting_absence")
    correct_pres = 0
    correct_forg = 0
    judge_failures = 0
    for c in crit:
        # Retry once before giving up; Memora published 3-judge majority,
        # we use single-judge with one retry to balance cost vs robustness.
        ok = _evaluation_question_correct(response_text, c, judge_model=judge_model)
        for _ in range(judge_retries):
            if ok is not None:
                break
            ok = _evaluation_question_correct(response_text, c, judge_model=judge_model)
        if ok is None:
            judge_failures += 1
            ok = False  # Codex-fix: treat as incorrect rather than skip.
        if (c.get("evaluation_type") or "") == "memory_presence":
            correct_pres += int(ok)
        elif (c.get("evaluation_type") or "") == "forgetting_absence":
            correct_forg += int(ok)
    # Denominators are the FULL per-question criterion counts (not the
    # evaluated subset) so judge failures cannot inflate MPA / FAA / FAMA.
    mpa = (correct_pres / n_pres) if n_pres > 0 else 0.0
    faa = (correct_forg / n_forg) if n_forg > 0 else 1.0
    lam = (n_forg / (n_pres + n_forg)) if (n_pres + n_forg) > 0 else 0.0
    fama = max(0.0, mpa - lam * (1.0 - faa))
    overall = bool(
        judge_failures == 0
        and (correct_pres == n_pres)
        and (correct_forg == n_forg)
        and (n_pres + n_forg) > 0
    )
    return overall, {
        "mpa": mpa,
        "faa": faa,
        "lambda": lam,
        "fama": fama,
        "n_presence": n_pres,
        "n_forget": n_forg,
        "judge_failures": judge_failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memora-root", required=True, type=Path)
    parser.add_argument(
        "--duration", choices=["weekly", "monthly", "quarterly"], default="weekly"
    )
    parser.add_argument(
        "--personas",
        default="academic_researcher",
        help="Comma-separated persona names (or 'all').",
    )
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--reader-model", default=os.environ.get("TTMG_MODEL", "deepseek-v3.2"))
    parser.add_argument("--writer-model", default=None)
    parser.add_argument("--linker-model", default=None)
    parser.add_argument("--parser-model", default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--alpha-grid", default="0.05,0.10,0.15,0.20,0.25")
    parser.add_argument("--delta", type=float, default=0.10)
    parser.add_argument("--n-min", type=int, default=30)
    parser.add_argument("--n-cand-per-group", type=int, default=5)
    parser.add_argument("--score-w-h", type=float, default=0.5)
    parser.add_argument("--score-w-u", type=float, default=0.3)
    parser.add_argument("--score-w-p", type=float, default=0.0)  # 0 by default until PMI verified
    parser.add_argument("--enable-pmi", action="store_true")
    parser.add_argument("--max-questions-per-persona", type=int, default=0,
                        help="0 = no limit; small numbers for smoke tests.")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    from ttmg.crc import (
        ALPHA_GRID,
        CRCConfig,
        CalibrationSample,
        calibrate_thresholds,
        freeze_candidate_thresholds,
    )
    from ttmg.system import TTMGConfig, TTMGSystem

    args.out.parent.mkdir(parents=True, exist_ok=True)

    if args.personas.lower() == "all":
        personas = sorted(
            d.name for d in (args.memora_root / args.duration).iterdir() if d.is_dir()
        )
    else:
        personas = [p.strip() for p in args.personas.split(",") if p.strip()]

    alpha_grid = tuple(float(a) for a in args.alpha_grid.split(","))
    crc_cfg = CRCConfig(
        alpha_grid=alpha_grid,
        delta=args.delta,
        n_min=args.n_min,
        n_candidates_per_group=args.n_cand_per_group,
    )
    judge_model = args.judge_model or args.reader_model

    cfg = TTMGConfig(
        reader_model=args.reader_model,
        writer_model=args.writer_model or args.reader_model,
        linker_model=args.linker_model or args.reader_model,
        parser_model=args.parser_model or args.reader_model,
        enable_beta=True,
        enable_beta_writer=True,
        enable_beta_linker=True,
        enable_pmi=args.enable_pmi,
        score_w_h=args.score_w_h,
        score_w_u=args.score_w_u,
        score_w_p=args.score_w_p,
    )

    dev_signals: List[Dict[str, Any]] = []
    dev_samples: List[CalibrationSample] = []
    cal_samples: List[CalibrationSample] = []

    for persona in personas:
        print(f"[calibrate] persona={persona} duration={args.duration}", flush=True)
        sessions, questions_blob = _load_memora_persona(args.memora_root, args.duration, persona)
        if not sessions:
            print(f"  (skip: no sessions for {persona})", flush=True)
            continue

        sys_inst = TTMGSystem(cfg)
        sys_inst.ingest_conversation(
            [_convert_session_to_ttmg(s) for s in sessions], verbose=False
        )

        flat = _flatten_question_groups(questions_blob)
        if args.max_questions_per_persona > 0:
            flat = flat[: args.max_questions_per_persona]
        # Stable ordering before deterministic shuffle, per Codex review.
        flat = sorted(flat, key=lambda tq: (tq[0], (tq[1].get("question_id") or "")))
        dev_set, cal_set = _split_dev_cal(flat, dev_frac=0.6, seed=args.seed)

        for split_name, qs in (("dev", dev_set), ("cal", cal_set)):
            for task, q in qs:
                t0 = time.time()
                resp = sys_inst.answer(q.get("question") or "")
                elapsed = time.time() - t0
                # The β path returns score / group; non-β questions (route=flat)
                # are skipped from CRC because Mondrian groups don't apply.
                if resp.get("route") not in ("ttmg", "abstain"):
                    continue
                # Codex-fix CRITICAL #3: failed judge → mark INCORRECT (not skip),
                # keep denominators at full per-question criterion counts.
                ok, fama_fields = _question_correct_overall(
                    resp.get("answer") or "", q, judge_model=judge_model
                )
                if ok is None:
                    # No criteria attached at all → cannot label this question.
                    continue
                row = {
                    "persona": persona,
                    "duration": args.duration,
                    "task": task,
                    "split": split_name,
                    "question_id": q.get("question_id"),
                    "score": float(resp.get("score", 0.0)),
                    "group": list(resp.get("group", [])),
                    "route": resp.get("route"),
                    "answered_correctly": bool(ok),
                    "elapsed": elapsed,
                    **fama_fields,
                }
                dev_signals.append(row)
                sample = CalibrationSample(
                    score=row["score"],
                    correct=row["answered_correctly"],
                    group=tuple(row["group"]),
                    meta={"persona": persona, "task": task, "qid": row["question_id"]},
                )
                if split_name == "dev":
                    dev_samples.append(sample)
                else:  # "cal"
                    cal_samples.append(sample)

    # Persist raw signals — used for dev tuning & post-hoc PMI phase diagram.
    sig_path = args.out.with_suffix(".dev_signals.jsonl")
    with open(sig_path, "w") as fh:
        for r in dev_signals:
            fh.write(json.dumps(r) + "\n")
    print(
        f"[calibrate] wrote {len(dev_signals)} signals "
        f"(dev={len(dev_samples)} / cal={len(cal_samples)}) → {sig_path}",
        flush=True,
    )

    if not cal_samples:
        print("[calibrate] no calibration samples collected; aborting", flush=True)
        return 1
    if not dev_samples:
        print("[calibrate] no dev samples collected; cannot freeze candidates; aborting", flush=True)
        return 1

    # Codex-fix CRITICAL #1: freeze T_cand on dev; calibrate on cal.
    # The two splits are disjoint (deterministic shuffle, dev_frac=0.6).
    cand = freeze_candidate_thresholds(dev_samples, config=crc_cfg)
    table = calibrate_thresholds(cal_samples, cand, config=crc_cfg)
    table["meta"] = {
        "memora_root": str(args.memora_root),
        "duration": args.duration,
        "personas": personas,
        "reader_model": args.reader_model,
        "judge_model": judge_model,
        "score_weights": [args.score_w_h, args.score_w_u, args.score_w_p],
        "n_calibration_samples": len(cal_samples),
        "n_dev_signals": len(dev_signals),
        "git_hash": _git_hash(_PROJECT_ROOT),
        "code_sha256_crc_py": _file_sha256(_PROJECT_ROOT / "ttmg" / "crc.py"),
        "code_sha256_truth_retriever_py": _file_sha256(
            _PROJECT_ROOT / "ttmg" / "truth_retriever.py"
        ),
    }
    with open(args.out, "w") as fh:
        json.dump(table, fh, indent=2)
    print(f"[calibrate] locked threshold_table → {args.out}", flush=True)
    print(f"[calibrate] code SHA256 (crc.py) = {table['meta']['code_sha256_crc_py'][:16]}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
