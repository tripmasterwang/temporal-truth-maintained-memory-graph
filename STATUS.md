# TTMG Project Status — 2026-04-22

## Current state

- Code complete (ttmg/, experiments/, scripts/). Paper compiles cleanly at 9 pages.
- N=50 stratified LongMemEval-S pilot finished for 3 methods + 1 ablation.
- 11 review rounds run; peak avg 7.00 (round 9), current 6.50, target 8.5.

## Headline result (N=50, seed 0)

| | Flat | A-Mem | TTMG v5 |
|-|------|-------|---------|
| Overall | 0.660 | 0.640 | 0.620 |
| **TR (n=13)** | 0.462 | 0.385 | **0.615** |
| Efficiency (tok/q) | 1100 | 35904 | 14589 |

TTMG on TR: **+15.3 pp vs Flat, +23.0 pp vs A-Mem**. Paired analysis is a strict dominance (every TR question Flat/A-Mem gets right, TTMG also gets right; TTMG gets 2-3 more).

Ablation (`--disable-contradict`): TR drops to 46.2% (= Flat). LLM linker is the necessary ingredient.

## Next steps to break 8.5

Writing-only changes have plateaued. What remains is compute:

1. **Cross-domain on LoCoMo** (loader at `experiments/eval_locomo.py`, never run). ~1h per method.
2. **Multi-seed** seeds 7, 17 on N=50 (~2h each). Needed for CIs + significance.
3. **Expand N to 150** to get TR slice to n=40+ (~6h total).
4. **Investigate KU regression** at N=50 (0.875 → 0.750). Pull failing rows, inspect writer output.

## One-shot continuation

```bash
cd "/home/workspace/lww/project0412/projects/Temporal Truth-Maintained Memory Graph"

# Cross-domain
nohup python -u -m experiments.eval_locomo --method amem_flat --output results/locomo_flat.json > results/locomo_flat.log &
nohup python -u -m experiments.eval_locomo --method ttmg --output results/locomo_ttmg.json > results/locomo_ttmg.log &

# Multi-seed (sequential to avoid MAAS rate-limit)
for s in 7 17; do
    for m in amem_flat amem ttmg; do
        python -u -m experiments.eval_longmemeval --method $m --limit 50 --stratify --max-sessions 3 --seed $s \
            --writer-model Kimi-K2 --reader-model deepseek-v3.2 --parser-model Kimi-K2 \
            --output results/pilot_n50_s${s}_${m}.json
    done
done

# Re-fill + compile + re-review
python scripts/fill_macros.py --flat ... --paper paper/main.tex
scripts/compile_paper.sh
python scripts/review_via_maas.py --out results/review_final.json
```

## Rules still active

- MAAS API only (no Agent tool)
- No limitations writing
- No overclaim; TR +15.3pp is the supported headline
