"""Agentic RAG 主管道 — LangChain 编排."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from apps.agent.prompts import (
    REFUSE_MESSAGE,
    format_context,
    hits_to_citations,
    load_system_prompt,
)
from apps.agent.rewrite import rewrite_query
from apps.agent.session import append_turn, get_history
from apps.agent.tools.hybrid_search import hybrid_search
from apps.agent.tools.self_check import check_answer_supported, check_retrieval_confidence
from apps.config import get_settings, load_profile
from apps.generation.llm_router import generate


@dataclass
class PipelineResult:
    answer: str
    citations: list[dict]
    retrieval_log_id: str | None
    refused: bool


def _agent_config() -> dict:
    return load_profile(get_settings().ior_profile).get("agent", {})


def _build_messages(
    system: str,
    history: list[dict[str, str]],
    context: str,
    query: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": f"参考资料：\n{context}\n\n用户问题：{query}",
        }
    )
    return messages


async def _retrieve(search_query: str) -> list[dict]:
    return await hybrid_search(search_query)


async def _generate_answer(
    query: str,
    history: list[dict[str, str]],
    hits: list[dict],
) -> str:
    context = format_context(hits)
    messages = _build_messages(load_system_prompt(), history, context, query)
    return await generate(messages)


async def run_agentic_rag(
    session_id: str,
    query: str,
    *,
    history: list[dict] | None = None,
) -> PipelineResult:
    """
    1. query rewrite（多轮指代）
    2. hybrid retrieve + rerank
    3. generate (vLLM / TRT / API)
    4. self-check → 拒答或二次检索
    """
    cfg = _agent_config()
    max_turns = int(cfg.get("max_history_turns", 3))
    self_check_enabled = bool(cfg.get("self_check_enabled", True))
    refuse_on_low_confidence = bool(cfg.get("refuse_on_low_confidence", True))

    session_history = history if history is not None else get_history(session_id, max_turns)
    log_id = str(uuid.uuid4())

    search_query = await rewrite_query(query, session_history)
    hits = await _retrieve(search_query)

    if refuse_on_low_confidence and not check_retrieval_confidence(hits):
        append_turn(session_id, query, REFUSE_MESSAGE)
        return PipelineResult(
            answer=REFUSE_MESSAGE,
            citations=[],
            retrieval_log_id=log_id,
            refused=True,
        )

    answer = await _generate_answer(query, session_history, hits)

    if self_check_enabled:
        supported = await check_answer_supported(
            query, answer, format_context(hits)
        )
        if not supported:
            expanded_query = await rewrite_query(
                query, session_history, expand=True
            )
            hits_retry = await _retrieve(expanded_query)
            if hits_retry and check_retrieval_confidence(hits_retry):
                answer_retry = await _generate_answer(
                    query, session_history, hits_retry
                )
                if await check_answer_supported(
                    query, answer_retry, format_context(hits_retry)
                ):
                    hits = hits_retry
                    answer = answer_retry
                else:
                    append_turn(session_id, query, REFUSE_MESSAGE)
                    return PipelineResult(
                        answer=REFUSE_MESSAGE,
                        citations=hits_to_citations(hits_retry),
                        retrieval_log_id=log_id,
                        refused=True,
                    )
            else:
                append_turn(session_id, query, REFUSE_MESSAGE)
                return PipelineResult(
                    answer=REFUSE_MESSAGE,
                    citations=hits_to_citations(hits),
                    retrieval_log_id=log_id,
                    refused=True,
                )

    append_turn(session_id, query, answer)
    return PipelineResult(
        answer=answer,
        citations=hits_to_citations(hits),
        retrieval_log_id=log_id,
        refused=False,
    )
