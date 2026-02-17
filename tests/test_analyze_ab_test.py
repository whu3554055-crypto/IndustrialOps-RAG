"""analyze_ab_test 脚本与聚合逻辑."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from apps.ab_test.analyze import build_experiment_report

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ab_test"


def _load_fixture() -> tuple[list[dict], list[dict], list[dict]]:
    assignments = [
        json.loads(line)
        for line in (FIXTURE / "assignments.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    feedback = [
        json.loads(line)
        for line in (FIXTURE / "feedback.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    logs = [
        json.loads(line)
        for line in (FIXTURE / "retrieval_logs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return assignments, feedback, logs


def test_build_experiment_report_arms() -> None:
    assignments, feedback, logs = _load_fixture()
    report = build_experiment_report(
        experiment_id="exp_demo",
        assignments=assignments,
        feedback=feedback,
        retrieval_logs=logs,
        min_sample_size=3,
    )
    assert report["total_requests"] == 3
    assert len(report["arms"]) == 2
    assert report["sample_sufficient"] is True


def test_analyze_ab_test_dry_run_cli(tmp_path: Path) -> None:
    out = tmp_path / "reports"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "analyze_ab_test.py"),
            "--experiment",
            "exp_demo",
            "--dry-run",
            "--min-sample-size",
            "3",
            "--output-dir",
            str(out),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert (out / "ab_test_exp_demo.md").is_file()
    assert (out / "ab_test_exp_demo.json").is_file()
