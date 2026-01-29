"""tune_common — holdout 划分与小样本 golden."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_split_holdout_is_disjoint() -> None:
    from apps.eval.tune_common import split_holdout

    rows = [{"question": f"q{i}", "doc_ids": ["a.md"]} for i in range(20)]
    tune, holdout = split_holdout(rows, holdout_ratio=0.2, seed=1)
    assert len(tune) + len(holdout) == 20
    assert len(holdout) == 4
    tune_q = {r["question"] for r in tune}
    hold_q = {r["question"] for r in holdout}
    assert not tune_q & hold_q


def test_limited_golden_file(tmp_path: Path) -> None:
    from apps.eval.tune_common import limited_golden_file, load_golden_rows

    src = tmp_path / "g.jsonl"
    src.write_text(
        "\n".join(
            json.dumps({"question": f"q{i}", "doc_ids": ["a.md"]}) for i in range(5)
        ),
        encoding="utf-8",
    )
    with limited_golden_file(src, 3) as limited:
        rows = load_golden_rows(limited)
    assert len(rows) == 3


def test_m2_golden_tiny_exists() -> None:
    path = ROOT / "data" / "eval" / "m2_golden_tiny.jsonl"
    assert path.is_file()
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 10


def test_verify_m2_load_golden_limit() -> None:
    from scripts.verify_m2 import load_golden

    path = ROOT / "data" / "eval" / "m2_golden_tiny.jsonl"
    assert len(load_golden(path)) == 10
    assert len(load_golden(path, limit=3)) == 3
