"""Ingest CLI — 解析 → 切块 → Milvus + OpenSearch."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from apps.config import ROOT, get_settings
from pipelines.ingest.chunker import chunk_documents
from pipelines.ingest.documents import load_documents
from pipelines.ingest.indexer import Embedder, MilvusIndexer, OpenSearchIndexer, resolve_embedding_model_path


def main() -> None:
    parser = argparse.ArgumentParser(description="IndustrialOps-RAG ingest")
    parser.add_argument("--input", type=str, default="data/raw", help="原始文档目录")
    parser.add_argument("--batch-size", type=int, default=8, help="embedding batch size")
    parser.add_argument(
        "--recreate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="重建 Milvus collection / OpenSearch index（默认开启）",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.is_absolute():
        input_dir = ROOT / input_dir

    docs = load_documents(input_dir)
    if not docs:
        print(f"[ingest] 未找到 .md/.txt 文档: {input_dir}", file=sys.stderr)
        sys.exit(1)

    chunks = chunk_documents(docs)
    if not chunks:
        print("[ingest] 切块结果为空", file=sys.stderr)
        sys.exit(1)

    s = get_settings()
    model_path = resolve_embedding_model_path()
    print(f"[ingest] docs={len(docs)} chunks={len(chunks)} embed={model_path} device={s.embedding_device}")

    embedder = Embedder(model_path, s.embedding_device)
    texts = [c.text for c in chunks]
    vectors = embedder.encode(texts, batch_size=args.batch_size)

    milvus = MilvusIndexer(s.milvus_collection, embedder.dimension)
    opensearch = OpenSearchIndexer(s.opensearch_index)
    if args.recreate:
        print(f"[ingest] recreate Milvus={s.milvus_collection} OpenSearch={s.opensearch_index}")
        milvus.recreate()
        opensearch.recreate()

    milvus.insert(chunks, vectors)
    opensearch.insert(chunks)
    print(f"[ingest] done: {len(chunks)} chunks indexed")


if __name__ == "__main__":
    main()
