"""M6 RAGAS — 无 Gateway 单元测试."""

import json
from pathlib import Path

import pytest

from pipelines.evaluation.run_ragas import dry_run_report, load_golden

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "eval" / "golden.jsonl.example"


def test_load_golden_example() -> None:
    rows = load_golden(GOLDEN)
    assert len(rows) >= 2
    assert "question" in rows[0]


def test_dry_run_deterministic() -> None:
    rows = load_golden(GOLDEN)
    a = dry_run_report(rows)
    b = dry_run_report(rows)
    assert a["faithfulness"] == b["faithfulness"]
    assert 0.5 < a["faithfulness"] < 1.0
    assert a["sample_count"] == len(rows)


def test_dry_run_cli(tmp_path: Path) -> None:
    import subprocess
    import sys

    out = tmp_path / "ragas.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "pipelines" / "evaluation" / "run_ragas.py"),
            "--dry-run",
            "--golden",
            str(GOLDEN),
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["mode"] == "dry-run"
