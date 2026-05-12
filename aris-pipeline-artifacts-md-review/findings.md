# Research Findings — TTMG Project

---

## Result-to-Claim Gate: 2026-04-30

### Verdict: `no` (provisional — no integrity audit)

**Codex judgment:** The current results are NOT sufficient to support a coherent, defensible NeurIPS/ICML paper. The data supports a weaker, reframed story only.

---

### Per-Claim Breakdown

| # | Claim | Verdict | Confidence |
|---|-------|---------|-----------|
| 1 | SSU: 100% vs 90.5% Flat (paired 2-0) | `partial` | high |
| 2 | Abstention behavioral advantage | `partial` | high |
| 3 | LLM linker is causally necessary | `no` | high |
| 4 | Efficiency: ~59.4% fewer tokens than A-Mem | `partial` | high |
| 5 | Overall accuracy "statistically indistinguishable" from Flat | `no` | high |
| 6 | Router composition recovers Flat accuracy | `partial` | high |

**Overall verdict:** `no`

---

### What the Data Actually Shows

**Supported:**
- TTMG reduces token usage ~59% vs A-Mem reimpl (14,589 vs 35,904 tokens/q)
- Linker removal hurts most slices (overall -2.6pp, TR -5pp, KU -8.7pp)
- On the tiny N=9 abstention subset within N=150, TTMG is 8/9 vs Flat 4/9 (trend-level)
- Router variants numerically match Flat RAG on N=150

**Not Supported / Contradicted:**
- SSU win: only 2 examples (paired 2-0, p=0.50), does NOT replicate at N=500 (TTMG 88.6% vs Flat 92.9%)
- Full abstention N=30: BOTH systems tie at 76.7%; TTMG's explicit abstain rate is only 3.3% (1/30)
- Overall accuracy: directionally worse at N=150 (-6.7pp, p=0.21), confirmed worse at N=500 (-7.2pp)
- "No regression" claim: non-significant McNemar ≠ equivalence; larger data shows clear regression
- Linker "drops every slice": MS improves slightly with linker removed (45% → 50%); SSP unchanged
- Cross-domain LoCoMo: TTMG 38.3% vs Flat 51.7% (**-13.3pp**, major regression)
- SSA regression: TTMG 58.8% vs Flat 94.1% at N=150, TTMG 73.2% vs Flat 94.6% at N=500

---

### Hypotheses for Why TTMG Underperforms

1. **SSA/SSP regressions**: Claim schema is designed for user-authored facts; assistant-authored content and preference tracking have different linguistic patterns that the claim schema fails to canonicalize. Writer extracts too-narrow (subject, predicate) pairs, losing the broader context that Flat RAG's raw text preserves.

2. **MS regression**: Cross-session fact linking requires coreference that the S/P gate misses. Writer splits coreferent facts across sessions; retriever can't aggregate.

3. **LoCoMo regression**: Longer conversations (avg 300 turns vs LongMemEval's ~53 sessions) cause claim graph to become noisy; flat hybrid retrieval stays robust because it indexes raw text. The 88.2% read-side actionable rate from gating decomposition suggests truth-maintenance edges aren't the bottleneck — basic retrieval quality is.

4. **Structural white-space misalignment**: Gating analysis shows 88.2% of failures are retrieval-side (B+C), not write-side (A). Adding more write-time structure (validity intervals, supersede edges) doesn't address the dominant failure mode.

---

### Constraints for Future Attempts (What NOT to Try Again)

1. ❌ A write-time-heavy method when 88.2% of failures are retrieval-side
2. ❌ Claiming "no overall regression" with underpowered N=150 and negative N=500 trend
3. ❌ Leading with SSU/abstention slice wins when overall is -7pp vs Flat RAG baseline
4. ❌ Cross-domain validation with LoCoMo when the system regresses -13pp there
5. ❌ Claiming behavioral differences (abstain_rate=3.3%) as meaningful abstention advantage
6. ❌ Router composition that only recovers baseline (not exceeds it) as a main contribution
7. ❌ Ablation claiming "linker drops every slice" when MS and SSP are flat/improved without it

---

### Review Score History
- Round 10 (2026-04-30): avg 5.5/10 (Kimi-K2: 6.5, glm-5.1: 4.5)
- Target: 8.5
- 12 review rounds completed; peak 7.0 (round 9)

---

### Next Decision

Given that:
- Current TTMG design underperforms Flat RAG overall (+/-7pp) and cross-domain (-13pp)
- 88.2% of failures are read-side — retrieval, not truth-maintenance, is the bottleneck
- Path D (validity-interval specialist) and Path β (conformal-selective) also failed
- RESEARCH_BRIEF.md identifies statistical/information-theoretic machinery as the structural white-space

**Recommended route:** Re-run `/idea-discovery` using RESEARCH_BRIEF.md as grounding (post-Path-D, post-β, post-current-TTMG constraints). The new idea must:
- Attack read-side (retrieval, routing, scoring) rather than write-side
- Apply to ≥50% of question types (not a specialist)
- Have ≥50% LoCoMo applicability (no LoCoMo regression)
- Bring statistical/info-theoretic machinery from outside the memory subfield

**Alternative (lower-bar):** Reframe current paper for an ICLR/AAAI workshop venue with honest claims: "TTMG is a behavioral architecture study — it changes how abstention works but does not improve overall accuracy." This is defensible if explicitly framed as an analysis/system paper, not a positive-result methods paper.

---

*Verdict generated: 2026-04-30 via /result-to-claim, Codex judge (xhigh reasoning effort)*

---

## Idea Discovery: 2026-04-30

**Pipeline run:** /idea-discovery (research-lit → idea-creator → novelty-check → research-review → research-refine-pipeline)  
**New direction:** CARTA (Calibrated Adaptive Retrieval with Temporal Awareness)  
**Status:** Kill gate pending (SSR pilot E2 by May 7, 2026)

### Outcome Summary

- 12 ideas generated → 9 survived first-pass filtering → CARTA (ACD+SSR) recommended
- ACD pilot (oracle analysis): gold coverage k=3=84%, k=5=92%; +11.5pp accuracy gap
- Novelty: ACD=4/10 (reframe as session-budget coverage calibration), SSR=6/10 (no prior read-time NLI without write-time tagging), CARTA=6-7/10
- Review prediction: 3/10 (reject) with pilot only → ACL/EMNLP-viable with SSR results
- Problem anchor: omission risk (P[S+(q) ⊄ R_B(q)]) + stale-inclusion risk (P[S-(q) ∩ R_B(q) ≠ ∅])
- Venue: EMNLP 2026 ARR May 25 (NeurIPS 2026 deadline May 4 — impossible)

### CARTA Design

- ACD: Adaptive k via split conformal prediction; "coverage-calibrated session-budget selection" NOT "first conformal k"
- SSR: Later-timestamp-only NLI gating (O(30·k_later)≈O(300)); DeBERTa-v3-small; targets FAMA recommending/reasoning
- Backend: Flat RAG + MemMachine (NOT Flat + Memanto — muddies SSR story)

### Kill Gate (hard)
If E2 (100q Memora monthly+quarterly rec/reason pilot) shows <5 absolute FAMA gain by May 7 → kill CARTA as main-track paper.

### Files
- Full report: `idea-stage/IDEA_REPORT.md`
- Proposal: `refine-logs/carta_FINAL_PROPOSAL.md`
- Experiment plan: `refine-logs/carta_EXPERIMENT_PLAN.md`
- Tracker: `refine-logs/carta_EXPERIMENT_TRACKER.md`
