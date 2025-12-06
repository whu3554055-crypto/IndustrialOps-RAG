"""Milvus dense + OpenSearch BM25 indexing.

schema 与 verify_m1 / M2 retrieval 共用字段；见 docs/m1_ingest.md §3。
"""

from __future__ import annotations

from opensearchpy import OpenSearch
from pymilvus import DataType, MilvusClient
from sentence_transformers import SentenceTransformer

from apps.config import ROOT, get_settings
from pipelines.ingest.chunker import Chunk


def resolve_embedding_model_path() -> str:
    s = get_settings()
    local = ROOT / "models" / "bge-m3"
    if local.is_dir():
        return str(local)
    return s.embedding_model


class Embedder:
    def __init__(self, model_path: str, device: str) -> None:
        self._model = SentenceTransformer(model_path, device=device, trust_remote_code=True)

    @property
    def dimension(self) -> int:
        get_dim = getattr(self._model, "get_embedding_dimension", None)
        if get_dim is not None:
            dim = get_dim()
        else:
            dim = self._model.get_sentence_embedding_dimension()
        if dim is None:
            raise RuntimeError("Could not determine embedding dimension")
        return dim

    def encode(self, texts: list[str], batch_size: int) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > batch_size,
        )
        return vectors.tolist()


class MilvusIndexer:
    def __init__(self, collection_name: str, dim: int) -> None:
        s = get_settings()
        self._collection_name = collection_name
        self._dim = dim
        self._client = MilvusClient(uri=f"http://{s.milvus_host}:{s.milvus_port}")

    def recreate(self) -> None:
        if self._client.has_collection(self._collection_name):
            self._client.drop_collection(self._collection_name)

        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(
            field_name="chunk_id", datatype=DataType.VARCHAR, is_primary=True, max_length=256
        )
        schema.add_field(field_name="doc_id", datatype=DataType.VARCHAR, max_length=256)
        schema.add_field(field_name="source_file", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=256)
        schema.add_field(field_name="chunk_index", datatype=DataType.INT64)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=8192)
        schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=self._dim)

        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )
        self._client.create_collection(
            collection_name=self._collection_name,
            schema=schema,
            index_params=index_params,
        )

    def insert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        rows = [
            {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "source_file": chunk.source_file,
                "title": chunk.title,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "embedding": vector,
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self._client.insert(collection_name=self._collection_name, data=rows)
        self._client.load_collection(self._collection_name)


class OpenSearchIndexer:
    def __init__(self, index_name: str) -> None:
        s = get_settings()
        self._index = index_name
        self._client = OpenSearch(
            hosts=[{"host": s.opensearch_host, "port": s.opensearch_port}],
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
        )

    def recreate(self) -> None:
        if self._client.indices.exists(index=self._index):
            self._client.indices.delete(index=self._index)
        self._client.indices.create(
            index=self._index,
            body={
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                "mappings": {
                    "properties": {
                        "chunk_id": {"type": "keyword"},
                        "doc_id": {"type": "keyword"},
                        "source_file": {"type": "keyword"},
                        "title": {"type": "text"},
                        "chunk_index": {"type": "integer"},
                        "text": {"type": "text"},
                    }
                },
            },
        )

    def insert(self, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            self._client.index(
                index=self._index,
                id=chunk.chunk_id,
                body={
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "source_file": chunk.source_file,
                    "title": chunk.title,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                },
                refresh=True,
            )
