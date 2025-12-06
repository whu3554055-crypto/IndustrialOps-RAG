"""LangChain LCEL — hybrid + rerank 主链.

M2/M3 共用：Agent 通过 hybrid_search 调用 mode=hybrid_rerank。
16GB 本机：rerank 前 release_embedder()，见 docs/m2_retrieval.md §3.3 / m3_agent.md §4。
"""

from __future__ import annotations

import asyncio

from apps.retrieval.core import ChunkHit, bm25_search, get_retrieval_config, release_embedder, vector_search
from apps.retrieval.hybrid.merge import hybrid_retrieve
from apps.retrieval.rerank.bge_reranker import release_reranker, rerank_hits


async def retrieve_context(
    query: str,
    *,
    mode: str = "hybrid_rerank",
    rerank: bool | None = None,
) -> list[dict]:
    cfg = get_retrieval_config()
    top_n = cfg.get("rerank_top_n", 5)
    use_rerank = rerank if rerank is not None else mode.endswith("rerank")

    if mode in ("vector", "vector_only"):
        hits = await asyncio.to_thread(vector_search, query)
    elif mode in ("bm25", "keyword", "bm25_only"):
        hits = await asyncio.to_thread(bm25_search, query)
    elif mode in ("hybrid", "hybrid_rerank"):
        hits = await asyncio.to_thread(hybrid_retrieve, query)
    else:
        raise ValueError(f"Unknown retrieval mode: {mode}")

    if use_rerank and hits:
        release_embedder()
        hits = await asyncio.to_thread(rerank_hits, query, hits, top_n)
        release_reranker()
    else:
        hits = hits[:top_n]

    return [h.to_dict() if isinstance(h, ChunkHit) else h for h in hits]
