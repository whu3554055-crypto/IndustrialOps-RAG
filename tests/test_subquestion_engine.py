"""SubQuestionQueryEngine — 规则分解与 LLM 拆问单元测试."""

from __future__ import annotations

import json

import pytest

from apps.retrieval.llamaindex.subquestion.question_gen import (
    FallbackQuestionGenerator,
    LLMQuestionGenerator,
    RuleBasedQuestionGenerator,
    assign_tool_name,
    parse_subquestions_json,
    split_subquestions,
)
from apps.retrieval.llamaindex.subquestion.types import QueryEngineTool


_TOOL_DEFS = [
    QueryEngineTool("hybrid", "语义+关键词混合检索"),
    QueryEngineTool("keyword", "BM25 关键词检索"),
]


def test_split_subquestions_on_compound_query() -> None:
    parts = split_subquestions("P-101 压力范围？还有 E1024 怎么处理")
    assert len(parts) == 2
    assert "P-101" in parts[0]
    assert "E1024" in parts[1]


def test_split_subquestions_fallback_single() -> None:
    assert split_subquestions("短") == ["短"]


def test_assign_tool_name_routes_fault_code_to_keyword() -> None:
    names = {"hybrid", "keyword", "hybrid_rerank"}
    assert assign_tool_name("故障码 E1024 原因", tool_names=names) == "keyword"
    assert assign_tool_name("P-101 出口压力", tool_names=names) == "hybrid_rerank"


def test_assign_tool_name_routes_graph_and_tree() -> None:
    names = {"hybrid", "hybrid_rerank", "graph", "tree", "summary", "keyword"}
    assert assign_tool_name("E1024会影响哪些部件", tool_names=names) == "graph"
    assert assign_tool_name("手册目录结构在哪一章", tool_names=names) == "tree"
    assert assign_tool_name("文档概述是什么", tool_names=names) == "summary"


@pytest.mark.asyncio
async def test_rule_based_generator_includes_original_for_compound() -> None:
    gen = RuleBasedQuestionGenerator(include_original=True)
    subqs = await gen.generate("A？还有 B", _TOOL_DEFS)
    texts = [sq.sub_question for sq in subqs]
    assert "A？还有 B" in texts
    assert any("A" in t for t in texts)
    assert any("B" in t for t in texts)


@pytest.mark.asyncio
async def test_rule_based_generator_assigns_keyword_tool_for_fault_code_part() -> None:
    gen = RuleBasedQuestionGenerator(include_original=False)
    subqs = await gen.generate("P-101 参数；故障码 E1024 怎么处理", _TOOL_DEFS)
    by_text = {sq.sub_question: sq.tool_name for sq in subqs}
    assert by_text["P-101 参数"] == "hybrid"
    assert by_text["故障码 E1024 怎么处理"] == "keyword"


def test_parse_subquestions_json_from_fence() -> None:
    raw = """```json
[{"sub_question": "P-101 出口压力范围", "tool_name": "hybrid"},
 {"sub_question": "故障码 E1024 处理步骤", "tool_name": "keyword"}]
```"""
    subqs = parse_subquestions_json(raw, tool_names={"hybrid", "keyword"})
    assert len(subqs) == 2
    assert subqs[1].tool_name == "keyword"


def test_parse_subquestions_json_repairs_unknown_tool() -> None:
    raw = json.dumps([{"sub_question": "故障码 E1024 原因", "tool_name": "unknown"}])
    subqs = parse_subquestions_json(raw, tool_names={"hybrid", "keyword"})
    assert subqs[0].tool_name == "keyword"


@pytest.mark.asyncio
async def test_llm_generator_calls_vllm_and_parses() -> None:
    payload = json.dumps(
        [
            {"sub_question": "P-101 出口压力正常范围", "tool_name": "hybrid"},
            {"sub_question": "E1024 故障怎么处理", "tool_name": "keyword"},
        ],
        ensure_ascii=False,
    )

    async def fake_llm(_messages: list[dict], *, max_tokens: int = 512) -> str:
        return payload

    gen = LLMQuestionGenerator(llm_generate=fake_llm)
    subqs = await gen.generate("P-101 压力？还有 E1024", _TOOL_DEFS)
    assert len(subqs) == 2
    assert subqs[0].tool_name == "hybrid"
    assert subqs[1].tool_name == "keyword"


@pytest.mark.asyncio
async def test_fallback_uses_rule_based_when_llm_fails() -> None:
    async def broken_llm(_messages: list[dict], *, max_tokens: int = 512) -> str:
        raise RuntimeError("503 vLLM unavailable")

    llm = LLMQuestionGenerator(llm_generate=broken_llm)
    rule = RuleBasedQuestionGenerator(include_original=False)
    gen = FallbackQuestionGenerator(llm, rule)
    subqs = await gen.generate("P-101 参数；故障码 E1024 怎么处理", _TOOL_DEFS)
    assert len(subqs) >= 2
    assert gen.name == "llm"


@pytest.mark.asyncio
async def test_fallback_uses_rule_based_on_invalid_json() -> None:
    async def bad_json(_messages: list[dict], *, max_tokens: int = 512) -> str:
        return "not json at all"

    llm = LLMQuestionGenerator(llm_generate=bad_json)
    rule = RuleBasedQuestionGenerator(include_original=False)
    gen = FallbackQuestionGenerator(llm, rule)
    subqs = await gen.generate("P-101 参数；故障码 E1024 怎么处理", _TOOL_DEFS)
    assert len(subqs) >= 2
