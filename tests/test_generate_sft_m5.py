"""SFT 语料生成脚本."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pipelines.finetune.train_qlora import load_sft_records, validate_sft_records

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_sft_from_corpus.py"


def test_generate_heuristic(tmp_path: Path) -> None:
    out = tmp_path / "sft.generated.jsonl"
    review = tmp_path / "sft.review_sample.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(ROOT / "data" / "raw"),
            "--output",
            str(out),
            "--review-out",
            str(review),
            "--per-doc",
            "2",
            "--no-llm",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    records = load_sft_records(out)
    validate_sft_records(records)
    assert len(records) >= 4
    assert all("doc_id" in r for r in records)
    review_rows = [json.loads(line) for line in review.read_text(encoding="utf-8").splitlines() if line]
    assert review_rows
    assert review_rows[0].get("_review", {}).get("status") == "pending"
