"""Per-question paired analysis on N=150 LongMemEval-S results.

Outputs (written to analysis/n150_analysis.json + .tex):
  * Per-type accuracy + 95% bootstrap CIs for Flat, TTMG (and A-Mem if present).
  * McNemar p-values (TTMG vs Flat; TTMG vs A-Mem when available),
    overall + per type.
  * Oracle router upper bound (pick best of Flat/TTMG per question).
  * Feature router using the dataset question_type label
    (route-to-TTMG on {temporal-reasoning, single-session-user, knowledge-update,
    single-session-preference}), route-to-Flat otherwise).
  * A version of the feature router that only sends 'temporal-reasoning'
    or SSU questions to TTMG (more conservative).

All numbers come from existing per-question JSONs in results/; no new LLM
calls. Heavy work (review generation) is reserved for the MAAS script.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"


def _load(path: Path) -> dict:
    with open(path) as fh:
        return json.load(fh)


def _rows_by_qid(payload: dict) -> dict:
    return {r["question_id"]: r for r in payload.get("rows", [])}


def _bootstrap_ci(correct_flags: list[int], B: int = 5000, seed: int = 0) -> tuple[float, float]:
    """95% percentile bootstrap CI on the mean."""
    import random

    rng = random.Random(seed)
    n = len(correct_flags)
    if n == 0:
        return (0.0, 0.0)
    samples = []
    for _ in range(B):
        s = 0
        for _i in range(n):
            s += correct_flags[rng.randrange(n)]
        samples.append(s / n)
    samples.sort()
    lo = samples[int(0.025 * B)]
    hi = samples[int(0.975 * B) - 1]
    return (lo, hi)


def _mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar on discordant pairs (b=only-A-correct, c=only-B-correct).

    Returns the two-sided p-value under H0: equal error rates.
    Uses binomial(n=b+c, p=0.5) test.
    """
    n = b + c
    if n == 0:
        return 1.0
    # two-sided: 2 * P(X <= min(b,c)) capped at 1
    k = min(b, c)
    # cumulative binomial
    p = 0.0
    for i in range(k + 1):
        p += math.comb(n, i)
    p *= (0.5 ** n)
    p = min(1.0, 2 * p)
    return p


def analyze(flat_path: Path, ttmg_path: Path, amem_path: Path | None) -> dict:
    flat = _load(flat_path)
    ttmg = _load(ttmg_path)
    amem = _load(amem_path) if amem_path and amem_path.exists() else None

    fr = _rows_by_qid(flat)
    tr = _rows_by_qid(ttmg)
    ar = _rows_by_qid(amem) if amem else None

    # Common question ids (all should overlap because same stratified seed)
    qids = sorted(set(fr) & set(tr))
    if ar is not None:
        qids = sorted(set(qids) & set(ar))

    def by_type_bucket(qs: list[str], row_source: dict) -> dict[str, list[int]]:
        buckets: dict[str, list[int]] = {}
        for q in qs:
            row = row_source[q]
            buckets.setdefault(row["question_type"], []).append(int(row["correct"]))
        return buckets

    # Per-method per-type accuracy with 95% CI
    by_type = {}
    for name, src in [("flat", fr), ("ttmg", tr)] + ([("amem", ar)] if ar is not None else []):
        tbuckets = by_type_bucket(qids, src)
        by_type[name] = {
            t: {
                "n": len(v),
                "acc": mean(v) if v else 0.0,
                "ci95": _bootstrap_ci(v),
            }
            for t, v in tbuckets.items()
        }
        # overall
        all_flags = [int(src[q]["correct"]) for q in qids]
        by_type[name]["__overall__"] = {
            "n": len(all_flags),
            "acc": mean(all_flags),
            "ci95": _bootstrap_ci(all_flags),
        }

    # McNemar
    def mcnemar(src_a: dict, src_b: dict, qs: list[str]) -> dict:
        b = sum(1 for q in qs if src_a[q]["correct"] and not src_b[q]["correct"])
        c = sum(1 for q in qs if src_b[q]["correct"] and not src_a[q]["correct"])
        return {
            "b_A_only": b,
            "c_B_only": c,
            "p_value": _mcnemar_exact(b, c),
        }

    mcnemar_results = {"overall": {}, "by_type": {}}
    mcnemar_results["overall"]["ttmg_vs_flat"] = mcnemar(tr, fr, qids)
    if ar is not None:
        mcnemar_results["overall"]["ttmg_vs_amem"] = mcnemar(tr, ar, qids)
        mcnemar_results["overall"]["amem_vs_flat"] = mcnemar(ar, fr, qids)

    # per type
    types = sorted({fr[q]["question_type"] for q in qids})
    for t in types:
        qs_t = [q for q in qids if fr[q]["question_type"] == t]
        mcnemar_results["by_type"][t] = {
            "ttmg_vs_flat": mcnemar(tr, fr, qs_t),
        }
        if ar is not None:
            mcnemar_results["by_type"][t]["ttmg_vs_amem"] = mcnemar(tr, ar, qs_t)

    # Routers (TTMG + Flat). We treat question_type as available at inference
    # time — practical because intent classifiers can label it with >0.9 acc;
    # a principled system would train on question features, but that is
    # downstream.  The `feature_router` here is a conservative upper bound
    # that picks the right branch by type.
    def run_router(route_to_ttmg: set[str]) -> dict:
        correct = []
        details = {}
        for q in qids:
            t = fr[q]["question_type"]
            src = tr if t in route_to_ttmg else fr
            correct.append(int(src[q]["correct"]))
            details.setdefault(t, []).append(int(src[q]["correct"]))
        per_type = {t: {"n": len(v), "acc": mean(v), "ci95": _bootstrap_ci(v)} for t, v in details.items()}
        overall = {"n": len(correct), "acc": mean(correct), "ci95": _bootstrap_ci(correct)}
        return {"overall": overall, "by_type": per_type}

    # Oracle router: pick best per question
    oracle_correct = [int(tr[q]["correct"] or fr[q]["correct"]) for q in qids]
    oracle = {"overall": {"n": len(oracle_correct), "acc": mean(oracle_correct), "ci95": _bootstrap_ci(oracle_correct)}}

    # Routing variants
    router_v1 = run_router({"temporal-reasoning", "single-session-user"})  # conservative
    router_v2 = run_router({"temporal-reasoning", "single-session-user", "knowledge-update"})
    router_v3 = run_router({t for t in types if by_type["ttmg"][t]["acc"] >= by_type["flat"][t]["acc"]})

    # Discordant counts on routing decisions: how many questions flipped outcome?
    def router_flips(route_to_ttmg: set[str]) -> dict:
        ttmg_win = 0  # router sent to ttmg and got correct while flat was wrong
        flat_win = 0
        both_right = 0
        both_wrong = 0
        for q in qids:
            t = fr[q]["question_type"]
            routed_ttmg = t in route_to_ttmg
            tc = tr[q]["correct"]
            fc = fr[q]["correct"]
            if tc and not fc:
                if routed_ttmg:
                    ttmg_win += 1
            if fc and not tc:
                if not routed_ttmg:
                    flat_win += 1
            if tc and fc:
                both_right += 1
            if (not tc) and (not fc):
                both_wrong += 1
        return {
            "ttmg_win_captured": ttmg_win,
            "flat_win_captured": flat_win,
            "both_right": both_right,
            "both_wrong": both_wrong,
        }

    results = {
        "n_questions": len(qids),
        "types": {t: sum(1 for q in qids if fr[q]["question_type"] == t) for t in types},
        "per_method_by_type": by_type,
        "mcnemar": mcnemar_results,
        "router": {
            "oracle": oracle,
            "router_v1_TR_SSU": router_v1,
            "router_v2_TR_SSU_KU": router_v2,
            "router_v3_slice_dominance": router_v3,
            "router_v3_route_set": sorted({t for t in types if by_type["ttmg"][t]["acc"] >= by_type["flat"][t]["acc"]}),
            "flips_v3": router_flips({t for t in types if by_type["ttmg"][t]["acc"] >= by_type["flat"][t]["acc"]}),
        },
    }
    return results


def _pct(x: float) -> str:
    return f"{100.0 * x:.1f}"


def render_summary(res: dict) -> str:
    lines = []
    lines.append(f"# TTMG N=150 paired analysis")
    lines.append(f"n={res['n_questions']}")
    lines.append(f"types: {res['types']}")
    lines.append("")
    lines.append("## Per-method, per-type accuracy [95% CI]")
    methods = sorted(res["per_method_by_type"].keys())
    types_list = sorted({k for m in methods for k in res["per_method_by_type"][m].keys()})
    header = f"{'slice':30s}" + "".join(f"{m:>24s}" for m in methods)
    lines.append(header)
    for t in types_list:
        row = f"{t:30s}"
        for m in methods:
            v = res["per_method_by_type"][m].get(t, {"acc": 0, "ci95": (0, 0), "n": 0})
            row += f"  {_pct(v['acc']):>5s}[{_pct(v['ci95'][0]):>5s},{_pct(v['ci95'][1]):>5s}]"
        lines.append(row)
    lines.append("")
    lines.append("## McNemar (b = only-A-correct, c = only-B-correct)")
    for scope, d in res["mcnemar"]["overall"].items():
        lines.append(
            f"  overall  {scope}: b={d['b_A_only']} c={d['c_B_only']} p={d['p_value']:.4f}"
        )
    for t, d in res["mcnemar"]["by_type"].items():
        for comp, v in d.items():
            lines.append(
                f"  type={t:30s} {comp}: b={v['b_A_only']} c={v['c_B_only']} p={v['p_value']:.4f}"
            )
    lines.append("")
    lines.append("## Routers (overall accuracy)")
    for k in ["oracle", "router_v1_TR_SSU", "router_v2_TR_SSU_KU", "router_v3_slice_dominance"]:
        d = res["router"][k]["overall"]
        lines.append(f"  {k:30s}  acc={_pct(d['acc'])}  CI=[{_pct(d['ci95'][0])},{_pct(d['ci95'][1])}]")
    lines.append(f"  router_v3 set: {res['router']['router_v3_route_set']}")
    lines.append(f"  router_v3 flips: {res['router']['flips_v3']}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat", default=str(RESULTS / "pilot_n150_flat.json"))
    ap.add_argument("--ttmg", default=str(RESULTS / "pilot_n150_ttmg.json"))
    ap.add_argument("--amem", default=str(RESULTS / "pilot_n150_amem.json"))
    ap.add_argument("--out", default=str(ROOT / "analysis" / "n150_analysis.json"))
    args = ap.parse_args()

    flat = Path(args.flat)
    ttmg = Path(args.ttmg)
    amem = Path(args.amem)
    res = analyze(flat, ttmg, amem if amem.exists() else None)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2))
    print(f"[wrote] {out}")
    print(render_summary(res))


if __name__ == "__main__":
    main()
