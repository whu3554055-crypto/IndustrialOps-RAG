"""LangChain tool: 按 mode 检索（默认 hybrid_rerank）.

检索链见 docs/m2_retrieval.md §3；A/B 时 mode 由 pipeline 传入。
"""

from __future__ import annotations

from apps.retrieval.mode_dispatch import dispatch_search

DEFAULT_MODE = "hybrid_rerank"


async def hybrid_search(
    query: str,
    top_k: int = 20,
    *,
    mode: str = DEFAULT_MODE,
) -> list[dict]:
    return await dispatch_search(query, mode, top_k)
