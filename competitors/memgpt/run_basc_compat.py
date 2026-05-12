"""Faithful MemGPT-lite reimplementation (Packer et al., 2024).

The official Letta repo (`competitors/memgpt/MemGPT/`) is service-oriented and
requires Postgres / Docker / a running server, which this project's policy
asks us not to add to shared infra without explicit sign-off. Per the plan's
documented fallback ("if Letta blocks for >1h, swap MemGPT for the simpler
MemGPT-lite paged-memory abstraction described in 2310.08566"), we re-implement
MemGPT's tiered store in-process:

* **Working buffer**: most recent `K` raw sessions (paper §3 — recent context
  stays in main memory).
* **Recall storage**: all earlier raw sessions are vector-indexed for query-
  time retrieval (paper §3 — paged FIFO).
* **Archival notes**: when the union of working + recall would overflow the
  configured token budget, MemGPT's LLM agent decides to "archive" oldest
  sessions by writing a summary note. We approximate that automated decision
  with a deterministic head-tail truncation per session (matches BASC's
  `event_compress` cost function so the comparison is fair across systems).
  This is the *paper's behaviour without the LLM-self-archive cost*, the same
  simplification used by the public LightMem reproduction.

Budget enforcement is **native**: we incrementally archive the oldest raw
session (replacing it with a head-tail-truncated stub) until total kept
tokens fit `budget_tokens`. If even all-archived overshoots, fall back to
post_truncate_to_budget.

Each kept session maps 1:1 to one entry in `ConsolidatedBuffer.retained_text`.
The `retrievable_mask` is True for every kept session (raw or archived) and
False for none — MemGPT's whole story is "nothing is permanently dropped";
when the budget is too tight to keep all archived stubs, the truncate
fallback drops oldest-first to mimic FIFO eviction.

Reference:
  Packer et al., "MemGPT: Towards LLMs as Operating Systems", arXiv 2310.08566.
  Local copy: competitors/memgpt/paper_arxiv_2310.08566.pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from competitors._common.protocol import (  # noqa: E402
    ConsolidatedBuffer, Item, post_truncate_to_budget,
)


def _archive_text(text: str) -> str:
    """Head-tail truncation matching BASC's event_compress (~10% kept)."""
    toks = text.split()
    n = len(toks)
    keep_each = max(1, n // 20)  # 5% from each side ≈ 10% total
    if n <= 2 * keep_each:
        return text
    return " ".join(toks[:keep_each] + ["...[archived]..."] + toks[-keep_each:])


def _archive_n_tokens(n_tokens: int) -> int:
    return max(1, int(round(n_tokens * 0.10)))


def consolidate(memory: list[Item], *, budget_tokens: int,
                reader_model: str | None = None,
                seed: int = 7) -> ConsolidatedBuffer:
    """MemGPT-lite consolidation under a hard token budget.

    Strategy
    --------
    1. Start with all sessions kept raw.
    2. While total tokens > budget: pick the oldest still-raw session and
       replace it with its archival stub (paper's "page out to recall" with
       agent-self-summary approximated by head-tail truncation).
    3. If even all-archived overshoots, drop oldest-first via
       post_truncate_to_budget (FIFO eviction; paper §4.1).
    """
    del reader_model, seed  # MemGPT-lite is reader-agnostic for consolidation.

    n = len(memory)
    retained = [it.text for it in memory]
    sizes = [it.n_tokens for it in memory]
    archived = [False] * n  # newest stays raw longer (recency bias).

    cur = sum(sizes)
    note = "all-raw"
    if cur > budget_tokens:
        # Archive oldest-first.
        for i in range(n):
            if cur <= budget_tokens:
                note = f"archive-{sum(archived)}"
                break
            new_size = _archive_n_tokens(sizes[i])
            cur -= sizes[i] - new_size
            sizes[i] = new_size
            retained[i] = _archive_text(retained[i])
            archived[i] = True
        else:
            note = "all-archived"

    retrievable_mask = [True] * n
    if cur > budget_tokens:
        # FIFO eviction — drop oldest first.
        importance = list(range(n))  # ascending => oldest = lowest, drops first.
        retained, retrievable_mask, cur = post_truncate_to_budget(
            retained, retrievable_mask, sizes, importance, budget_tokens,
        )
        note = "all-archived+fifo-evict"

    return ConsolidatedBuffer(
        retained_text=retained,
        retrievable_mask=retrievable_mask,
        total_tokens=cur,
        budget_enforcement=f"native({note})",
        notes=dict(
            archived=int(sum(archived)),
            kept_raw=int(n - sum(archived)),
            evicted=int(n - sum(retrievable_mask)),
        ),
    )


# ---------------- smoke harness ----------------------------------------------

def _smoke() -> int:
    memory = [
        Item(session_id=f"s{i}",
             text=("user said " + "lorem ipsum " * (8 + i % 4)).strip(),
             n_tokens=120 + 30 * (i % 5))
        for i in range(20)
    ]
    raw = sum(it.n_tokens for it in memory)
    for bf in (0.05, 0.10, 0.20, 1.0):
        cap = int(raw * bf)
        buf = consolidate(memory, budget_tokens=cap)
        kept = sum(buf.retrievable_mask)
        archived = buf.notes["archived"]
        evicted = buf.notes["evicted"]
        print(
            f"MemGPT-lite smoke b={bf}  cap={cap}  total={buf.total_tokens}  "
            f"kept={kept}/{len(memory)}  archived={archived}  evicted={evicted}  "
            f"enforce={buf.budget_enforcement}"
        )
        assert buf.total_tokens <= cap, "post-cap invariant violated"
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(_smoke())
