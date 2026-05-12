"""Aggregate parser probe JSONs across personas into a single applicability table.

Usage: python scripts/aggregate_probe.py results/m0_smoke/parser_probe_*_weekly.json
"""
from __future__ import annotations
import glob, json, sys
from collections import Counter, defaultdict


def main():
    paths = sorted(glob.glob(sys.argv[1])) if len(sys.argv) >= 2 else sorted(
        glob.glob("results/m0_smoke/parser_probe_*_weekly.json")
    )
    if not paths:
        print("no probe JSONs found"); sys.exit(1)

    print(f"=== aggregating {len(paths)} persona files ===\n")
    by_task = defaultdict(lambda: {"total": 0, "applicable": 0,
                                    "single_valued": 0, "multi_valued": 0,
                                    "unknown_slot": 0, "asks_tof_true": 0})
    rows_by_persona = []
    all_keys = []
    for p in paths:
        rows = json.loads(open(p).read())
        persona = p.split("parser_probe_")[1].rsplit("_", 1)[0]
        n_app = sum(1 for r in rows if r.get("applicable"))
        rows_by_persona.append((persona, len(rows), n_app))
        for r in rows:
            t = r.get("task", "?")
            by_task[t]["total"] += 1
            if r.get("applicable"): by_task[t]["applicable"] += 1
            st = r.get("slot_type") or "?"
            if st == "single_valued": by_task[t]["single_valued"] += 1
            elif st == "multi_valued": by_task[t]["multi_valued"] += 1
            else: by_task[t]["unknown_slot"] += 1
            if r.get("asks_truth_of_fact"): by_task[t]["asks_tof_true"] += 1
            if r.get("claim_key"):
                all_keys.append((r.get("claim_key", {}).get("entity"),
                                 r.get("claim_key", {}).get("slot_name"),
                                 t, persona))

    # Per-persona applicability
    print(f"{'persona':<30}{'n':>6}{'applicable':>13}{'%':>8}")
    print("-" * 60)
    g_total = g_app = 0
    for persona, n, n_app in rows_by_persona:
        g_total += n; g_app += n_app
        print(f"{persona:<30}{n:>6}{n_app:>13}{100*n_app/max(1,n):>7.0f}%")
    print("-" * 60)
    print(f"{'TOTAL':<30}{g_total:>6}{g_app:>13}{100*g_app/max(1,g_total):>7.0f}%")
    print()

    # Per-task breakdown (across all personas)
    print(f"{'task':<14}{'n':>5}{'app':>5}{'sing':>6}{'mult':>6}{'unk':>5}{'tof':>5}")
    print("-" * 50)
    for t in ("remembering", "reasoning", "recommending"):
        s = by_task[t]
        print(f"{t:<14}{s['total']:>5}{s['applicable']:>5}{s['single_valued']:>6}{s['multi_valued']:>6}{s['unknown_slot']:>5}{s['asks_tof_true']:>5}")
    print()

    # Most common single-valued claim_keys (could become the controlled slice)
    print("=== top 15 (entity, slot_name) for *applicable* questions ===")
    app_keys = Counter()
    for r_path in paths:
        for r in json.loads(open(r_path).read()):
            if r.get("applicable") and r.get("claim_key"):
                ent = r["claim_key"].get("entity")
                slot = r["claim_key"].get("slot_name")
                app_keys[(ent, slot)] += 1
    for (ent, slot), cnt in app_keys.most_common(15):
        print(f"  {cnt:>3}× {ent}.{slot}")


if __name__ == "__main__":
    main()
