# Novelty Check Report — Adaptive E-Process Reader

**Date:** 2026-04-27
**Idea:** Adaptive E-Process Reader for Long-Conversation Agent Memory (Idea #1 in `IDEA_REPORT.md`)
**Search method:** focused general-purpose agent over arXiv 2024-04 to 2026-04, Google Scholar, Semantic Scholar, plus the project's existing frontier survey.

## Per-claim novelty

| Claim | Score | Closest paper | Differentiation |
|---|---:|---|---|
| **C1** — e-process / SPRT / anytime-valid testing as the answer-time decision rule in *agent memory* reading | **HIGH (8.5/10)** | E-valuator (2512.03109) — e-process for verifier-side trust on agent trajectories | Different task (verifier vs answering), different decision (binary trajectory abort vs multi-candidate answer selection), no memory substrate |
| **C2** — Sequential statistical testing over a *heterogeneous evidence stream* (multiple retrieval modalities into one test) | **MEDIUM-HIGH (7.0/10)** | MiCP (2604.01413) — conformal early-stopping for multi-turn ReAct/RAG | MiCP is single-substrate (one ReAct loop), static conformal calibration with budget split, not anytime-valid in Ville sense, not memory |
| **C3** — Adaptive-budget retrieval with a *statistical* stopping rule | **MEDIUM (5.5/10)** | MiCP (2604.01413), Stop-RAG (2510.14337) | "Statistical stopping" slot now contested; the *anytime-valid* + *per-candidate* + *multi-substrate* angle is still open but the umbrella is occupied |

## Closest 8 prior works

| Paper | arXiv | Year | Overlap | Key difference |
|---|---|---|---|---|
| E-valuator | 2512.03109 | 2025 | E-process for agent decisions | Verifier wrapping a scalar score; not memory; not multi-candidate; not multi-substrate |
| **MiCP — Multi-turn Conformal Prediction** ⚠ | 2604.01413 | 2026 | **Statistical early-stopping for multi-turn LLM with coverage guarantee** | Conformal (not anytime-valid e-process); single-substrate ReAct/RAG; not memory; budget-split, not Ville/martingale. **Strongest reviewer attack target.** |
| Stop-RAG | 2510.14337 | 2025 | Adaptive stopping for iterative RAG | Value-based RL, not statistical; single substrate; not memory |
| Conformal-RAG | 2506.20978 | 2025 | Coverage guarantee on RAG sub-claims | Static threshold; not sequential / anytime-valid; not memory |
| Online LLM-text detection by betting | 2410.22318 | 2024 | Sequential testing-by-betting on streaming text | Source detection (LLM vs human); not RAG / memory / answer selection |
| BMAM — 4-way hybrid memory retrieval | 2601.20465 | 2026 | BM25 + dense + graph + temporal fused for memory | RRF fusion; no statistical sequential test; no anytime stopping |
| ConSol | 2503.17587 | 2025 | SPRT for LLM self-consistency mode-detection | Self-consistency over single sampler; not memory; not heterogeneous substrates |
| SIM-RAG / TA-ARE / DRAGIN / FLARE | 2024-25 | various | Adaptive retrieval depth for multi-hop QA | All heuristic / learned / entropy critics; no statistical guarantee |

## Newly-surfaced papers worth adding to project's frontier survey

The novelty agent found **6 papers I missed in the earlier delta survey** — these should be folded into `LIT_SURVEY_DELTA.md` and (for the relevant ones) cited as baselines:

1. **MiCP (2604.01413)** — Multi-turn Conformal Prediction. Critical: must be a baseline.
2. **Stop-RAG (2510.14337)** — Value-based RL stopping for iterative RAG. Critical: must be a baseline.
3. **BMAM (2601.20465)** — 4-way hybrid memory retrieval (BM25 + dense + graph + temporal) with RRF fusion. Closest *multi-substrate* memory neighbour.
4. **MAGMA (2601.03236)** — Multi-Graph Agentic Memory. New 2026 frontier system not in our pre-2026-04 cut-off.
5. **HetaRAG (2509.21336)** — Heterogeneous data stores in RAG. Adjacent multi-substrate work.
6. **Conformal Information Pursuit (2507.03279)** — Adjacent conformal RAG variant.
7. **E-value stopping for Bayesian Deep Ensembles (2604.18089)** — Adjacent e-process application; cites Ville's inequality.

## Overall

**Score: 7.5 / 10 — PROCEED WITH CAUTION.**

Justification: the **intersection** {anytime-valid e-process} × {heterogeneous memory substrates} × {long-conversation memory QA} × {per-candidate stopping with abstention} is genuinely open. But each individual axis is now well-populated, and the "principled stopping for retrieval depth" narrative is contested by Stop-RAG, MiCP, and Conformal-RAG.

Defensibility requires:
1. **MiCP and Stop-RAG as baselines.** Non-negotiable.
2. **Multi-substrate composition + anytime-valid e-process** must be the load-bearing technical contribution, not just "we use e-values".
3. **Measurable memory-QA wins** on LongMemEval-S + LoCoMo + Memora-FAMA, not just synthetic / RAG benchmarks.

## Irreducible novelty (the 3 things no neighbour combines)

1. **Multi-substrate composition into one e-process** — likelihood-ratio surrogates from semantic + lexical + claim-graph + raw-turn fed into a coupled e-value under one null. Neither MiCP nor E-valuator does this.
2. **Per-candidate-answer competition** — multiple alternative answers each accumulate their own e-value; first to cross threshold wins. E-valuator is binary trajectory-abort; MiCP outputs prediction sets. This is a sequential **multiple-testing** problem with FDR-safe candidate selection.
3. **Coupling with the TTMG supersede edges** — e-process can downweight evidence whose underlying claim has been superseded → temporally-valid answer selection. Piggybacks on Path D's existing claim-graph machinery — a unique angle no general-RAG paper can match. **This is the project-specific moat.**

## Strongest reviewer attack

**MiCP (2604.01413)**: "you're doing conformal-style adaptive-stopping multi-turn RAG; MiCP has coverage guarantee with adaptive termination — what does the e-process buy you?"

**Defence (must appear in §Discussion):**
- (i) MiCP is *static conformal* with pre-allocated per-turn error budget — cannot continue indefinitely without re-calibration. E-process is *anytime-valid by construction* under any stopping.
- (ii) MiCP operates on a *single* substrate / loop. E-process here aggregates *heterogeneous modalities* into one test.
- (iii) MiCP gives prediction sets; we give *per-candidate dominance* — directly actionable for an answering agent.
- (iv) MiCP is not evaluated on memory benchmarks. Memory adaptation is non-trivial because of supersede / temporal validity.

## Suggested positioning

Frame as the **first anytime-valid statistical reader for agent memory** with two layered contributions:

- **Method:** Adaptive-budget memory reader where heterogeneous substrates (semantic, lexical, claim-graph-with-supersede, raw-turn k-NN) compose into a per-candidate e-process whose threshold gives an α-controlled stopping rule, FDR-safe across an unbounded sequence of evidence batches; abstention is the natural overflow event.
- **Systems angle:** First reader for memory-augmented LLM agents that gives a *statistical* stopping rule and a *statistical* abstention rule simultaneously — replacing the heuristic "top-K then read" pipeline used by all 11+ 2026 memory frontiers (A-Mem, Mem0, MemoryOS, BMAM, MAGMA, SimpleMem, EverMemOS, SmartSearch, APEX-MEM, HyperMem, RoMem, Synthius-Mem, HiGMem).

Title axes (maximise novelty perception):
- "**Anytime-Valid Memory Reading**" — foregrounds statistical novelty
- "**E-Process Memory Reader**" — mirrors E-valuator's name; flags lineage but stakes different territory
- ❌ Avoid "Adaptive RAG" framing — places paper in MiCP/Stop-RAG/SIM-RAG's crowded sub-genre

In related work, **explicitly cite and contrast** E-valuator + MiCP + Stop-RAG + ConSol + Conformal-RAG + BMAM in a single dedicated subsection. Hiding any of these gets the paper desk-rejected.

---

## Verdict for the project

✅ **PROCEED**. The novelty is at the intersection, the irreducible moat (multi-substrate + per-candidate + supersede-aware) is genuine, and the project has a unique substrate (Path D's TTMG claim graph + raw-turn fallback already in code). Risks are real but manageable through careful baseline coverage and the framing above.

The mandatory next steps are:
1. Add MiCP, Stop-RAG, BMAM, MAGMA, Conformal-RAG to the experiment plan as baselines.
2. Position as "first anytime-valid memory reader" not "adaptive RAG".
3. Make multi-substrate composition + supersede-coupling the load-bearing technical contributions.
