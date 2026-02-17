"""Gateway A/B admin 状态接口."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.ab_test.config import ABTestConfig, VersionArm
from apps.gateway.main import app


def test_admin_ab_test_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.gateway.main.load_ab_test_config", lambda: None)
    client = TestClient(app)
    r = client.get("/v1/admin/ab-test/status")
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_admin_ab_test_enabled_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = ABTestConfig(
        experiment_id="exp_admin",
        traffic_split=0.5,
        min_sample_size=10,
        scope="search",
        version_a=VersionArm("A", "hybrid_rerank"),
        version_b=VersionArm("B", "graph"),
    )
    monkeypatch.setattr("apps.gateway.main.load_ab_test_config", lambda: cfg)

    path = tmp_path / "ab.jsonl"
    path.write_text(
        '{"log_id":"1","experiment_id":"exp_admin","session_id":"s","variant":"A",'
        '"retrieval_mode":"hybrid_rerank","scope":"search"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("apps.gateway.main.load_assignments", lambda **_: [
        {
            "variant": "A",
            "scope": "search",
            "experiment_id": "exp_admin",
        }
    ])

    client = TestClient(app)
    r = client.get("/v1/admin/ab-test/status")
    body = r.json()
    assert body["enabled"] is True
    assert body["experiment_id"] == "exp_admin"
    assert body["total_assignments"] == 1
