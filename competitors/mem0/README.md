# Mem0

**Paper:** *Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory*, arXiv:2504.19413 — https://arxiv.org/abs/2504.19413  
**PDF (local):** `paper_arxiv_2504.19413.pdf`  
**LaTeX (arXiv export):** `arxiv_2504.19413.tar.gz` → unpacked in `extracted/` (main: `extracted/main.tex`).

**Official code:** `mem0/` — https://github.com/mem0ai/mem0

B3 integration: Mem0 is API- and store-centric; map its retained memory units onto session-scoped text for our shared LongMemEval / LoCoMo retriever, and document token accounting + any cap-and-truncate fallback per `EXPERIMENT_PLAN.md`.
