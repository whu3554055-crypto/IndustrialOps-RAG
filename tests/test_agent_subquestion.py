"""Agent pipeline sub_question 路径."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_chat_sub_question_mode_uses_synthesizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("apps.ab_test.resolve.load_ab_test_config", lambda: None)
    monkeypatch.setattr(
        "apps.agent.pipeline.rewrite_query",
        AsyncMock(return_value="rewritten compound"),
    )
    monkeypatch.setattr("apps.agent.pipeline.get_history", lambda *_a, **_k: [])
    monkeypatch.setattr("apps.agent.pipeline.append_turn", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "apps.agent.pipeline.check_answer_supported",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr("apps.agent.pipeline.write_retrieval_log", lambda **_k: {})
    monkeypatch.setattr(
        "apps.agent.pipeline._agent_config",
        lambda: {
            "self_check_enabled": True,
            "refuse_on_low_confidence": False,
        },
    )

    class _ResolvedSubQ:
        mode = "sub_question"
        experiment_id = None
        variant = None

    monkeypatch.setattr(
        "apps.agent.pipeline.resolve_retrieval_mode",
        lambda _s: _ResolvedSubQ(),
    )

    mock_sq = AsyncMock(
        return_value=(
            "合成答案",
            [
                {
                    "score": 2.0,
                    "text": "t",
                    "source_file": "f.md",
                    "doc_id": "d1",
                    "chunk_id": "c1",
                    "title": "T",
                }
            ],
            [{"sub_question": "q1", "tool_name": "hybrid"}],
            [{"sub_question": "q1", "tool_name": "hybrid", "answer": "a1"}],
            "rule_based",
        )
    )
    monkeypatch.setattr("apps.agent.pipeline._run_subquestion_path", mock_sq)
    mock_retrieve = AsyncMock()
    monkeypatch.setattr("apps.agent.pipeline._retrieve", mock_retrieve)
    mock_gen = AsyncMock()
    monkeypatch.setattr("apps.agent.pipeline.generate", mock_gen)

    from apps.agent.pipeline import run_agentic_rag

    result = await run_agentic_rag("sess-sq", "A？还有 B")
    assert result.retrieval_mode == "sub_question"
    assert result.answer == "合成答案"
    assert result.sub_questions is not None
    assert result.sub_answers is not None
    mock_sq.assert_awaited_once()
    mock_retrieve.assert_not_awaited()
    mock_gen.assert_not_awaited()


@pytest.mark.asyncio
async def test_compound_auto_switch_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.ab_test.resolve.load_ab_test_config", lambda: None)
    monkeypatch.setattr("apps.agent.pipeline.rewrite_query", AsyncMock(return_value="q"))
    monkeypatch.setattr("apps.agent.pipeline.get_history", lambda *_a, **_k: [])
    monkeypatch.setattr("apps.agent.pipeline.append_turn", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "apps.agent.pipeline.check_answer_supported",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr("apps.agent.pipeline.write_retrieval_log", lambda **_k: {})
    monkeypatch.setattr(
        "apps.agent.pipeline._agent_config",
        lambda: {
            "sub_question_for_compound": True,
            "refuse_on_low_confidence": False,
            "self_check_enabled": False,
        },
    )

    class _Resolved:
        mode = "hybrid_rerank"
        experiment_id = None
        variant = None

    monkeypatch.setattr(
        "apps.agent.pipeline.resolve_retrieval_mode",
        lambda _s: _Resolved(),
    )

    mock_sq = AsyncMock(
        return_value=(
            "ok",
            [
                {
                    "score": 1.0,
                    "text": "t",
                    "source_file": "f.md",
                    "doc_id": "d",
                    "chunk_id": "c",
                    "title": "T",
                }
            ],
            [],
            [],
            "rule_based",
        )
    )
    monkeypatch.setattr("apps.agent.pipeline._run_subquestion_path", mock_sq)

    from apps.agent.pipeline import run_agentic_rag

    result = await run_agentic_rag("sess-c", "P-101 压力？还有 E1024 怎么处理")
    assert result.retrieval_mode == "sub_question"
    mock_sq.assert_awaited_once()
