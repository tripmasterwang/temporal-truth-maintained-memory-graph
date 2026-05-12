"""Compare multiple eval_memora.py output JSONs side-by-side.

Usage: python scripts/compare_methods.py <result1.json> <result2.json> [...]

Produces:
  - Per-task FAMA × 100 / N table (Memora paper convention).
  - Per-method route distribution.
  - Per-question matched-by-question_id comparison (FAMA delta).
  - Aggregate FAMA per duration (sum of three task scores, max 300).
"""
from __future__ import annotations
import json, sys
from collections import defaultdict


def load(path: str):
    return json.load(open(path))


def main():
    if len(sys.argv) < 2:
        print("usage: compare_methods.py <result.json> [<result.json> ...]")
        sys.exit(1)
    runs = [(p, load(p)) for p in sys.argv[1:]]

    # Per-method summary
    print("=" * 70)
    print(f"{'method':<22}{'rem':>9}{'rea':>9}{'rec':>9}{'sum':>9}{'n_q':>6}{'sec':>7}")
    print("-" * 70)
    for path, d in runs:
        ta = d.get("task_aggregates", {})
        print(
            f"{d.get('method','?'):<22}"
            f"{ta.get('remembering', 0):>9.2f}"
            f"{ta.get('reasoning', 0):>9.2f}"
            f"{ta.get('recommending', 0):>9.2f}"
            f"{d.get('duration_total_max300', 0):>9.2f}"
            f"{len(d.get('per_question', [])):>6}"
            f"{d.get('elapsed_sec', 0):>7.0f}"
        )
    print()

    # Route distribution per method
    print("=== route distribution ===")
    for path, d in runs:
        from collections import Counter
        routes = Counter(q.get("route") for q in d.get("per_question", []))
        print(f"  {d.get('method','?'):<22} {dict(routes)}")
    print()

    # Per-question match-by-id (assumes ≥2 runs)
    if len(runs) >= 2:
        print("=== per-question FAMA (matched by question_id) ===")
        ids = sorted({q["question_id"] for _, d in runs for q in d.get("per_question", [])})
        header = f"{'qid':<48}" + "".join(f"{r[1].get('method','?')[:10]:>12}" for r in runs)
        print(header)
        for qid in ids:
            row = f"{qid:<48}"
            for _, d in runs:
                hit = next((q for q in d.get("per_question", []) if q.get("question_id") == qid), None)
                if hit is None:
                    row += f"{'-':>12}"
                else:
                    row += f"{hit.get('fama', 0.0):>12.3f}"
            print(row)
    print()

    # Judge failure rate per method
    print("=== judge failure rate ===")
    for path, d in runs:
        per_q = d.get("per_question", [])
        jf = sum(q.get("judge_failures", 0) for q in per_q)
        total = sum(q.get("n_presence", 0) + q.get("n_forget", 0) for q in per_q)
        print(f"  {d.get('method','?'):<22} {jf}/{total} ({100*jf/max(1,total):.1f}%)")


if __name__ == "__main__":
    main()
