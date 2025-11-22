"""LlamaIndex SubQuestionQueryEngine — 复杂问题拆解."""

from __future__ import annotations

import asyncio
import re

from apps.retrieval.core import ChunkHit
from apps.retrieval.hybrid.merge import hybrid_retrieve
from apps.retrieval.hybrid.rrf import reciprocal_rank_fusion


def _split_subquestions(query: str) -> list[str]:
    parts = re.split(r"[？?；;]|以及|还有|另外", query)
    cleaned = [p.strip() for p in parts if len(p.strip()) >= 4]
    return cleaned or [query]


async def query_subquestion(query: str, top_k: int = 10) -> list[dict]:
    subqs = _split_subquestions(query)
    if len(subqs) == 1:
        hits = await asyncio.to_thread(hybrid_retrieve, query, top_n=top_k)
        return [h.to_dict() for h in hits]

    ranked_lists: list[list[str]] = []
    id_to_hit: dict[str, ChunkHit] = {}
    for sub in subqs:
        hits = await asyncio.to_thread(hybrid_retrieve, sub, top_n=top_k)
        ranked_lists.append([h.chunk_id for h in hits])
        id_to_hit.update({h.chunk_id: h for h in hits})

    fused = reciprocal_rank_fusion(ranked_lists, top_n=top_k)
    results = [
        ChunkHit(
            chunk_id=chunk_id,
            doc_id=id_to_hit[chunk_id].doc_id,
            source_file=id_to_hit[chunk_id].source_file,
            title=id_to_hit[chunk_id].title,
            text=id_to_hit[chunk_id].text,
            score=score,
            retriever="sub_question",
        )
        for chunk_id, score in fused
    ]
    return [h.to_dict() for h in results]
