"""verify_m2.py — 模式选择与验收逻辑单元测试."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_pass_threshold_scales_with_dataset() -> None:
    from scripts.verify_m2 import pass_threshold

    assert pass_threshold(10) == 8
    assert pass_threshold(80) == 64
    assert pass_threshold(40) == 32


def test_get_modes_base_and_extended() -> None:
    from scripts.verify_m2 import MODES_BASE, MODES_EXTENDED, get_modes

    assert len(get_modes(extended=False)) == len(MODES_BASE)
    assert len(get_modes(extended=True)) == len(MODES_EXTENDED)
    assert get_modes(mode="graph", extended=True)[0][0] == "graph"


def test_get_modes_unknown_raises() -> None:
    from scripts.verify_m2 import get_modes

    with pytest.raises(ValueError, match="Unknown mode"):
        get_modes(mode="sub_question", extended=True)


def test_hit_logic() -> None:
    from scripts.verify_m2 import _hit

    assert _hit(["samples/pump_p101_manual.md"], ["pump_p101_manual.md"])
    assert not _hit(["samples/other.md"], ["pump_p101_manual.md"])


@pytest.mark.asyncio
async def test_eval_mode_counts_recall() -> None:
    from scripts.verify_m2 import GoldenCase, eval_mode

    cases = [
        GoldenCase("q1", ["a.md"], "parameter"),
        GoldenCase("q2", ["b.md"], "parameter"),
    ]
    fn = AsyncMock(
        side_effect=[
            [{"source_file": "samples/a.md"}],
            [{"source_file": "samples/c.md"}],
        ]
    )
    result = await eval_mode(cases, "vector", fn)
    assert result["passed"] == 1
    assert result["total"] == 2
    assert result["recall_at_5"] == 0.5


@pytest.mark.asyncio
async def test_eval_mode_timeout() -> None:
    import asyncio

    from scripts.verify_m2 import GoldenCase, eval_mode

    async def slow(_q: str) -> list[dict]:
        await asyncio.sleep(0.2)
        return []

    cases = [GoldenCase("q", ["a.md"], "parameter")]
    result = await eval_mode(cases, "graph", slow, timeout_s=0.05)
    assert result["timeouts"] == 1
    assert result["passed"] == 0


def test_m2_golden_has_five_categories() -> None:
    path = ROOT / "data" / "eval" / "m2_golden.jsonl.example"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    categories = {row.get("category", "") for row in rows}
    for expected in (
        "parameter",
        "fault_code",
        "procedure",
        "troubleshooting",
        "component_relation",
    ):
        assert expected in categories
    assert len(rows) >= 40


def test_write_comparison_markdown(tmp_path: Path) -> None:
    from scripts.verify_m2 import write_comparison_markdown

    out = tmp_path / "compare.md"
    write_comparison_markdown(
        [
            {
                "mode": "graph",
                "recall_at_5": 0.95,
                "passed": 19,
                "total": 20,
                "p95_ms": 100.0,
                "timeouts": 0,
            }
        ],
        out,
    )
    text = out.read_text(encoding="utf-8")
    assert "graph" in text
    assert "95%" in text
