"""Shared vector / BM25 retrieval against Milvus + OpenSearch."""

from __future__ import annotations

import gc
from dataclasses import asdict, dataclass
from functools import lru_cache

from opensearchpy import OpenSearch
from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer

from apps.config import ROOT, get_settings, load_profile


@dataclass
class ChunkHit:
    chunk_id: str
    doc_id: str
    source_file: str
    title: str
    text: str
    score: float
    retriever: str

    def to_dict(self) -> dict:
        return asdict(self)


def get_retrieval_config() -> dict:
    return load_profile(get_settings().ior_profile).get("retrieval", {})


def resolve_embedding_model_path() -> str:
    s = get_settings()
    local = ROOT / "models" / "bge-m3"
    if local.is_dir():
        return str(local)
    return s.embedding_model


def resolve_rerank_model_path() -> str:
    s = get_settings()
    local = ROOT / "models" / "bge-reranker-v2-m3"
    if local.is_dir():
        return str(local)
    return s.rerank_model


@lru_cache
def _embedder() -> SentenceTransformer:
    s = get_settings()
    return SentenceTransformer(
        resolve_embedding_model_path(),
        device=s.embedding_device,
        trust_remote_code=True,
    )


def release_embedder() -> None:
    """Unload embedding model — 16GB 本机与 reranker 互斥加载."""
    _embedder.cache_clear()
    gc.collect()


@lru_cache
def _milvus_client() -> MilvusClient:
    s = get_settings()
    return MilvusClient(uri=f"http://{s.milvus_host}:{s.milvus_port}")


@lru_cache
def _opensearch_client() -> OpenSearch:
    s = get_settings()
    return OpenSearch(
        hosts=[{"host": s.opensearch_host, "port": s.opensearch_port}],
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False,
    )


def _entity_to_hit(entity: dict, score: float, retriever: str) -> ChunkHit:
    return ChunkHit(
        chunk_id=entity["chunk_id"],
        doc_id=entity["doc_id"],
        source_file=entity["source_file"],
        title=entity["title"],
        text=entity["text"],
        score=float(score),
        retriever=retriever,
    )


def vector_search(query: str, top_k: int | None = None) -> list[ChunkHit]:
    cfg = get_retrieval_config()
    top_k = top_k or cfg.get("vector_top_k", 20)
    s = get_settings()
    vec = _embedder().encode([query], normalize_embeddings=True)[0].tolist()
    hits = _milvus_client().search(
        collection_name=s.milvus_collection,
        data=[vec],
        limit=top_k,
        output_fields=["chunk_id", "doc_id", "source_file", "title", "text"],
    )[0]
    return [_entity_to_hit(hit["entity"], hit["distance"], "vector") for hit in hits]


def bm25_search(query: str, top_k: int | None = None) -> list[ChunkHit]:
    cfg = get_retrieval_config()
    top_k = top_k or cfg.get("bm25_top_k", 20)
    s = get_settings()
    resp = _opensearch_client().search(
        index=s.opensearch_index,
        body={
            "query": {"match": {"text": query}},
            "size": top_k,
            "_source": ["chunk_id", "doc_id", "source_file", "title", "text"],
        },
    )
    results: list[ChunkHit] = []
    for hit in resp["hits"]["hits"]:
        src = hit["_source"]
        results.append(
            ChunkHit(
                chunk_id=src["chunk_id"],
                doc_id=src["doc_id"],
                source_file=src["source_file"],
                title=src["title"],
                text=src["text"],
                score=float(hit["_score"]),
                retriever="bm25",
            )
        )
    return results


def list_all_chunks(limit: int = 500) -> list[ChunkHit]:
    s = get_settings()
    resp = _opensearch_client().search(
        index=s.opensearch_index,
        body={
            "query": {"match_all": {}},
            "size": limit,
            "_source": ["chunk_id", "doc_id", "source_file", "title", "text"],
        },
    )
    return [
        ChunkHit(
            chunk_id=hit["_source"]["chunk_id"],
            doc_id=hit["_source"]["doc_id"],
            source_file=hit["_source"]["source_file"],
            title=hit["_source"]["title"],
            text=hit["_source"]["text"],
            score=1.0,
            retriever="catalog",
        )
        for hit in resp["hits"]["hits"]
    ]
