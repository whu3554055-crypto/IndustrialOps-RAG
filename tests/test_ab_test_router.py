"""Phase 3 A/B 路由与配置."""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.ab_test.config import load_ab_test_config
from apps.ab_test.router import select_variant


def test_select_variant_sticky(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "apps.ab_test.config.load_profile",
        lambda: {
            "ab_test": {
                "enabled": True,
                "experiment_id": "exp_test",
                "traffic_split": 0.5,
                "scope": "search",
                "version_a": {"label": "A", "mode": "hybrid_rerank"},
                "version_b": {"label": "B", "mode": "graph"},
            }
        },
    )
    cfg = load_ab_test_config()
    assert cfg is not None
    first = select_variant("user-42", cfg)
    for _ in range(50):
        assert select_variant("user-42", cfg) == first


def test_load_ab_test_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "apps.ab_test.config.load_profile",
        lambda: {"ab_test": {"enabled": False}},
    )
    assert load_ab_test_config() is None


def test_traffic_split_extremes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "apps.ab_test.config.load_profile",
        lambda: {
            "ab_test": {
                "enabled": True,
                "experiment_id": "exp_edge",
                "traffic_split": 0.0,
                "scope": "search",
                "version_a": {"label": "A", "mode": "hybrid_rerank"},
                "version_b": {"label": "B", "mode": "graph"},
            }
        },
    )
    cfg = load_ab_test_config()
    assert cfg is not None
    assert select_variant("any", cfg).variant == "A"

    monkeypatch.setattr(
        "apps.ab_test.config.load_profile",
        lambda: {
            "ab_test": {
                "enabled": True,
                "experiment_id": "exp_edge",
                "traffic_split": 1.0,
                "scope": "search",
                "version_a": {"label": "A", "mode": "hybrid_rerank"},
                "version_b": {"label": "B", "mode": "graph"},
            }
        },
    )
    cfg = load_ab_test_config()
    assert cfg is not None
    assert select_variant("any", cfg).variant == "B"


def test_assignment_file_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.ab_test.assignment_log import write_assignment

    path = tmp_path / "ab.jsonl"
    monkeypatch.setattr("apps.ab_test.assignment_log.assignment_file_path", lambda: path)
    monkeypatch.setattr("apps.ab_test.assignment_log.assignment_backend", lambda: "file")

    row = write_assignment(
        log_id="00000000-0000-4000-8000-000000000001",
        experiment_id="exp1",
        session_id="s1",
        variant="A",
        retrieval_mode="hybrid_rerank",
        scope="search",
        latency_ms=12.5,
    )
    assert row["stored"] == "file"
    text = path.read_text(encoding="utf-8")
    assert "exp1" in text
    assert '"variant": "A"' in text
