"""LangChain tool: 混合检索.

Agent 固定走 hybrid_rerank；context 条数由 profile agent.context_top_k 或 rerank_top_n 决定。
CPU 模型分时加载见 docs/m3_agent.md §4。
"""

from __future__ import annotations

from apps.retrieval.langchain.hybrid_chain import retrieve_context


async def hybrid_search(query: str, top_k: int = 20) -> list[dict]:
    hits = await retrieve_context(query, mode="hybrid_rerank")
    return hits[:top_k]
