"""子问题生成 — M2 默认 rule-based；LLM 生成器为 M6 预留桩."""

from __future__ import annotations

import re
from typing import Protocol

from apps.retrieval.patterns import FAULT_CODE_PATTERN
from apps.retrieval.llamaindex.subquestion.types import QueryEngineTool, SubQuestion

SPLIT_PATTERN = re.compile(r"[？?；;]|以及|还有|另外|同时|并且")


class QuestionGenerator(Protocol):
    """LlamaIndex QuestionGenerator 协议（检索-only 子集）."""

    @property
    def name(self) -> str: ...

    def generate(self, query: str, tools: list[QueryEngineTool]) -> list[SubQuestion]: ...


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

    def generate(self, query: str, tools: list[QueryEngineTool]) -> list[SubQuestion]:
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
    """LlamaIndex LLMQuestionGenerator 占位 — M6 接入 vLLM 后启用."""

    @property
    def name(self) -> str:
        return "llm"

    def generate(self, query: str, tools: list[QueryEngineTool]) -> list[SubQuestion]:
        raise NotImplementedError(
            "LLM sub-question generation requires vLLM (M6); "
            "set retrieval.sub_question.generator=rule_based for M2."
        )


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


def build_question_generator(cfg: dict) -> QuestionGenerator:
    sq_cfg = cfg.get("sub_question", {})
    kind = sq_cfg.get("generator", "rule_based")
    if kind == "llm":
        return LLMQuestionGenerator()
    return RuleBasedQuestionGenerator(
        min_subquestion_len=sq_cfg.get("min_subquestion_len", 4),
        include_original=sq_cfg.get("include_original", True),
    )
