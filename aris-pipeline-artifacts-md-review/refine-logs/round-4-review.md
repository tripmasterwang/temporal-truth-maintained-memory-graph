# Round-4 Review (FINAL) — CalLB (round-3 refinement)

**Reviewer:** GPT-5.4 xhigh via Codex MCP (same thread)
**Thread ID:** `019dcdd2-8a56-7c51-8017-9ac14ad3038e`
**Date:** 2026-04-27
**Overall:** **9.0 / 10 — READY** ✓

> "This is now **READY for `/experiment-plan` handoff**. No pivot is needed at the proposal stage."
> "The remaining uncertainty is now empirical, not framing-level. The proposal is sharp enough to proceed exactly as written."

## Scores

| Dimension | R1 | R2 | R3 | R4 | Δ R3→R4 |
|---|---:|---:|---:|---:|---:|
| Problem Fidelity | 8 | 8.5 | 9 | **9.5** | +0.5 |
| Method Specificity | 7.5 | 8.5 | 9 | **9.0** | 0 |
| Contribution Quality | 5.5 | 6.5 | 8 | **9.0** | +1.0 |
| Frontier Leverage | 7 | 8 | 8.5 | **8.8** | +0.3 |
| Feasibility | 6 | 7 | 8.5 | **8.8** | +0.3 |
| Validation Focus | 5.5 | 7.5 | 8 | **9.0** | +1.0 |
| Venue Readiness | 5.5 | 7 | 8 | **8.8** | +0.8 |

## Verdict

**READY** — score 9.0 (≥ threshold 9). No further refinement rounds required (MAX_ROUNDS=4 reached anyway).

## Critical-lens final verdict

- **L1''** ✓ Clean-set indicator risk is the right repair. Monotonicity holds, fixed-grid Clopper-Pearson + union-bound is valid, bound now informative at α = 0.20 and usable at α = 0.10.
- **L2''** ✓ Supervision-validation strong enough for the 3-class label that underwrites the theory.
- **L3''** ✓ The 4 attribution baselines are sufficient to answer "the calibration isn't doing the work".
- **L4''** ✓ Robustness features + pre-registered Class-B rescue analysis are enough; prevent overclaim if agreement doesn't carry the load.
- **L5''** ✓ 31-run matrix realistic for 1 person in Week 2.
- **L6''** ✓ With right wording: novelty is NOT new CRC theory — it's a **new clean-set risk object for reader-visible memory evidence selection**. Defensible main-track.
- **L7''** Fallback "formal-guarantee-only" paper is still not the main-track target, but the **Path A / Path B gate handles this correctly**.

## Operational requirement

> "The only thing I would insist on operationally is: **honor the pre-committed venue logic**. If neither Path A nor Path B lands, do not rationalize it into a main-track theory paper after the fact."

## Next step

Proceed to `/experiment-plan` to formalize the experiment roadmap (Week-1 build + label + calibrate; Week-2 31-run eval matrix; Week-3 paper).
