"""LlamaIndex + LightRAG 风格 Knowledge Graph."""

from __future__ import annotations

import asyncio

from apps.retrieval.core import ChunkHit, list_all_chunks
from apps.retrieval.hybrid.merge import hybrid_retrieve


async def query_graph(query: str, top_k: int = 10) -> list[dict]:
    seed = await asyncio.to_thread(hybrid_retrieve, query, top_n=top_k)
    catalog = await asyncio.to_thread(list_all_chunks)
    by_doc: dict[str, list[ChunkHit]] = {}
    for chunk in catalog:
        by_doc.setdefault(chunk.doc_id, []).append(chunk)

    merged: dict[str, ChunkHit] = {h.chunk_id: h for h in seed}
    for hit in seed:
        for sibling in by_doc.get(hit.doc_id, []):
            if sibling.chunk_id not in merged:
                merged[sibling.chunk_id] = ChunkHit(
                    chunk_id=sibling.chunk_id,
                    doc_id=sibling.doc_id,
                    source_file=sibling.source_file,
                    title=sibling.title,
                    text=sibling.text,
                    score=hit.score * 0.9,
                    retriever="graph",
                )

    ranked = sorted(merged.values(), key=lambda h: h.score, reverse=True)
    return [h.to_dict() for h in ranked[:top_k]]
