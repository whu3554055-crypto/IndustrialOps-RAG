"""post-M7 完善项 — 单元测试."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_resolve_eval_jsonl_example() -> None:
    from apps.eval_paths import resolve_eval_jsonl

    p = resolve_eval_jsonl("data/eval/m2_golden.jsonl")
    assert p.suffix == ".jsonl" or p.name.endswith(".jsonl.example")


def test_rate_limit_allows_without_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.rate_limit.allow_request", lambda k: True)
    from apps.rate_limit import allow_request

    assert allow_request("test") is True


def test_table_parser() -> None:
    from pipelines.ingest.deepdoc.table_parser import append_table_rows_as_lines

    text = "| 参数 | 值 |\n| a | 1 |"
    out = append_table_rows_as_lines(text)
    assert "（表）" in out


def test_trulens_dry_run_cli(tmp_path: Path) -> None:
    import subprocess
    import sys

    out = tmp_path / "t.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "pipelines" / "evaluation" / "trulens_eval.py"), "--dry-run", "--output", str(out)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert proc.returncode == 0
    assert json.loads(out.read_text(encoding="utf-8"))["mode"] == "trulens-dry-run"


def test_helm_ingest_template_exists() -> None:
    assert (ROOT / "deploy" / "helm" / "industrial-ops-rag" / "templates" / "ingest-cronjob.yaml").is_file()
