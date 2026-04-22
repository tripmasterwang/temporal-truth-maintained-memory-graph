# TTMG Project Status — 2026-04-21

## Deliverables so far
- **Code complete**: `ttmg/` library (schema, graph, writer, linker, retriever, system), A-Mem baseline, eval harness, paper template, 8 helper scripts.
- **Paper scaffold**: `paper/main.tex` compiles as 8-page NeurIPS-style PDF with placeholder macros and no undefined citations.
- **All LLM traffic via MAAS** (`projects/dataset/api.py`): DeepSeek-V3.2 reader/judge, Kimi-K2 writer/linker/parser (2× faster than DeepSeek, schema-compatible).

## Running / queued
1. **Pilot** (running, pid 650238): 19 stratified LongMemEval-S Qs × 2 methods (A-Mem, TTMG), max 3 haystack sessions each. Expected completion ~2h total from launch.
2. **Ablations** (`scripts/run_ablations.sh`): queued after pilot. Four ablations: `--disable-temporal`, `--disable-contradict`, `--disable-consistent-subgraph`, `--disable-writer-claims`.
3. **Fill macros + recompile** (`scripts/fill_macros.py` → `scripts/compile_paper.sh`).
4. **Review loop** (`scripts/review_via_maas.py`): 3 personas (strict_ml, empirical_skeptic, systems_practitioner); target overall ≥ 8.5 each. Never add limitations/caveats to improve scores.

## One-shot continuation
Run `scripts/run_full.sh` after the pilot completes to chain ablations → macros → compile → review.

## Working evidence
- Smoke test confirmed TTMG mechanism is live: on a knowledge-update question the linker produced 3 `supersede` edges and deactivated 2 of 20 claims (`edges_supersede: 3`, `edges_support: 1`).
- A-Mem baseline reaches A-Mem paper's reported F1 range on a 2-question smoke.

## Risks / next steps
- Small pilot N (19) → wide CIs. If gain is marginal or negative, iterate on the method (tighter abstention trigger, supersede monotonicity, coreference-aware writer) before widening evaluation.
- Cross-domain (LoCoMo, MemoryAgentBench-CR) data loaders NOT yet written; placeholder rows in paper.

