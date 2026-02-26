"""SubQuestion synthesizer 单元测试."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.retrieval.llamaindex.subquestion.synthesizer import (
    SubQuestionAnswer,
    generate_sub_answer,
    run_subquestion_query,
    synthesize_sub_answers,
)
from apps.retrieval.llamaindex.subquestion.types import SubQuestion


@pytest.fixture(autouse=True)
def _stub_agent_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = types.ModuleType("apps.agent.prompts")
    mod.format_context = lambda hits, max_chars_per_chunk=None: hits[0]["text"] if hits else ""
    monkeypatch.setitem(sys.modules, "apps.agent.prompts", mod)


def _hit_dict(cid: str) -> dict:
    return {
        "chunk_id": cid,
        "doc_id": "d1",
        "source_file": "a.md",
        "title": "T",
        "text": "出口压力正常范围 0.3-0.5MPa",
        "score": 1.0,
        "retriever": "hybrid",
    }


@pytest.mark.asyncio
async def test_generate_sub_answer_mock_llm() -> None:
    async def fake_llm(_messages: list[dict], *, max_tokens: int = 256) -> str:
        assert max_tokens == 256
        return "压力范围 0.3-0.5MPa"

    text = await generate_sub_answer(
        "P-101 出口压力范围",
        [_hit_dict("c1")],
        llm_generate=fake_llm,
    )
    assert "0.3" in text


@pytest.mark.asyncio
async def test_synthesize_sub_answers_mock_llm() -> None:
    async def fake_llm(_messages: list[dict], *, max_tokens: int = 512) -> str:
        return "整合后的最终答案"

    out = await synthesize_sub_answers(
        "复合问题",
        [
            SubQuestionAnswer("子问A", "hybrid", "答A"),
            SubQuestionAnswer("子问B", "keyword", "答B"),
        ],
        llm_generate=fake_llm,
    )
    assert out == "整合后的最终答案"


@pytest.mark.asyncio
async def test_run_subquestion_query_end_to_end_mock() -> None:
    h1 = MagicMock()
    h1.to_dict.return_value = _hit_dict("c1")
    h2 = MagicMock()
    h2.to_dict.return_value = _hit_dict("c2")

    detail = MagicMock()
    detail.hits = [h1, h2]
    detail.sub_questions = [
        SubQuestion("P-101 压力范围", "hybrid"),
        SubQuestion("E1024 故障处理", "keyword"),
    ]
    detail.generator = "rule_based"

    mock_engine = MagicMock()
    mock_engine.retrieve = AsyncMock(return_value=detail)

    def _per_sub_hits(sq: SubQuestion, _k: int) -> list[MagicMock]:
        m = MagicMock()
        m.to_dict.return_value = _hit_dict(f"h-{sq.tool_name}")
        return [m]

    mock_engine.retrieve_subquestion_hits = AsyncMock(side_effect=_per_sub_hits)

    calls = {"n": 0}

    async def fake_llm(messages: list[dict], *, max_tokens: int = 512) -> str:
        calls["n"] += 1
        if max_tokens == 256:
            return f"短答{calls['n']}"
        return "最终合成答案"

    result = await run_subquestion_query(
        "P-101 压力？还有 E1024",
        top_k=5,
        llm_generate=fake_llm,
        engine=mock_engine,
    )

    assert result.answer == "最终合成答案"
    assert len(result.sub_answers) == 2
    assert result.generator == "rule_based"
    assert mock_engine.retrieve_subquestion_hits.await_count == 2
