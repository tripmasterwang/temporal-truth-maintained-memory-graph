#!/usr/bin/env bash
# R003-SSU: Re-train MLP + lock CRC thresholds on single-session-user subset.
# Reads lb_calibration_labels.jsonl, filters to question_type=single-session-user
# (70 qids, ~1100 pairs), trains MLP, runs CRC calibration.
# Output: results/lb_mlp_ssu.json + results/lb_crc_ssu.json
# CPU-only (no GPU needed), runs in <2 min.
set -euo pipefail

cd "$(dirname "$0")/.."
source /home/workspace/lww/project0412/Auto-claude-code-research-in-sleep/.venv/bin/activate

echo "[r003-ssu] Re-training MLP+CRC on single-session-user subset"
python scripts/calibrate_lb.py \
    --labels results/lb_calibration_labels.jsonl \
    --question-type single-session-user \
    --mlp-out results/lb_mlp_ssu.json \
    --crc-out results/lb_crc_ssu.json \
    --epochs 10 \
    --train-frac 0.80 \
    --cal-of-dev-frac 0.50 \
    --seed 0

echo "[r003-ssu] Done."
