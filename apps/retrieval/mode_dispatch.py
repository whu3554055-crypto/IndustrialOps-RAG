"""按 mode 分发检索 — Gateway / A/B / 后续 chat 共用."""

from __future__ import annotations

from apps.retrieval.langchain.hybrid_chain import retrieve_context
from apps.retrieval.llamaindex.graph_engine import query_graph
from apps.retrieval.llamaindex.keyword_engine import query_keyword
from apps.retrieval.llamaindex.router_engine import query_router
from apps.retrieval.llamaindex.subquestion_engine import query_subquestion
from apps.retrieval.llamaindex.summary_engine import query_summary
from apps.retrieval.llamaindex.tree_engine import query_tree
from apps.retrieval.llamaindex.vector_engine import query_vector


async def dispatch_search(query: str, mode: str, top_k: int) -> list[dict]:
    if mode == "vector":
        hits = await query_vector(query, top_k=top_k)
    elif mode in ("bm25", "keyword"):
        hits = await query_keyword(query, top_k=top_k)
    elif mode == "hybrid":
        hits = await retrieve_context(query, mode="hybrid", rerank=False)
    elif mode == "hybrid_rerank":
        hits = await retrieve_context(query, mode="hybrid_rerank")
    elif mode == "summary":
        hits = await query_summary(query, top_k=top_k)
    elif mode == "tree":
        hits = await query_tree(query, top_k=top_k)
    elif mode == "graph":
        hits = await query_graph(query, top_k=top_k)
    elif mode == "router":
        hits = await query_router(query)
    elif mode == "sub_question":
        hits = await query_subquestion(query, top_k=top_k)
    else:
        raise ValueError(f"Unknown search mode: {mode}")
    return hits[:top_k]
