"""Gating experiment — oracle error decomposition for the read-side direction.

For each WRONG answer in `results/full500_ttmg_v51.json`, send the
question + gold + Path-D-pred + answer-evidence sessions (only the sessions
LongMemEval marked as containing the answer evidence) to an LLM judge and
classify the failure into one of four classes:

  A: evidence does NOT support the gold (dataset / labelling issue)
  B: evidence supports the gold, but Path-D's pred *ignored* the evidence
     → retrieval missed it OR reader didn't use it (read-side has room)
  C: evidence supports the gold, pred used relevant evidence but logic /
     format / aggregation is wrong (read-side has room — reader logic)
  D: pred is correct in spirit, judge marked wrong (judge error)

Decision tree:
  - (B + C) >> (A + D) → read-side has room; commit to reranker direction.
  - (A + D) >> (B + C) → most "wrongs" are dataset/judge issues; we already
    overstated the bottleneck. Re-think.
  - Roughly even → reranker scoped to specifically Class B/C subset.

Cost: ~186 wrong answers × 1 long-context MAAS call ≈ 2-3 hr sequential.
Single in-flight call (server-load policy).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ttmg.maas_client import chat_json  # noqa: E402

LME_PATH = "/home/workspace/lww/project0412/projects/dataset/LongMemEval-main/data/longmemeval_s.json"

_JUDGE_SYS = (
    "You are a strict ML researcher diagnosing why a memory-augmented LLM "
    "system answered a question wrong. You have full access to the original "
    "answer-evidence sessions. Respond ONLY with strict JSON."
)

_JUDGE_USER_TMPL = """A long-conversation memory system answered a question WRONG.
We need to classify the failure mode to decide whether read-side methods can help.

QUESTION: {question}

GOLD ANSWER: {gold}

SYSTEM'S WRONG PREDICTION: {pred}

These are the conversation sessions LongMemEval annotated as containing the answer evidence:
{sessions}

Classify the failure into EXACTLY ONE of four classes:

A: The conversation sessions DO NOT clearly contain the gold answer's information.
   (Dataset noise; the question is unfair given just these sessions.)

B: The conversation sessions clearly contain the gold answer's information, but
   the system's prediction shows it did NOT use that information at all
   (e.g. it abstained, hallucinated, or referenced unrelated content).
   → read-side problem: retrieval missed the relevant content OR reader did not ground on it.

C: The conversation sessions clearly contain the gold answer's information,
   the system's prediction shows it tried to use related content, but the
   answer is wrong due to logical / format / aggregation / numerical error.
   → read-side problem: reader logic broke after grounding.

D: The system's prediction is actually CORRECT in spirit; the judge that
   marked it "wrong" was over-strict (e.g., paraphrase, equivalent value).
   → not a real failure.

Return strict JSON:
{{
  "class": "A" | "B" | "C" | "D",
  "evidence_supports_gold": true/false,
  "pred_uses_relevant_evidence": true/false,
  "rationale": "one sentence"
}}"""


def _format_sessions(sessions: List[Dict[str, Any]], dates: List[str]) -> str:
    """Compact format of evidence sessions for the judge."""
    out = []
    for sid, sdate, sess in zip(range(len(sessions)), dates, sessions):
        turns = []
        for t in sess:
            if not isinstance(t, dict):
                continue
            role = t.get("role", "?")
            content = (t.get("content") or "").strip()
            if not content:
                continue
            turns.append(f"  [{role}] {content[:600]}")
        if turns:
            out.append(f"--- Session {sid+1} ({sdate}) ---\n" + "\n".join(turns))
    return "\n\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default="results/full500_ttmg_v51.json")
    ap.add_argument("--lme-data", default=LME_PATH)
    ap.add_argument("--out", default="results/gating_decomposition.json")
    ap.add_argument("--judge-model", default="glm-5.1",
                    help="Long-context judge — glm-5.1 / kimi-k2 / deepseek-v3.2")
    ap.add_argument("--max-questions", type=int, default=0,
                    help="0 = all wrongs; small for smoke")
    ap.add_argument("--start", type=int, default=0,
                    help="Resume offset (in case of mid-run failure)")
    args = ap.parse_args()

    project_root = Path(args.results).resolve().parent.parent
    results_path = project_root / args.results
    out_path = project_root / args.out

    with open(results_path) as fh:
        d = json.load(fh)
    rows = d.get("rows", [])
    wrongs = [r for r in rows if r.get("correct") == 0]
    print(f"[gating] total rows: {len(rows)} | wrong answers: {len(wrongs)}")

    # Load LongMemEval-S as a question_id → record map
    lme = {q["question_id"]: q for q in json.load(open(args.lme_data))}

    decisions: List[Dict[str, Any]] = []
    if args.start > 0 and out_path.exists():
        try:
            decisions = json.load(open(out_path)).get("decisions", [])[: args.start]
            print(f"[gating] resuming from {len(decisions)} cached decisions")
        except Exception:
            decisions = []

    for i, r in enumerate(wrongs[args.start :], start=args.start + 1):
        if args.max_questions > 0 and i > args.max_questions:
            break
        qid = r.get("question_id")
        question = r.get("question", "")
        gold = r.get("gold", "")
        pred = r.get("pred", "")
        if not qid or qid not in lme:
            print(f"  [{i}] skip {qid}: no LME match")
            continue
        lme_rec = lme[qid]
        ans_ids = set(lme_rec.get("answer_session_ids", []) or [])
        haystack_ids = lme_rec.get("haystack_session_ids", []) or []
        haystack = lme_rec.get("haystack_sessions", []) or []
        haystack_dates = lme_rec.get("haystack_dates", []) or []

        ev_sessions: List[Dict[str, Any]] = []
        ev_dates: List[str] = []
        for sid, sdate, sess in zip(haystack_ids, haystack_dates, haystack):
            if sid in ans_ids:
                ev_sessions.append(sess)
                ev_dates.append(sdate)
        if not ev_sessions:
            print(f"  [{i}] skip {qid}: no answer-evidence sessions")
            continue

        sessions_text = _format_sessions(ev_sessions, ev_dates)
        prompt = _JUDGE_USER_TMPL.format(
            question=question.strip(), gold=gold.strip(),
            pred=pred.strip()[:800], sessions=sessions_text[:18000],
        )

        t0 = time.time()
        try:
            payload = chat_json(
                prompt, system=_JUDGE_SYS, model=args.judge_model,
                default={"class": "A", "rationale": "judge_failed"},
                temperature=0.0, max_tokens=300,
            )
        except Exception as e:
            payload = {"class": "A", "rationale": f"judge_exception:{e}"[:200]}
        elapsed = time.time() - t0

        cls = (payload.get("class") or "A").strip().upper()[:1]
        if cls not in ("A", "B", "C", "D"):
            cls = "A"
        decision = {
            "question_id": qid,
            "question_type": r.get("question_type"),
            "question": question[:200],
            "gold": gold[:200],
            "pred": pred[:300],
            "class": cls,
            "evidence_supports_gold": bool(payload.get("evidence_supports_gold")),
            "pred_uses_relevant_evidence": bool(payload.get("pred_uses_relevant_evidence")),
            "rationale": (payload.get("rationale") or "")[:300],
            "elapsed": elapsed,
        }
        decisions.append(decision)

        # Save .part on every step
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as fh:
            json.dump({"decisions": decisions}, fh, indent=2, ensure_ascii=False)

        # Live counter
        cnts = Counter(d["class"] for d in decisions)
        running = " ".join(f"{k}={cnts[k]}" for k in "ABCD")
        print(
            f"  [{i}/{len(wrongs)}] {r.get('question_type'):<26} class={cls} "
            f"({elapsed:.0f}s) | {running}"
        )

    # Final aggregation
    cnts = Counter(d["class"] for d in decisions)
    by_type: Dict[str, Counter] = {}
    for d in decisions:
        qt = d.get("question_type", "?")
        by_type.setdefault(qt, Counter())[d["class"]] += 1
    summary = {
        "n_decisions": len(decisions),
        "class_counts": dict(cnts),
        "by_question_type": {qt: dict(c) for qt, c in by_type.items()},
        "read_side_actionable_pct": (
            100.0 * (cnts.get("B", 0) + cnts.get("C", 0)) / max(1, len(decisions))
        ),
        "dataset_or_judge_issue_pct": (
            100.0 * (cnts.get("A", 0) + cnts.get("D", 0)) / max(1, len(decisions))
        ),
    }
    out_payload = {"summary": summary, "decisions": decisions}
    with open(out_path, "w") as fh:
        json.dump(out_payload, fh, indent=2, ensure_ascii=False)

    print("\n=== GATING SUMMARY ===")
    print(f"  decisions: {summary['n_decisions']}")
    print(f"  class counts: {summary['class_counts']}")
    print(f"  read-side actionable (B+C): {summary['read_side_actionable_pct']:.1f}%")
    print(f"  dataset/judge issues (A+D): {summary['dataset_or_judge_issue_pct']:.1f}%")
    print()
    print("=== DECISION ===")
    if summary["read_side_actionable_pct"] >= 60:
        print("  ✅ Read-side has room. Proceed with Drift-Calibrated Hybrid Reranker.")
    elif summary["read_side_actionable_pct"] >= 40:
        print("  ⚠ Mixed. Reranker scoped to Class B/C subset; report transparency.")
    else:
        print("  ❌ Read-side dominated by dataset/judge issues. Pivot to writer-side training.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
