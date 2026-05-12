# Experiment Tracker — CalLB

**Source plan.** `refine-logs/EXPERIMENT_PLAN.md`
**Date.** 2026-04-27
**Total runs.** 30 (28 MUST + 2 NICE). Estimated wall-clock: ~45 hr; fits Week-1 (M0 = 15 hr) + Week-2 (M1+M2+M3 = 30 hr) + Week-3 paper writing.
**Status legend.** TODO / IN_PROGRESS / DONE / FAILED / SKIPPED.

| Run ID | Milestone | Block | Purpose | System / Variant | Split | Metrics | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | M0 | B0 | LLM-judge auto-label of 10K cal pairs | `deepseek-v3.2` over (q, candidate item) | LME-S train + Memora train (40 % each) → 10K stratified subsample | LLM-judge label {LB, S, D}; latency; cost | MUST | TODO | Sequential MAAS; ~8.3 hr; checkpoint per 100 items |
| R002 | M0 | B0 | Author manual audit of judge labels | author vs `deepseek-v3.2` | 100 stratified-borderline pairs (30 % `confidence=low`) | Cohen's κ (3-class); D-vs-non-D κ; 3×3 confusion matrix | MUST | TODO | ~50 min author; spot-check by 2nd author for 20 disagreed |
| R003 | M0 | B0 | Train MLP reranker | 13-feature MLP (32 hidden, 1 logit) | 80/20 query-split of 10K labelled pairs | dev AUC on `1[label=LB]` | MUST | TODO | < 5 min CPU; Adam lr=1e-3 wd=1e-4 5 epochs |
| R004 | M0 | B0 | Compute Clopper-Pearson CRC table | CRC over 100-pt λ-grid | 600 cal-of-cal queries (held back from R003 train) | per-α `R̂_dev(λ̂_α)` for α ∈ {0.10, 0.20, 0.30, 0.40} | MUST | TODO | δ/m=0.0005; lock λ̂ table; commit hash |
| R005 | M1 | B1 | Main headline: CalLB on LongMemEval-S | CalLB (full 13-feat + CRC at α*=0.20) | LME-S full N=500 | B+C slice acc; per-question_type acc; per-α `R̂_test`; non-vacuity utility metrics | MUST | TODO | 3 seeds (0,1,2); ~3 hr × 3 seeds = ~9 hr MAAS |
| R006 | M1 | B1 | Path D `ttmg` baseline on LME-S | Path D existing reader | LME-S full N=500 | B+C slice acc; per-question_type acc | MUST | TODO | 3 seeds; ~3 hr per seed |
| R007 | M1 | B1 | MiCP-on-Path-D baseline | MiCP per-query stopping ported | LME-S full N=500 | B+C slice acc | MUST | TODO | 3 seeds; arXiv 2604.01413 ref impl |
| R008 | M1 | B1 | Stop-RAG-on-Path-D baseline | Stop-RAG iterative + RL stop ported | LME-S full N=500 | B+C slice acc | MUST | TODO | 3 seeds; arXiv 2510.14337 |
| R009 | M1 | B1 | Flat hybrid-RAG baseline | Sem + lex RRF (no claim graph) | LME-S full N=500 | B+C slice acc | MUST | TODO | 3 seeds |
| R010 | M2 | B3 | `prompt-only` attribution baseline | Path D top-k + load-bearing prompt; no MLP/CRC | LME-S full N=500 | B+C slice acc | MUST | TODO | seed 0 only; flagged single-seed |
| R011 | M2 | B3 | `rerank-only` attribution baseline | CalLB MLP ranking; flat reader prompt | LME-S full N=500 | B+C slice acc | MUST | TODO | seed 0 |
| R012 | M2 | B3 | `agreement-heuristic-only` baseline | Heuristic agreement-count rank + load-bearing prompt | LME-S full N=500 | B+C slice acc | MUST | TODO | seed 0 |
| R013 | M2 | B2 | `no_CRC` baseline (same MLP + dev-tuned fixed threshold) | CalLB MLP scores + fixed threshold | LME-S full N=500 + Memora full | B+C slice acc; per-α `R̂_test` | MUST | TODO | 3 seeds on LME-S (Path A bootstrap); 1 seed on Memora |
| R014 | M2 | B3 | `no_cross_substrate_agreement` mechanism ablation | MLP without `cross_substrate_agreement` feature | LME-S full N=500 | B+C slice acc; Class-B-fix delta | MUST | TODO | seed 0; re-train MLP |
| R015 | M2 | B3 | `no_drift_features` mechanism ablation | MLP without 4 drift features | LME-S full N=500 | KU slice acc | MUST | TODO | seed 0 |
| R016 | M2 | B3 | `no_robustness_features` mechanism ablation | MLP without {max_score, singleton_raw_turn_hit, entity_overlap} | LME-S full N=500 | Class-B-fix delta | MUST | TODO | seed 0 |
| R017 | M2 | B3 | `portable_features_only` generality ablation | MLP with 8 substrate-agnostic features | LME-S full N=500 | B+C slice acc | MUST | TODO | seed 0 |
| R018 | M2 | B5 | CalLB on Memora full | CalLB | Memora full test | aggregate FAMA per duration; per-α `R̂_test`; non-vacuity | MUST | TODO | 1 seed; cluster-bootstrap CIs |
| R019 | M2 | B5 | A-Mem on Memora full | A-Mem reimpl | Memora full test | FAMA | MUST | TODO | 1 seed |
| R020 | M2 | B5 | Mem0 on Memora full | Mem0 best-effort reproduce | Memora full test | FAMA | MUST | TODO | 1 seed |
| R021 | M2 | B5 | LightMem on Memora full | LightMem best-effort reproduce | Memora full test | FAMA | MUST | TODO | 1 seed |
| R022 | M2 | B5 | EverMemOS on Memora full (appendix only) | EverMemOS best-effort Memora-port | Memora full test | FAMA | NICE | TODO | 1 seed; appendix sub-row; skip if not buildable in 1 day |
| R023 | M2 | B6 | CalLB on LoCoMo | CalLB | LoCoMo full | LoCoMo accuracy | NICE | TODO | 1 seed; appendix |
| R024 | M2 | B6 | Path D `ttmg` on LoCoMo | Path D | LoCoMo full | LoCoMo accuracy | NICE | TODO | 1 seed; appendix |
| R025 | M2 | B6 | SmartSearch on LoCoMo | SmartSearch | LoCoMo full | LoCoMo accuracy | NICE | TODO | 1 seed; appendix |
| R026 | M3 | B2 | Path A — paired-bootstrap CalLB vs `no_CRC` | post-hoc analysis | LME-S (R005, R013) + Memora (R013, R018) | B+C slice acc delta; paired-bootstrap p over 1000 resamples | MUST | TODO | ≥ 1 pp + p < 0.05 → Path A passes |
| R027 | M3 | B2 | Path B — cross-dataset CRC threshold transfer | apply LME-S λ̂ to Memora test (and reverse) | LME-S λ̂ → Memora test; Memora λ̂ → LME-S test | empirical `R̂` on held-out corpus for both CalLB and `no_CRC` | MUST | TODO | CalLB within α + 0.06; `no_CRC` violates by > 0.10 → Path B passes |
| R028 | M3 | B7 | Class-B-rescue qualitative analysis | post-hoc on R005 seed-0 outputs | 77 Class-B examples from `gating_decomposition.json` | rescue counts by agreement bucket × singleton flag | MUST | TODO | Narrative reframe trigger if high-agreement < 30 % |
| R029 | M3 | B7 | Non-vacuity / utility metrics on L | post-hoc on R005 outputs | LME-S full N=500 at α*=0.20 | `non_empty(L)`, `mean |L|`, `LB_recall`, `LB_precision`, mean distractor frac | MUST | TODO | Targets: ≥ 0.85, [2,5], ≥ 0.75 |
| R030 | M3 | gate | **Acceptance gate decision** | analyst judgment | results from R026 + R027 | Path A or Path B passes? | MUST | TODO | If neither → activate Option F1 (workshop) or F2 (empirical-only ≥ 5 pp bar) |
