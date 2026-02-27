"""SubQuestion LI benchmark — dry-run recall comparison (CI-safe)."""

from __future__ import annotations

import pytest

from apps.retrieval.llamaindex.subquestion.li_benchmark import (
    BenchmarkSummary,
    compare_case,
    compare_golden,
    recall_hit,
    run_official_li_retrieval,
)


@pytest.mark.asyncio
async def test_recall_hit_matches_source_file() -> None:
    hits = [{"source_file": "samples/pump_p101_manual.md", "chunk_id": "c1"}]
    ok, sources = recall_hit(hits, ["samples/pump_p101_manual.md"], top_k=5)
    assert ok is True
    assert sources == ["samples/pump_p101_manual.md"]


@pytest.mark.asyncio
async def test_compare_case_with_mock_runners() -> None:
    async def self_runner(_q: str, _k: int) -> list[dict]:
        return [{"source_file": "samples/pump_p101_manual.md"}]

    async def official_runner(_q: str, _k: int) -> list[dict]:
        return [{"source_file": "samples/pump_p101_manual.md"}]

    result = await compare_case(
        "P-101 压力？还有 E01",
        ["samples/pump_p101_manual.md"],
        self_runner=self_runner,
        official_runner=official_runner,
    )
    assert result.self_recall is True
    assert result.official_recall is True


@pytest.mark.asyncio
async def test_compare_golden_dry_run(tmp_path) -> None:
    golden = tmp_path / "compound.jsonl"
    golden.write_text(
        '{"question": "Q1", "doc_ids": ["doc.md"], "category": "compound"}\n',
        encoding="utf-8",
    )

    async def runner(_q: str, _k: int) -> list[dict]:
        return [{"source_file": "doc.md"}]

    summary = await compare_golden(
        golden,
        top_k=5,
        self_runner=runner,
        official_runner=runner,
    )
    assert isinstance(summary, BenchmarkSummary)
    assert summary.total == 1
    assert summary.self_passed == 1
    assert summary.official_passed == 1


@pytest.mark.asyncio
async def test_official_li_retrieval_skips_when_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.retrieval.llamaindex.subquestion.li_benchmark.llamaindex_available",
        lambda: False,
    )
    hits = await run_official_li_retrieval("test query", top_k=3)
    assert hits == []
