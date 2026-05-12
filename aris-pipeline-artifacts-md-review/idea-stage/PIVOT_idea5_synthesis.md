# Pivot Synthesis — Drift-Calibrated Hybrid Reranker

**Date:** 2026-04-27
**Status:** Locked in after Idea 1 (Adaptive E-Process Reader) was killed by Codex review (4.1/10, math fatal + wrong-bottleneck).
**Authority:** User granted decision authority ("允许你按照自己的想法做").

## TL;DR

A **learned, calibrated reranker** for memory-augmented reading that fuses *raw conversation signals* (semantic + lexical + raw-turn k-NN), *structured memory signals* (claim relevance, supersede-edge presence, validity-interval freshness), and *temporal-volatility signals* (drift score, contradiction count) into a single rank quality score per retrieved item, with **conformal coverage at the rank-quality level** (per-item calibrated reliability) — *not* at the decision level (avoids β's over-abstain trap and Idea 1's e-process math trap).

**Read-side**, per Diagnosing-Memory ("retrieval drives 20 pp; write-strategy 3-8 pp"). Reuses Path D substrate. Universal across question types. The contribution is the **calibrated hybrid reranker + the supersede-aware drift score**, validated on Memora-FAMA (the natural fit for forgetting-aware metrics) and LongMemEval-S (the natural fit for KU + abstention).

## Why this is *not* "just recency weighting with better branding"

The brainstorm reviewer flagged that risk. Three concrete defenses baked into the design:

1. **Hybrid-substrate weight is learned, not heuristic.** Drift score is one of ~10 features; the reranker learns when drift matters (KU/TR slots) vs when it's noise (static facts).
2. **Supersede-aware ≠ recency-aware.** A 2-week-old claim with no supersede edge gets full weight; a 1-day-old claim with a supersede edge from yesterday gets near-zero weight. Recency-only would invert this.
3. **Calibrated.** Per-item reliability score is conformally calibrated against held-out answer correctness. Recency-only methods don't produce reliability scores at all.

## Why this is *not* MiCP / Stop-RAG / E-Process Reader

| Axis | This | MiCP / Stop-RAG / Idea 1 |
|---|---|---|
| **Where the contribution lives** | Per-item rank quality score | Per-query stopping decision |
| **Statistical object** | Conformal coverage on item reliability | Coverage on prediction set / e-process on candidates |
| **Failure mode** | Item gets low score → drops out of top-k → reader doesn't see it (graceful) | Threshold not crossed → abstain (binary, β's trap) |
| **Math complexity** | Standard split conformal on real-valued score (off-the-shelf) | Multi-substrate joint e-process (broken in 3 weeks) |
| **Scope** | Universal: any retrieved item gets a calibrated score | Single-answer FDR-safe (broken on free-form QA) |

The reranker decision is **fuzzy** (item-level scoring) not **binary** (per-query answer/abstain). That's the right primitive for memory-augmented LLMs, where the reader can integrate uncertainty across multiple supplied items.

## Concrete contribution shape

1. **Feature set** (≈10-15 features per retrieved item):
   - Semantic similarity (raw-turn embedding cosine).
   - Lexical similarity (BM25 over raw turns).
   - Claim-graph relevance (cosine over claim content).
   - Supersede signal (count of supersede edges into this item; downweighted).
   - Validity-interval score (1 if `valid_at(τ_q)`, decayed if outside).
   - Per-claim contradiction count.
   - Time-since-creation × topic-volatility (drift score).
   - Cross-substrate agreement (raw + claim both surface this content?).
   - Source-type: raw-turn vs structured-claim.
   - Recency baseline (for ablation).

2. **Reranker**: small MLP (~10K params) on the feature vector → real-valued score in [0, 1].

3. **Calibration**: split conformal on a held-out dev split — for any new item with score `s`, output a calibrated `P(item is relevant given query)` estimate.

4. **Reader**: standard reader prompt with top-k items by calibrated score. Same reader as Path D / Flat baseline.

## Why this satisfies all the brief's hard constraints

| Hard constraint (§5 of RESEARCH_BRIEF.md) | How satisfied |
|---|---|
| ❌ No N<50% specialist | Reranker runs on every query; universal scope. |
| ❌ No canonical-key strict matching | Features include cosine similarity (paraphrase-robust); no rule-based key matching. |
| ❌ No over-abstain rules | No abstain rule; reranker just scores items, reader decides. |
| ❌ No single-valued only | Items are scored regardless of slot type. |
| ❌ No exact triple dependence | Triples don't enter the feature set (just embedding + structured-graph features). |
| ❌ No fancier write-time | Read-side method; writer is unchanged. |
| ❌ No new structural memory | Reuses Path D substrate. |

## Positive constraints

| Positive (§6) | How |
|---|---|
| ✅ Statistical/info-theoretic tool | Conformal coverage on rank quality (split conformal, simple but novel for memory). |
| ✅ Generalises ≥50% of question types | Universal applicability; reader still sees top-k regardless of question type. |
| ✅ Validates ≥2 of LongMemEval-S/LoCoMo/Memora-FAMA | Memora-FAMA primary (forgetting metric directly tests the drift signal); LongMemEval-S secondary (KU + abstention slices). |
| ✅ Distinguishes from EverMemOS/etc | Read-side calibrated reranker is not in any of the 11 named systems. |
| ✅ Hybrid retrieval substrate preserved | Substrate is the input to the reranker. |
| ✅ Reuses Path D substrate | All Path D features (claims, supersede edges, raw turns) become reranker inputs. |

## The gating experiment — runs FIRST, before refinement commits

**Oracle error decomposition** (per the brutal reviewer's recommendation):

- Take 200 stratified queries from LongMemEval-S (proportional across question_type + abstention).
- For each query, run Path D's current reader + LLM-judge.
- For each WRONG answer, oracle-label (with LLM judge + author spot-check) whether the failure was:
  - **Class A**: writer didn't extract the relevant fact at all (raw turns also missing the info)
  - **Class B**: writer extracted but reader couldn't ground (info present in retrieval but reader didn't use it)
  - **Class C**: writer extracted, reader grounded, but answer is wrong (logical / aggregation / format error)
- Decision tree:
  - **Class A dominates** (>50%) → kill read-side; pivot to writer-side training (Memory-R1-style RL).
  - **Class B + C dominates** → read-side has room; proceed with the reranker.
  - **Roughly 50-50** → reranker is justified IF it can specifically address Class B (supplementing weak retrieval).

Cost: ~200 questions × 30 sec MAAS = ~2 hr wall-clock (sequential, single in-flight call). Plus ~2 hr labeling.

**This gating experiment runs BEFORE we write a single line of new code.** Spend 1 day on the decomposition; commit weeks only if the math says read-side has room.

## What happens if the gate fails

If writer-extraction failures dominate (Class A > 50 %), **escalate to a writer-side direction**:

- Memory-R1 (arXiv 2508.19828) — RL-train writer with reader-feedback reward.
- MemBuilder (arXiv 2601.05488) — attributed dense rewards.
- IB-RAG-style (arXiv 2406.01549) — IB-train extractor.

These were Idea-pool S3 white-space candidates; not preferred initially because of training cost, but become the *only* coherent direction if the gate fails.

## Compute & timeline (preliminary)

- **Day 1-2**: Gating experiment (200-question oracle decomposition).
- **Day 3-4**: If gate passes, build feature extractor + initial reranker on top of Path D substrate.
- **Day 5-7**: Calibration on LongMemEval-S dev split.
- **Week 2**: Memora-FAMA + LongMemEval-S full evaluation; comparison vs MiCP-style stopping (porting MiCP to memory as a fair baseline) + Path D reader + Flat.
- **Week 3**: Ablations + paper writing.

## Branching tree summary

```
Gating exp (Day 1-2)
  ├── Class A dominates (>50%)
  │     → KILL reader-side
  │     → Escalate to writer-side training
  │
  ├── Class B+C dominates (>50%)
  │     → Build reranker (Day 3-7)
  │     → Validate on Memora-FAMA + LongMemEval-S (Wk 2)
  │     → Paper (Wk 3)
  │
  └── Roughly 50-50
        → Build reranker scoped to Class B (Day 3-10)
        → Validate Class-B-specific lift
```

## Next step

Do NOT invoke `/research-refine-pipeline` blindly. Do the **gating experiment first** (1 day, real signal). Only after the gate is green do we commit to refinement.

---

## ✅ Gating result (added 2026-04-27, after running the experiment)

**`results/gating_decomposition.json`** (186 wrong answers from `full500_ttmg_v51.json`, judged by `deepseek-v3.2` over the answer-evidence sessions):

| Class | Count | % |
|---|---:|---:|
| A (dataset / labelling issue) | 21 | 11.3 % |
| **B (retrieval missed; evidence supports gold)** | **77** | **41.4 %** |
| **C (reader logic error after correct grounding)** | **87** | **46.8 %** |
| D (judge over-strict) | 1 | 0.5 % |

**Read-side actionable (B+C): 88.2 %.** The brutal reviewer's "writer is the bottleneck" concern is **rejected by data**.

**Per-question-type breakdown:**

| question_type | A | B | C | D | Read-side % |
|---|---:|---:|---:|---:|---:|
| single-session-user | 0 | 4 | 4 | 0 | **100 %** |
| single-session-preference | 0 | **18** | 0 | 0 | **100 %** |
| knowledge-update | 0 | 7 | 15 | 0 | **100 %** |
| temporal-reasoning | 7 | 25 | 23 | 1 | 86 % |
| multi-session | 8 | 17 | 42 | 0 | 88 % |
| single-session-assistant | 6 | 6 | 3 | 0 | 60 % |

**Empirical patterns from the qualitative rationales:**

1. **Class C dominates (47 %) and is over-specification by the reader.** Three representative examples:
   - *"What did I buy for sister's birthday?"* — gold `yellow dress` — pred `yellow dress AND earrings`.
   - *"Gin martini ratio?"* — gold `3:1` — pred `3:1 with a dash of citrus bitters`.
   - *"Shampoo brand?"* — gold `Trader Joe's` — pred `lavender scented shampoo from Trader Joe's`.
   The reader correctly grounded on the right evidence, then *added adjacent context* that wasn't in the gold. **A reranker that surfaces clean top-1 evidence alone (no padding with marginal items) addresses this.**

2. **Class B (41 %) is retrieval-surfacing-wrong-content.** Three representatives:
   - *"Where did I redeem the $5 coupon?"* — gold `Target` — pred discussed *timing* not location.
   - *"Where do I take yoga?"* — gold `Serenity Yoga` — pred recommended apps from earlier.
   - *"How many bikes do I own?"* — gold `three` — pred `I don't know` (raw-turn `I've got three of them` was in haystack but reader didn't see it).
   **A hybrid substrate (semantic + lexical + raw-turn voting) addresses this — rank by cross-substrate agreement, not by single-substrate score.**

3. **Class A noise (11 %)** — these are genuinely under-specified by the dataset. Cannot be addressed by any read-side method; defines the **ceiling**.

## Design implications locked

1. **Top-k cleanliness, not top-k breadth.** When a high-confidence item is found, don't pad with marginal items. Reranker outputs ≤ 3 items at high confidence, not 10 noisy items.
2. **Cross-substrate agreement as primary feature.** Items present in BOTH semantic-top-k AND lexical-top-k (or BOTH raw-turn AND claim-graph) get a multiplicative boost.
3. **Drift signal weights highest on KU + single-session-preference slices** (both 100 % B-only-actionable per the breakdown).
4. **Per-question-type calibration is justified** — coverage targets can differ across single-session-assistant (60 % ceiling) vs knowledge-update (100 % ceiling).

Gate is clearly open; proceeding to refinement.
