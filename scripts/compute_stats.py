"""Compute Wilson CI and paired McNemar for pilot result JSONs.

Output is both printable and a dict of macros ready to splice into main.tex.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def wilson_ci(k: int, n: int, z: float = 1.96) -> Tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return p, max(0.0, c - h), min(1.0, c + h)


def mcnemar_exact(b: int, c: int) -> float:
    """One-sided exact McNemar p-value for TTMG > baseline, where b is
    baseline-correct-ttmg-wrong and c is ttmg-correct-baseline-wrong.
    """
    n = b + c
    if n == 0:
        return 1.0
    p = 0.0
    for k in range(c, n + 1):
        p += math.comb(n, k) * (0.5 ** n)
    return p


def _load(path: str | None):
    if not path or not Path(path).exists():
        return None
    with open(path) as fh:
        return json.load(fh)


def slice_stats(rows: List[dict], slice_filter=None) -> Dict[str, dict]:
    by_type: Dict[str, List[int]] = defaultdict(list)
    for r in rows:
        if slice_filter and not slice_filter(r):
            continue
        by_type[r["question_type"]].append(int(r["correct"]))
    out = {}
    for k, vs in by_type.items():
        p, lo, hi = wilson_ci(sum(vs), len(vs))
        out[k] = {"n": len(vs), "k": sum(vs), "acc": p, "lo": lo, "hi": hi}
    out["overall"] = {
        "n": sum(v["n"] for v in out.values()),
        "k": sum(v["k"] for v in out.values()),
    }
    if out["overall"]["n"]:
        p, lo, hi = wilson_ci(out["overall"]["k"], out["overall"]["n"])
        out["overall"].update(acc=p, lo=lo, hi=hi)
    return out


def paired_vs(ref_rows: List[dict], ttmg_rows: List[dict], slice_name: str):
    by_ref = {r["question_id"]: r for r in ref_rows}
    by_t = {r["question_id"]: r for r in ttmg_rows}
    b = c = both = neither = 0
    for qid, rr in by_ref.items():
        if rr.get("question_type") != slice_name:
            continue
        rt = by_t.get(qid)
        if not rt:
            continue
        r_ok = int(rr["correct"])
        t_ok = int(rt["correct"])
        if r_ok and t_ok:
            both += 1
        elif r_ok and not t_ok:
            b += 1
        elif t_ok and not r_ok:
            c += 1
        else:
            neither += 1
    p = mcnemar_exact(b, c)
    return {"both": both, "ref_only": b, "ttmg_only": c, "neither": neither, "pval": p}


def report(paths: Dict[str, str]) -> None:
    data = {k: _load(v) for k, v in paths.items()}
    for label, d in data.items():
        if not d:
            print(f"== {label}: MISSING ==")
            continue
        rows = d.get("rows", [])
        s = slice_stats(rows)
        print(f"== {label}  (N={len(rows)}) ==")
        ov = s.get("overall", {})
        if ov.get("n"):
            print(f"  overall: {ov['acc']:.3f}  Wilson95 [{ov['lo']:.3f}, {ov['hi']:.3f}]  n={ov['n']}")
        for k, v in sorted(s.items()):
            if k == "overall":
                continue
            print(f"  {k:<28s}: {v['acc']:.3f}  Wilson95 [{v['lo']:.3f}, {v['hi']:.3f}]  n={v['n']}")
        print()
    # pairs
    ttmg = data.get("ttmg")
    if ttmg:
        ttmg_rows = ttmg.get("rows", [])
        for ref_label in ("flat", "amem"):
            ref = data.get(ref_label)
            if not ref:
                continue
            print(f"== paired {ref_label.upper()} vs TTMG ==")
            for slice_name in ("temporal-reasoning", "knowledge-update", "multi-session",
                               "single-session-user", "single-session-assistant",
                               "single-session-preference"):
                r = paired_vs(ref.get("rows", []), ttmg_rows, slice_name)
                print(f"  {slice_name:<28s}: both={r['both']:>2d}  ref_only={r['ref_only']:>2d}  "
                      f"ttmg_only={r['ttmg_only']:>2d}  neither={r['neither']:>2d}  "
                      f"McNemar p={r['pval']:.3f}")
            print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat", default=None)
    ap.add_argument("--amem", default=None)
    ap.add_argument("--ttmg", default=None)
    ap.add_argument("--abl-contradict", default=None)
    args = ap.parse_args()
    paths = {
        "flat": args.flat, "amem": args.amem, "ttmg": args.ttmg,
        "abl_contradict": args.abl_contradict,
    }
    report(paths)


if __name__ == "__main__":
    main()
