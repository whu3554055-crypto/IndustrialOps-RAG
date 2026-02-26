"""SubQuestion Query 层 — 子问短答 + ResponseSynthesizer（Phase B）."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from apps.retrieval.llamaindex.subquestion.types import SubQuestion

LlmGenerateFn = Callable[..., Awaitable[str]]

_SUB_ANSWER_PROMPT = """根据参考资料简要回答子问题。只使用资料中的事实；若资料不足请说「资料中未找到相关信息」。控制在3句话内。

参考资料：
{context}

子问题：{sub_question}"""

_SYNTHESIS_PROMPT = """你是工业设备运维知识库助手。用户提出了一个复合问题，下面是从知识库分别检索得到的子问题与参考答案。
请整合为一条连贯、简洁的中文回答，直接回应用户原问题。不要重复罗列子问题编号。

用户原问题：{query}

{sub_blocks}

请给出最终答案："""


@dataclass
class SubQuestionAnswer:
    sub_question: str
    tool_name: str
    answer: str
    hits: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub_question": self.sub_question,
            "tool_name": self.tool_name,
            "answer": self.answer,
        }


@dataclass
class SynthesizedQueryResult:
    answer: str
    hits: list[dict]
    sub_questions: list[dict]
    sub_answers: list[dict]
    generator: str

    def trace_payload(self) -> dict[str, Any]:
        return {
            "generator": self.generator,
            "sub_questions": self.sub_questions,
            "sub_answers": self.sub_answers,
        }


async def _default_generate(messages: list[dict[str, str]], *, max_tokens: int = 512) -> str:
    from apps.generation.llm_router import generate

    return await generate(messages, max_tokens=max_tokens)


async def generate_sub_answer(
    sub_question: str,
    hits: list[dict],
    *,
    max_tokens: int = 256,
    max_chars_per_chunk: int | None = None,
    llm_generate: LlmGenerateFn | None = None,
) -> str:
    from apps.agent.prompts import format_context

    context = format_context(hits, max_chars_per_chunk=max_chars_per_chunk)
    prompt = _SUB_ANSWER_PROMPT.format(context=context, sub_question=sub_question)
    gen = llm_generate or _default_generate
    return (await gen([{"role": "user", "content": prompt}], max_tokens=max_tokens)).strip()


async def synthesize_sub_answers(
    query: str,
    sub_answers: list[SubQuestionAnswer],
    *,
    max_tokens: int = 512,
    llm_generate: LlmGenerateFn | None = None,
) -> str:
    blocks = "\n\n".join(f"【{item.sub_question}】\n{item.answer}" for item in sub_answers)
    prompt = _SYNTHESIS_PROMPT.format(query=query.strip(), sub_blocks=blocks)
    gen = llm_generate or _default_generate
    return (await gen([{"role": "user", "content": prompt}], max_tokens=max_tokens)).strip()


async def run_subquestion_query(
    query: str,
    *,
    top_k: int = 5,
    per_sub_top_k: int | None = None,
    sub_answer_max_tokens: int = 256,
    synthesis_max_tokens: int = 512,
    max_chars_per_chunk: int | None = None,
    llm_generate: LlmGenerateFn | None = None,
    engine: Any | None = None,
) -> SynthesizedQueryResult:
    """完整 SubQuestion Query：拆问 → 分路检索 → 子问短答 → 合成最终答案."""
    if engine is None:
        from apps.retrieval.llamaindex.subquestion.engine import get_default_engine

        engine = get_default_engine()
    detail = await engine.retrieve(query, top_k=top_k)
    per_k = per_sub_top_k or top_k
    gen = llm_generate or _default_generate

    seen: set[str] = set()
    unique_subqs: list[SubQuestion] = []
    for sq in detail.sub_questions:
        if sq.sub_question in seen:
            continue
        seen.add(sq.sub_question)
        unique_subqs.append(sq)

    async def _answer_one(sq: SubQuestion) -> SubQuestionAnswer:
        hit_objs = await engine.retrieve_subquestion_hits(sq, per_k)
        hit_dicts = [h.to_dict() for h in hit_objs]
        text = await generate_sub_answer(
            sq.sub_question,
            hit_dicts,
            max_tokens=sub_answer_max_tokens,
            max_chars_per_chunk=max_chars_per_chunk,
            llm_generate=gen,
        )
        return SubQuestionAnswer(
            sub_question=sq.sub_question,
            tool_name=sq.tool_name,
            answer=text,
            hits=hit_dicts,
        )

    answered = list(await asyncio.gather(*[_answer_one(sq) for sq in unique_subqs]))
    final = await synthesize_sub_answers(
        query,
        answered,
        max_tokens=synthesis_max_tokens,
        llm_generate=gen,
    )
    return SynthesizedQueryResult(
        answer=final,
        hits=[h.to_dict() for h in detail.hits],
        sub_questions=[
            {"sub_question": sq.sub_question, "tool_name": sq.tool_name}
            for sq in detail.sub_questions
        ],
        sub_answers=[a.to_dict() for a in answered],
        generator=detail.generator,
    )
