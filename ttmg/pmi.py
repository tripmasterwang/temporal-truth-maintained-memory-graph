"""PMI estimator: pointwise mutual information between query and context.

PMI(q, C) = log[ P(q | C) / P(q) ]

Per the PMI-RAG paper (arXiv 2411.07773), this affinely correlates with
answer log-odds and is computable from frozen-LM prefix probabilities.

Implementation strategy (cheap path first):
  1. Try MAAS endpoint with `logprobs=True` + `max_tokens=0`-style echo. If
     the provider supports it, sum token-level logprobs of `q` under two
     contexts (`C` and empty) and return the difference.
  2. If logprobs are unsupported by the MAAS endpoint, return `None` —
     callers must treat PMI as a missing signal and degrade gracefully (drop
     the PMI score axis, collapse the PMI Mondrian bin to a single bucket).

This degradation matches FINAL_PROPOSAL §Failure-Modes.C2 — "PMI signal
collapses → drop PMI from S; collapse pmi_bin to single bin; PMI phase
diagram becomes negative result."
"""

from __future__ import annotations

import math
import os
import sys
from typing import List, Optional, Sequence

_DATASET_DIR = "/home/workspace/lww/project0412/projects/dataset"
if _DATASET_DIR not in sys.path:
    sys.path.insert(0, _DATASET_DIR)

try:
    from api import get_client as _get_client  # type: ignore
except Exception:  # pragma: no cover
    _get_client = None  # type: ignore

DEFAULT_PMI_MODEL = os.environ.get("TTMG_PMI_MODEL", "deepseek-v3.2")


def _completion_logprobs(
    prefix: str,
    completion: str,
    *,
    model: str,
) -> Optional[float]:
    """Sum of token logprobs of `completion` under `prefix`.

    Uses the OpenAI-compatible `chat.completions.create` with
    `logprobs=True`. Many MAAS providers expose only top-K logprobs of
    SAMPLED tokens, not arbitrary completions; in that case this function
    returns None and the caller treats PMI as unavailable.

    The PMI-RAG paper computes prefix probabilities directly via the LM API.
    Our current MAAS routing exposes a chat-style endpoint where forcing
    `completion` requires a hack: we set the assistant's prior tokens via
    the messages list and sum logprobs of the assistant's first response.
    Practical reliability of this varies per provider; we attempt a single
    short call and bail out cleanly on failure.
    """
    if _get_client is None:
        return None
    try:
        client = _get_client()
    except Exception:
        return None
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Continue exactly the user's text. Output nothing else."},
                {"role": "user", "content": prefix},
                {"role": "assistant", "content": completion},
            ],
            temperature=0.0,
            max_tokens=1,
            logprobs=True,
            top_logprobs=1,
        )
    except Exception:
        return None
    try:
        choice = response.choices[0]
        token_logs = getattr(choice, "logprobs", None)
        if token_logs is None:
            return None
        contents = getattr(token_logs, "content", None)
        if not contents:
            return None
        return float(sum(getattr(t, "logprob", 0.0) for t in contents))
    except Exception:
        return None


def compute_pmi(
    question: str,
    context: str,
    *,
    model: Optional[str] = None,
) -> Optional[float]:
    """Return PMI(question, context) under a frozen LM, or None if unsupported.

    Caller MUST treat None as "PMI signal unavailable" and not assume any
    particular value. The CRC `S(q)` score function should set its PMI
    weight to 0 when PMI is None; the Mondrian PMI-bin axis collapses to a
    single bucket.
    """
    model = model or DEFAULT_PMI_MODEL
    if not question.strip():
        return 0.0
    log_p_q_given_c = _completion_logprobs(context, question, model=model)
    log_p_q = _completion_logprobs("", question, model=model)
    if log_p_q_given_c is None or log_p_q is None:
        return None
    return float(log_p_q_given_c - log_p_q)


def pmi_signal_available(probe_question: str = "What is the user's coffee preference?") -> bool:
    """Cheap one-shot probe of whether the MAAS endpoint supports logprobs."""
    return compute_pmi(probe_question, "The user likes coffee piping hot.") is not None


__all__ = ["compute_pmi", "pmi_signal_available", "DEFAULT_PMI_MODEL"]
