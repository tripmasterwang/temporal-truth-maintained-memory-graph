#!/usr/bin/env bash
# R001: LLM-judge auto-labelling.
# Uses Kimi-K2 writer + max_sessions=3 to match full500_ttmg_v51 baseline
# exactly — the CRC threshold trained here only transfers to M1 evaluation
# if both sides see the same memory state.
# Estimated: 200 questions × ~97 s ingest + ~125 s judge = ~12 hr.
# Resumable: re-running skips already-labelled pairs.
# Usage: bash scripts/run_r001.sh [max_questions=200]
set -euo pipefail

MAX_Q="${1:-200}"
OUT="results/lb_calibration_labels.jsonl"
LOG="results/r001_label_log.txt"

cd "$(dirname "$0")/.."
source /home/workspace/lww/project0412/Auto-claude-code-research-in-sleep/.venv/bin/activate

echo "[r001] Starting R001: max_questions=$MAX_Q, max_sessions=3, writer=Kimi-K2, judge=deepseek-v3.2"
echo "[r001] GPU: CUDA_VISIBLE_DEVICES=5"
echo "[r001] Log: $LOG"
date >> "$LOG"

nohup env CUDA_VISIBLE_DEVICES=5 python -u scripts/label_lb_pairs.py \
    --max-questions "$MAX_Q" \
    --max-sessions 3 \
    --writer-model Kimi-K2 \
    --judge-model deepseek-v3.2 \
    --out "$OUT" \
    >> "$LOG" 2>&1 &

PID=$!
echo "[r001] PID=$PID  tail -f $LOG"
echo "$PID" > results/r001_pid.txt
