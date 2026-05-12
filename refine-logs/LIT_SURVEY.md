---
name: lit-survey
description: Phase-1 literature landscape for the "push MemMachine 8→9" idea-discovery round; offline-first scan of competitor/*/latex/ + targeted web expansion for D1/D2/D8/D9 white-space and 2026 scoop threats.
type: idea-stage-input
---

# Literature Survey — Push MemMachine 8→9

**Round date.** 2026-04-26  
**Mode.** Push 8→9 on remaining blockers (NOT pivot). Algorithmic/theoretical emphasis (D1, D2, D8, D9).  
**Coverage.** Offline corpus = 11 papers in `competitor/*/latex/` (already curated by user). Web expansion = targeted gap-fill for (a) calibration / conformal / OPE / MI tooling outside memory papers, (b) new 2026 competitors not in `competitor/`.

## 1. Updated competitor inventory (12 → 18)

### 1a. Already in `competitor/` (curated, full LaTeX + code in repo)

| arXiv ID | Paper | Role for MemMachine 8→9 |
|---|---|---|
| 2305.10250 | MemoryBank | Historical concept baseline (Ebbinghaus-style forgetting). Low priority. |
| 2310.08560 | MemGPT (now Letta) | Hierarchical memory management concept. Low priority — already cited. |
| 2402.17753 | LoCoMo | Eval anchor (primary benchmark). |
| 2410.10813 | LongMemEval | Eval anchor. |
| 2502.05589 | SeCom | **Strong matched-baseline candidate** (segmentation + denoising; has `human_evaluation.tex` table — reusable methodology for blocker 6). |
| 2504.19413 | Mem0 | Existing baseline (matched comparison failed: did not finish). |
| 2510.18866 | LightMem | **Strong matched-baseline candidate** that finishes (sleep-time consolidation, 2-9.65% gain over previous, 30-159× API call reduction). Replaces failed Mem0 matched comparison for blocker 3. |
| 2601.02553 | SimpleMem | Lightweight strong baseline; also a candidate for matched ingestion comparison. |
| 2602.06025 | BudgetMem | Per-module budget tiers via PPO router. **Closest to D9** (per-query budget allocation) — must differentiate vs. BudgetMem. |
| 2603.02473 | Diagnosing_memory (memory-probe) | **🚨 SCOOP THREAT.** Ran 3×3 factorial (3 write × 3 retrieve) on LoCoMo and concludes "retrieval dominates" — the cleanly factorial design reviewer asked MemMachine to do (blocker 1+3+4). Differential: this paper is a *diagnostic*, MemMachine is a *system*; combine, don't compete. |
| 2603.15599 | SmartSearch | **🚨 COUNTER-BASELINE.** 91.9% LoCoMo with fully deterministic CPU-only retrieval (no LLM in loop, 650 ms). Questions whether MemMachine's adaptive LLM router justifies its complexity. Identifies a "compilation bottleneck": recall=98.6%, only 22.5% gold survives truncation → ranking, not retrieval, is the bottleneck. |

### 1b. New 2026 competitors **not yet in `competitor/`** (must address before submission)

| arXiv ID | Paper | Why it matters | Action |
|---|---|---|---|
| **2601.02163** | **EverMemOS** (Jan 2026) | **🚨 92.3% LoCoMo SOTA** (vs MemMachine 91.7%). Engram-inspired: Episodic Trace Formation → MemCells (atomic facts + foresight) → Semantic Consolidation → MemScenes → Reconstructive Recollection (agentic multi-round retrieval). Code on github.com/EverMind-AI/EverOS. **Threatens accuracy SOTA claim and ground-truth-preservation claim** (since EverMemOS structures memory but still wins). | Add to `competitor/`, run matched comparison, cite as concurrent work, differentiate on (a) algorithmic novelty if added, (b) cost/latency. |
| **2602.02474** | **MemSkill** (Feb 2026) | Learnable "memory skills" with controller + designer that evolves skill set. LoCoMo/LongMemEval/HotpotQA/ALFWorld. Same author family as BudgetMem (ViktorAxelsen). Differs from BudgetMem by skill evolution. | Add to `competitor/`. Cite + matched comparison if feasible. |
| **2604.20006** | **Memora benchmark** + **FAMA** metric | Long-term memory **benchmark** (weeks–months conversations); FAMA (Forgetting-Aware Memory Accuracy) penalizes reliance on obsolete memory. **Direct opportunity for blocker 2**: a benchmark designed to measure ground-truth preservation under temporal drift — exactly where MemMachine's design philosophy should win. | Strong candidate to add to MemMachine's main eval table for second-benchmark accuracy gain. |
| 2604.07798 | Lightweight LLM Agent Memory with SLMs | Small-LM memory baseline. | Cite, possibly include in cost/efficiency comparison. |
| 2603.04814 | Beyond the Context Window: Cost-Performance of Fact-Based Memory vs Long-Context | Cost-performance analysis space adjacency. | Cite in efficiency analysis. |
| 2502.12110 | A-MEM (Agentic Memory) | Agentic memory baseline. | Likely already cited in MemMachine; verify. |
| 2603.07670 | Memory for Autonomous LLM Agents (survey) | Survey covering this exact space. | Cite for related work positioning. |
| **(workshop)** | **ICLR 2026 MemAgents Workshop** | New venue specifically for memory-for-LLM-agent systems papers. **Better venue match than NeurIPS main given reviewer's "systems venue" feedback.** | Consider as alternate / dual submission. |

## 2. White-space for D1/D2/D8/D9 — confirmed AND tool-rich

A keyword scan of all 141 .tex files in `competitor/` returned **zero matches in body text** for: *conformal*, *calibrat-* (in method context), *off-policy / importance sampling*, *mutual information*, *PAC*, *sequential test*, *constrained-optim*, *Lagrang-*, *bandit*, *matched comparison*, *ground-truth-preserving*. Hits exist only in `MemoryBank/anthology.bib` (a noisy ACL bibliography database) and `BudgetMem/5_Appendix.tex` (PPO context — not calibration). **Memory-system literature has not adopted these tools.**

This is a **structural white-space**: D1/D2/D8/D9 introduce mathematical machinery that the entire competitor field lacks.

### D1 — Calibrated/conformal CGSE replacement (algorithmic novelty)

Tools available outside memory literature:

- **Conformal-RAG** ([2506.20978](https://arxiv.org/html/2506.20978), SIGIR 2025) — leverages internal RAG signals to give group-conditional coverage guarantees on response quality without manual labelling. Retains 60% more high-quality sub-claims while preserving reliability. **Direct tool for D1**: replace MemMachine's heuristic CGSE threshold with a conformal coverage rule on reranker scores → guaranteed quality coverage while gating strategy escalation.
- **Conformal prediction as context-engineering filter** ([2511.17908](https://www.arxiv.org/pdf/2511.17908)) — coverage-controlled filtering that removes irrelevant content while preserving recall of supporting evidence. **Direct tool for D8**.
- Conformal Prediction: A Data Perspective ([2410.06494](https://arxiv.org/pdf/2410.06494)) — survey/methodology reference.

### D8 — Sufficiency-aware ChainOfQuery with formal stopping rule (algorithmic novelty)

Tools available:

- **SIM-RAG** — multi-round RAG framework with a lightweight **critic module** that decides "have we retrieved enough?" → exactly D8 territory. MemMachine already has heuristic sufficiency check in ChainOfQuery; replacing with a calibrated critic + formal stopping (sequential probability ratio, conformal coverage, or Bayesian posterior threshold) is the natural delta.
- Sequential testing literature (SPRT, e-values) — well-developed; importable.

### D2 — Information-theoretic theory of when retrieval dominates ingestion (theory)

Tools available:

- **PMI as RAG performance gauge** ([2411.07773](https://arxiv.org/abs/2411.07773)) — pointwise mutual information between context and question correlates with RAG accuracy. **Direct tool for D2**: derive that if PMI(question; raw episode) > PMI(question; summarized memory), retrieval-time access to raw episode wins. Predicts when ground-truth preservation matters.
- **Swin-VIB / variational information bottleneck for RAG** ([2504.12982](https://arxiv.org/html/2504.12982)) — information-theoretic framework for knowledge conflicts; usable to formalize ingestion as lossy compression and bound the information loss.
- **MI-RAG** — mutual information as retrieval evaluation metric.

### D9 — Per-query budget allocation theory (algorithmic novelty + budget angle)

- **BudgetMem (in-repo)** is the closest neighbor: per-module budget tiers, PPO router, cost-aware reward. **Differentiation needed**: BudgetMem allocates compute across **modules** of an extraction pipeline; D9 would allocate compute across **retrieval depths / strategies** within a single query at inference time, with a closed-form / analytic solution rather than RL. The two are complementary, not duplicative — D9 lives at retrieval, BudgetMem at extraction.
- **Conformal/coverage-aware budget** is unexplored: a constrained optimization "minimize expected token cost subject to ≥ 1−α answer-quality coverage" is novel and aligns with both D1 and D9.

## 3. Scoop-threat analysis and mitigations

### 3a. memory-probe / Diagnosing (2603.02473) — "retrieval dominates" thesis scoop

- **Threat scope.** They prove "retrieval method drives 14–23 pp; write strategy 3–8 pp" with a clean 3×3 factorial on LoCoMo. MemMachine's central empirical claim is essentially the same.
- **What's still defensible.** (a) memory-probe is a *diagnostic study* — it has no deployable system, no graph backend, no adaptive routing, no CGSE. (b) Their write strategies are simplistic (raw chunks, Mem0-style, MemGPT-style); they did NOT compare against modern compression (LightMem, SeCom, SimpleMem). (c) They run only LoCoMo, single benchmark.
- **Mitigation.** Cite as concurrent/follow-up; reframe MemMachine's thesis from "retrieval dominates" (now a known finding) to **"given retrieval dominates, here is the principled algorithmic mechanism that exploits it: calibrated CGSE + sufficiency-aware ChainOfQuery + theory of when ground-truth preservation pays."** This rebases the contribution on D1+D8+D2 — i.e., the algorithmic novelty exactly addresses the 7.5 cap.

### 3b. SmartSearch (2603.15599) — counter-baseline "ranking beats structure"

- **Threat scope.** 91.9% LoCoMo with deterministic CPU pipeline, 650 ms latency, 8.5× fewer tokens than full-context, no LLM in retrieval. They explicitly claim BudgetMem-style learned routing isn't needed. Their "compilation bottleneck" framing (recall=98.6%, gold-survival=22.5%) directly competes with MemMachine's CGSE story.
- **What's still defensible.** (a) SmartSearch only runs LoCoMo + LongMemEval-S; (b) deterministic substring matching may fail on harder multi-hop benchmarks; (c) no theoretical guarantee, no calibration, just engineering.
- **Mitigation.** Add SmartSearch to baseline table as the **strongest minimal-router competitor**. MemMachine's value-add must be (a) generality across multi-hop (HotpotQA, WikiMultiHop where SmartSearch isn't run), (b) calibration guarantee (D1) that SmartSearch lacks, (c) theory (D2) that explains when MemMachine's complexity earns its keep.

### 3c. EverMemOS (2601.02163) — current LoCoMo SOTA

- **Threat scope.** 92.3% LoCoMo SOTA. MemCells (atomic facts + foresight) + MemScenes (consolidation) + agentic multi-round retrieval. **Beats MemMachine on LoCoMo and contradicts ground-truth-preservation thesis** (they extract structure and still win).
- **Mitigation.** Run matched comparison vs EverMemOS under fixed answer LLM and token budget. Hypothesize EverMemOS wins on accuracy at the cost of ingestion time (reproducing the Mem0-style trade-off MemMachine already showed). If matched comparison reveals >10× ingestion gap with <2 pp accuracy gap, MemMachine's cost-efficiency claim survives. If accuracy gap is large and ingestion gap is small, MemMachine's thesis is in real trouble — and the right move is to narrow claim to **cost-constrained regimes** and broaden to multi-hop (HotpotQA/WikiMultiHop) where MemMachine wins. Plan B: position as "ground-truth-preserving + calibrated retrieval" while EverMemOS is "structured + agentic retrieval" → orthogonal.

## 4. Implications for Phase 2 idea generation

Based on this survey, Phase 2 (`/idea-creator`) should generate ideas that **simultaneously satisfy**:

1. **Algorithmic novelty** (cracks blocker 1, the binding 7.5 cap). At least one of D1/D2/D8/D9. Tools listed in §2 are all available.
2. **Survives the scoop tests** (memory-probe + SmartSearch + EverMemOS).
3. **Multi-benchmark accuracy** (cracks blocker 2). Strongest candidate: add **Memora** (FAMA metric) as second benchmark where ground-truth preservation should win by design; HotpotQA/WikiMultiHop where SmartSearch isn't run.
4. **Matched-comparison-feasible** baselines (cracks blocker 3). Use **LightMem + SeCom + SimpleMem + EverMemOS + MemSkill**, NOT Mem0 (doesn't finish).
5. **Reranker isolation** (blocker 4) and **paired LoCoMo significance + human eval** (blockers 5, 6) become standard ablations included in any idea's experiment plan.

Best-bet bundle that combines max novelty with min new compute:

> **Calibrated Adaptive Retrieval (CAR) for ground-truth-preserving memory.** Replace heuristic CGSE with a conformal coverage rule on reranker scores; replace heuristic sufficiency check in ChainOfQuery with a sequential testing critic; derive a PMI-based condition that identifies when raw-episode retrieval beats ingestion compression and validate on the slice where the condition holds. Three coupled algorithmic contributions, each backed by an established external tool, all serving the same retrieval-dominant thesis. Matched comparison vs LightMem/SeCom/SimpleMem/EverMemOS replaces failed Mem0; Memora + HotpotQA + LoCoMo break LoCoMo-only accuracy ceiling.

This is **one** candidate. Phase 2 will brainstorm 8–12 and prune. The seed list (D1–D9) in `REF_PAPER_SUMMARY.md` is the starting point; this survey adds:
- D10: Conformal-RAG-based answer-quality coverage layer (orthogonal to retrieval).
- D11: Memora-FAMA-targeted ground-truth-preservation experiment.
- D12: SmartSearch ablation — strip MemMachine to its CGSE+CoQ contribution and show what remains is necessary beyond deterministic ranking.

## 5. Sources

Web sources used in §1b and §2:

- [Conformal-RAG: Response Quality Assessment for RAG via Conditional Conformal Factuality (2506.20978)](https://arxiv.org/html/2506.20978)
- [Principled Context Engineering for RAG (2511.17908)](https://www.arxiv.org/pdf/2511.17908)
- [Conformal Prediction: A Data Perspective (2410.06494)](https://arxiv.org/pdf/2410.06494)
- [Pointwise Mutual Information as a Performance Gauge for RAG (2411.07773)](https://arxiv.org/abs/2411.07773)
- [Accommodate Knowledge Conflicts in RAG (Swin-VIB, 2504.12982)](https://arxiv.org/html/2504.12982)
- [EverMemOS: A Self-Organizing Memory OS (2601.02163)](https://arxiv.org/abs/2601.02163)
- [MemSkill: Learning and Evolving Memory Skills (2602.02474)](https://arxiv.org/abs/2602.02474)
- [Memora: From Recall to Forgetting / FAMA (2604.20006)](https://arxiv.org/html/2604.20006)
- [Lightweight LLM Agent Memory with SLMs (2604.07798)](https://arxiv.org/html/2604.07798)
- [ICLR 2026 MemAgents Workshop](https://openreview.net/forum?id=U51WxL382H)

In-repo sources used in §1a and §3:

- `competitor/2603.02473_Diagnosing_memory/latex/iclr2026_conference.tex` — abstract and method
- `competitor/2603.15599_SmartSearch/latex/smartsearch.tex` — abstract and related work
- `competitor/2602.06025_BudgetMem/latex/{0_intro,2_Method,3_Exp}.tex` — full method + sufficiency context
- `competitor/2510.18866_LightMem/latex/section/introduction.tex` — sleep-time consolidation framing
- `competitor/2502.05589_SeCom/latex/tables/human_evaluation.tex` — human-eval table format (reusable for blocker 6)
- `idea.md` Section A — baseline thesis
- `AUTO_REVIEW.md` Round 9 — final reviewer state
