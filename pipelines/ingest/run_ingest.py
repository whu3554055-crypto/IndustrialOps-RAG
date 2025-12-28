"""Ingest CLI — 解析 → 切块 → Milvus + OpenSearch.

学习文档：docs/m1_ingest.md §5
默认：data/raw → bge-m3 embedding → 双索引 recreate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from apps.config import ROOT, get_settings
from pipelines.ingest.chunker import chunk_documents
from pipelines.ingest.documents import load_documents
from pipelines.ingest.indexer import Embedder, MilvusIndexer, OpenSearchIndexer, resolve_embedding_model_path


def run_ingest_job(
    *,
    input_dir: Path,
    batch_size: int = 8,
    recreate: bool = True,
    max_docs: int | None = None,
) -> dict[str, int | str]:
    """可被 Gateway /v1/ingest 或 CLI 调用."""
    if not input_dir.is_absolute():
        input_dir = ROOT / input_dir

    docs = load_documents(input_dir)
    if max_docs is not None and max_docs > 0:
        docs = docs[:max_docs]
    if not docs:
        raise FileNotFoundError(f"No documents under {input_dir}")

    chunks = chunk_documents(docs)
    if not chunks:
        raise ValueError("Chunking produced no chunks")

    s = get_settings()
    model_path = resolve_embedding_model_path()
    embedder = Embedder(model_path, s.embedding_device)
    vectors = embedder.encode([c.text for c in chunks], batch_size=batch_size)

    milvus = MilvusIndexer(s.milvus_collection, embedder.dimension)
    opensearch = OpenSearchIndexer(s.opensearch_index)

    if recreate:
        milvus.recreate()
        opensearch.recreate()
    else:
        if not milvus.has_collection() or not opensearch.exists():
            milvus.recreate()
            opensearch.recreate()
        else:
            doc_ids = sorted({c.doc_id for c in chunks})
            milvus.delete_by_doc_ids(doc_ids)
            opensearch.delete_by_doc_ids(doc_ids)

    milvus.insert(chunks, vectors)
    opensearch.insert(chunks)
    return {
        "docs": len(docs),
        "chunks": len(chunks),
        "input": str(input_dir),
        "recreate": recreate,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IndustrialOps-RAG ingest — md/txt/pdf → Milvus + OpenSearch",
        epilog="示例: python pipelines/ingest/run_ingest.py --input data/raw --batch-size 8\n"
        "文档: docs/m1_ingest.md §5",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", type=str, default="data/raw", help="原始文档目录")
    parser.add_argument("--batch-size", type=int, default=8, help="embedding batch size")
    parser.add_argument(
        "--recreate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="重建索引；--no-recreate 时按 doc_id 覆盖增量",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="仅 ingest 前 N 篇文档（演示/调试；按文件名排序截断）",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    try:
        result = run_ingest_job(
            input_dir=input_dir,
            batch_size=args.batch_size,
            recreate=args.recreate,
            max_docs=args.max_docs,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ingest] {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"[ingest] done: {result['chunks']} chunks from {result['docs']} docs "
        f"(recreate={result['recreate']})"
    )


if __name__ == "__main__":
    main()
