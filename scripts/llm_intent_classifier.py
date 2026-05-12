"""Zero-shot question-type classifier via MAAS LLM.

Classifies each question in the N=150 eval slice into LongMemEval's
six types using Kimi-K2. Outputs per-question predicted types and
an evaluation against the gold labels.

Cost: 150 small calls at ~500 tokens each = ~75K tokens. Batched
below.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET = "/home/workspace/lww/project0412/projects/dataset"
sys.path.insert(0, DATASET)
from api import chat  # type: ignore

CLASS_DESC = {
    "single-session-user": "A question about a fact the user stated in a single session about themselves (their own life, preferences, history, possessions, schedule). Example: 'What was my previous occupation?'",
    "single-session-assistant": "A question asking the assistant to recall something the assistant previously said or discussed. Example: 'Can you remind me what date you mentioned for the court case?'",
    "single-session-preference": "A question about the user's taste/preference expressed in a single session. Example: 'What was my favorite dish at the restaurant?'",
    "multi-session": "A question that requires aggregating information across multiple sessions, including counting, comparing, or totalling. Example: 'How many graduation ceremonies have I attended in the past three months?'",
    "knowledge-update": "A question that asks about the current value of something that may have changed across sessions, or that requires reasoning about updates. Example: 'What is my current Fitbit step goal?'",
    "temporal-reasoning": "A question that requires temporal arithmetic, ordering of events across the timeline, or 'how many days/weeks/months ago' style calculations. Example: 'How many days ago did I read the March 15th issue of The New Yorker?'",
}

SYS_PROMPT = (
    "You are a question-type classifier for the LongMemEval benchmark. "
    "Given a single question, return exactly one of these six labels: "
    + ", ".join(CLASS_DESC.keys()) + "."
    " Output JSON with a single key 'type'."
)

USER_TMPL = """Label definitions:
{defs}

Classify this question:
\"\"\"{q}\"\"\"

Output strictly: {{"type": "<one of the six labels>"}}"""


def classify_one(question: str, model: str) -> str:
    user = USER_TMPL.format(
        defs="\n".join(f"- {k}: {v}" for k, v in CLASS_DESC.items()),
        q=question.replace("\"\"\"", "\""),
    )
    for attempt in range(3):
        try:
            out = chat(user, system=SYS_PROMPT, model=model, temperature=0.0, max_tokens=40)
            # Find the JSON
            import re
            m = re.search(r"\{[^}]*\}", out, re.S)
            if m:
                j = json.loads(m.group(0))
                t = j.get("type", "").strip().strip('"').strip("'").lower()
                for k in CLASS_DESC:
                    if t == k.lower():
                        return k
            # Fallback: scan for a label mention
            txt = out.lower()
            for k in CLASS_DESC:
                if k.lower() in txt:
                    return k
        except Exception as e:
            time.sleep(1 + attempt)
    return ""


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ttmg", default=str(PROJECT_ROOT / "results" / "pilot_n150_ttmg.json"))
    ap.add_argument("--model", default="Kimi-K2")
    ap.add_argument("--out", default=str(PROJECT_ROOT / "results" / "intent_classifier_n150.json"))
    ap.add_argument("--limit", type=int, default=-1)
    args = ap.parse_args()

    rows = json.load(open(args.ttmg))["rows"]
    if args.limit > 0:
        rows = rows[: args.limit]

    out = {"model": args.model, "predictions": []}
    correct_total = 0
    per_type_counts: dict[str, dict[str, int]] = {}
    for i, r in enumerate(rows):
        q = r["question"]
        gold = r["question_type"]
        pred = classify_one(q, args.model)
        ok = int(pred == gold)
        correct_total += ok
        per_type_counts.setdefault(gold, {"tp": 0, "n": 0})
        per_type_counts[gold]["n"] += 1
        per_type_counts[gold]["tp"] += ok
        out["predictions"].append({
            "question_id": r["question_id"],
            "gold": gold,
            "pred": pred,
            "question": q[:200],
        })
        if (i + 1) % 10 == 0:
            print(f"[classify] {i+1}/{len(rows)}  running_acc={correct_total/(i+1):.3f}", flush=True)

    out["overall_acc"] = correct_total / len(rows)
    out["per_type"] = {t: {"recall": v["tp"] / max(1, v["n"]), "n": v["n"]} for t, v in per_type_counts.items()}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\n[classify] overall accuracy = {out['overall_acc']:.3f}  wrote {out_path}")
    for t, v in out["per_type"].items():
        print(f"  {t:30s}  recall={v['recall']:.3f}  n={v['n']}")


if __name__ == "__main__":
    main()
