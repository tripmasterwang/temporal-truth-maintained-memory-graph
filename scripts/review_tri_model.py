"""Tri-model peer-review loop on the current paper.

Runs three distinct reviewer personas across three different MAAS
models (qwen3-235b-a22b, Kimi-K2, glm-5), as required by the project's
"acceptance" rule: all 9 = 3 prompts x 3 models reviews must score
overall >= 8.5 before we stop iterating.

Heavy work (review generation) goes through the Chat API. This script
only orchestrates.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from review_via_maas import REVIEWER_PROMPTS, review_paper  # type: ignore


# Three models (must match api.py's MAAS_CHAT_MODEL_IDS).
MODELS = ["qwen3-235b-a22b", "Kimi-K2", "glm-5"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=MODELS)
    ap.add_argument("--personas", nargs="*", default=list(REVIEWER_PROMPTS.keys()))
    ap.add_argument("--out", default=None, help="output JSON path")
    ap.add_argument("--tag", default=time.strftime("r_%Y%m%d_%H%M"))
    args = ap.parse_args()

    out_path = Path(args.out) if args.out else (
        PROJECT_ROOT / "results" / f"review_tri_{args.tag}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict] = {}
    all_overalls = []
    below_threshold = []
    for model in args.models:
        results[model] = {}
        for persona in args.personas:
            key = f"{model}::{persona}"
            print(f"[review] {key}", flush=True)
            t0 = time.time()
            try:
                res = review_paper(persona, model)
            except Exception as e:
                res = {"error": str(e)}
            dt = time.time() - t0
            results[model][persona] = {"elapsed_sec": dt, **res}
            overall = res.get("scores", {}).get("overall")
            if isinstance(overall, (int, float)):
                all_overalls.append(overall)
                if overall < 8.5:
                    below_threshold.append((key, overall, res.get("verdict", "?")))
            print(
                f"  overall={overall}  verdict={res.get('verdict','?')}  t={dt:.1f}s",
                flush=True,
            )

    summary = {
        "avg_overall": (sum(all_overalls) / len(all_overalls)) if all_overalls else 0.0,
        "min_overall": min(all_overalls) if all_overalls else 0.0,
        "max_overall": max(all_overalls) if all_overalls else 0.0,
        "below_threshold": below_threshold,
        "target_met": (not below_threshold) and len(all_overalls) >= len(args.models) * len(args.personas),
    }
    out_path.write_text(json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False))
    print(f"\n[review] wrote {out_path}")
    print(f"[summary] avg={summary['avg_overall']:.2f}  min={summary['min_overall']:.1f}  target_met={summary['target_met']}")
    if below_threshold:
        print("[below 8.5]")
        for k, o, v in below_threshold:
            print(f"  {k}: {o} ({v})")


if __name__ == "__main__":
    main()
