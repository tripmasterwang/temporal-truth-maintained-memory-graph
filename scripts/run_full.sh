#!/bin/bash
# One-shot pipeline AFTER pilot finishes: ablations → fill macros → compile → review
set -euo pipefail
cd "$(dirname "$0")/.."
source /home/workspace/lww/project0412/Auto-claude-code-research-in-sleep/.venv/bin/activate 2>/dev/null

TAG=${TAG:-pilot_v1}

# 1) Fill macros from pilot results
if [ -f "results/${TAG}_amem.json" ] && [ -f "results/${TAG}_ttmg.json" ]; then
  python scripts/fill_macros.py \
    --amem "results/${TAG}_amem.json" \
    --ttmg "results/${TAG}_ttmg.json" \
    --paper paper/main.tex
fi

# 2) Ablations (uses same TAG)
LIMIT=${LIMIT:-20} MAX_SESS=${MAX_SESS:-3} TAG=abl_v1 bash scripts/run_ablations.sh

# 3) Merge ablations into macros
python scripts/fill_macros.py \
  --amem "results/${TAG}_amem.json" \
  --ttmg "results/${TAG}_ttmg.json" \
  --abl-validity results/abl_v1_validity.json \
  --abl-contradict results/abl_v1_contradict.json \
  --abl-consistent results/abl_v1_consistent.json \
  --abl-emb-only results/abl_v1_embonly.json \
  --paper paper/main.tex

# 4) Compile
scripts/compile_paper.sh

# 5) Review (3 personas)
python scripts/review_via_maas.py --out results/review_round1.json

# 6) Print overall scores
python -c "
import json
d = json.load(open('results/review_round1.json'))
for p, r in d.items():
    s = r.get('scores',{}).get('overall','??')
    v = r.get('verdict','??')
    print(f'{p}: overall={s} verdict={v}')
"
