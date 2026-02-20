"""SubQuestion 可用的 QueryEngineTool 注册表."""

from __future__ import annotations

from collections.abc import Callable

from apps.retrieval.core import ChunkHit, bm25_search, get_retrieval_config
from apps.retrieval.hybrid.merge import hybrid_retrieve
from apps.retrieval.llamaindex.subquestion.types import QueryEngineTool

RetrievalToolFn = Callable[[str, int], list[ChunkHit]]

DEFAULT_TOOL_DEFS: list[QueryEngineTool] = [
    QueryEngineTool(
        name="hybrid",
        description="语义+关键词混合检索，适用于参数、流程、现象描述类子问题",
    ),
    QueryEngineTool(
        name="keyword",
        description="BM25 关键词检索，适用于故障码、型号、精确术语类子问题",
    ),
]


def _hybrid_tool(query: str, top_k: int) -> list[ChunkHit]:
    return hybrid_retrieve(query, top_n=top_k)


def _keyword_tool(query: str, top_k: int) -> list[ChunkHit]:
    cfg = get_retrieval_config()
    top_k = top_k or cfg.get("bm25_top_k", 20)
    hits = bm25_search(query, top_k)
    return [
        ChunkHit(
            chunk_id=h.chunk_id,
            doc_id=h.doc_id,
            source_file=h.source_file,
            title=h.title,
            text=h.text,
            score=h.score,
            retriever="keyword",
        )
        for h in hits
    ]


DEFAULT_TOOLS: dict[str, RetrievalToolFn] = {
    "hybrid": _hybrid_tool,
    "keyword": _keyword_tool,
}
