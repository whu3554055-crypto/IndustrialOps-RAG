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
from apps.retrieval.llamaindex.subquestion.question_gen import split_subquestions
from apps.retrieval.llamaindex.subquestion.synthesizer import run_subquestion_query


@dataclass
class PipelineResult:
    answer: str
    citations: list[dict]
    retrieval_log_id: str | None
    refused: bool
    experiment_id: str | None = None
    variant: str | None = None
    retrieval_mode: str | None = None
    sub_questions: list[dict] | None = None
    sub_answers: list[dict] | None = None
    subquestion_generator: str | None = None


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


def _is_compound_query(query: str) -> bool:
    retrieval = load_profile(get_settings().ior_profile).get("retrieval", {})
    sq_cfg = retrieval.get("sub_question", {})
    min_len = int(sq_cfg.get("min_subquestion_len", 4))
    return len(split_subquestions(query, min_len=min_len)) > 1


def _resolve_effective_mode(
    resolved_mode: str,
    query: str,
    cfg: dict,
    *,
    in_ab_experiment: bool,
) -> str:
    if in_ab_experiment:
        return resolved_mode
    if resolved_mode == "sub_question":
        return resolved_mode
    if bool(cfg.get("sub_question_for_compound")) and _is_compound_query(query):
        return "sub_question"
    return resolved_mode


def _subquestion_synthesis_cfg(cfg: dict) -> dict[str, int | None]:
    return {
        "sub_answer_max_tokens": int(cfg.get("sub_answer_max_tokens", 256)),
        "synthesis_max_tokens": int(cfg.get("synthesis_max_tokens", 512)),
        "max_chars_per_chunk": _max_chars_per_chunk(cfg),
    }


async def _retrieve(search_query: str, cfg: dict, *, mode: str) -> list[dict]:
    return await hybrid_search(search_query, top_k=_context_top_k(cfg), mode=mode)


async def _run_subquestion_path(
    query: str,
    cfg: dict,
    *,
    top_k: int | None = None,
) -> tuple[str, list[dict], list[dict], list[dict], str]:
    synth_cfg = _subquestion_synthesis_cfg(cfg)
    result = await run_subquestion_query(
        query,
        top_k=top_k or _context_top_k(cfg),
        **synth_cfg,
    )
    return (
        result.answer,
        result.hits,
        result.sub_questions,
        result.sub_answers,
        result.generator,
    )


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
    in_ab_experiment = bool(resolved.experiment_id)
    retrieval_mode = _resolve_effective_mode(
        resolved.mode,
        query,
        cfg,
        in_ab_experiment=in_ab_experiment,
    )
    experiment_id = resolved.experiment_id
    variant = resolved.variant
    retrieve_latency_ms = 0.0
    sub_questions: list[dict] | None = None
    sub_answers: list[dict] | None = None
    subquestion_generator: str | None = None
    trace_payload: dict | None = None

    search_query = await rewrite_query(query, session_history)
    t0 = time.perf_counter()

    if retrieval_mode == "sub_question":
        (
            answer,
            hits,
            sub_questions,
            sub_answers,
            subquestion_generator,
        ) = await _run_subquestion_path(search_query, cfg)
        trace_payload = {
            "generator": subquestion_generator,
            "sub_questions": sub_questions,
            "sub_answers": sub_answers,
        }
    else:
        hits = await _retrieve(search_query, cfg, mode=retrieval_mode)
        answer = ""

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
            sub_question_trace=trace_payload,
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
            sub_questions=sub_questions,
            sub_answers=sub_answers,
            subquestion_generator=subquestion_generator,
        )

    if refuse_on_low_confidence and not check_retrieval_confidence(hits):
        return _refuse(hits if hits else [])

    if retrieval_mode != "sub_question":
        answer = await _generate_answer(query, session_history, hits, cfg)

    check_context = format_context(hits, max_chars_per_chunk=_max_chars_per_chunk(cfg))

    if self_check_enabled:
        supported = await check_answer_supported(query, answer, check_context)
        if not supported:
            expanded_query = await rewrite_query(query, session_history, expand=True)
            t1 = time.perf_counter()
            if retrieval_mode == "sub_question":
                (
                    answer_retry,
                    hits_retry,
                    sub_questions,
                    sub_answers,
                    subquestion_generator,
                ) = await _run_subquestion_path(expanded_query, cfg)
                trace_payload = {
                    "generator": subquestion_generator,
                    "sub_questions": sub_questions,
                    "sub_answers": sub_answers,
                }
            else:
                hits_retry = await _retrieve(expanded_query, cfg, mode=retrieval_mode)
                answer_retry = ""
            retrieve_latency_ms += (time.perf_counter() - t1) * 1000.0
            if hits_retry and check_retrieval_confidence(hits_retry):
                if retrieval_mode != "sub_question":
                    answer_retry = await _generate_answer(
                        query, session_history, hits_retry, cfg
                    )
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
        sub_questions=sub_questions,
        sub_answers=sub_answers,
        subquestion_generator=subquestion_generator,
    )
