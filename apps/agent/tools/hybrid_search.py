"""LangChain tool: 混合检索."""

from __future__ import annotations

from apps.retrieval.langchain.hybrid_chain import retrieve_context


async def hybrid_search(query: str, top_k: int = 20) -> list[dict]:
    hits = await retrieve_context(query, mode="hybrid_rerank")
    return hits[:top_k]
