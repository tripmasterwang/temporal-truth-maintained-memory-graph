#!/bin/bash
# M0 baseline runs — pair with the ttmg_beta smoke for a 3-way comparison.
# Each baseline uses identical (5 sessions × 15 questions × academic_researcher × seed=0).
# Sequential, single in-flight MAAS call (server-load policy).
#
# Run AFTER ttmg_beta smoke validates.
set -euo pipefail
cd "$(dirname "$0")/.."
source /home/workspace/lww/project0412/Auto-claude-code-research-in-sleep/.venv/bin/activate

MEMORA=/home/workspace/lww/project0412/projects/MemMachine/competitor/2604.20006_Memora_FAMA/code/Memora/data
OUTDIR=results/m0_smoke
mkdir -p "$OUTDIR"

for METHOD in flat amem; do
  OUT="$OUTDIR/m0_smoke_${METHOD}_15q.json"
  LOG="$OUTDIR/m0_smoke_${METHOD}_15q.log"
  if [ -f "$OUT" ]; then
    echo "[skip] $OUT already exists"; continue
  fi
  echo "=== launching $METHOD ==="
  uptime
  python -u -m experiments.eval_memora \
    --memora-root "$MEMORA" \
    --duration weekly \
    --personas academic_researcher \
    --method "$METHOD" \
    --max-sessions-per-persona 5 \
    --max-questions-per-persona 15 \
    --max-parallel-questions 1 \
    --output "$OUT" \
    --seed 0 2>&1 | tee "$LOG"
  echo "[done] wrote $OUT"
done

echo
echo "=== comparison ==="
python scripts/compare_methods.py \
  results/m0_smoke/m0_smoke_ttmg_beta_15q.json \
  results/m0_smoke/m0_smoke_flat_15q.json \
  results/m0_smoke/m0_smoke_amem_15q.json
