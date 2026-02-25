"""Gateway sub_question include_trace."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from apps.gateway.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_search_sub_question_include_trace(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("apps.gateway.main.load_ab_test_config", lambda: None)
    mock = AsyncMock(
        return_value={
            "hits": [
                {
                    "chunk_id": "c1",
                    "doc_id": "d1",
                    "source_file": "a.md",
                    "title": "t",
                    "text": "x",
                    "score": 0.9,
                    "retriever": "sub_question",
                }
            ],
            "sub_questions": [
                {"sub_question": "P-101 压力", "tool_name": "hybrid_rerank"},
                {"sub_question": "E1024 故障", "tool_name": "keyword"},
            ],
            "generator": "rule_based",
        }
    )
    monkeypatch.setattr("apps.gateway.main.query_subquestion_detail", mock)

    r = client.post(
        "/v1/search",
        json={
            "query": "P-101 压力？还有 E1024",
            "mode": "sub_question",
            "include_trace": True,
            "top_k": 5,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "sub_question"
    assert len(body["sub_questions"]) == 2
    assert body["subquestion_generator"] == "rule_based"
    mock.assert_awaited_once()


def test_search_without_trace_uses_dispatch(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("apps.gateway.main.load_ab_test_config", lambda: None)
    mock_dispatch = AsyncMock(
        return_value=[
            {
                "chunk_id": "c1",
                "doc_id": "d1",
                "source_file": "a.md",
                "title": "t",
                "text": "x",
                "score": 0.9,
                "retriever": "sub_question",
            }
        ]
    )
    mock_detail = AsyncMock()
    monkeypatch.setattr("apps.gateway.main.dispatch_search", mock_dispatch)
    monkeypatch.setattr("apps.gateway.main.query_subquestion_detail", mock_detail)

    r = client.post(
        "/v1/search",
        json={"query": "test", "mode": "sub_question", "top_k": 3},
    )
    assert r.status_code == 200
    assert r.json().get("sub_questions") is None
    mock_dispatch.assert_awaited_once()
    mock_detail.assert_not_awaited()
