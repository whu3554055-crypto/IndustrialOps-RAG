"""SubQuestion 可用的 QueryEngineTool 注册表."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from apps.retrieval.core import ChunkHit, bm25_search, get_retrieval_config, release_embedder
from apps.retrieval.hybrid.merge import hybrid_retrieve
from apps.retrieval.llamaindex.subquestion.types import QueryEngineTool
from apps.retrieval.rerank.bge_reranker import release_reranker, rerank_hits

RetrievalToolFn = Callable[[str, int], list[ChunkHit]]

DEFAULT_TOOL_DEFS: list[QueryEngineTool] = [
    QueryEngineTool(
        name="hybrid_rerank",
        description="混合检索+BGE 重排，适用于需要高精度的参数、流程、综合现象描述",
    ),
    QueryEngineTool(
        name="hybrid",
        description="向量+BM25 RRF 混合检索，适用于一般语义与关键词兼顾的子问题",
    ),
    QueryEngineTool(
        name="keyword",
        description="BM25 关键词检索，适用于故障码、型号、精确术语类子问题",
    ),
    QueryEngineTool(
        name="summary",
        description="文档章节级摘要召回，适用于概述、章节概览、文档级背景",
    ),
    QueryEngineTool(
        name="tree",
        description="手册目录/层级检索，适用于章节位置、目录结构、文档组织",
    ),
    QueryEngineTool(
        name="graph",
        description="部件/故障关联图谱扩展，适用于部件关系、影响范围、关联设备",
    ),
]


def _tag_hits(hits: list[ChunkHit], retriever: str) -> list[ChunkHit]:
    return [
        ChunkHit(
            chunk_id=h.chunk_id,
            doc_id=h.doc_id,
            source_file=h.source_file,
            title=h.title,
            text=h.text,
            score=h.score,
            retriever=retriever,
        )
        for h in hits
    ]


def _hits_from_dicts(rows: list[dict], retriever: str) -> list[ChunkHit]:
    return [
        ChunkHit(
            chunk_id=str(r["chunk_id"]),
            doc_id=str(r["doc_id"]),
            source_file=str(r["source_file"]),
            title=str(r["title"]),
            text=str(r["text"]),
            score=float(r["score"]),
            retriever=retriever,
        )
        for r in rows
    ]


def _run_async_engine(coro) -> list[dict]:
    return asyncio.run(coro)


def _hybrid_tool(query: str, top_k: int) -> list[ChunkHit]:
    return _tag_hits(hybrid_retrieve(query, top_n=top_k), "hybrid")


def _hybrid_rerank_tool(query: str, top_k: int) -> list[ChunkHit]:
    hits = hybrid_retrieve(query)
    if not hits:
        return []
    release_embedder()
    reranked = rerank_hits(query, hits, top_k)
    release_reranker()
    return _tag_hits(reranked, "hybrid_rerank")


def _keyword_tool(query: str, top_k: int) -> list[ChunkHit]:
    cfg = get_retrieval_config()
    k = top_k or cfg.get("bm25_top_k", 20)
    return _tag_hits(bm25_search(query, k), "keyword")


def _summary_tool(query: str, top_k: int) -> list[ChunkHit]:
    from apps.retrieval.llamaindex.summary_engine import query_summary

    rows = _run_async_engine(query_summary(query, top_k))
    return _hits_from_dicts(rows, "summary")


def _tree_tool(query: str, top_k: int) -> list[ChunkHit]:
    from apps.retrieval.llamaindex.tree_engine import query_tree

    rows = _run_async_engine(query_tree(query, top_k))
    return _hits_from_dicts(rows, "tree")


def _graph_tool(query: str, top_k: int) -> list[ChunkHit]:
    from apps.retrieval.llamaindex.graph_engine import query_graph

    rows = _run_async_engine(query_graph(query, top_k))
    return _hits_from_dicts(rows, "graph")


DEFAULT_TOOLS: dict[str, RetrievalToolFn] = {
    "hybrid_rerank": _hybrid_rerank_tool,
    "hybrid": _hybrid_tool,
    "keyword": _keyword_tool,
    "summary": _summary_tool,
    "tree": _tree_tool,
    "graph": _graph_tool,
}
