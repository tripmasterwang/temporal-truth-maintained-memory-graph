#!/bin/bash
# Run a small stratified pilot on LongMemEval-S for A-Mem + TTMG (sequential,
# same subset) so the comparison is paired.
set -euo pipefail
cd "$(dirname "$0")/.."

LIMIT=${LIMIT:-20}
MAX_SESS=${MAX_SESS:-3}
SEED=${SEED:-0}
TAG=${TAG:-pilot}
WRITER_MODEL=${WRITER_MODEL:-Kimi-K2}
LINKER_MODEL=${LINKER_MODEL:-Kimi-K2}
PARSER_MODEL=${PARSER_MODEL:-Kimi-K2}
READER_MODEL=${READER_MODEL:-deepseek-v3.2}

echo "== Pilot: LIMIT=$LIMIT  MAX_SESS=$MAX_SESS  SEED=$SEED  TAG=$TAG =="
source /home/workspace/lww/project0412/Auto-claude-code-research-in-sleep/.venv/bin/activate 2>/dev/null

# A-Mem baseline
echo ""
echo "-- A-Mem --"
python -u -m experiments.eval_longmemeval \
  --method amem \
  --limit "$LIMIT" --stratify --max-sessions "$MAX_SESS" --seed "$SEED" \
  --writer-model "$WRITER_MODEL" --reader-model "$READER_MODEL" \
  --output "results/${TAG}_amem.json" 2>&1 | tee "results/${TAG}_amem.log" | \
  grep -E "\[eval\]|corr=|summary|running_acc|wrote"

# TTMG full
echo ""
echo "-- TTMG (full) --"
python -u -m experiments.eval_longmemeval \
  --method ttmg \
  --limit "$LIMIT" --stratify --max-sessions "$MAX_SESS" --seed "$SEED" \
  --writer-model "$WRITER_MODEL" --reader-model "$READER_MODEL" \
  --parser-model "$PARSER_MODEL" \
  --output "results/${TAG}_ttmg.json" 2>&1 | tee "results/${TAG}_ttmg.log" | \
  grep -E "\[eval\]|corr=|summary|running_acc|wrote|writer|linker"

echo ""
echo "== Pilot done. Filling paper macros. =="
python scripts/fill_macros.py \
  --amem "results/${TAG}_amem.json" \
  --ttmg "results/${TAG}_ttmg.json" \
  --paper paper/main.tex

echo ""
echo "== Recompiling paper =="
scripts/compile_paper.sh
