"""LlamaIndex RouterQueryEngine — 自动选检索模式.

规则：故障码/ALM 模式 → keyword；否则 hybrid_rerank。见 docs/m2_retrieval.md §4.2。
"""

from __future__ import annotations

from apps.retrieval.langchain.hybrid_chain import retrieve_context
from apps.retrieval.llamaindex.keyword_engine import query_keyword
from apps.retrieval.llamaindex.vector_engine import query_vector
from apps.retrieval.patterns import FAULT_CODE_PATTERN


async def query_router(query: str) -> list[dict]:
    if FAULT_CODE_PATTERN.search(query):
        keyword_hits = await query_keyword(query, top_k=10)
        if len(keyword_hits) >= 3:
            return keyword_hits[:5]
    return await retrieve_context(query, mode="hybrid_rerank")
