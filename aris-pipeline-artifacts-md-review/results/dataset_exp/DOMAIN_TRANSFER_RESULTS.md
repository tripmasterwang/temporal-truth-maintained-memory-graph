# In-domain (per benchmark): TTMG vs CalLB on held-out test

Generated: 2026-04-29 (local run; see JSON `elapsed_sec` for wall times). Each dataset uses its **own** cal labels and CalLB weights (same spirit as LME-S in-domain cal → test; **not** cross-benchmark weight transfer).

## Setting

- Split: `results/dataset_exp/{perltqa,qaconv,locomo_ssu}/split_s0.json` (in-domain cal / test qids; QAConv uses train→cal, test→test).
- Calibration: LLM-labelled **cal** pool → `scripts/calibrate_lb.py` → per-dataset `lb_mlp.json` + `lb_crc.json` (`SEED=0`).
- Evaluation: `python -m experiments.eval_transfer` on **test**, `--limit 40`, methods **ttmg** vs **callb** (per-dataset CalLB weights; module name is historical).

## Test accuracy (n = 40)

| Dataset | TTMG acc | TTMG abstain | CalLB acc | CalLB abstain | Δ (CalLB − TTMG) |
|---------|----------|--------------|-----------|---------------|------------------|
| PerLTQA | 0.625 | 0.000 | 0.550 | 0.000 | −0.075 |
| QAConv (held-out test) | 0.775 | 0.100 | 0.800 | 0.000 | +0.025 |
| LoCoMo SSU | 0.625 | 0.000 | 0.525 | 0.000 | −0.100 |

Source metrics are taken from `test_*.jsonl.summary.json` under each dataset directory (`summary.accuracy`, `summary.abstain_rate`).

## LoCoMo SSU calibration (this run)

- Labelled pairs in `locomo_ssu/labels_cal.jsonl`: **736** lines (after resumed labelling).
- `calibrate_lb` MLP dev AUC: **0.796** (internal gate ≥ 0.75: **PASS**).
- CRC table: CP UCB thresholds did **not** clear at listed α (same class of “cal too small / risk” message as PerLTQA/QAConv logs); smoke coverage gate: **FAIL**.

## Engineering note

Several overlapping `eval_transfer` processes had briefly appended to the same `test_callb.jsonl`; outputs were reset and **LoCoMo callb was re-run once** to completion before locking numbers above. `test_ttmg` for LoCoMo was not restarted (summary already reflected 40/40).

## Artifact paths (repo-relative)

- `results/dataset_exp/perltqa/labels_cal.jsonl`, `lb_mlp.json`, `lb_crc.json`, `test_ttmg.jsonl.summary.json`, `test_callb.jsonl.summary.json`
- `results/dataset_exp/qaconv/labels_cal.jsonl`, `lb_mlp.json`, `lb_crc.json`, `test_ttmg.jsonl.summary.json`, `test_callb.jsonl.summary.json`
- `results/dataset_exp/locomo_ssu/labels_cal.jsonl`, `lb_mlp.json`, `lb_crc.json`, `test_ttmg.jsonl.summary.json`, `test_callb.jsonl.summary.json`, `run_locomo_label.log`
