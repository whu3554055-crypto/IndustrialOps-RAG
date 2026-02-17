"""Agent pipeline chat A/B（mock 检索与 LLM）."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from apps.ab_test.config import ABTestConfig, VersionArm


@pytest.mark.asyncio
async def test_chat_ab_uses_variant_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = ABTestConfig(
        experiment_id="exp_chat",
        traffic_split=0.0,
        min_sample_size=10,
        scope="chat",
        version_a=VersionArm("A", "hybrid_rerank"),
        version_b=VersionArm("B", "graph"),
    )
    monkeypatch.setattr("apps.ab_test.resolve.load_ab_test_config", lambda: cfg)

    mock_search = AsyncMock(
        return_value=[
            {
                "score": 2.0,
                "text": "t",
                "source_file": "f.md",
                "doc_id": "d1",
                "chunk_id": "c1",
                "title": "T",
            }
        ]
    )
    monkeypatch.setattr("apps.agent.tools.hybrid_search.dispatch_search", mock_search)
    monkeypatch.setattr(
        "apps.agent.pipeline.rewrite_query",
        AsyncMock(return_value="rewritten"),
    )
    monkeypatch.setattr(
        "apps.agent.pipeline.generate",
        AsyncMock(return_value="answer text"),
    )
    monkeypatch.setattr(
        "apps.agent.pipeline.check_answer_supported",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr("apps.agent.pipeline.get_history", lambda *_a, **_k: [])
    monkeypatch.setattr("apps.agent.pipeline.append_turn", lambda *_a, **_k: None)

    assign_path = tmp_path / "ab.jsonl"
    log_path = tmp_path / "ret.jsonl"
    monkeypatch.setattr(
        "apps.ab_test.assignment_log.assignment_file_path",
        lambda: assign_path,
    )
    monkeypatch.setattr("apps.ab_test.assignment_log.assignment_backend", lambda: "file")
    monkeypatch.setattr("apps.retrieval_log.log_file_path", lambda: log_path)
    monkeypatch.setattr("apps.retrieval_log.log_backend", lambda: "file")

    from apps.agent.pipeline import run_agentic_rag

    result = await run_agentic_rag("sess-chat-1", "泵压力范围？")
    assert result.variant == "A"
    assert result.retrieval_mode == "hybrid_rerank"
    assert result.experiment_id == "exp_chat"
    mock_search.assert_awaited()
    assert mock_search.await_args.args[1] == "hybrid_rerank"
    assert assign_path.is_file()
