"""Conflict / supersede edge linker.

Given a new claim and its k semantic nearest neighbours, decide for each
pair one of {support, contradict, supersede, unrelated} with a confidence
score.

Strategy:
  1. Cheap lexical-semantic pre-filter selects candidate pairs.
  2. A single batched LLM call labels all candidates jointly.
  3. Supersede rule: if (subject, predicate) matches and the new claim has
     a later `valid_from`, we upgrade a `contradict` to `supersede`.
  4. Edges above `hard_threshold` flip `active` on the older claim
     (supersede) or mark pair as disputed (contradict).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from .maas_client import chat_json
from .schema import Claim, Edge

_LABEL_SYS = (
    "You label pairs of factual claims as one of "
    "'support', 'contradict', 'supersede', or 'unrelated'. "
    "Respond in strict JSON only."
)

_LABEL_USER_TMPL = """For the NEW claim and each CANDIDATE claim, output a label in {{"support","contradict","supersede","unrelated"}} and a confidence in [0,1].

Definitions:
- support: both claims assert the same fact (can coexist).
- contradict: claims disagree on the same (subject, predicate) at overlapping times.
- supersede: the NEW claim replaces the CANDIDATE because it is about the SAME subject+predicate but at a later time or marked as a correction/update. Use when the claims cannot both be current simultaneously.
- unrelated: otherwise.

Be conservative: default to "unrelated" unless the claims share subject and predicate. Two different preferences by the same subject over time are usually a 'supersede' if the NEW claim is later, not 'contradict'.

NEW claim:
id: NEW
content: {new_content}
subject: {new_subject}
predicate: {new_predicate}
object: {new_object}
valid_from: {new_valid_from}
polarity: {new_polarity}
volatility: {new_volatility}

Candidates (each line has the id):
{cand_block}

Return JSON of the form:
{{"pairs": [{{"id": "<candidate_id>", "label": "...", "confidence": 0.0}}, ...]}}"""


def _candidate_block(cands: List[Claim]) -> str:
    lines = []
    for c in cands:
        lines.append(
            f"- id: {c.id} | subject: {c.subject} | predicate: {c.predicate} "
            f"| object: {c.object} | valid_from: {c.valid_from} | polarity: {c.polarity} "
            f"| volatility: {c.volatility} | content: {c.content}"
        )
    return "\n".join(lines)


def link_claim(
    new_claim: Claim,
    candidates: List[Claim],
    *,
    model: Optional[str] = None,
    hard_threshold: float = 0.7,
) -> List[Edge]:
    if not candidates:
        return []
    prompt = _LABEL_USER_TMPL.format(
        new_content=new_claim.content,
        new_subject=new_claim.subject,
        new_predicate=new_claim.predicate,
        new_object=new_claim.object,
        new_valid_from=new_claim.valid_from,
        new_polarity=new_claim.polarity,
        new_volatility=new_claim.volatility,
        cand_block=_candidate_block(candidates),
    )
    payload = chat_json(
        prompt,
        system=_LABEL_SYS,
        model=model,
        default={"pairs": []},
        temperature=0.0,
        max_tokens=700,
    )
    pairs = payload.get("pairs", []) if isinstance(payload, dict) else []
    by_id: Dict[str, Claim] = {c.id: c for c in candidates}

    edges: List[Edge] = []
    for p in pairs:
        if not isinstance(p, dict):
            continue
        cand_id = p.get("id")
        label = p.get("label")
        conf = float(p.get("confidence", 0.0))
        if cand_id not in by_id or label not in ("support", "contradict", "supersede"):
            continue
        cand = by_id[cand_id]
        # Supersede rule reinforcement: same (s,p), new is later → force supersede
        if new_claim.sp_key() == cand.sp_key() and new_claim.sp_key().strip("|"):
            if new_claim.valid_from and cand.valid_from and new_claim.valid_from > cand.valid_from:
                if label == "contradict":
                    label = "supersede"
                    conf = max(conf, 0.75)
        if label == "supersede" and conf >= hard_threshold:
            cand.active = False
            cand.superseded_by = new_claim.id
        edges.append(
            Edge(
                src=new_claim.id,
                dst=cand.id,
                label=label,
                confidence=conf,
                rationale=p.get("rationale", "")[:200],
            )
        )
    return edges


def link_claim_3call(
    new_claim: Claim,
    candidates: List[Claim],
    *,
    model: Optional[str] = None,
    hard_threshold: float = 2 / 3,
) -> List[Edge]:
    """β round-2 linker: 3 independent calls (varied temperature + prompt
    phrasing) per pair; hardness = max-agreement-fraction across the 3 calls.

    Edge admitted iff label ∈ {contradict, supersede} AND hardness ≥
    `hard_threshold` (default 2/3 = exactly 2-of-3 agreement).

    The `support` label is *never* used in β's decision policy — supersede
    materialisation, contradiction surfacing, abstention all ignore support
    edges. Support edges are still returned for diagnostic richness.

    The Edge.confidence field is overwritten with the agreement-based
    hardness so downstream `Edge.is_hard()` semantics carry the calibrated
    signal.
    """
    if not candidates:
        return []
    base_prompt = _LABEL_USER_TMPL.format(
        new_content=new_claim.content,
        new_subject=new_claim.subject,
        new_predicate=new_claim.predicate,
        new_object=new_claim.object,
        new_valid_from=new_claim.valid_from,
        new_polarity=new_claim.polarity,
        new_volatility=new_claim.volatility,
        cand_block=_candidate_block(candidates),
    )
    # Variant 2: emphasise conservative supersede labelling
    prompt_v2 = base_prompt + (
        "\n\nReminder: only use 'supersede' when the NEW claim explicitly "
        "REPLACES the old one for the same (subject, predicate). When unsure, "
        "use 'contradict' or 'unrelated'."
    )
    # Variant 3: emphasise paraphrase tolerance to reduce false contradicts
    prompt_v3 = base_prompt + (
        "\n\nReminder: claims that paraphrase the same fact (e.g. 'piping hot' "
        "vs 'very hot') are 'support', not 'contradict'."
    )
    variants: List[Tuple[str, float]] = [
        (base_prompt, 0.0),
        (prompt_v2, 0.3),
        (prompt_v3, 0.6),
    ]

    by_id: Dict[str, Claim] = {c.id: c for c in candidates}
    # cand_id -> list of (label, single-call-confidence)
    votes: Dict[str, List[Tuple[str, float]]] = {cid: [] for cid in by_id}

    for prompt, temp in variants:
        payload = chat_json(
            prompt,
            system=_LABEL_SYS,
            model=model,
            default={"pairs": []},
            temperature=temp,
            max_tokens=700,
        )
        pairs = payload.get("pairs", []) if isinstance(payload, dict) else []
        for p in pairs:
            if not isinstance(p, dict):
                continue
            cand_id = p.get("id")
            label = p.get("label")
            if cand_id not in by_id or label not in (
                "support",
                "contradict",
                "supersede",
                "unrelated",
            ):
                continue
            try:
                conf = float(p.get("confidence", 0.0))
            except Exception:
                conf = 0.0
            votes[cand_id].append((label, conf))

    edges: List[Edge] = []
    for cand_id, vote_list in votes.items():
        if not vote_list:
            continue
        # Hardness = max-agreement-fraction across the 3 calls
        label_counts: Dict[str, int] = {}
        for lab, _ in vote_list:
            label_counts[lab] = label_counts.get(lab, 0) + 1
        top_label, top_count = max(label_counts.items(), key=lambda x: x[1])
        hardness = top_count / 3.0  # always exactly 3 calls (unless API failed)
        if not vote_list:
            continue
        # Average self-reported confidence across the calls that agreed
        avg_conf = sum(c for lab, c in vote_list if lab == top_label) / max(
            1, top_count
        )
        cand = by_id[cand_id]
        # Supersede rule reinforcement: same canonical claim_key (or sp_key
        # fallback), new is later in time → upgrade contradict to supersede.
        same_key = (
            new_claim.claim_key is not None
            and cand.claim_key is not None
            and new_claim.claim_key == cand.claim_key
        ) or (
            new_claim.claim_key is None
            and cand.claim_key is None
            and new_claim.sp_key() == cand.sp_key()
            and new_claim.sp_key().strip("|")
        )
        if same_key and new_claim.valid_from and cand.valid_from:
            if new_claim.valid_from > cand.valid_from and top_label == "contradict":
                top_label = "supersede"
                hardness = max(hardness, 2 / 3)
        # β decision policy: ONLY {contradict, supersede} contribute to truth
        # maintenance. Support edges are emitted as DIAGNOSTIC (very low
        # confidence so Edge.is_hard() returns False).
        is_decision = top_label in ("contradict", "supersede")
        edge_conf = hardness if is_decision else 0.0
        if (
            top_label == "supersede"
            and hardness >= hard_threshold
            and same_key
            and new_claim.slot_type == "single_valued"
            and cand.slot_type == "single_valued"
        ):
            cand.active = False
            cand.superseded_by = new_claim.id
            # Materialise valid_to ← valid_from − ε (paper-version supersede rule)
            if new_claim.valid_from:
                cand.valid_to = new_claim.valid_from
        edges.append(
            Edge(
                src=new_claim.id,
                dst=cand.id,
                label=top_label,
                confidence=edge_conf,
                rationale=f"hardness={hardness:.2f} avg_call_conf={avg_conf:.2f} n_calls={len(vote_list)}",
            )
        )
    return edges


__all__ = ["link_claim", "link_claim_3call"]
