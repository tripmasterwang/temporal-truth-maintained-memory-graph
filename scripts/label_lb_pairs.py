"""Label (q, item) pairs for CalLB calibration via LLM-judge (deepseek-v3.2).

For each calibration question, ingest its haystack into a TTMGSystem, gather
the multi-substrate candidate pool (≤30 items) via `lb_retrieval`, and ask
the judge to label each (q, item) pair as LB / S / D.

Outputs a JSONL with one line per (q, item) pair:
  {
    "question_id": str,
    "question": str,
    "gold": str,
    "item_id": str,
    "content": str,
    "source_type": "claim" | "raw-turn",
    "label": "LB" | "S" | "D",
    "rationale": str,
    "confidence": "high" | "low",
    "features": [13 floats],
    "feature_names": [13 strs],
  }

Resumable: writes incrementally, skips already-labelled (qid, item_id) pairs.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sentence_transformers import SentenceTransformer

from ttmg.lb_features import FEATURE_NAMES_FULL, extract_features
from ttmg.lb_retrieval import gather_candidates
from ttmg.maas_client import chat_json
from ttmg.system import TTMGConfig, TTMGSystem


_JUDGE_SYS = (
    "You are a careful annotator labelling whether a retrieved memory item "
    "is Load-Bearing, Supporting, or Distractor for answering a question. "
    "Respond ONLY with strict JSON."
)

_JUDGE_USER_TMPL = """GIVEN:
  - Question: {question}
  - Gold answer: {gold}
  - Candidate retrieved item:
      content: {item}
      source: {source}
      uttered_at: {ts}

Judge whether the item, *taken on its own*, supports the gold answer:

(A) LOAD-BEARING — the item by itself contains (or directly entails) the gold-answer information. A reader given just this item could produce the gold answer.
(B) SUPPORTING — the item is topically related to the question or gold answer (same person, place, event, or theme) but does NOT by itself contain the gold answer. Safe context.
(C) DISTRACTOR — the item is on-topic enough to be retrieved but would mislead a reader: it mentions a different entity / wrong value / outdated state / superseded preference, OR it invites the reader to add unsupported adjacent detail (over-specification).

Important:
- Judge each item *self-sufficiently*; do not assume what other items the reader will see.
- If the item is the user/assistant simply discussing the topic without stating the gold value → SUPPORTING.
- If the item mentions a SIMILAR-BUT-DIFFERENT entity / value than the gold → DISTRACTOR.
- Use timestamps when relevant (e.g. for knowledge-update questions, an old value is a DISTRACTOR vs the latest).

Return strict JSON:
{{
  "label": "LB" | "S" | "D",
  "rationale": "one sentence",
  "confidence": "high" | "low"
}}"""

# Sentinel rationales returned when the underlying judge call failed. We
# refuse to materialise these as labels — they would silently corrupt the
# MLP target distribution and make the CRC bound certify garbage.
_JUDGE_FAILURE_SENTINELS = ("judge_failed", "judge_exception")


def _convert_lme_sessions(record: Dict[str, Any], max_sessions: Optional[int] = None) -> List[Dict[str, Any]]:
    """Convert LME-S record into the {session_id, session_ts, turns} format
    expected by TTMGSystem.ingest_conversation.

    `max_sessions` matches the v51 baseline cap (full500_ttmg_v51 used 3).
    Selection mirrors `experiments/eval_longmemeval.py:run_one`:
    keep all answer sessions (`answer_session_ids`), then fill with the
    earliest non-answer sessions up to `max_sessions`. Calibrating on the
    same memory state TTMG inference sees is required for the CRC threshold
    to transfer to M1 evaluation.
    """
    sids = record.get("haystack_session_ids", []) or []
    sessions = record.get("haystack_sessions", []) or []
    dates = record.get("haystack_dates", []) or []
    triples = list(zip(sids, dates, sessions))
    if max_sessions is not None and max_sessions > 0:
        answer_ids = set(record.get("answer_session_ids", []) or [])
        core = [t for t in triples if t[0] in answer_ids]
        rest = [t for t in triples if t[0] not in answer_ids]
        keep = core + rest[: max(0, max_sessions - len(core))]
        triples = keep[:max_sessions]
    out = []
    for sid, sdate, sess in triples:
        turns = []
        for t in sess:
            if not isinstance(t, dict):
                continue
            text = (t.get("content") or "").strip()
            if text:
                turns.append({"speaker": t.get("role") or "user", "text": text})
        out.append({"session_id": sid, "session_ts": sdate or "", "turns": turns})
    return out


def _ingest_lme_question(
    record: Dict[str, Any],
    embed_model,
    *,
    disable_writer_claims: bool = False,
    writer_model: Optional[str] = None,
    max_sessions: Optional[int] = None,
) -> TTMGSystem:
    """Build a fresh TTMGSystem and ingest the haystack of one LME-S question.

    When `disable_writer_claims=True`, stores each turn directly as a raw
    claim (zero MAAS writer calls) — use for fast smoke tests.  In production,
    set `disable_writer_claims=False` (default) so the claim graph is built
    with real writer calls (batch-per-session, ~1 call / session via
    `ingest_conversation`); TTMG-specific features will then be populated.
    """
    from ttmg.maas_client import DEFAULT_MODEL
    cfg = TTMGConfig(
        enable_beta=False,
        raw_turn_fallback=True,
        batch_writer_per_session=True,
        disable_writer_claims=disable_writer_claims,
        disable_contradict=disable_writer_claims,  # skip linker when skipping writer
        writer_model=writer_model or DEFAULT_MODEL,
        linker_model=writer_model or DEFAULT_MODEL,
    )
    sys_obj = TTMGSystem(config=cfg, embed_model=embed_model)
    sessions = _convert_lme_sessions(record, max_sessions=max_sessions)
    sys_obj.ingest_conversation(sessions, verbose=False)
    return sys_obj


def _load_existing_labels(out_path: Path) -> Set[Tuple[str, str]]:
    """Return set of (qid, item_id) already labelled (resume)."""
    seen: Set[Tuple[str, str]] = set()
    if not out_path.exists():
        return seen
    with open(out_path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                seen.add((rec["question_id"], rec["item_id"]))
            except Exception:
                continue
    return seen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lme-data", default="/home/workspace/lww/project0412/projects/dataset/LongMemEval-main/data/longmemeval_s.json")
    ap.add_argument("--out", default="results/lb_calibration_labels.jsonl",
                    help="JSONL output path (resumable).")
    ap.add_argument("--max-questions", type=int, default=200,
                    help="Cap how many cal questions to process.")
    ap.add_argument("--start", type=int, default=0,
                    help="Skip first N questions (for sharding).")
    ap.add_argument("--k-per-substrate", type=int, default=10)
    ap.add_argument("--max-candidates", type=int, default=30)
    ap.add_argument("--judge-model", default="deepseek-v3.2")
    ap.add_argument("--writer-model", default=None,
                    help="Writer model for ingest (default: TTMG_MODEL env or deepseek-v3.2).")
    ap.add_argument("--embed-model", default="all-MiniLM-L6-v2")
    ap.add_argument("--disable-writer-claims", action="store_true",
                    help="Skip MAAS writer calls (fast smoke). TTMG-specific features "
                         "will be 0; use only for verifying judge prompt logic.")
    ap.add_argument("--max-sessions", type=int, default=3,
                    help="Cap sessions per question (matches v51 baseline=3). "
                         "Critical: must match the value used at M1 evaluation, "
                         "otherwise CRC threshold won't transfer.")
    args = ap.parse_args()

    out_path = (PROJECT_ROOT / args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = _load_existing_labels(out_path)
    # Per-qid pair count for skip-ingest fast-path (don't re-run Kimi-K2
    # writer on a qid we already finished).
    qid_pair_counts: Dict[str, int] = {}
    for q, _ in seen:
        qid_pair_counts[q] = qid_pair_counts.get(q, 0) + 1
    skip_ingest_threshold = 10  # finished qids in cache had ≥13 pairs
    print(f"[label] resume: {len(seen)} (qid, item) pairs already labelled "
          f"across {len(qid_pair_counts)} qids in {out_path.name}")

    print(f"[label] loading LME-S from {args.lme_data}")
    with open(args.lme_data) as fh:
        lme = json.load(fh)
    print(f"[label] {len(lme)} questions in LME-S")

    print(f"[label] loading embed model {args.embed_model}")
    embed_model = SentenceTransformer(args.embed_model)

    fail_path = out_path.with_name(out_path.stem + "_failures.jsonl")
    n_done_pairs = 0
    n_judge_calls = 0
    n_failures = 0
    t_start = time.time()

    for qi, record in enumerate(lme[args.start:args.start + args.max_questions], start=args.start + 1):
        qid = record.get("question_id") or f"q{qi}"
        question = str(record.get("question") or "").strip()
        gold = str(record.get("answer") or "").strip()  # LME-S has 32/500 int answers
        ts_q = record.get("question_date")  # LME-S anchor for τ_q
        if not question or not gold:
            continue

        # Skip-ingest fast-path: this qid already has enough pairs cached.
        if qid_pair_counts.get(qid, 0) >= skip_ingest_threshold:
            continue

        # Build a fresh system per question (LME-S sessions are per-question).
        try:
            sys_obj = _ingest_lme_question(
                record, embed_model,
                disable_writer_claims=args.disable_writer_claims,
                writer_model=args.writer_model,
                max_sessions=args.max_sessions,
            )
        except Exception as e:
            print(f"  [{qi}] qid={qid}: ingest failed: {e}")
            continue

        # Gather candidates
        try:
            cands = gather_candidates(question, sys_obj, k_per_substrate=args.k_per_substrate, max_candidates=args.max_candidates)
        except Exception as e:
            print(f"  [{qi}] qid={qid}: candidate gather failed: {e}")
            continue
        if not cands:
            print(f"  [{qi}] qid={qid}: 0 candidates")
            continue

        # Score each candidate and label via judge
        n_new = 0
        for c in cands:
            key = (qid, c.id)
            if key in seen:
                continue
            # Extract features (uses LME-S question_date as τ_q)
            feats = extract_features(question, c, sys_obj.graph, ts_q=ts_q,
                                     feature_names=FEATURE_NAMES_FULL)
            # Label via judge
            prompt = _JUDGE_USER_TMPL.format(
                question=question,
                gold=gold,
                item=c.content[:600],
                source=c.source_type,
                ts=(c.claim.provenance.session_ts if (c.claim and c.claim.provenance) else
                    (c.raw_turn.get("session_ts") if c.raw_turn else "?")),
            )
            judge_failed = False
            try:
                payload = chat_json(
                    prompt, system=_JUDGE_SYS, model=args.judge_model,
                    default={"label": "S", "rationale": "judge_failed", "confidence": "low"},
                    temperature=0.0, max_tokens=200,
                )
                # Detect the default sentinel: chat_json returned the default
                # without a real model response.
                rationale_lower = (payload.get("rationale") or "").lower()
                if any(s in rationale_lower for s in _JUDGE_FAILURE_SENTINELS):
                    judge_failed = True
            except Exception as e:
                judge_failed = True
                payload = {"label": "S", "rationale": f"judge_exception:{e}"[:200], "confidence": "low"}
            n_judge_calls += 1

            if judge_failed:
                # Do NOT materialise this as a label. Write to failure log so
                # we can retry on resume. `seen` is intentionally NOT updated
                # so a re-run will retry this (qid, item_id).
                n_failures += 1
                fail_rec = {
                    "question_id": qid,
                    "item_id": c.id,
                    "rationale": (payload.get("rationale") or "")[:300],
                    "ts": time.time(),
                }
                with open(fail_path, "a") as fh:
                    fh.write(json.dumps(fail_rec) + "\n")
                continue

            label = (payload.get("label") or "S").strip().upper()
            if label not in ("LB", "S", "D"):
                # Sometimes judge returns "(A)"/"LOAD-BEARING" — normalise:
                up = label
                if "LB" in up or "LOAD" in up or up.startswith("A"):
                    label = "LB"
                elif "DIS" in up or up.startswith("C"):
                    label = "D"
                elif "SUPP" in up or up.startswith("B"):
                    label = "S"
                else:
                    # Unknown label format — treat as judge failure rather
                    # than silently coercing to S.
                    n_failures += 1
                    with open(fail_path, "a") as fh:
                        fh.write(json.dumps({
                            "question_id": qid, "item_id": c.id,
                            "rationale": f"unparseable_label:{label}", "ts": time.time(),
                        }) + "\n")
                    continue
            rec = {
                "question_id": qid,
                "question": question[:400],
                "gold": gold[:200],
                "item_id": c.id,
                "content": c.content[:500],
                "source_type": c.source_type,
                "in_topk": dict(c.in_topk),
                "substrate_scores": {k: (float(v) if v is not None else None) for k, v in c.score.items()},
                "label": label,
                "rationale": (payload.get("rationale") or "")[:300],
                "confidence": (payload.get("confidence") or "low").lower(),
                "features": [float(x) for x in feats.tolist()],
                "feature_names": list(FEATURE_NAMES_FULL),
            }
            with open(out_path, "a") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            seen.add(key)
            n_done_pairs += 1
            n_new += 1
        elapsed = time.time() - t_start
        rate = n_judge_calls / max(1.0, elapsed)
        print(f"  [{qi}/{args.start + args.max_questions}] qid={qid} | +{n_new} pairs | "
              f"total new={n_done_pairs} | fail={n_failures} | calls={n_judge_calls} | {rate:.2f} call/s")

    print(f"\n[label] done. New pairs: {n_done_pairs}; judge calls: {n_judge_calls}; "
          f"failures: {n_failures}; output: {out_path}; failures: {fail_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
