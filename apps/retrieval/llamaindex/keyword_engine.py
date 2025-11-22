"""LlamaIndex BM25 / keyword — OpenSearch."""

from __future__ import annotations

import asyncio

from apps.retrieval.core import bm25_search


async def query_keyword(query: str, top_k: int = 20) -> list[dict]:
    hits = await asyncio.to_thread(bm25_search, query, top_k)
    return [h.to_dict() for h in hits]
