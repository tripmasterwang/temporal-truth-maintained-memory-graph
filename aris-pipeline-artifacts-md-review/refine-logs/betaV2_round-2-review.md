# Round 2 Review (GPT-5.4 xhigh, same thread) — Pivot β v2

**Thread ID:** `019dc991-2df1-79d0-8e01-d350d7638426`
**Date:** 2026-04-26
**Verdict:** REVISE
**Overall score:** 8.6 / 10 (was 7.6)
**Anchor status:** PRESERVED + better aligned

## Scores

| Dimension | R1 | R2 | Δ | Notes |
|-----------|---:|---:|---:|-------|
| Problem Fidelity | 9 | 9 | 0 | Better-aligned by leading with temporal-forgetting subset. |
| Method Specificity | 6 | 8 | +2 | Concrete enough to implement; theorem still overreaches procedure. |
| Contribution Quality | 8 | 9 | +1 | Sharp; PMI subordinate. |
| Frontier Leverage | 9 | 9 | 0 | Right machinery. |
| Feasibility | 8 | 8 | 0 | Realistic; risk = calibration sample fragmentation. |
| Validation Focus | 6 | 8 | +2 | Right shape; still busy. |
| Venue Readiness | 6 | 8 | +2 | Plausible main-track if theorem cleaned + group def made inference-time. |

## CRITICAL action items

1. **Theorem ↔ procedure alignment.** Wilson UCB is *approximate*; doesn't justify a strict finite-sample `1−δ` theorem. Adaptive search over a 50-point threshold grid needs correction over `|G|·|A|·|T|`, not just `|G|·|A|`.
   - **Fix (preferred — clean):** *Freeze candidate thresholds on dev split*; on calibration evaluate exactly *one fixed threshold per (g, α)*. Then Clopper-Pearson on a single binomial gives an exact finite-sample UCB; Bonferroni only over `|G|·|A|`.
   - **Alternative:** keep adaptive grid, replace Wilson with **Clopper-Pearson exact one-sided** + correction over `|G|·|A|·|T|`, OR use simultaneous confidence bands over the whole threshold grid (DKW / VC-style).
   - *Decision*: take the clean path — fix candidate thresholds on dev, evaluate one τ per (g, α) on calibration, exact binomial UCB.

## IMPORTANT action items

2. **`update_pattern` must be inference-time computable from the memory graph**, not from Memora-only metadata.
   - **Fix.** Define from observable graph features at query time: `n_supersede_edges(claim_key_q)`, `n_active_values(claim_key_q)`, `n_temporal_updates(claim_key_q)`, `conflict_degree(claim_key_q)`. Memora metadata only *validates* the proxy on dev; method computes from graph in deployment.

3. **Strict 3-way split hygiene.** Weight tuning, `PMI_scale`, bin boundaries, merge rules — all fixed *before* threshold calibration.
   - **Fix.** Strict protocol: **dev for score design and binning, calibration for thresholding only, test once**. Document in proposal + paper.

4. **Matched-answer-rate baseline comparison must not look post-hoc.**
   - **Fix.** Either (a) choose baseline thresholds on *dev*, or (b) make the **full risk-coverage curve** the primary comparison and the matched-rate point secondary.

## MINOR

- Drop weighted-conformal fallback from main paper (mention only as appendix/future work) unless actually implemented.
- Report per-cell counts (`n_g`) and abstention mass per cell — reviewers will check the 9 cells are genuinely populated after merging.

## Drift Warning

**NONE.** Anchor preserved + better aligned.

---

<details>
<summary>Raw GPT-5.4 response (verbatim)</summary>

This is a substantial improvement. The proposal now reads like a guarantee paper anchored to temporal truth maintenance, not like another structural-memory variant. The main remaining issue is narrow but still blocking: the theorem must match the exact threshold-selection protocol.

**Re-scores**

1. **Problem Fidelity: 9/10** — Still centered on obsolete/conflicting memory under temporal updates, and the new temporal-forgetting headline subset makes that even clearer.

2. **Method Specificity: 8/10** — The score, groups, calibration rule, abstention rule, matched-abstention comparison, and ablations are now concrete enough to implement. The remaining weakness is theorem/procedure alignment.

3. **Contribution Quality: 9/10** — The dominant contribution is now sharp: selective-risk-controlled abstention for memory under forgetting. PMI is subordinate enough not to feel like sprawl.

4. **Frontier Leverage: 9/10** — This uses exactly the right imported machinery for the white-space you identified: selective classification / CRC, not another memory-architecture tweak.

5. **Feasibility: 8/10** — The implementation budget is realistic and the evaluation is much tighter. Main risk is calibration sample fragmentation, not engineering.

6. **Validation Focus: 8/10** — Memora-first, temporal-forgetting-first, LongMemEval-S parity only, and trimmed ablations is the right shape. Still somewhat busy, but no longer bloated.

7. **Venue Readiness: 8/10** — Much closer. If the theorem is cleaned up and benchmark-specific grouping is removed, this is plausibly main-track ready as a guarantee paper.

**OVERALL: 8.6/10**

**Problem Anchor Preserved?** Yes. More than preserved: it is better aligned now.

**Dominant Contribution Sharp Enough?** Yes, mostly. "First selective-risk-controlled abstention operator for memory under forgetting" is a clean main contribution. The only caveat is that the theorem must be stated exactly at the strength the procedure really supports.

**Remaining Issues**

**CRITICAL**
- **The theorem still overreaches the written procedure.**
  Two gaps remain:
  - `Wilson UCB` is approximate; it does not justify a strict finite-sample `1-δ` theorem.
  - You adaptively search over a 50-point threshold grid, so the correction needs to cover thresholds too, not just `|G|·|A|`.

  **Concrete fix:**
  Use an exact one-sided binomial bound or a CRC theorem that matches adaptive thresholding. In practice:
  - replace Wilson in the theorem-bearing version with Clopper-Pearson / exact binomial inversion;
  - apply correction over `|G|·|A|·|T|`, or build simultaneous confidence bands over the whole threshold grid;
  - alternatively, freeze candidate thresholds on a dev split, then evaluate only one fixed threshold per `(g, α)` on calibration.

**IMPORTANT**
- **`update_pattern` must be computable at inference from the memory graph, not from Memora-only metadata.**
  Right now this reads benchmark-dependent.
  **Fix:** define it from observable graph features, e.g. number of temporal updates for the claim key, supersede-edge count, conflict degree, active-value multiplicity. Memora metadata can validate the proxy, but should not define the method.

- **Split hygiene needs to be explicit.**
  Weight tuning, `PMI_scale`, bin boundaries, and merge rules must be fixed before threshold calibration.
  **Fix:** state a strict 3-way protocol: dev for score design and binning, calibration for thresholding only, test once.

- **Matched-answer-rate baseline comparison should avoid looking post-hoc.**
  **Fix:** either choose baseline thresholds on dev, or make the full risk-coverage curve the primary comparison and the matched-rate point secondary.

**MINOR**
- Weighted-conformal fallback is probably too much for the main paper unless you actually implement it; otherwise keep it as appendix/future work.
- Report per-cell counts and abstention mass. Reviewers will ask whether the 9 cells are genuinely populated after merging.

**Verdict: REVISE**

This is now a credible guarantee-paper direction. One more pass on theorem/protocol correctness and inference-time group definition would likely move it into READY territory.

</details>
