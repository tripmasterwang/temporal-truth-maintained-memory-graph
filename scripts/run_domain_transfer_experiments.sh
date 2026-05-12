#!/usr/bin/env bash
# Domain CalLB on PerLTQA, QAConv (trn/tst disjoint), LoCoMo SSU:
#   split -> label (cal pool) -> calibrate_lb -> eval_transfer (test pool) x2 methods
#
# Usage (from repo root, venv activated):
#   export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1   # after HF embed cache exists
#   CAL_MAX=40 TEST_MAX=40 ./scripts/run_domain_transfer_experiments.sh
#
# Heavy: MAAS writer + judge. Tune CAL_MAX / TEST_MAX for budget.

set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="results/dataset_exp"
CAL_MAX="${CAL_MAX:-40}"
TEST_MAX="${TEST_MAX:-40}"
SEED="${SEED:-0}"

mkdir -p "$ROOT/perltqa" "$ROOT/qaconv" "$ROOT/locomo_ssu"

echo "=== [1/3] PerLTQA: split + label(cal) + calibrate + eval(test) ttmg/callb ==="
python scripts/label_lb_dataset.py --dataset perltqa \
  --split-json "$ROOT/perltqa/split_s${SEED}.json" --write-split-only --split-seed "$SEED" --cal-frac 0.70
python scripts/label_lb_dataset.py --dataset perltqa \
  --split-json "$ROOT/perltqa/split_s${SEED}.json" --eval-set cal --max-questions "$CAL_MAX" \
  --out "$ROOT/perltqa/labels_cal.jsonl"
python scripts/calibrate_lb.py --labels "$ROOT/perltqa/labels_cal.jsonl" \
  --mlp-out "$ROOT/perltqa/lb_mlp.json" --crc-out "$ROOT/perltqa/lb_crc.json" --seed "$SEED"
python -m experiments.eval_transfer --bench perltqa --method ttmg \
  --split-json "$ROOT/perltqa/split_s${SEED}.json" --eval-set test --limit "$TEST_MAX" \
  --out "$ROOT/perltqa/test_ttmg.jsonl"
python -m experiments.eval_transfer --bench perltqa --method callb \
  --split-json "$ROOT/perltqa/split_s${SEED}.json" --eval-set test --limit "$TEST_MAX" \
  --callb-model "$ROOT/perltqa/lb_mlp.json" --callb-crc "$ROOT/perltqa/lb_crc.json" \
  --out "$ROOT/perltqa/test_callb.jsonl"

echo "=== [2/3] QAConv: trn=tst disjoint split + label(train) + calibrate + eval(test) ==="
python scripts/label_lb_dataset.py --dataset qaconv \
  --split-json "$ROOT/qaconv/split_s${SEED}.json" --write-split-only --split-seed "$SEED"
python scripts/label_lb_dataset.py --dataset qaconv \
  --split-json "$ROOT/qaconv/split_s${SEED}.json" --eval-set cal --max-questions "$CAL_MAX" \
  --out "$ROOT/qaconv/labels_cal.jsonl"
python scripts/calibrate_lb.py --labels "$ROOT/qaconv/labels_cal.jsonl" \
  --mlp-out "$ROOT/qaconv/lb_mlp.json" --crc-out "$ROOT/qaconv/lb_crc.json" --seed "$SEED"
python -m experiments.eval_transfer --bench qaconv --method ttmg \
  --split-json "$ROOT/qaconv/split_s${SEED}.json" --eval-set test --limit "$TEST_MAX" \
  --out "$ROOT/qaconv/test_ttmg.jsonl"
python -m experiments.eval_transfer --bench qaconv --method callb \
  --split-json "$ROOT/qaconv/split_s${SEED}.json" --eval-set test --limit "$TEST_MAX" \
  --callb-model "$ROOT/qaconv/lb_mlp.json" --callb-crc "$ROOT/qaconv/lb_crc.json" \
  --out "$ROOT/qaconv/test_callb.jsonl"

echo "=== [3/3] LoCoMo SSU: split + label(cal) + calibrate + eval(test) ==="
python scripts/label_lb_dataset.py --dataset locomo-ssu \
  --split-json "$ROOT/locomo_ssu/split_s${SEED}.json" --write-split-only --split-seed "$SEED" --cal-frac 0.70 \
  --locomo-data "/home/workspace/lww/project0412/projects/dataset/locomo-main/data/locomo10.json"
python scripts/label_lb_dataset.py --dataset locomo-ssu \
  --split-json "$ROOT/locomo_ssu/split_s${SEED}.json" --eval-set cal --max-questions "$CAL_MAX" \
  --out "$ROOT/locomo_ssu/labels_cal.jsonl" \
  --locomo-data "/home/workspace/lww/project0412/projects/dataset/locomo-main/data/locomo10.json"
python scripts/calibrate_lb.py --labels "$ROOT/locomo_ssu/labels_cal.jsonl" \
  --mlp-out "$ROOT/locomo_ssu/lb_mlp.json" --crc-out "$ROOT/locomo_ssu/lb_crc.json" --seed "$SEED"
python -m experiments.eval_transfer --bench locomo-ssu --method ttmg \
  --split-json "$ROOT/locomo_ssu/split_s${SEED}.json" --eval-set test --limit "$TEST_MAX" \
  --locomo-data "/home/workspace/lww/project0412/projects/dataset/locomo-main/data/locomo10.json" \
  --out "$ROOT/locomo_ssu/test_ttmg.jsonl"
python -m experiments.eval_transfer --bench locomo-ssu --method callb \
  --split-json "$ROOT/locomo_ssu/split_s${SEED}.json" --eval-set test --limit "$TEST_MAX" \
  --locomo-data "/home/workspace/lww/project0412/projects/dataset/locomo-main/data/locomo10.json" \
  --callb-model "$ROOT/locomo_ssu/lb_mlp.json" --callb-crc "$ROOT/locomo_ssu/lb_crc.json" \
  --out "$ROOT/locomo_ssu/test_callb.jsonl"

python3 << 'PY'
import json
from pathlib import Path

def acc(p):
    lines = [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return None, 0
    return sum(r["correct"] for r in lines) / len(lines), len(lines)

root = Path("results/dataset_exp")
for name in ["perltqa", "qaconv", "locomo_ssu"]:
    a = root / name / "test_ttmg.jsonl"
    b = root / name / "test_callb.jsonl"
    if a.is_file() and b.is_file():
        ta, na = acc(a)
        tb, nb = acc(b)
        print(f"{name}: ttmg={ta:.3f} n={na}  callb={tb:.3f} n={nb}  delta={tb-ta:+.3f}")
PY

echo "Done. Artifacts under $ROOT/{perltqa,qaconv,locomo_ssu}/"
