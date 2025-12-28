"""M7 之后非 GPU 落地项 — 单元测试."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_session_file_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.session_store.session_file_path", lambda: tmp_path / "s.json")
    monkeypatch.setattr("apps.session_store.session_backend", lambda: "file")
    from apps.session_store import append_turn, get_history

    append_turn("s1", "hi", "hello")
    hist = get_history("s1", max_turns=2)
    assert len(hist) == 2
    assert hist[0]["content"] == "hi"


def test_retrieval_log_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.retrieval_log.log_file_path", lambda: tmp_path / "r.jsonl")
    monkeypatch.setattr("apps.retrieval_log.log_backend", lambda: "file")
    from apps.retrieval_log import write_retrieval_log

    write_retrieval_log(
        log_id="id1",
        session_id="s",
        query="q",
        search_query="sq",
        hits=[{"source_file": "samples/a.md"}],
        refused=False,
    )
    lines = (tmp_path / "r.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["hit_count"] == 1


def test_run_ingest_job_mock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "a.md").write_text("# T\n\nbody text here for chunking.", encoding="utf-8")

    class FakeChunk:
        def __init__(self) -> None:
            self.chunk_id = "a#0"
            self.doc_id = "a"
            self.source_file = "a.md"
            self.title = "T"
            self.chunk_index = 0
            self.text = "body"

    monkeypatch.setattr("pipelines.ingest.run_ingest.load_documents", lambda _: [object()])
    monkeypatch.setattr("pipelines.ingest.run_ingest.chunk_documents", lambda _: [FakeChunk()])
    monkeypatch.setattr(
        "pipelines.ingest.run_ingest.resolve_embedding_model_path", lambda: "fake"
    )

    class FakeEmbedder:
        dimension = 4

        def __init__(self, model_path: str, device: str) -> None:
            pass

        def encode(self, texts, batch_size=8):
            return [[0.0] * 4 for _ in texts]

    class FakeMilvus:
        def __init__(self, *a, **k) -> None:
            pass

        def has_collection(self):
            return False

        def recreate(self):
            pass

        def delete_by_doc_ids(self, doc_ids):
            pass

        def insert(self, chunks, vectors):
            pass

    class FakeOS:
        def __init__(self, *a, **k) -> None:
            pass

        def exists(self):
            return False

        def recreate(self):
            pass

        def delete_by_doc_ids(self, doc_ids):
            pass

        def insert(self, chunks):
            pass

    monkeypatch.setattr("pipelines.ingest.run_ingest.Embedder", FakeEmbedder)
    monkeypatch.setattr("pipelines.ingest.run_ingest.MilvusIndexer", FakeMilvus)
    monkeypatch.setattr("pipelines.ingest.run_ingest.OpenSearchIndexer", FakeOS)

    from pipelines.ingest.run_ingest import run_ingest_job

    out = run_ingest_job(input_dir=raw, batch_size=2, recreate=True)
    assert out["chunks"] == 1


def test_m2_golden_example_exists() -> None:
    path = ROOT / "data" / "eval" / "m2_golden.jsonl.example"
    assert path.is_file()
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) >= 30
