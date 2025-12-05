"""Retrieval confidence + answer faithfulness checks.

MIN_RERANK_SCORE：BGE rerank 原始分阈值，低于则拒答（见 docs/m3_agent.md §8）。
check_answer_supported：LLM 首行 YES/NO 判答案是否被 context 支持。
"""

from __future__ import annotations

from apps.agent.prompts import SELF_CHECK_SYSTEM
from apps.generation.llm_router import generate

# BGE reranker raw score; below this treat as low-confidence retrieval.
MIN_RERANK_SCORE = -2.0


def check_retrieval_confidence(hits: list[dict]) -> bool:
    if not hits:
        return False
    return float(hits[0].get("score", 0.0)) >= MIN_RERANK_SCORE


async def check_answer_supported(query: str, answer: str, context: str) -> bool:
    user = (
        f"参考资料：\n{context}\n\n"
        f"问题：{query}\n\n"
        f"候选答案：\n{answer}"
    )
    raw = await generate(
        [
            {"role": "system", "content": SELF_CHECK_SYSTEM},
            {"role": "user", "content": user},
        ]
    )
    first_line = raw.strip().splitlines()[0].strip().upper() if raw.strip() else "NO"
    return first_line.startswith("YES")
