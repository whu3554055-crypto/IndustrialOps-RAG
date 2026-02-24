"""子问题生成 — M2 默认 rule-based；`generator=llm` 走 vLLM（失败可回退）."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Awaitable, Callable, Protocol

from apps.retrieval.patterns import FAULT_CODE_PATTERN
from apps.retrieval.llamaindex.subquestion.types import QueryEngineTool, SubQuestion

logger = logging.getLogger(__name__)

SPLIT_PATTERN = re.compile(r"[？?；;]|以及|还有|另外|同时|并且")

LlmGenerateFn = Callable[..., Awaitable[str]]


class QuestionGenerator(Protocol):
    """LlamaIndex QuestionGenerator 协议（async）."""

    @property
    def name(self) -> str: ...

    async def generate(self, query: str, tools: list[QueryEngineTool]) -> list[SubQuestion]: ...


def split_subquestions(query: str, *, min_len: int = 4) -> list[str]:
    """规则拆分复合问句."""
    parts = SPLIT_PATTERN.split(query.strip())
    cleaned = [p.strip() for p in parts if len(p.strip()) >= min_len]
    return cleaned or [query.strip()]


def assign_tool_name(text: str, *, tool_names: set[str]) -> str:
    """按内容选择子问题对应的 QueryEngineTool."""
    if "keyword" in tool_names and FAULT_CODE_PATTERN.search(text):
        return "keyword"
    if "hybrid" in tool_names:
        return "hybrid"
    return next(iter(tool_names))


def _dedupe_subquestions(subqs: list[SubQuestion]) -> list[SubQuestion]:
    seen: set[tuple[str, str]] = set()
    out: list[SubQuestion] = []
    for sq in subqs:
        key = (sq.sub_question, sq.tool_name)
        if key in seen:
            continue
        seen.add(key)
        out.append(sq)
    return out


def _format_tool_list(tools: list[QueryEngineTool]) -> str:
    return "\n".join(f"- {t.name}: {t.description}" for t in tools)


def _build_llm_prompt(query: str, tools: list[QueryEngineTool], *, max_subquestions: int) -> str:
    return (
        "你是工业设备运维知识库助手。将用户的复合问题拆解为若干独立子问题，"
        "并为每个子问题选择最合适的检索工具。\n\n"
        f"可用工具：\n{_format_tool_list(tools)}\n\n"
        f"用户问题：{query.strip()}\n\n"
        "请输出 JSON 数组，每项包含 sub_question（字符串）和 tool_name（必须是上述工具名之一）。"
        f"最多 {max_subquestions} 个子问题。只输出 JSON，不要其他说明。\n\n"
        '示例：[{"sub_question":"P-101出口压力正常范围","tool_name":"hybrid"},'
        '{"sub_question":"E1024故障怎么处理","tool_name":"keyword"}]'
    )


def _extract_json_payload(raw: str) -> str:
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start >= 0 and end > start:
        return raw[start : end + 1]
    return raw.strip()


def parse_subquestions_json(
    raw: str,
    *,
    tool_names: set[str],
    min_subquestion_len: int = 4,
    max_subquestions: int = 5,
) -> list[SubQuestion]:
    """解析 LLM 输出的子问题 JSON."""
    payload = _extract_json_payload(raw)
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError("LLM sub-question output must be a JSON array")

    subqs: list[SubQuestion] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        text = str(item.get("sub_question", "")).strip()
        tool = str(item.get("tool_name", "")).strip()
        if len(text) < min_subquestion_len:
            continue
        if tool not in tool_names:
            tool = assign_tool_name(text, tool_names=tool_names)
        subqs.append(SubQuestion(sub_question=text, tool_name=tool))
        if len(subqs) >= max_subquestions:
            break

    subqs = _dedupe_subquestions(subqs)
    if not subqs:
        raise ValueError("LLM returned no valid sub-questions")
    return subqs


class RuleBasedQuestionGenerator:
    """无 LLM 子问题生成 — 规则拆分 + 工具路由（M2 默认）."""

    def __init__(
        self,
        *,
        min_subquestion_len: int = 4,
        include_original: bool = True,
    ) -> None:
        self._min_len = min_subquestion_len
        self._include_original = include_original

    @property
    def name(self) -> str:
        return "rule_based"

    async def generate(self, query: str, tools: list[QueryEngineTool]) -> list[SubQuestion]:
        tool_names = {t.name for t in tools}
        parts = split_subquestions(query, min_len=self._min_len)
        subqs: list[SubQuestion] = []

        if self._include_original and len(parts) > 1:
            subqs.append(
                SubQuestion(
                    sub_question=query.strip(),
                    tool_name=assign_tool_name(query, tool_names=tool_names),
                )
            )

        for part in parts:
            subqs.append(
                SubQuestion(
                    sub_question=part,
                    tool_name=assign_tool_name(part, tool_names=tool_names),
                )
            )

        return _dedupe_subquestions(subqs)


class LLMQuestionGenerator:
    """vLLM 子问题生成 — 复用 apps.generation.llm_router.generate."""

    def __init__(
        self,
        *,
        max_subquestions: int = 5,
        min_subquestion_len: int = 4,
        max_tokens: int = 512,
        llm_generate: LlmGenerateFn | None = None,
    ) -> None:
        self._max_subquestions = max_subquestions
        self._min_len = min_subquestion_len
        self._max_tokens = max_tokens
        self._llm_generate = llm_generate

    @property
    def name(self) -> str:
        return "llm"

    async def _call_llm(self, messages: list[dict[str, str]]) -> str:
        if self._llm_generate is not None:
            return await self._llm_generate(messages, max_tokens=self._max_tokens)
        from apps.generation.llm_router import generate

        return await generate(messages, max_tokens=self._max_tokens)

    async def generate(self, query: str, tools: list[QueryEngineTool]) -> list[SubQuestion]:
        tool_names = {t.name for t in tools}
        prompt = _build_llm_prompt(query, tools, max_subquestions=self._max_subquestions)
        raw = await self._call_llm([{"role": "user", "content": prompt}])
        return parse_subquestions_json(
            raw,
            tool_names=tool_names,
            min_subquestion_len=self._min_len,
            max_subquestions=self._max_subquestions,
        )


class FallbackQuestionGenerator:
    """LLM 失败或空结果时回退 rule_based."""

    def __init__(
        self,
        primary: QuestionGenerator,
        fallback: RuleBasedQuestionGenerator,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def name(self) -> str:
        return self._primary.name

    async def generate(self, query: str, tools: list[QueryEngineTool]) -> list[SubQuestion]:
        try:
            return await self._primary.generate(query, tools)
        except Exception as exc:
            logger.warning("LLM sub-question generation failed, using rule_based: %s", exc)
            return await self._fallback.generate(query, tools)


def build_question_generator(cfg: dict[str, Any]) -> QuestionGenerator:
    sq_cfg = cfg.get("sub_question", {})
    rule = RuleBasedQuestionGenerator(
        min_subquestion_len=sq_cfg.get("min_subquestion_len", 4),
        include_original=sq_cfg.get("include_original", True),
    )
    kind = sq_cfg.get("generator", "rule_based")
    if kind != "llm":
        return rule

    llm = LLMQuestionGenerator(
        max_subquestions=sq_cfg.get("llm_max_subquestions", 5),
        min_subquestion_len=sq_cfg.get("min_subquestion_len", 4),
        max_tokens=sq_cfg.get("llm_max_tokens", 512),
    )
    if sq_cfg.get("llm_fallback", True):
        return FallbackQuestionGenerator(llm, rule)
    return llm
