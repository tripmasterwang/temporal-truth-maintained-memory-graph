"""Claim writer: turn a conversational turn (or a whole session) into
structured `Claim` objects.

`extract_claims` handles a single turn. `extract_claims_session` batches
all turns of one session into a single LLM call, which is crucial for
ingesting benchmarks that carry ~50 sessions × ~10 turns per question.

On LLM failure we return an empty list — the caller may store the raw
text as a fallback note.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .canonicalize import Canonicalizer
from .maas_client import chat_json
from .schema import Claim, Provenance

_EXTRACTION_SYS = (
    "You extract factual claims from conversation turns for a long-term "
    "memory system. Only extract information the speaker ACTUALLY asserts. "
    "Do NOT invent content. Respond with strict JSON only."
)

_EXTRACTION_USER_TMPL = """Extract structured claims from the following conversation turn.

Turn:
- speaker: {speaker}
- session_ts: {session_ts}
- text: {text}

For EACH distinct factual assertion (facts, preferences, plans, states), output a claim with:
- content: a self-contained paraphrase that includes the subject.
- subject/predicate/object: shallow triple if possible (else leave empty).
- valid_from / valid_to: ISO date or datetime. Default valid_from to "{session_ts}". Use null for open-ended sides.
- polarity: "assert" or "deny".
- volatility: "stable" | "preference" | "state".
- confidence: 0.0-1.0.

Rules:
- If the turn has no factual claim (greetings, small talk, meta-chat), return [].
- Subjects default to the speaker when the sentence is about the speaker.
- Corrections / replacements: volatility="preference", valid_from = session_ts.
- Keep content <= 25 words.

Return JSON: {{"claims": [{{...}}, ...]}}"""


_SESSION_USER_TMPL = """Extract factual claims from the conversation below.

Session metadata:
- session_id: {session_id}
- session_ts: {session_ts}

Conversation (numbered turns):
{turn_block}

For EACH turn that contains factual content, output one or more claims:
- turn_id: the integer index of the turn you got the claim from.
- speaker: "user" or "assistant".
- content: a self-contained paraphrase (<=40 words). For assistant
  turns, PRESERVE every specific named entity the assistant mentions
  (brand names, company names, case names, dates, years, numeric
  values, titles). Produce ONE claim per distinct named entity the
  assistant asserts; do NOT summarise away the entity names. Example:
  if the assistant says "companies like Patagonia and Southwest
  Airlines prioritize...", write TWO claims, one naming Patagonia
  and one naming Southwest Airlines.
- subject, predicate, object: shallow triple; for assistant turns
  the subject is the named entity and the predicate is the relation
  asserted about it.
- valid_from, valid_to: ISO strings. Default valid_from = "{session_ts}"; valid_to null for open-ended.
- polarity: "assert" | "deny".
- volatility: "stable" | "preference" | "state".
- confidence: 0.0-1.0.

Skip greetings / small talk / pure questions asked of the model.
Do NOT invent facts. Keep content concise but DO NOT drop named
entities.

Return JSON: {{"claims": [{{...}}, ...]}}"""


def _mk_claim(c: Dict[str, Any], provenance: Provenance) -> Optional[Claim]:
    content = (c.get("content") or "").strip()
    if not content:
        return None
    try:
        return Claim(
            content=content[:500],
            subject=(c.get("subject") or "")[:120],
            predicate=(c.get("predicate") or "")[:120],
            object=(c.get("object") or "")[:200],
            valid_from=c.get("valid_from") or None,
            valid_to=c.get("valid_to") or None,
            polarity=c.get("polarity") if c.get("polarity") in ("assert", "deny") else "assert",
            volatility=c.get("volatility") if c.get("volatility") in ("stable", "preference", "state") else "state",
            confidence=float(c.get("confidence", 0.7)),
            provenance=provenance,
            keywords=[],
            tags=[],
        )
    except Exception:
        return None


def extract_claims(
    text: str,
    provenance: Provenance,
    *,
    model: Optional[str] = None,
    max_claims: int = 6,
) -> List[Claim]:
    if not text or not text.strip():
        return []
    prompt = _EXTRACTION_USER_TMPL.format(
        speaker=provenance.speaker,
        session_ts=provenance.session_ts or "unknown",
        text=text.strip()[:2000],
    )
    payload = chat_json(
        prompt,
        system=_EXTRACTION_SYS,
        model=model,
        default={"claims": []},
        temperature=0.0,
        max_tokens=900,
    )
    raw = payload.get("claims", []) if isinstance(payload, dict) else []
    out: List[Claim] = []
    for c in raw[:max_claims]:
        if not isinstance(c, dict):
            continue
        cl = _mk_claim(c, provenance)
        if cl is not None:
            out.append(cl)
    return out


def extract_claims_session(
    session_id: str,
    session_ts: Optional[str],
    turns: List[Dict[str, Any]],
    *,
    model: Optional[str] = None,
    max_claims: int = 20,
) -> List[Claim]:
    """Batch-extract all claims from a session in a single LLM call."""
    if not turns:
        return []
    lines = []
    for ti, t in enumerate(turns):
        if not isinstance(t, dict):
            continue
        speaker = t.get("speaker") or "user"
        text = (t.get("text") or "").strip().replace("\n", " ")
        if not text:
            continue
        lines.append(f"[{ti}] ({speaker}): {text[:800]}")
    if not lines:
        return []
    prompt = _SESSION_USER_TMPL.format(
        session_id=session_id,
        session_ts=session_ts or "unknown",
        turn_block="\n".join(lines),
    )
    payload = chat_json(
        prompt,
        system=_EXTRACTION_SYS,
        model=model,
        default={"claims": []},
        temperature=0.0,
        max_tokens=1800,
    )
    raw = payload.get("claims", []) if isinstance(payload, dict) else []
    out: List[Claim] = []
    for c in raw[:max_claims]:
        if not isinstance(c, dict):
            continue
        ti = c.get("turn_id")
        try:
            turn_id = int(ti)
        except Exception:
            turn_id = -1
        speaker = c.get("speaker") or "user"
        prov = Provenance(
            session_id=session_id,
            turn_id=turn_id,
            speaker=speaker if speaker in ("user", "assistant") else "user",
            session_ts=session_ts,
        )
        cl = _mk_claim(c, prov)
        if cl is not None:
            out.append(cl)
    return out


_BETA_SESSION_USER_TMPL = """Extract factual claims from the conversation below.

Session metadata:
- session_id: {session_id}
- session_ts: {session_ts}

Conversation (numbered turns):
{turn_block}

For EACH turn that contains factual content, output one or more claims with the following fields:
- turn_id: integer index of the turn.
- speaker: "user" or "assistant".
- content: a self-contained paraphrase (<=40 words).
- subject, predicate, object: shallow triple (subject is usually the speaker for self-statements).
- claim_key: a (entity, slot_name) pair that uniquely identifies the slot this claim is about. Examples:
    {{"entity": "user", "slot_name": "preferred_coffee_temperature"}}
    {{"entity": "user", "slot_name": "current_to_do_list"}}
    {{"entity": "user", "slot_name": "favourite_movie_director"}}
    Use canonical forms: "user" for first-person mentions, "assistant" for the AI, surface-form proper nouns otherwise.
- slot_type: "single_valued" if the slot holds ONE value at a time and updates REPLACE the prior value (preferences, current state, single attributes). "multi_valued" if the slot holds MANY simultaneous values that ACCUMULATE (lists, collections, group memberships).
- object_norm: a SHORT canonical normalised form of the value (e.g. "hot" for "she likes coffee piping hot"; "vegetarian" for "user is vegetarian"). Used to test value-equivalence at read time. Keep <= 8 words.
- valid_from, valid_to: ISO strings. Default valid_from = "{session_ts}"; valid_to null for open-ended.
- polarity: "assert" | "deny".
- volatility: "stable" | "preference" | "state".
- confidence: 0.0-1.0.

Skip greetings / small talk / pure questions. Do NOT invent facts.

Return JSON: {{"claims": [{{...}}, ...]}}"""


def _mk_claim_beta(
    c: Dict[str, Any],
    provenance: Provenance,
    canonicaliser: Canonicalizer,
) -> Optional[Claim]:
    """β variant: also fills `claim_key`/`slot_type`/`object_norm`."""
    claim = _mk_claim(c, provenance)
    if claim is None:
        return None
    raw_key = c.get("claim_key") or {}
    if isinstance(raw_key, dict):
        ent = raw_key.get("entity") or claim.subject or "user"
        slot = raw_key.get("slot_name") or claim.predicate or "unspecified_slot"
    elif isinstance(raw_key, (list, tuple)) and len(raw_key) == 2:
        ent, slot = raw_key
    else:
        ent = claim.subject or "user"
        slot = claim.predicate or "unspecified_slot"
    claim.claim_key = canonicaliser.canonical_claim_key(ent, slot)
    raw_slot_type = c.get("slot_type")
    if raw_slot_type in ("single_valued", "multi_valued"):
        claim.slot_type = raw_slot_type
    else:
        claim.slot_type = "single_valued"  # default — paper's primary scope
    raw_norm = c.get("object_norm")
    if isinstance(raw_norm, str) and raw_norm.strip():
        claim.object_norm = raw_norm.strip().lower()[:80]
    else:
        claim.object_norm = canonicaliser.canonical_object_norm(claim.object or claim.content)
    return claim


def extract_claims_session_beta(
    session_id: str,
    session_ts: Optional[str],
    turns: List[Dict[str, Any]],
    canonicaliser: Canonicalizer,
    *,
    model: Optional[str] = None,
    max_claims: int = 20,
) -> List[Claim]:
    """β round-2 session writer — emits claim_key / slot_type / object_norm.

    The `canonicaliser` is shared with the read-side parser so write-time
    and read-time claim_keys are byte-equal.
    """
    if not turns:
        return []
    lines = []
    for ti, t in enumerate(turns):
        if not isinstance(t, dict):
            continue
        speaker = t.get("speaker") or "user"
        text = (t.get("text") or "").strip().replace("\n", " ")
        if not text:
            continue
        lines.append(f"[{ti}] ({speaker}): {text[:800]}")
    if not lines:
        return []
    prompt = _BETA_SESSION_USER_TMPL.format(
        session_id=session_id,
        session_ts=session_ts or "unknown",
        turn_block="\n".join(lines),
    )
    payload = chat_json(
        prompt,
        system=_EXTRACTION_SYS,
        model=model,
        default={"claims": []},
        temperature=0.0,
        max_tokens=2000,
    )
    raw = payload.get("claims", []) if isinstance(payload, dict) else []
    out: List[Claim] = []
    for c in raw[:max_claims]:
        if not isinstance(c, dict):
            continue
        ti = c.get("turn_id")
        try:
            turn_id = int(ti)
        except Exception:
            turn_id = -1
        speaker = c.get("speaker") or "user"
        prov = Provenance(
            session_id=session_id,
            turn_id=turn_id,
            speaker=speaker if speaker in ("user", "assistant") else "user",
            session_ts=session_ts,
        )
        cl = _mk_claim_beta(c, prov, canonicaliser)
        if cl is not None:
            out.append(cl)
    return out


__all__ = [
    "extract_claims",
    "extract_claims_session",
    "extract_claims_session_beta",
]
