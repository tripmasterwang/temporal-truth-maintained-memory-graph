"""Offload long paper-section drafting to MAAS (external Chat API).

This script pre-drafts the sections that are mostly expository and won't
be touched by experimental numbers: §5 Analysis (ablation layout),
§6 Conclusion, §A Appendix. It writes LaTeX files directly into
paper/sections/.

All heavy writing goes through the MAAS chat API to keep the main
conversation's token budget clear, per CLAUDE.md guidance.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DATASET = "/home/workspace/lww/project0412/projects/dataset"
if DATASET not in sys.path:
    sys.path.insert(0, DATASET)

from api import chat  # type: ignore


PAPER_DIR = Path(__file__).resolve().parent.parent / "paper" / "sections"
DEFAULT_MODEL = os.environ.get("TTMG_DRAFT_MODEL", "deepseek-v3.2")

SYS_PROMPT = (
    "You are an expert NeurIPS author writing a rigorous, objective, "
    "concise paper. Output LaTeX ONLY (no prose explanations, no markdown). "
    "Use booktabs for tables. Match the style of top ML papers. "
    "Never overclaim. Never add limitations or 'future work' unless requested. "
    "Use the provided macros for numbers (\\AmemLMEAcc etc.)."
)


ABLATION_PROMPT = """Write section \\section{Analysis and Ablations}\n\\label{sec:ablation} for a NeurIPS paper on the \"Temporal Truth-Maintained Memory Graph (TTMG)\".

Required content:
- One paragraph summarising four ablations of TTMG, each disabling one mechanism:
  (a) --validity: drop validity intervals (turn all claims atemporal).
  (b) --contradict: disable the LLM linker; keep semantic edges only.
  (c) --consistent-subgraph: skip maximum-consistent-subgraph selection at read time.
  (d) --embedding-only linker: replace LLM linker with embedding-based nearest-neighbour labelling.
- A booktabs table "tab:ablation" with columns (Variant, LongMemEval-S overall, KU, TR, ABS).
  Use the macros \\TTMGLMEAcc \\TTMGLMEAccKU \\TTMGLMEAccTR \\TTMGLMEAccABS for the full TTMG row,
  and \\AblValidity, \\AblContradict, \\AblConsistent, \\AblEmbOnly for the ablation rows' Overall column (other columns dashes).
- One paragraph describing what each ablation tells us (e.g., supersede edges are what drives knowledge-update gains; the consistent-subgraph is what drives abstention).
- Stop there. Do NOT add a limitations paragraph, do NOT add future work, do NOT add caveats.

Length: ~0.7 pages, single \\section.

Return LaTeX only.
"""


CONCLUSION_PROMPT = """Write \\section{Conclusion} for the same paper. About half a page.

Content:
- One paragraph restating the problem (conversational memory must maintain truth over time, not just retrieve similar text).
- One paragraph summarising the mechanism (claim schema + validity + contradict/supersede edges + truth-consistent retrieval + abstention).
- One sentence on headline numbers, using macro \\DeltaLMEAcc (overall improvement on LongMemEval-S).
- One brief sentence on the broader takeaway (truth maintenance is a useful unit of memory).

Do NOT include a limitations section. Do NOT include future-work promises longer than one sentence.

Return LaTeX only.
"""


APPENDIX_PROMPT = """Write \\section{Appendix} for the same paper.

Include subsections:
- \\subsection{Writer prompt}: a short blurb and a verbatim copy of the claim-extraction prompt template (you can paraphrase; ~15 lines inside a verbatim block).
- \\subsection{Linker prompt}: a short blurb and paraphrased linker prompt template.
- \\subsection{Retriever query parser}: short blurb and paraphrased query-parser prompt.
- \\subsection{Hyper-parameters}: a booktabs table listing:
    embedding model (all-MiniLM-L6-v2), reader (deepseek-v3.2),
    writer/linker/parser model (deepseek-v3.2), $k$ for retrieval (8),
    $k_{\\text{keep}}$ (3), hard-edge threshold (0.7),
    linker similarity gate (0.65), bypass threshold (0.85),
    session-batched writer (on), seeds (0/7/17).
- \\subsection{Dataset splits}: one paragraph about the LongMemEval-S
  types distribution (summarise: 500 questions, 6 types, 30 abstention).

Pure LaTeX, no markdown. Return code only.
"""


def draft(section_path: Path, prompt: str, model: str) -> None:
    text = chat(
        user=prompt,
        system=SYS_PROMPT,
        model=model,
        temperature=0.0,
    )
    section_path.parent.mkdir(parents=True, exist_ok=True)
    section_path.write_text(text.strip() + "\n", encoding="utf-8")
    print(f"[wrote] {section_path} ({len(text)} chars)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--only", nargs="*", default=None, help="optionally restrict to sections")
    args = ap.parse_args()

    jobs = {
        "analysis": (PAPER_DIR / "5_analysis.tex", ABLATION_PROMPT),
        "conclusion": (PAPER_DIR / "6_conclusion.tex", CONCLUSION_PROMPT),
        "appendix": (PAPER_DIR / "A_appendix.tex", APPENDIX_PROMPT),
    }
    if args.only:
        jobs = {k: v for k, v in jobs.items() if k in set(args.only)}

    for name, (path, prompt) in jobs.items():
        print(f"[drafting] {name} -> {path}")
        draft(path, prompt, args.model)


if __name__ == "__main__":
    main()
