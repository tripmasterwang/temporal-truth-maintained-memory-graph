# research-review trace — 2026-04-30 run01

## Skill: research-review (Phase 4 of idea-discovery)
## Date: 2026-04-30
## Codex thread: 019ddcaa-d0a7-7692-8ca1-505eb8bea93e (continued from novelty-check)
## Model reasoning effort: xhigh

## Idea reviewed: CARTA (Calibrated Adaptive Retrieval with Temporal Awareness)

## Score prediction: 3/10 (weak reject / reject)
## Expected reviewer scores if submitted today: 3/4/4/5

## Strongest Objections

1. **"Incremental engineering, not a new idea"**
   - ACD is a domain adaptation of CONFLARE / C-RAG / 2511.17908 to agent memory
   - SSR is another temporal/consistency reranker (TSM, SuperLocalMemory V3, Memanto all exist)

2. **"Coverage guarantee misaligned with the task"**
   - P(gold_session ∈ top-k) ≠ P(all answer-supporting sessions ∈ top-k)
   - Especially weak on multi-session reasoning (MS) questions
   - Should be set coverage over all supporting sessions under context budget

3. **"Empirical story incomplete and compute-oblivious"**
   - SSR has no results yet (fatal at submission)
   - O(30²) = 900 NLI calls per query needs latency/cost analysis
   - No pruning ablations shown

## ACD Framing Fix
Do NOT claim "first conformal adaptive-k retrieval." Instead:
→ Frame as "coverage-calibrated session-budget selection for evolving conversational memory"
Differentiators: session (not passage), non-stationary multi-session memory, minimal budget per query.
Requirement: matched-budget comparisons against fixed-k; per-question-type analysis; ideally set coverage over all supporting sessions.

## SSR Efficiency Requirements
- Must use small NLI model (not LLM judge)
- Must report latency/cost
- Must show pruning ablations: full pairwise → later-timestamp-only → top-h semantically similar → quality vs latency curves

## FAMA Evaluation Target
- Do NOT anchor on A-Mem=154.50/300 (LangMem is the best baseline per Memora paper)
- Minimum convincing: +10 absolute overall FAMA over best reproduced baseline
- Must win on recommending/reasoning tasks (stale-memory failure modes), NOT just remembering
- A gain only on remembering is not compelling

## Backend Selection
- Use Flat + MemMachine (strongest credibility pair)
- Do NOT use Flat + Memanto as main pair (Memanto already claims conflict resolution → muddies SSR story)
- TTMG optional as third backend (shows orthogonality to write-side systems)

## Minimum Viable Paper (with SSR+15% FAMA, ACD+2pp, no regression)
- ACL/EMNLP long paper
- NOT NeurIPS/ICML without: 2 backends, efficiency analysis, significance tests, theory story

## 9/10 Upgrade Paths
1. Unified formalism: two controlled risks (missed evidence + stale evidence) in evolving-memory retrieval
2. Theorem: set coverage over all answer-supporting sessions under context budget (not single gold session)
3. SSR → principled sub-quadratic supersession module (not heuristic reranking)
4. Broad evidence: 2 backends, 3 benchmarks, cost-quality tradeoffs, human/error analysis
5. Released artifact: supersession annotations or FAMA-oriented retrieval evaluation harness

## Key Conclusion
Paper worth continuing. Becomes credible when:
- SSR shows unmistakable FAMA gains on MemMachine (recommending/reasoning)
- ACD wins at matched context budget vs fixed-k
- Conformal novelty claim is narrowed to "session-budget coverage calibration"
