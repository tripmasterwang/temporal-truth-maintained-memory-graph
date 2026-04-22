#!/bin/bash
# Run the four TTMG ablations on the same stratified slice as the pilot.
set -euo pipefail
cd "$(dirname "$0")/.."

LIMIT=${LIMIT:-20}
MAX_SESS=${MAX_SESS:-3}
SEED=${SEED:-0}
TAG=${TAG:-abl_v1}
WRITER_MODEL=${WRITER_MODEL:-Kimi-K2}
READER_MODEL=${READER_MODEL:-deepseek-v3.2}

source /home/workspace/lww/project0412/Auto-claude-code-research-in-sleep/.venv/bin/activate 2>/dev/null

run () {
  local name="$1"; shift
  echo "-- ablation $name --"
  python -u -m experiments.eval_longmemeval \
    --method ttmg \
    --limit "$LIMIT" --stratify --max-sessions "$MAX_SESS" --seed "$SEED" \
    --writer-model "$WRITER_MODEL" --reader-model "$READER_MODEL" \
    --parser-model "$WRITER_MODEL" \
    --output "results/${TAG}_${name}.json" \
    "$@" 2>&1 | tee "results/${TAG}_${name}.log" | \
    grep -E "\[eval\]|corr=|summary|running_acc|wrote"
}

# (a) drop validity intervals
run validity --disable-temporal --disable-supersede-flag

# (b) drop contradict/supersede edges (linker disabled)
run contradict --disable-contradict

# (c) drop max-consistent-subgraph selection
run consistent --disable-consistent-subgraph

# (d) drop LLM linker in favour of writer-only flat claims
run embonly --disable-contradict --disable-writer-claims

echo "== Ablations done. =="
