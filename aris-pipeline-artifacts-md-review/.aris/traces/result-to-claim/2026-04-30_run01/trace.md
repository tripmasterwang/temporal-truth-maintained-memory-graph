# result-to-claim trace — 2026-04-30 run01

## Skill: result-to-claim
## Date: 2026-04-30
## Codex thread: 019ddc4b-3302-78e0-bf9f-7b03ff1c92a1
## Model reasoning effort: xhigh

## Evidence collected
- LongMemEval-S N=150: pilot_n150_{ttmg,flat,amem}.json
- LongMemEval-S N=500: full500_{ttmg_v51,flat}.json
- Abstention full set N=30: abs30_{ttmg,flat}.json
- LoCoMo cross-domain N=60: locomo_{ttmg,flat,amem}.json
- Ablation (no linker) N=150: pilot_n150_abl_contradict.json
- Analysis with McNemar + CIs: analysis/n150_analysis.json
- Gating decomposition: results/gating_decomposition.json
- Latest review round 10: results/review_tri_r10.json (avg 5.5/10)

## Verdict
- overall: no
- claim_1_SSU: partial
- claim_2_abstention: partial
- claim_3_linker_causal: no
- claim_4_efficiency: partial
- claim_5_no_overall_regression: no
- claim_6_router_composition: partial
- confidence: high

## Key finding
TTMG is -6.7pp vs Flat RAG at N=150 (p=0.21) and -7.2pp at N=500. LoCoMo cross-domain: -13.3pp. SSA regression: -35pp. SSU win only 2 examples (p=0.50), does not replicate at N=500. Full abstention set ties at 76.7%. 88.2% of failures are read-side.

## Routing: no → postmortem in findings.md, recommend /idea-discovery pivot
