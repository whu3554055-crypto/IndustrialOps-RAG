"""M7 — 反馈存储与 golden 模板（无 Gateway）."""

import json
from pathlib import Path

import pytest

from apps.feedback import FeedbackEvent, append_feedback, load_feedback_events
from pipelines.evaluation.run_ragas import load_golden

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_M7 = ROOT / "data" / "eval" / "golden_m7.jsonl.example"


def test_golden_m7_example() -> None:
    rows = load_golden(GOLDEN_M7)
    assert len(rows) >= 10
    assert rows[0]["doc_ids"]


def test_feedback_file_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "fb.jsonl"
    monkeypatch.setattr(
        "apps.feedback.feedback_file_path",
        lambda: path,
    )
    monkeypatch.setattr("apps.feedback.feedback_backend", lambda: "file")
    append_feedback(
        FeedbackEvent(
            session_id="t1",
            message_id="m1",
            rating=1,
            query="q",
            answer_preview="a",
        )
    )
    rows = load_feedback_events()
    assert len(rows) == 1
    assert rows[0]["rating"] == 1


def test_demo_corpus_files_exist() -> None:
    demo = ROOT / "data" / "corpus" / "demo"
    for name in (
        "pump_p101_manual.md",
        "reactor_r201_sop.md",
        "compressor_sa01_fault_codes.md",
    ):
        assert (demo / name).is_file()
