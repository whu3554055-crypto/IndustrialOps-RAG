"""bayesian_optimize.py — dry-run 与 planner 单元测试."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_plan_trials_count() -> None:
    from scripts.bayesian_optimize import _plan_trials

    trials = _plan_trials(3, random_state=0)
    assert len(trials) == 3
    assert "retrieval.rrf_k" in trials[0]


def test_bayesian_dry_run_cli(tmp_path: Path) -> None:
    import subprocess
    import sys

    out = tmp_path / "bayes_dry.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "bayesian_optimize.py"),
            "--dry-run",
            "--n-calls",
            "2",
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["dry_run"] is True
    assert len(payload["planned_params"]) == 2


def test_random_search_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import bayesian_optimize

    calls: list[dict] = []

    def fake_objective(params: dict) -> dict:
        calls.append(params)
        return {"params": params, "score": 0.5, "objective": -0.5}

    trials, best = bayesian_optimize.run_random_search(fake_objective, 2, 0)
    assert len(trials) == 2
    assert best is not None
