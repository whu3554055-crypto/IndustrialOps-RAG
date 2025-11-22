"""LlamaIndex VectorStoreIndex — Milvus."""

from __future__ import annotations

import asyncio

from apps.retrieval.core import vector_search


async def query_vector(query: str, top_k: int = 20) -> list[dict]:
    hits = await asyncio.to_thread(vector_search, query, top_k)
    return [h.to_dict() for h in hits]
