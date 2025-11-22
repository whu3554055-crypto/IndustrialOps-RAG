"""LlamaIndex RouterQueryEngine — 自动选检索模式."""

from __future__ import annotations

import re

from apps.retrieval.langchain.hybrid_chain import retrieve_context
from apps.retrieval.llamaindex.keyword_engine import query_keyword
from apps.retrieval.llamaindex.vector_engine import query_vector

FAULT_CODE_PATTERN = re.compile(
    r"\b(?:ALM|E|F)[-_]?\d{2,4}\b|\b(?:故障码|报警码)\s*[A-Z0-9-]+\b",
    re.IGNORECASE,
)


async def query_router(query: str) -> list[dict]:
    if FAULT_CODE_PATTERN.search(query):
        keyword_hits = await query_keyword(query, top_k=10)
        if len(keyword_hits) >= 3:
            return keyword_hits[:5]
    return await retrieve_context(query, mode="hybrid_rerank")
