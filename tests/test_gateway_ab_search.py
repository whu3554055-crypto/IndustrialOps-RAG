"""Gateway /v1/search A/B 接入."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from apps.gateway.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_search_without_ab_uses_request_mode(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("apps.gateway.main.load_ab_test_config", lambda: None)
    mock = AsyncMock(return_value=[{"chunk_id": "c1", "doc_id": "d1", "source_file": "s.md", "title": "t", "text": "x", "score": 0.9, "retriever": "hybrid"}])
    monkeypatch.setattr("apps.gateway.main.dispatch_search", mock)

    r = client.post("/v1/search", json={"query": "泵压力", "mode": "vector", "top_k": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "vector"
    assert body.get("experiment_id") is None
    mock.assert_awaited_once()
    assert mock.await_args.args[1] == "vector"


def test_search_ab_requires_session_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.ab_test.config import ABTestConfig, VersionArm

    cfg = ABTestConfig(
        experiment_id="exp_live",
        traffic_split=0.5,
        min_sample_size=10,
        scope="search",
        version_a=VersionArm("A", "hybrid_rerank"),
        version_b=VersionArm("B", "graph"),
    )
    monkeypatch.setattr("apps.gateway.main.load_ab_test_config", lambda: cfg)

    r = client.post("/v1/search", json={"query": "E01", "mode": "vector"})
    assert r.status_code == 400


def test_search_ab_overrides_mode_and_logs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from apps.ab_test.config import ABTestConfig, VersionArm

    cfg = ABTestConfig(
        experiment_id="exp_live",
        traffic_split=0.0,
        min_sample_size=10,
        scope="search",
        version_a=VersionArm("A", "hybrid_rerank"),
        version_b=VersionArm("B", "graph"),
    )
    monkeypatch.setattr("apps.gateway.main.load_ab_test_config", lambda: cfg)
    mock = AsyncMock(return_value=[])
    monkeypatch.setattr("apps.gateway.main.dispatch_search", mock)

    assign_path = tmp_path / "ab.jsonl"
    log_path = tmp_path / "ret.jsonl"
    monkeypatch.setattr(
        "apps.ab_test.assignment_log.assignment_file_path",
        lambda: assign_path,
    )
    monkeypatch.setattr("apps.ab_test.assignment_log.assignment_backend", lambda: "file")
    monkeypatch.setattr("apps.retrieval_log.log_file_path", lambda: log_path)
    monkeypatch.setattr("apps.retrieval_log.log_backend", lambda: "file")

    r = client.post(
        "/v1/search",
        json={"query": "E01", "session_id": "sess-1", "mode": "vector", "top_k": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "hybrid_rerank"
    assert body["variant"] == "A"
    assert body["experiment_id"] == "exp_live"
    assert body["log_id"]
    assert assign_path.is_file()
    assert log_path.is_file()
