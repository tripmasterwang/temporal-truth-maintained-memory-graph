# A-Mem (Agentic Memory)

**Paper:** *A-Mem: Agentic Memory for LLM Agents*, arXiv:2502.12110 — https://arxiv.org/abs/2502.12110  
**PDF (local):** `paper_arxiv_2502.12110.pdf`  
**LaTeX (arXiv export):** `arxiv_2502.12110.tar.gz` → unpacked in `extracted/` (main: `extracted/neurips_2025.tex`).

**Official code (this folder):**

| Role | Path | Upstream |
|------|------|----------|
| Experiment / eval code | `AgenticMemory/` | https://github.com/WujiangXu/AgenticMemory |
| System implementation | `A-mem-sys/` | https://github.com/WujiangXu/A-mem-sys |

B3 integration: wire `run_basc_compat.py` (to be added) to emit a `ConsolidatedBuffer` per `competitors/_common/protocol.py`, with matched post-write token budget and disclosed knobs.
