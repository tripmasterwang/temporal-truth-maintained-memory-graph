# research-refine-pipeline trace — 2026-04-30 run01

## Skill: research-refine-pipeline (Phase 4.5 of idea-discovery)
## Date: 2026-04-30
## Codex thread: 019ddcaa-d0a7-7692-8ca1-505eb8bea93e (continued from novelty-check + research-review)
## Model reasoning effort: xhigh

## Idea refined: CARTA (Calibrated Adaptive Retrieval with Temporal Awareness)

## Problem Anchor (frozen)
Evolving agent memory retrieval fails in two read-side ways: omission risk (retrieved set excludes support) + stale-inclusion risk (retrieved set contains superseded memories). CARTA controls both. No write-time restructuring claims.

## Method Refinements Applied
1. ACD framing: "coverage-calibrated session-budget selection" (NOT "first conformal adaptive-k")
2. SSR: later-timestamp-only gating reduces O(30²) → O(30·k_later)≈O(300); small NLI model required; latency/pruning ablations required
3. FAMA: must win on recommending/reasoning (not just remembering)
4. Backend: Flat + MemMachine (not Memanto — muddies SSR story)
5. Formal notation: S+(q) omission risk, S-(q) stale-inclusion risk, R_B(q) retrieved context

## Venue
Primary: EMNLP 2026 (ARR May 25, 2026) — NeurIPS 2026 deadline May 4 is impossible
Backup: ICLR 2027 (~late September 2026)

## Kill Gate
Week 1 end (May 7, 2026): SSR E2 pilot must show ≥5 absolute FAMA gain on Memora monthly+quarterly rec/reason
If negative: kill CARTA as main-track paper

## Outputs Written
- refine-logs/carta_FINAL_PROPOSAL.md
- refine-logs/carta_EXPERIMENT_PLAN.md
- refine-logs/carta_EXPERIMENT_TRACKER.md

## Day 1 Priority
1. P0: Instrument Flat RAG to store top-30 candidates with timestamps
2. E2: 100q Memora monthly+quarterly rec+reason pilot with SSR
3. E1: ACD vs fixed-k on LME-S N=500 (parallel)
