"""Simulate NeurIPS peer review of the current PDF via MAAS.

Uses three distinct reviewer personas. For each persona we submit the
entire LaTeX source (main.tex + all sections + bib) and ask for a
structured review with an overall score in [1, 10].

Heavy work (review generation) happens via the external Chat API.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAPER_DIR = PROJECT_ROOT / "paper"
DATASET = "/home/workspace/lww/project0412/projects/dataset"
if DATASET not in sys.path:
    sys.path.insert(0, DATASET)

from api import chat  # type: ignore


def _expand_macros(text: str, macros: dict[str, str]) -> str:
    """Substitute \\Name{} and \\Name (in text contexts) with the macro value."""
    import re
    for name, val in macros.items():
        # \Name{} form
        text = re.sub(rf"\\{re.escape(name)}\{{\s*\}}", val, text)
        # \Name followed by non-letter
        text = re.sub(rf"\\{re.escape(name)}(?=[^A-Za-z])", val, text)
    return text


def _collect_macros(main_tex: str) -> dict[str, str]:
    """Extract \\newcommand{\\Name}{value} definitions."""
    import re
    out: dict[str, str] = {}
    for m in re.finditer(r"\\newcommand\{\\([A-Za-z]+)\}\{([^}]*)\}", main_tex):
        out[m.group(1)] = m.group(2)
    return out


def _read_paper_source() -> str:
    import re as _re
    main = (PAPER_DIR / "main.tex").read_text(encoding="utf-8")
    macros = _collect_macros(main)
    # Strip the \newcommand definition block (reviewers misread it as placeholders).
    main_clean = _re.sub(r"\\newcommand\{\\[A-Za-z]+\}\{[^}]*\}\n?", "", main)
    # Expand any remaining macro uses in main.tex (e.g., title).
    main_clean = _expand_macros(main_clean, macros)
    chunks = []
    chunks.append(f"=== main.tex (macros pre-substituted with real numerical values) ===\n{main_clean}")
    for name in [
        "0_abstract.tex",
        "1_introduction.tex",
        "2_related_work.tex",
        "3_method.tex",
        "4_experiments.tex",
        "5_analysis.tex",
        "6_conclusion.tex",
        "A_appendix.tex",
    ]:
        path = PAPER_DIR / "sections" / name
        if path.exists():
            txt = path.read_text(encoding="utf-8")
            chunks.append(f"=== sections/{name} (macros expanded) ===\n{_expand_macros(txt, macros)}")
    return "\n\n".join(chunks)


REVIEWER_PROMPTS = {
    "strict_ml": (
        "You are a strict NeurIPS 2026 area-chair-level reviewer. You value "
        "rigor, clarity, honest evaluation, and strong empirical support. "
        "Read the submitted paper and review it per NeurIPS criteria "
        "(originality, quality, clarity, significance). Score each criterion "
        "in [1,10] and give an overall score in [1,10]. Respond with ONLY "
        "the JSON described below."
    ),
    "empirical_skeptic": (
        "You are a seasoned empirical-ML reviewer who cares most about "
        "experimental soundness: fair baselines, statistical significance, "
        "ablation coverage, reproducibility, and failure-mode analysis. "
        "Score the paper on the same four NeurIPS criteria with scores in "
        "[1,10] each, and give an overall score in [1,10]. Respond with "
        "ONLY the JSON described below."
    ),
    "systems_practitioner": (
        "You are a systems-leaning reviewer who cares most about whether "
        "the proposed memory system is practical: throughput, cost, "
        "latency, integration surface, and robustness on real workloads. "
        "Also judge novelty and clarity. Score on the four NeurIPS criteria "
        "in [1,10] each, and give an overall score in [1,10]. Respond with "
        "ONLY the JSON described below."
    ),
}

REVIEW_INSTRUCTIONS = """Output JSON with fields:
{
  "scores": {
    "originality": <int 1-10>,
    "quality":     <int 1-10>,
    "clarity":     <int 1-10>,
    "significance":<int 1-10>,
    "overall":     <float 1-10>
  },
  "strengths":   [ "<short bullet>", ... ],
  "weaknesses":  [ "<short bullet>", ... ],
  "required_revisions": [ "<specific fix>", ... ],
  "verdict": "<reject | weak_reject | borderline | weak_accept | accept>"
}

Constraints:
- You MUST score based on what is WRITTEN in the paper (including the
  macros even if some are placeholders).
- Do not reject for placeholder numbers alone; comment on them under
  required_revisions.
- Return JSON ONLY. No prose, no markdown."""


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```\s*$", "", text)
    if text.startswith("{"):
        try:
            return json.loads(text)
        except Exception:
            pass
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {"scores": {"overall": 0}, "strengths": [], "weaknesses": [text[:400]],
            "required_revisions": [], "verdict": "unknown"}


def review_paper(persona: str, model: str) -> dict:
    sys_prompt = REVIEWER_PROMPTS[persona]
    paper_src = _read_paper_source()
    user = f"{REVIEW_INSTRUCTIONS}\n\n---\nPaper source begins below.\n---\n{paper_src}"
    out = chat(user, system=sys_prompt, model=model, temperature=0.0)
    return _extract_json(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="deepseek-v3.2")
    ap.add_argument("--personas", nargs="*", default=list(REVIEWER_PROMPTS.keys()))
    ap.add_argument("--out", default="results/review.json")
    args = ap.parse_args()

    results = {}
    for p in args.personas:
        print(f"[review] persona={p}")
        t0 = time.time()
        try:
            res = review_paper(p, args.model)
        except Exception as e:
            res = {"error": str(e)}
        dt = time.time() - t0
        results[p] = {"elapsed_sec": dt, **res}
        scores = res.get("scores", {}) if isinstance(res, dict) else {}
        print(f"  overall={scores.get('overall', '??')}  verdict={res.get('verdict','??')}  t={dt:.1f}s")

    out = PROJECT_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"[review] wrote {out}")

    # Summary
    overalls = [r.get("scores", {}).get("overall", 0) for r in results.values() if isinstance(r, dict)]
    overalls = [float(x) for x in overalls if isinstance(x, (int, float))]
    if overalls:
        print(f"[review] avg overall = {sum(overalls)/len(overalls):.2f} (min={min(overalls):.1f})")


if __name__ == "__main__":
    main()
