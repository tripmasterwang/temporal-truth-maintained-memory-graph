"""Direct β-parser probe: for every Memora question, print parser output.

Cheap diagnostic. ~15 MAAS calls per persona, no ingestion. Tells us whether
the applicability gate is being triggered correctly per question.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

from ttmg.canonicalize import Canonicalizer
from ttmg.truth_retriever import parse_query_beta
from calibrate_crc import _load_memora_persona, _flatten_question_groups


def main():
    if len(sys.argv) < 2:
        print("usage: probe_parser.py <persona> [<duration=weekly>] [<max_n=15>]"); sys.exit(1)
    persona = sys.argv[1]
    duration = sys.argv[2] if len(sys.argv) >= 3 else "weekly"
    max_n = int(sys.argv[3]) if len(sys.argv) >= 4 else 15
    root = Path("/home/workspace/lww/project0412/projects/MemMachine/competitor/2604.20006_Memora_FAMA/code/Memora/data")
    _, qb = _load_memora_persona(root, duration, persona)
    flat = _flatten_question_groups(qb)[:max_n]
    canon = Canonicalizer()
    rows = []
    print(f"{'qid':<48}{'task':<14}{'applicable':>11}{'slot_type':>15}{'asks_tof':>10}  claim_key")
    print("-" * 130)
    for task, q in flat:
        qid = q.get("question_id") or ""
        text = q.get("question") or ""
        try:
            parsed = parse_query_beta(text, canon)
        except Exception as e:
            parsed = {"_error": str(e)}
        ck = parsed.get("claim_key")
        ck_str = json.dumps(ck) if ck else "null"
        st = parsed.get("slot_type") or "-"
        atof = parsed.get("asks_truth_of_fact")
        applicable = parsed.get("_applicable")
        rows.append({
            "qid": qid, "task": task, "question": text,
            "claim_key": ck, "slot_type": st, "asks_truth_of_fact": atof,
            "applicable": applicable,
            "canonical_key_str": parsed.get("_canonical_claim_key_str"),
        })
        print(f"{qid:<48}{task:<14}{str(applicable):>11}{st:>15}{str(atof):>10}  {ck_str}")
    out_path = _ROOT / "results" / "m0_smoke" / f"parser_probe_{persona}_{duration}.json"
    out_path.write_text(json.dumps(rows, indent=2))
    print(f"\n[wrote] {out_path}")
    n_app = sum(1 for r in rows if r["applicable"])
    print(f"applicable rate: {n_app}/{len(rows)} = {100*n_app/max(1,len(rows)):.0f}%")


if __name__ == "__main__":
    main()
