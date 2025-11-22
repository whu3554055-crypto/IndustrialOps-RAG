"""LlamaIndex Tree Index — 手册目录层级."""

from __future__ import annotations

import asyncio

from apps.retrieval.hybrid.merge import hybrid_retrieve


async def query_tree(query: str, top_k: int = 10) -> list[dict]:
    hits = await asyncio.to_thread(hybrid_retrieve, query, top_n=top_k * 2)
    hits.sort(key=lambda h: h.source_file)
    return [h.to_dict() for h in hits[:top_k]]
