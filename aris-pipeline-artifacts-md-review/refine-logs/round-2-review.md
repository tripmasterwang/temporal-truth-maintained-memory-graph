# Round-2 Review — CalLB (round-1 refinement)

**Reviewer:** GPT-5.4 xhigh via Codex MCP (same thread)
**Thread ID:** `019dcdd2-8a56-7c51-8017-9ac14ad3038e`
**Date:** 2026-04-27
**Overall:** **7.6 / 10 — REVISE** (up from 6.7 RETHINK)

> "Round 2 is a real improvement. The anchor is finally right, the label space is better, the
> generality claim is now honest, and the attribution story is much cleaner. The remaining blocker
> is concentrated: **the formal CRC object is still not quite the right one, and as written the
> monotonicity claim is false.**"

## Scores

| Dimension | R1 | R2 | Δ | Note |
|---|---:|---:|---:|---|
| Problem Fidelity | 8 | **8.5** | +0.5 | Now much closer to anchored bottleneck. |
| Method Specificity | 7.5 | **8.5** | +1.0 | Pipeline concrete; CRC math still not correct. |
| Contribution Quality | 5.5 | **6.5** | +1.0 | Focused, but distractor-fraction risk not monotone → CRC story doesn't go through. |
| Frontier Leverage | 7 | **8** | +1.0 | Good primitive use; small learned component. |
| Feasibility | 6 | **7** | +1.0 | Method feasible; Week 2 evaluation matrix is the bottleneck. |
| Validation Focus | 5.5 | **7.5** | +2.0 | Attribution baselines are the right correction; FAMA correctly secondary. |
| Venue Readiness | 5.5 | **7** | +1.5 | Plausible REVISE if math + supervision-validation land. |

## Lens-by-lens readout

- **L1' (CRC validity).** *Monotonicity FAILS.* `R(λ; q) = #D / max(1, #items in tier)` is **not monotone non-increasing in λ**. Counterexample: at low λ, retained set has 1 distractor + 9 good items, risk = 0.1; at higher λ, only the distractor remains, risk = 1.0. (a) Boundedness ✓. (b) Monotonicity ✗. (c) Hoeffding for *fixed* λ is fine; for *selected* λ̂_α via threshold search, current argument is invalid without monotonicity OR uniform confidence over the grid. (d) Even if math were valid, expected fraction is loosely coupled to answer accuracy.
- **L2' (label).** 3-tier `LB / S / D` is real improvement. But κ ≥ 0.65 is too weak as the gate that underwrites the theory. Need: **κ ≥ 0.7**, full confusion matrix, **D-vs-non-D agreement separately** (since the risk object depends on D), stratified audit oversampling borderline cases.
- **L3' (attribution baselines).** The 3 baselines are right. **Do NOT add `random-MLP + CRC`** (proves random scores are bad — uninformative). DO add: redefine `no_CRC` to "**same learned scores, fixed dev-tuned threshold**". This is the *correct* calibration-isolation comparison.
- **L4' (FAMA).** Parity defensible only as **secondary**, not headline. If compute tight, demote to appendix or 1-seed.
- **L5' (prompt-only).** Yes, sufficient.
- **L6' (TTMG-coupling).** Yes, sufficient. Just don't oversell portability in positioning.
- **L7' (label cost).** 10K labels @ 8.3hr is plausible. Real risk is prompt debugging + retries + Week 2 eval matrix.
- **L8 (risk vs answer-quality compositional gap).** "One distractor poisons the answer" is closer to reality than average distractor fraction. **Strongly recommend** changing the primary risk to **clean-set risk**: `R(λ; q) = 1[∃ distractor in L_λ(q)]`. This is (i) better aligned with downstream harm, (ii) **monotone under thresholding**, fixing the CRC argument. If too strict, keep distractor fraction as secondary diagnostic.
- **L9 (agreement fragility).** Real fragility. Substrates aren't independent (claim graph derived from raw-turns; semantic + lexical over same corpus). The exact Class-B failure mode (gating example: "I've got three of them" was in raw-turn but reader didn't see it) is **low-agreement** — agreement may *hurt* not help. Concrete advice:
  - Do NOT hard-code agreement as "primary Class-B fix" without pilot support.
  - Add per-substrate signals: `max single-substrate score`, per-substrate ranks, lexical entity overlap, **`singleton_raw_turn_hit`** style feature (item is high-scoring in raw-turn substrate but absent from claim-graph).
  - Pre-register an analysis of rescued Class-B examples; if most rescued are low-agreement raw-turn facts, **reframe away from agreement**.
- **L10 (timeline).** Week 2 too large for one person. Cut to: **3 seeds for core methods on primary benchmark only; 1 seed for ablations + secondary benchmarks (Memora-FAMA, LoCoMo).**

## Five most consequential revisions for round-3

### Rev-1 (FATAL math, monotonicity) — Switch primary risk to clean-set indicator

**Old:** `R(λ; q) = #D / max(1, #items in tier)` — NOT monotone in λ.
**New:** `R(λ; q) = 1[∃ distractor with score ≥ λ]` — MONOTONE non-increasing in λ for each q.

- `R(λ; q) ∈ {0, 1}` ⊂ [0, 1] ✓
- For each q: as λ ↑, the load-bearing tier shrinks (only items with score ≥ λ retained), so the event {∃ distractor} can only become more rare ✓
- `R(λ) = E_q[R(λ; q)] = Pr_q[L_λ(q) contains any distractor]` — a clean *FWER-style* probability statement
- Hoeffding-CRC over a 100-point λ-grid + union bound (δ/100 per grid point) gives valid `λ̂_α` selection
- Guarantee: `Pr_test[L_λ̂_α(q) contains any distractor] ≤ α` — directly says "load-bearing tier is clean with probability ≥ 1 − α"
- This **composes** into reader behavior: with prob ≥ 1−α, no distractor in load-bearing tier → over-specification driver removed

Keep distractor-fraction as a **secondary descriptive** diagnostic (no formal claim).

### Rev-2 (label validity) — Tighten the D-class validation protocol

- **Cohen's κ ≥ 0.7** (not 0.65) on 100-q audit — appropriate for a 3-class label that underwrites the theory.
- Report **full 3×3 confusion matrix**.
- Report **D-vs-non-D binary agreement separately** (since the risk depends only on D detection).
- **Stratified audit** with 30 % oversampling of "borderline" cases (judge expressed uncertainty / score near decision boundary).
- If audit fails: 3-call self-consistency on judge → re-label disagreed items → re-audit.

### Rev-3 (calibration-isolation baseline) — Redefine `no_CRC`

**Old `no_CRC`:** raw MLP scores top-k, no calibrated tier.
**New `no_CRC`:** same learned MLP scores + **fixed dev-tuned threshold** (e.g., median of dev scores, or threshold optimized for dev-set Class-C-prone-slice accuracy).

This is the right comparison for "CRC adds value beyond reranking". `random-MLP + CRC` is dropped (proves random scores are bad — uninformative).

### Rev-4 (de-risk the agreement story) — Add per-substrate features + pre-register agreement-rescue analysis

- **Add features**: `max_substrate_score(item)` (max over the 4 substrate scores), per-substrate ranks, **`singleton_raw_turn_hit`** (item is in raw-turn top-k but not in any other substrate's top-k — protects the gating example "I've got three of them"), `entity_overlap(q, item.content)` (lexical NER overlap).
- **Reframe positioning**: do not call `cross_substrate_agreement` the "primary Class-B fix"; call it "one of several substrate-fusion features the MLP can learn to weight".
- **Pre-register Class-B-rescue analysis**: on the 77 Class-B examples in `gating_decomposition.json`, report what fraction are rescued by CalLB and what fraction of rescues are high-agreement vs low-agreement vs singleton-raw-turn. If most rescues are low-agreement / singleton, reframe paper away from agreement to "learned multi-substrate signal fusion".

### Rev-5 (shrink Week-2 eval matrix) — 3 seeds only on core/primary, 1 seed on ablations/secondary

Cut headline configs to:
- **Primary (3 seeds)**: CalLB + Path D `ttmg` on LongMemEval-S full N=500. (= 6 runs × 30 min = 3 hr)
- **Mandatory baselines (3 seeds)**: MiCP-on-Path-D, Stop-RAG-on-Path-D, Flat hybrid-RAG on LongMemEval-S full. (= 9 runs × 30 min = 4.5 hr)
- **Attribution + mechanism + generality (1 seed)**: 7 ablations × LongMemEval-S full. (= 7 runs × 30 min = 3.5 hr)
- **Memora-FAMA (1 seed)**: CalLB + 4 baselines × Memora full. (= 5 runs)
- **LoCoMo (1 seed)**: CalLB + Path D + SmartSearch × LoCoMo full. (= 3 runs)

Total: ~30 runs ≈ ~15 hr eval. Fits Week 2 with debugging slack.

## Implications for round-3 refinement

The math + validation protocol fixes are the dominant lift. After round-3:
- Math: clean-set indicator risk → real CRC theorem with valid Hoeffding+grid bound.
- Labels: κ ≥ 0.7, D-vs-non-D separately, stratified borderline audit.
- Baselines: `no_CRC` redefined; `random-MLP+CRC` dropped; agreement-isolation analysis pre-registered.
- Eval matrix: shrunk to ~30 runs; ablations 1-seed.

If round-3 lands these cleanly, expected score should be ≥ 9 (READY).
