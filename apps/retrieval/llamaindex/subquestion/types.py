"""LlamaIndex SubQuestionQueryEngine 轻量数据类型（无 core 依赖）."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryEngineTool:
    """对应 LlamaIndex QueryEngineTool 元数据（检索-only，无 LLM）."""

    name: str
    description: str


@dataclass(frozen=True)
class SubQuestion:
    """单条子问题及其目标检索工具."""

    sub_question: str
    tool_name: str
