"""auto_tune_params.py — profile 覆盖与评分逻辑."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_score_result_prefers_recall_and_latency() -> None:
    from scripts.auto_tune_params import score_result

    high_recall = score_result(1.0, 1000.0)
    low_recall = score_result(0.5, 1000.0)
    assert high_recall > low_recall


def test_profile_override_restores_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import yaml

    from apps.eval import tune_common

    profiles = tmp_path / "profiles"
    profiles.mkdir()
    profile_file = profiles / "dev-single-node.yaml"
    profile_file.write_text(
        yaml.safe_dump({"retrieval": {"rrf_k": 60}}, allow_unicode=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(tune_common, "PROFILES_DIR", profiles)

    original = profile_file.read_text(encoding="utf-8")
    with tune_common.profile_override("dev-single-node", {"retrieval.rrf_k": 90}):
        data = yaml.safe_load(profile_file.read_text(encoding="utf-8"))
        assert data["retrieval"]["rrf_k"] == 90
    assert profile_file.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_grid_search_dry_run(tmp_path: Path) -> None:
    from scripts.auto_tune_params import grid_search_param

    golden = tmp_path / "g.jsonl"
    golden.write_text('{"question":"q","doc_ids":["a.md"]}\n', encoding="utf-8")

    rows = await grid_search_param(
        "retrieval.rrf_k",
        [30, 60],
        golden,
        profile_name="dev-single-node",
        dry_run=True,
    )
    assert len(rows) == 2
    assert rows[0]["dry_run"] is True
