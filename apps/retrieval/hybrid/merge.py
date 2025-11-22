"""Hybrid retrieval — Milvus + OpenSearch + RRF."""

from __future__ import annotations

from apps.retrieval.core import ChunkHit, bm25_search, get_retrieval_config, vector_search
from apps.retrieval.hybrid.rrf import reciprocal_rank_fusion


def hybrid_retrieve(
    query: str,
    *,
    vector_top_k: int | None = None,
    bm25_top_k: int | None = None,
    rrf_k: int | None = None,
    top_n: int | None = None,
) -> list[ChunkHit]:
    cfg = get_retrieval_config()
    vector_top_k = vector_top_k or cfg.get("vector_top_k", 20)
    bm25_top_k = bm25_top_k or cfg.get("bm25_top_k", 20)
    rrf_k = rrf_k if rrf_k is not None else cfg.get("rrf_k", 60)
    top_n = top_n or cfg.get("rerank_top_n", 5) * 3

    vec_hits = vector_search(query, vector_top_k)
    bm25_hits = bm25_search(query, bm25_top_k)
    id_to_hit = {h.chunk_id: h for h in vec_hits + bm25_hits}

    fused = reciprocal_rank_fusion(
        [[h.chunk_id for h in vec_hits], [h.chunk_id for h in bm25_hits]],
        k=rrf_k,
        top_n=top_n,
    )

    results: list[ChunkHit] = []
    for chunk_id, score in fused:
        base = id_to_hit[chunk_id]
        results.append(
            ChunkHit(
                chunk_id=base.chunk_id,
                doc_id=base.doc_id,
                source_file=base.source_file,
                title=base.title,
                text=base.text,
                score=score,
                retriever="hybrid",
            )
        )
    return results
