"""Qdrant 向量 POC — 与 Milvus 对照（可选运行）."""

from __future__ import annotations

from typing import Any


def upsert_chunks(
    collection: str,
    ids: list[str],
    vectors: list[list[float]],
    payloads: list[dict[str, Any]],
    *,
    url: str = "http://localhost:6333",
) -> int:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    client = QdrantClient(url=url)
    dim = len(vectors[0])
    if not client.collection_exists(collection):
        client.create_collection(collection, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
    points = [
        PointStruct(id=i, vector=vectors[i], payload=payloads[i])
        for i in range(len(ids))
    ]
    client.upsert(collection_name=collection, points=points)
    return len(points)


def search(
    collection: str,
    vector: list[float],
    *,
    url: str = "http://localhost:6333",
    limit: int = 5,
) -> list[dict]:
    from qdrant_client import QdrantClient

    client = QdrantClient(url=url)
    hits = client.search(collection_name=collection, query_vector=vector, limit=limit)
    return [{"id": h.id, "score": h.score, "payload": h.payload} for h in hits]
