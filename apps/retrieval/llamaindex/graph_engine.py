"""图谱检索 — hybrid seed + 图谱 1-hop 关联 doc 扩展 + 同 doc 兄弟 chunk."""

from __future__ import annotations

import asyncio

from apps.retrieval.core import ChunkHit, list_all_chunks
from apps.retrieval.graph.store import expand_doc_ids, match_entity_ids
from apps.retrieval.hybrid.merge import hybrid_retrieve


async def query_graph(query: str, top_k: int = 10) -> list[dict]:
    seed = await asyncio.to_thread(hybrid_retrieve, query, top_n=top_k)
    catalog = await asyncio.to_thread(list_all_chunks)
    by_doc: dict[str, list[ChunkHit]] = {}
    for chunk in catalog:
        by_doc.setdefault(chunk.doc_id, []).append(chunk)

    merged: dict[str, ChunkHit] = {h.chunk_id: h for h in seed}
    base_score = seed[0].score if seed else 1.0

    # 图谱边关联的文档
    entity_ids = match_entity_ids(query)
    related_docs = expand_doc_ids(entity_ids, hops=1)
    for doc_path in related_docs:
        stem = doc_path.replace(".md", "")
        for chunk in catalog:
            if chunk.source_file == doc_path or chunk.doc_id == stem or stem in chunk.source_file:
                pass
            else:
                continue
            if chunk.chunk_id in merged:
                continue
            merged[chunk.chunk_id] = ChunkHit(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                source_file=chunk.source_file,
                title=chunk.title,
                text=chunk.text,
                score=base_score * 0.85,
                retriever="graph",
            )
    # 同 doc 兄弟 chunk（保留原策略）
    for hit in list(seed):
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
