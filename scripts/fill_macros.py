"""Populate LaTeX \newcommand{\XxxLMEAcc}{--} macros in paper/main.tex from result JSONs.

Usage:
  python scripts/fill_macros.py \
    --amem results/pilot_amem.json \
    --ttmg results/pilot_ttmg.json \
    --paper paper/main.tex

Safe: only rewrites macros inside the block starting at the comment
"Result macros" until the blank-line separator before the title.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path


def _pct(v):
    try: return f"{100.0*float(v):.1f}"
    except: return "--"


def _f1(v):
    try: return f"{float(v):.3f}"
    except: return "--"


def load(path):
    if not path:
        return None
    with open(path, 'r') as fh:
        return json.load(fh)


def extract_metrics(payload):
    if payload is None:
        return {}
    s = payload.get("summary", {})
    out = {"overall": _pct(s.get("accuracy", 0)), "f1": _f1(s.get("f1", 0))}
    bt = s.get("by_type", {})
    out["ku"] = _pct(bt.get("knowledge-update", {}).get("accuracy", 0))
    out["tr"] = _pct(bt.get("temporal-reasoning", {}).get("accuracy", 0))
    abs_corr = s.get("abstention_correct", None)
    if abs_corr is not None:
        out["abs"] = _pct(abs_corr)
    else:
        out["abs"] = "--"
    # Rough tokens-per-q estimate
    rows = payload.get("rows", [])
    tps = []
    for r in rows:
        m = r.get("metrics", {})
        cs = sum(int(m.get(k, 0)) for k in ("writer_calls","linker_calls","parser_calls","reader_calls"))
        # we don't log per-call tokens; estimate at ~900 prompt + 200 output = 1100 tokens per call
        tps.append(cs * 1100)
    out["tokens"] = f"{int(sum(tps)/max(1,len(tps)))}" if tps else "--"
    # Latency per question, mean
    if rows:
        lat = sum(float(r.get("ingest_time",0)) + float(r.get("answer_time",0)) for r in rows) / len(rows)
        out["latency"] = f"{lat:.1f}"
    else:
        out["latency"] = "--"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--amem", default=None)
    ap.add_argument("--ttmg", default=None)
    ap.add_argument("--flat", default=None)
    ap.add_argument("--abl-validity", default=None)
    ap.add_argument("--abl-contradict", default=None)
    ap.add_argument("--abl-consistent", default=None)
    ap.add_argument("--abl-emb-only", default=None)
    ap.add_argument("--locomo-amem", default=None)
    ap.add_argument("--locomo-ttmg", default=None)
    ap.add_argument("--mabcr-amem", default=None)
    ap.add_argument("--mabcr-ttmg", default=None)
    ap.add_argument("--paper", required=True)
    args = ap.parse_args()

    amem = extract_metrics(load(args.amem))
    ttmg = extract_metrics(load(args.ttmg))
    flat = extract_metrics(load(args.flat))

    replacements = {
        "FlatLMEAcc":  flat.get("overall","--"),
        "FlatLMEAccKU":flat.get("ku","--"),
        "FlatLMEAccTR":flat.get("tr","--"),
        "FlatLMEAccABS":flat.get("abs","--"),
        "FlatLMEF":    flat.get("f1","--"),
        "FlatTokens":  flat.get("tokens","--"),
        "AmemLMEAcc":  amem.get("overall","--"),
        "AmemLMEAccKU":amem.get("ku","--"),
        "AmemLMEAccTR":amem.get("tr","--"),
        "AmemLMEAccABS":amem.get("abs","--"),
        "AmemLMEF":    amem.get("f1","--"),
        "TTMGLMEAcc":  ttmg.get("overall","--"),
        "TTMGLMEAccKU":ttmg.get("ku","--"),
        "TTMGLMEAccTR":ttmg.get("tr","--"),
        "TTMGLMEAccABS":ttmg.get("abs","--"),
        "TTMGLMEF":    ttmg.get("f1","--"),
        "AmemTokens":  amem.get("tokens","--"),
        "TTMGTokens":  ttmg.get("tokens","--"),
        "AmemLatency": amem.get("latency","--"),
        "TTMGLatency": ttmg.get("latency","--"),
    }
    # Deltas
    def _diff(a, b):
        try: return f"{float(b)-float(a):.1f}"
        except: return "--"
    replacements["DeltaLMEAcc"] = _diff(amem.get("overall","--"), ttmg.get("overall","--"))
    replacements["DeltaLMEKU"]  = _diff(amem.get("ku","--"), ttmg.get("ku","--"))
    replacements["DeltaLMETR"]  = _diff(amem.get("tr","--"), ttmg.get("tr","--"))
    replacements["DeltaLMEABS"] = _diff(amem.get("abs","--"), ttmg.get("abs","--"))
    # Ablations
    for arg, macro in [
        (args.abl_validity, "AblValidity"),
        (args.abl_contradict, "AblContradict"),
        (args.abl_consistent, "AblConsistent"),
        (args.abl_emb_only, "AblEmbOnly"),
    ]:
        m = extract_metrics(load(arg))
        replacements[macro] = m.get("overall","--")
    # Cross-domain
    for arg, macro in [
        (args.locomo_amem, "AmemLoCoF"),
        (args.locomo_ttmg, "TTMGLoCoF"),
    ]:
        m = extract_metrics(load(arg))
        replacements[macro] = m.get("f1","--")
    for arg, macro in [
        (args.mabcr_amem, "AmemMABcr"),
        (args.mabcr_ttmg, "TTMGMABcr"),
    ]:
        m = extract_metrics(load(arg))
        replacements[macro] = m.get("overall","--")
    # Token overhead %
    try:
        overhead = (int(ttmg.get("tokens",0)) - int(amem.get("tokens",0))) / max(1, int(amem.get("tokens",1))) * 100
        replacements["TokensOverhead"] = f"{overhead:.1f}"
    except Exception:
        replacements["TokensOverhead"] = "--"

    p = Path(args.paper)
    text = p.read_text()
    for macro, val in replacements.items():
        text = re.sub(
            rf"\\newcommand\{{\\{macro}\}}\{{[^}}]*\}}",
            rf"\\newcommand{{\\{macro}}}{{{val}}}",
            text,
        )
    p.write_text(text)
    print("[fill_macros] done. Replacements:")
    for k, v in replacements.items():
        print(f"  {k} = {v}")


if __name__ == "__main__":
    main()
