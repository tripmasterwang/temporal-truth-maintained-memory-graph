# Literature Survey — Agent Memory Read-Side & Statistical Machinery

**Round date:** 2026-04-30
**Context:** Post-TTMG result-to-claim gate (overall verdict: no). New idea must attack read-side (88.2% failures), apply broadly, not regress on LoCoMo, bring statistical/info-theoretic machinery.

---

## 1. SOTA Snapshot (April 2026)

The field has moved extremely fast. In the past 3 months alone, 6+ new strong systems were posted:

| System | arXiv ID | LongMemEval-S | LoCoMo | Key mechanism | Published |
|--------|----------|--------------|--------|---------------|-----------|
| **MemMachine** | 2604.04853 | **93.0%** | 91.69% | Ground-truth-preserving, raw episode + contextualized retrieval, 6-axis ablation | Apr 6, 2026 |
| **EverMemOS** | 2601.02163 | ? | **92.3%** | MemCells + foresight + agentic recollection | Jan 2026 |
| **SmartSearch** | 2603.15599 | 88.4% | 91.9% | Deterministic CPU pipeline, no LLM in retrieval | Feb 2026 |
| **Memanto** | 2604.22085 | 89.8% | 87.1% | Information-theoretic retrieval (Moorcheh), typed schema, zero ingestion cost | Apr 23, 2026 |
| **APEX-MEM** | 2604.14362 | 86.2% | 88.88% | Property graph + append-only + multi-tool retrieval agent | Apr 15, 2026 |
| **TiMem** | 2601.02845 | 76.88% | 75.30% | Temporal-hierarchical memory tree | Jan 2026 |
| **MAGMA** | 2601.03236 | ? | ? | Multi-graph (semantic, temporal, causal, entity) + policy-guided traversal | Jan 2026 |
| **SGMem** | 2509.21212 | improvement | improvement | Sentence graph memory, multi-granularity | Sep 2025 |
| SimpleMem | 2601.02553 | 76.87% | ? | Lightweight baseline | Jan 2026 |
| LightMem | 2510.18866 | 68.67% | ? | Sleep-time consolidation | Oct 2025 |
| A-Mem | 2502.12110 | ~67% | ~50% | Self-organizing note graph | Feb 2025 |
| **TTMG (ours)** | — | 61.3% | 38.3% | Claim-level memory + truth maintenance | — |

**Our TTMG is 31.7pp below MemMachine SOTA and -13.3pp vs Flat RAG on LoCoMo.**

---

## 2. Training-Based Approaches (new angle)

Two papers introduce RL/preference-based training for memory management:

| System | arXiv ID | Key contribution | Result |
|--------|----------|-----------------|--------|
| **MEM1** | 2506.15841 | RL to train compact shared memory state for consolidation + reasoning; constant memory across multi-turn tasks | 3.5× performance, 3.7× memory reduction vs Qwen2.5-14B |
| **MemPO** | 2603.00680 | Self-memory policy optimization; credit assignment by memory effectiveness; agent learns to selectively retain crucial information | +25.98% absolute F1, +7.1% over prev SOTA |

**Gap:** Both train the WRITER/READER. No paper trains the RETRIEVAL SCORER.

---

## 3. Benchmarks

### LongMemEval-S (2410.10813)
- 500Q, 6 types: SSU, SSA, SSP, MS, KU, TR + 30 abstention
- SOTA now: MemMachine 93.0%

### LoCoMo (2402.17753)
- Avg 300 turns, 9K tokens, 35 sessions
- SOTA: EverMemOS 92.3%, SmartSearch 91.9%, MemMachine 91.69%

### Memora + FAMA (2604.20006) — **KEY FIRST-MOVER OPPORTUNITY**
- Weeks-to-months conversations; models must handle knowledge updates and obsolete-fact avoidance
- FAMA penalizes reliance on invalid/stale memory explicitly
- Current result: A-Mem FAMA=154.50/300, MemoryOS=106.67
- **NONE of the SOTA systems (MemMachine, Memanto, APEX-MEM, EverMemOS, SmartSearch) report FAMA scores**
- First paper to demonstrate a system that significantly improves FAMA has first-mover advantage

---

## 4. Confirmed Structural White-Space

Keyword scan of competitor/*.tex confirms **zero matches** for:
- `conformal`, `calibrat-` (in method context)
- `PMI`, `mutual information` (in retrieval scoring)
- `PAC`, `sequential test`, `Lagrang-`, `bandit`
- `forgetting-aware reranking` (beyond simple temporal weighting)
- `retrieval-time consistency` or `supersedence detection`

**What nobody does:**
1. **Calibrated/conformal retrieval** — no coverage guarantee on "does the retrieved set contain the gold evidence?"
2. **Retrieval-time supersedence detection** — no paper flags stale memories AT retrieval time (post-retrieval, pre-reader) without write-time tagging
3. **FAMA-targeted optimization** — no system explicitly optimizes for FAMA; huge first-mover opportunity
4. **Training the retrieval scorer** (MEM1/MemPO train writer/reader, not retriever)
5. **Multi-method routing with formal guarantee** — no bound on "routing to the correct memory system"

---

## 5. Key Empirical Insights

From Memanto's ablation study:
> "Retrieval recall, rather than architectural complexity, is the dominant performance driver, and modern LLMs perform the reasoning and filtering that graph-based systems attempt to pre-compute at ingestion time."

From MemMachine's ablation:
> Read-side optimizations: retrieval depth tuning (+4.2%), context formatting (+2.0%), search prompt design (+1.8%), query bias correction (+1.4%)

From Diagnosing-Memory (2603.02473):
> Retrieval method spread = 20pp; write strategy spread = 3-8pp

From our gating decomposition (project-internal):
> 88.2% of TTMG failures are retrieval-side (B+C). Write-side (A) = 11.3%.

**Consensus:** ROI is overwhelming on the read side. All top 2026 papers confirm this.

---

## 6. Threat Analysis

### 6a. Memanto (2604.22085) — partial information-theoretic threat
- Uses "information-theoretic retrieval" (Moorcheh engine: entropy-encoded binarization)
- But this is about **indexing efficiency** (32× compression, 9.6ms latency), NOT about coverage guarantees or forgetting-awareness
- White-space remains: calibrated coverage, forgetting-awareness, cross-session supersedence detection

### 6b. MemMachine (2604.04853) — accuracy SOTA threat
- 93.0% on LongMemEval-S through pure retrieval tuning. Devastating if we're trying to beat accuracy.
- But MemMachine does NOT report Memora/FAMA. FAMA-targeted systems can complement or differentiate.

### 6c. MemPO (2603.00680) / MEM1 (2506.15841) — training-side coverage
- Both train writer/reader, not retriever. Retrieval scorer training remains open.

---

## 7. Implications for Idea Generation

The field's convergence on "read-side dominates" opens exactly one clear lane: **make the retrieval step smarter without making the write-time pipeline heavier**. Concretely:

**Best-fit ideas (satisfying all hard constraints):**

1. **FAMA-targeted retrieval-time staleness reranker**: Post-retrieval consistency check that down-weights superseded memories before passing to reader. Purely read-side. Validated first on Memora/FAMA (first-mover), then LongMemEval KU/TR.

2. **Conformal retrieval coverage for memory QA**: Adaptive-k retrieval where k is set by a calibrated conformal rule guaranteeing "gold evidence is in the top-k with prob ≥ 1-α". First formal coverage guarantee in agent memory literature.

3. **PMI-weighted staleness scoring**: Discount PMI(query; memory_item) by temporal distance to query time; up-weight items where query time is within the validity interval. No write-time assumptions; works on raw timestamps.

4. **Training a retrieval reranker via memory QA preference signal**: Fine-tune a lightweight reranker on (query, retrieved_set, answer_outcome) with DPO/RLHF. Differentiates from MEM1/MemPO (they train the model, we train the retrieval scorer).

**Avoid:**
- Any method requiring write-time structural changes
- Any method that doesn't work on LoCoMo's 300-turn conversations
- Any method applicable to <50% of question types

---

## 8. Sources

Key papers:
- [MemMachine (2604.04853)](https://arxiv.org/abs/2604.04853) — 93.0% LongMemEval-S SOTA
- [Memanto (2604.22085)](https://arxiv.org/abs/2604.22085) — 89.8% LongMemEval-S, information-theoretic retrieval
- [APEX-MEM (2604.14362)](https://arxiv.org/abs/2604.14362) — 86.2% LME-S, 88.88% LoCoMo
- [Memora/FAMA (2604.20006)](https://arxiv.org/abs/2604.20006) — first-mover benchmark opportunity
- [MEM1 (2506.15841)](https://arxiv.org/abs/2506.15841) — RL for memory consolidation
- [MemPO (2603.00680)](https://arxiv.org/abs/2603.00680) — self-memory policy optimization
- [TiMem (2601.02845)](https://arxiv.org/abs/2601.02845) — temporal-hierarchical consolidation
- [EverMemOS (2601.02163)](https://arxiv.org/abs/2601.02163) — 92.3% LoCoMo
- [SmartSearch (2603.15599)](https://arxiv.org/abs/2603.15599) — deterministic CPU pipeline
- [Diagnosing-Memory (2603.02473)](https://arxiv.org/abs/2603.02473) — retrieval dominates (ICLR'26)
- [Conformal-RAG (2506.20978)](https://arxiv.org/abs/2506.20978) — conformal coverage for RAG (SIGIR'25)
- [PMI-RAG (2411.07773)](https://arxiv.org/abs/2411.07773) — PMI as retrieval performance gauge
- [SGMem (2509.21212)](https://arxiv.org/abs/2509.21212) — sentence graph memory
- [MAGMA (2601.03236)](https://arxiv.org/abs/2601.03236) — multi-graph agentic memory
- [StructMem (2604.21748)](https://arxiv.org/abs/2604.21748) — structured memory, ACL 2026
