"""SubQuestionQueryEngine — 规则分解单元测试（无 Milvus/OpenSearch）."""

from __future__ import annotations

import pytest

from apps.retrieval.llamaindex.subquestion.question_gen import (
    LLMQuestionGenerator,
    RuleBasedQuestionGenerator,
    assign_tool_name,
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
    assert assign_tool_name("故障码 E1024 原因", tool_names={"hybrid", "keyword"}) == "keyword"
    assert assign_tool_name("P-101 出口压力", tool_names={"hybrid", "keyword"}) == "hybrid"


def test_rule_based_generator_includes_original_for_compound() -> None:
    gen = RuleBasedQuestionGenerator(include_original=True)
    subqs = gen.generate("A？还有 B", _TOOL_DEFS)
    texts = [sq.sub_question for sq in subqs]
    assert "A？还有 B" in texts
    assert any("A" in t for t in texts)
    assert any("B" in t for t in texts)


def test_rule_based_generator_assigns_keyword_tool_for_fault_code_part() -> None:
    gen = RuleBasedQuestionGenerator(include_original=False)
    subqs = gen.generate("P-101 参数；故障码 E1024 怎么处理", _TOOL_DEFS)
    by_text = {sq.sub_question: sq.tool_name for sq in subqs}
    assert by_text["P-101 参数"] == "hybrid"
    assert by_text["故障码 E1024 怎么处理"] == "keyword"


def test_llm_generator_raises_not_implemented() -> None:
    gen = LLMQuestionGenerator()
    with pytest.raises(NotImplementedError, match="M6"):
        gen.generate("q", _TOOL_DEFS)
