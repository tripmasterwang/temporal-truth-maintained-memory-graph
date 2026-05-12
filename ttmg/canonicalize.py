"""Deterministic post-processor that canonicalises (entity_id, slot_name).

Pivot β / Path D round-2: writer + parser both emit a `claim_key` of shape
`(entity_id, slot_name)`; the canonicalizer normalises both halves so write-
side and read-side keys are byte-equal whenever they refer to the same slot.

The implementation is intentionally rule-based (no LLM, no spaCy):
  - lowercase
  - whitespace-collapse + strip
  - non-alphanumeric → underscore (preserves separability)
  - small static alias map for personal pronouns and common entity stand-ins
  - per-process growing alias map for proper nouns the writer first registers,
    so subsequent mentions collapse to the same key

A `Canonicalizer` instance is shared across writer + parser inside one
TTMGSystem run. State persists for the lifetime of the run; reset between
calibration / dev / test if desired.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Tuple

# Static aliases — universal pronouns + common stand-ins → canonical entity id.
# Conservative: only collapse words that almost always mean "the user" in a
# personal-memory context.
_USER_ALIASES = {
    "user", "the user", "i", "me", "myself", "my", "mine",
    "speaker", "the speaker", "u", "self",
}
_ASSISTANT_ALIASES = {
    "assistant", "the assistant", "ai", "the ai", "model", "the model",
    "you", "agent", "the agent",
}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MULTI_UNDERSCORE = re.compile(r"_+")


def _normalise_token(s: str) -> str:
    """lowercase, collapse non-alnum to underscore, strip leading/trailing _."""
    if not s:
        return ""
    s = s.lower().strip()
    s = _NON_ALNUM.sub("_", s)
    s = _MULTI_UNDERSCORE.sub("_", s)
    return s.strip("_")


def _normalise_phrase(s: str) -> str:
    """Same as _normalise_token but preserves multiword structure with _."""
    return _normalise_token(s)


@dataclass
class Canonicalizer:
    """Stateful canonicaliser shared by writer and parser within one run.

    State:
      - `entity_alias_map`: maps a normalised observed surface form to a
        canonical entity id. Grows as new entities are first written.
      - `slot_alias_map`: same for slot names; grows as new slots appear.
    """

    entity_alias_map: Dict[str, str] = field(default_factory=dict)
    slot_alias_map: Dict[str, str] = field(default_factory=dict)
    # Reverse map: canonical key → set of surface forms that mapped to it.
    # Useful for paper-side reproducibility audits (which surface forms
    # collapsed to which canonical key on the dev split).
    entity_canonical_to_surface: Dict[str, set] = field(default_factory=dict)
    slot_canonical_to_surface: Dict[str, set] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    # ------------------------------------------------------------------
    # Entity canonicalisation
    # ------------------------------------------------------------------
    def canonical_entity(self, raw: str) -> str:
        """Return canonical entity id for a raw surface form.

        Rules (in order):
          1. Empty / pronoun-of-self → "user"
          2. Assistant pronoun → "assistant"
          3. Look up in alias_map; if hit, return.
          4. Else: register the normalised form as its own canonical id.
        """
        if not raw:
            return "user"
        norm = _normalise_phrase(raw)
        if not norm:
            return "user"
        if raw.strip().lower() in _USER_ALIASES or norm in {"user", "i", "me", "myself"}:
            self._record_entity_surface("user", raw)
            return "user"
        if raw.strip().lower() in _ASSISTANT_ALIASES:
            self._record_entity_surface("assistant", raw)
            return "assistant"
        with self._lock:
            if norm in self.entity_alias_map:
                canonical = self.entity_alias_map[norm]
            else:
                canonical = norm
                self.entity_alias_map[norm] = canonical
            self._record_entity_surface_locked(canonical, raw)
        return canonical

    def _record_entity_surface(self, canonical: str, surface: str) -> None:
        with self._lock:
            self._record_entity_surface_locked(canonical, surface)

    def _record_entity_surface_locked(self, canonical: str, surface: str) -> None:
        self.entity_canonical_to_surface.setdefault(canonical, set()).add(surface.strip())

    # ------------------------------------------------------------------
    # Slot canonicalisation
    # ------------------------------------------------------------------
    def canonical_slot(self, raw: str) -> str:
        """Return canonical slot name for a raw surface form."""
        if not raw:
            return "unspecified_slot"
        norm = _normalise_phrase(raw)
        if not norm:
            return "unspecified_slot"
        with self._lock:
            if norm in self.slot_alias_map:
                canonical = self.slot_alias_map[norm]
            else:
                canonical = norm
                self.slot_alias_map[norm] = canonical
            self.slot_canonical_to_surface.setdefault(canonical, set()).add(raw.strip())
        return canonical

    # ------------------------------------------------------------------
    # Combined claim_key
    # ------------------------------------------------------------------
    def canonical_claim_key(
        self, entity: Optional[str], slot: Optional[str]
    ) -> Tuple[str, str]:
        ent = self.canonical_entity(entity or "")
        slot_c = self.canonical_slot(slot or "")
        return (ent, slot_c)

    # ------------------------------------------------------------------
    # Object normalisation (lightweight, deterministic)
    # ------------------------------------------------------------------
    def canonical_object_norm(self, raw: str) -> str:
        """Lightweight value canonicalisation.

        Used as a *hint* for the writer's `object_norm` field when the writer
        omits it; the writer's own emission takes priority because the LLM
        understands paraphrase equivalence better than this rule. Returns ''
        on empty input.
        """
        if not raw:
            return ""
        return _normalise_token(raw)

    # ------------------------------------------------------------------
    # Reproducibility audit
    # ------------------------------------------------------------------
    def alias_audit(self) -> Dict[str, Dict[str, list]]:
        """Snapshot of {entities: {canonical: [surfaces]}, slots: {...}}."""
        with self._lock:
            return {
                "entities": {
                    k: sorted(v) for k, v in self.entity_canonical_to_surface.items()
                },
                "slots": {
                    k: sorted(v) for k, v in self.slot_canonical_to_surface.items()
                },
            }


def canonical_key_str(claim_key: Optional[Tuple[str, str]]) -> str:
    """Stable byte-equal key for hashing / SP-index lookup."""
    if claim_key is None:
        return ""
    ent, slot = claim_key
    return f"{ent}||{slot}"


__all__ = ["Canonicalizer", "canonical_key_str"]
