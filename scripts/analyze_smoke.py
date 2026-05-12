"""Inspect a single eval_memora.py output JSON for sanity / route distribution.

Usage: python scripts/analyze_smoke.py <result.json>
"""
from __future__ import annotations
import json, sys
from collections import Counter

if len(sys.argv) < 2:
    print("usage: analyze_smoke.py <result.json>"); sys.exit(1)
d = json.load(open(sys.argv[1]))

print(f"=== {sys.argv[1]} ===")
print(f"method={d['method']} duration={d['duration']} elapsed={d['elapsed_sec']:.1f}s")
print(f"task_aggregates: {d['task_aggregates']}")
print(f"duration_total_max300: {d['duration_total_max300']:.2f}")
print(f"metrics: {d['metrics']}")
print()

per_q = d.get("per_question", [])
print(f"=== per-question (n={len(per_q)}) ===")
print()

# Route distribution
routes = Counter(q.get("route") for q in per_q)
print(f"route distribution: {dict(routes)}")

# Per-task FAMA
by_task = {}
for q in per_q:
    by_task.setdefault(q["task"], []).append(q)
for task in ("remembering", "reasoning", "recommending"):
    qs = by_task.get(task, [])
    if not qs: continue
    famas = [q.get("fama", 0.0) for q in qs]
    routes_t = Counter(q.get("route") for q in qs)
    print(f"\n{task}: n={len(qs)} mean_fama={sum(famas)/len(famas):.3f} routes={dict(routes_t)}")

# β path firings
print()
print("=== β-routed questions (interesting cases) ===")
for q in per_q:
    if q.get("route") == "ttmg":
        print(f"  [{q['task']}] [{q['question_id']}]")
        print(f"    score={q.get('score')} thr={q.get('threshold')} group={q.get('group')}")
        print(f"    vals={q.get('vals')} value={q.get('value','?')}")
        print(f"    fama={q.get('fama'):.2f} mpa={q.get('mpa'):.2f} faa={q.get('faa'):.2f}")
        print(f"    answer={(q.get('answer') or '')[:120]!r}")

# Abstentions
print()
abst = [q for q in per_q if q.get("abstain") or q.get("route") == "abstain"]
if abst:
    print(f"=== ABSTAINED questions (n={len(abst)}) ===")
    for q in abst:
        print(f"  [{q['task']}] [{q['question_id']}] route={q.get('route')} reason={q.get('abstain_reason','?')}")

# Judge failures
jf = sum(q.get("judge_failures", 0) for q in per_q)
total_crit = sum((q.get("n_presence", 0) + q.get("n_forget", 0)) for q in per_q)
print(f"\njudge failures: {jf} / {total_crit} criteria total ({100*jf/max(1,total_crit):.1f}%)")
