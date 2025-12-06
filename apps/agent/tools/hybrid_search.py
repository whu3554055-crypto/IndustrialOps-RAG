"""LangChain tool: 混合检索.

Agent 固定走 hybrid_rerank；检索链见 docs/m2_retrieval.md §3。
"""

from __future__ import annotations

from apps.retrieval.langchain.hybrid_chain import retrieve_context


async def hybrid_search(query: str, top_k: int = 20) -> list[dict]:
    hits = await retrieve_context(query, mode="hybrid_rerank")
    return hits[:top_k]
