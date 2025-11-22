"""LlamaIndex Summary Index — 章节级摘要召回."""

from __future__ import annotations

import asyncio

from apps.retrieval.core import ChunkHit, vector_search


async def query_summary(query: str, top_k: int = 10) -> list[dict]:
    hits = await asyncio.to_thread(vector_search, query, top_k * 3)
    seen: set[str] = set()
    summaries: list[ChunkHit] = []
    for hit in hits:
        if hit.doc_id in seen:
            continue
        seen.add(hit.doc_id)
        summaries.append(
            ChunkHit(
                chunk_id=hit.chunk_id,
                doc_id=hit.doc_id,
                source_file=hit.source_file,
                title=hit.title,
                text=f"{hit.title}：{hit.text[:200]}",
                score=hit.score,
                retriever="summary",
            )
        )
        if len(summaries) >= top_k:
            break
    return [h.to_dict() for h in summaries]
