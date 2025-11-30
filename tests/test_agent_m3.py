"""Unit tests for M3 agent helpers (no vLLM)."""

from apps.agent.pipeline import _build_messages, _context_top_k, _include_history_in_generation
from apps.agent.prompts import format_context, hits_to_citations, truncate_at_boundary
from apps.agent.session import append_turn, clear_session, get_history
from apps.agent.tools.self_check import check_retrieval_confidence


def test_session_history_trim():
    clear_session("t1")
    append_turn("t1", "q1", "a1")
    append_turn("t1", "q2", "a2")
    append_turn("t1", "q3", "a3")
    hist = get_history("t1", max_turns=2)
    assert len(hist) == 4
    assert hist[0]["content"] == "q2"
    clear_session("t1")


def test_retrieval_confidence():
    assert not check_retrieval_confidence([])
    assert check_retrieval_confidence([{"score": 1.5}])
    assert not check_retrieval_confidence([{"score": -5.0}])


def test_truncate_at_boundary():
    text = "第一段。\n\n第二段含轴承检查与日常点检要点。"
    out = truncate_at_boundary(text, 18)
    assert out.endswith("…")
    assert len(out) <= 19


def test_generation_excludes_chat_history_by_default():
    hist = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]
    cfg = {}
    msgs = _build_messages(
        "sys",
        hist,
        "ctx",
        "q2",
        include_history=_include_history_in_generation(cfg),
    )
    assert len(msgs) == 2
    assert msgs[1]["content"].startswith("参考资料")


def test_context_top_k_follows_rerank_top_n():
    cfg = {}
    assert _context_top_k(cfg) == 5


def test_format_context_and_citations():
    hits = [
        {
            "doc_id": "d1",
            "chunk_id": "c1",
            "source_file": "f.md",
            "title": "T",
            "text": "body",
            "score": 2.0,
        }
    ]
    assert "d1:c1" in format_context(hits)
    cites = hits_to_citations(hits)
    assert cites[0]["doc_id"] == "d1"
