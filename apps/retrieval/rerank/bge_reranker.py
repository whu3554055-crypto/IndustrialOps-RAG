"""BGE reranker — 默认 CPU（见 profile）."""

from __future__ import annotations

import asyncio
import gc
from functools import lru_cache

from sentence_transformers import CrossEncoder

from apps.config import get_settings, load_profile
from apps.retrieval.core import ChunkHit, resolve_rerank_model_path


def get_rerank_config() -> dict:
    profile = load_profile(get_settings().ior_profile)
    return profile.get("rerank", {})


@lru_cache
def _cross_encoder() -> CrossEncoder:
    s = get_settings()
    cfg = get_rerank_config()
    device = cfg.get("device", s.rerank_device)
    return CrossEncoder(resolve_rerank_model_path(), device=device, trust_remote_code=True)


def release_reranker() -> None:
    """Unload reranker — 与 embedding 模型分时占内存."""
    _cross_encoder.cache_clear()
    gc.collect()


def rerank_sync(query: str, documents: list[dict], top_n: int | None = None) -> list[dict]:
    if not documents:
        return []
    cfg = get_rerank_config()
    top_n = top_n or cfg.get("top_n", 5)
    pairs = [(query, doc["text"]) for doc in documents]
    scores = _cross_encoder().predict(pairs)
    ranked = sorted(
        zip(documents, scores, strict=True),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    results: list[dict] = []
    for doc, score in ranked[:top_n]:
        enriched = dict(doc)
        enriched["score"] = float(score)
        enriched["retriever"] = enriched.get("retriever", "rerank")
        results.append(enriched)
    return results


async def rerank(query: str, documents: list[dict], top_n: int | None = None) -> list[dict]:
    return await asyncio.to_thread(rerank_sync, query, documents, top_n)


def rerank_hits(query: str, hits: list[ChunkHit], top_n: int | None = None) -> list[ChunkHit]:
    ranked = rerank_sync(query, [h.to_dict() for h in hits], top_n=top_n)
    return [
        ChunkHit(
            chunk_id=d["chunk_id"],
            doc_id=d["doc_id"],
            source_file=d["source_file"],
            title=d["title"],
            text=d["text"],
            score=d["score"],
            retriever="rerank",
        )
        for d in ranked
    ]
