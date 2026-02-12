"""Agentic RAG 主管道 — LangChain 编排.

学习文档：docs/m3_agent.md（流程图、拒答路径、verify_m3、profile 参数）

入口：run_agentic_rag(session_id, query)
  改写 → hybrid_rerank → 生成 → 自检（可选二次检索）→ 拒答或返回答案+citations
"""

from __future__ import annotations

import time
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
from apps.ab_test.assignment_log import write_assignment
from apps.ab_test.resolve import resolve_retrieval_mode
from apps.retrieval_log import write_retrieval_log
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
    experiment_id: str | None = None
    variant: str | None = None
    retrieval_mode: str | None = None


def _agent_config() -> dict:
    return load_profile(get_settings().ior_profile).get("agent", {})


def _build_messages(
    system: str,
    history: list[dict[str, str]],
    context: str,
    query: str,
    *,
    include_history: bool,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    if include_history:
        messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": f"参考资料：\n{context}\n\n用户问题：{query}",
        }
    )
    return messages


def _context_top_k(cfg: dict) -> int:
    if "context_top_k" in cfg:
        return int(cfg["context_top_k"])
    retrieval = load_profile(get_settings().ior_profile).get("retrieval", {})
    return int(retrieval.get("rerank_top_n", 5))


def _max_chars_per_chunk(cfg: dict) -> int | None:
    raw = cfg.get("max_chars_per_chunk")
    return int(raw) if raw is not None else None


def _include_history_in_generation(cfg: dict) -> bool:
    return bool(cfg.get("include_history_in_generation", False))


async def _retrieve(search_query: str, cfg: dict, *, mode: str) -> list[dict]:
    return await hybrid_search(search_query, top_k=_context_top_k(cfg), mode=mode)


async def _generate_answer(
    query: str,
    history: list[dict[str, str]],
    hits: list[dict],
    cfg: dict,
) -> str:
    context = format_context(hits, max_chars_per_chunk=_max_chars_per_chunk(cfg))
    messages = _build_messages(
        load_system_prompt(),
        history,
        context,
        query,
        include_history=_include_history_in_generation(cfg),
    )
    return await generate(messages)


async def run_agentic_rag(
    session_id: str,
    query: str,
    *,
    history: list[dict] | None = None,
) -> PipelineResult:
    cfg = _agent_config()
    max_turns = int(cfg.get("max_history_turns", 3))
    self_check_enabled = bool(cfg.get("self_check_enabled", True))
    refuse_on_low_confidence = bool(cfg.get("refuse_on_low_confidence", True))

    session_history = history if history is not None else get_history(session_id, max_turns)
    log_id = str(uuid.uuid4())
    resolved = resolve_retrieval_mode(session_id)
    retrieval_mode = resolved.mode
    experiment_id = resolved.experiment_id
    variant = resolved.variant
    retrieve_latency_ms = 0.0

    search_query = await rewrite_query(query, session_history)
    t0 = time.perf_counter()
    hits = await _retrieve(search_query, cfg, mode=retrieval_mode)
    retrieve_latency_ms += (time.perf_counter() - t0) * 1000.0

    def _log(h: list[dict], refused: bool) -> None:
        write_retrieval_log(
            log_id=log_id,
            session_id=session_id,
            query=query,
            search_query=search_query,
            hits=h,
            refused=refused,
            experiment_id=experiment_id,
            variant=variant,
            retrieval_mode=retrieval_mode,
        )
        if experiment_id and variant:
            write_assignment(
                log_id=log_id,
                experiment_id=experiment_id,
                session_id=session_id,
                variant=variant,
                retrieval_mode=retrieval_mode,
                scope="chat",
                latency_ms=retrieve_latency_ms,
            )

    def _refuse(h: list[dict]) -> PipelineResult:
        append_turn(session_id, query, REFUSE_MESSAGE)
        _log(h, refused=True)
        return PipelineResult(
            answer=REFUSE_MESSAGE,
            citations=hits_to_citations(h),
            retrieval_log_id=log_id,
            refused=True,
            experiment_id=experiment_id,
            variant=variant,
            retrieval_mode=retrieval_mode,
        )

    if refuse_on_low_confidence and not check_retrieval_confidence(hits):
        return _refuse([])

    answer = await _generate_answer(query, session_history, hits, cfg)
    check_context = format_context(hits, max_chars_per_chunk=_max_chars_per_chunk(cfg))

    if self_check_enabled:
        supported = await check_answer_supported(query, answer, check_context)
        if not supported:
            expanded_query = await rewrite_query(query, session_history, expand=True)
            t1 = time.perf_counter()
            hits_retry = await _retrieve(expanded_query, cfg, mode=retrieval_mode)
            retrieve_latency_ms += (time.perf_counter() - t1) * 1000.0
            if hits_retry and check_retrieval_confidence(hits_retry):
                answer_retry = await _generate_answer(query, session_history, hits_retry, cfg)
                retry_context = format_context(
                    hits_retry, max_chars_per_chunk=_max_chars_per_chunk(cfg)
                )
                if await check_answer_supported(query, answer_retry, retry_context):
                    hits = hits_retry
                    answer = answer_retry
                else:
                    return _refuse(hits_retry)
            else:
                return _refuse(hits)

    append_turn(session_id, query, answer)
    _log(hits, refused=False)
    return PipelineResult(
        answer=answer,
        citations=hits_to_citations(hits),
        retrieval_log_id=log_id,
        refused=False,
        experiment_id=experiment_id,
        variant=variant,
        retrieval_mode=retrieval_mode,
    )
