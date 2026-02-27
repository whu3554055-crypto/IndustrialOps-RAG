"""compound_compare — 复合问句离线 A/B 逻辑."""

from __future__ import annotations

from apps.ab_test.compound_compare import (
    CompoundCaseRow,
    merge_case_rows,
    recall_from_hits,
    summarize_compound_ab,
)


class _Case:
    def __init__(self, question: str, doc_ids: list[str], category: str = "") -> None:
        self.question = question
        self.doc_ids = doc_ids
        self.category = category


def test_recall_from_hits() -> None:
    hits = [{"source_file": "samples/pump_p101_manual.md"}]
    ok, sources = recall_from_hits(hits, ["pump_p101_manual.md"], top_k=5)
    assert ok is True
    assert sources == ["samples/pump_p101_manual.md"]


def test_merge_and_summarize() -> None:
    cases = [
        _Case("q1", ["a.md"], "compound"),
        _Case("q2", ["b.md"], "compound"),
        _Case("q3", ["c.md"], "compound"),
    ]
    hybrid_rows = [(True, ["a.md"]), (True, ["b.md"]), (False, [])]
    sub_rows = [(True, ["a.md"]), (False, []), (True, ["c.md"])]

    rows = merge_case_rows(cases, hybrid_rows, sub_rows)
    assert rows[0].winner == "both"
    assert rows[1].winner == "hybrid_rerank"
    assert rows[2].winner == "sub_question"

    report = summarize_compound_ab(rows, top_k=5)
    assert report["hybrid_rerank"]["passed"] == 2
    assert report["sub_question"]["passed"] == 2
    assert report["case_breakdown"]["both_hit"] == 1
    assert report["recommendation"]["action"] in {
        "keep_default",
        "inconclusive",
        "consider_online_ab",
        "insufficient_data",
    }


def test_recommendation_keep_default_when_hybrid_wins() -> None:
    rows = [
        CompoundCaseRow("q", ["a.md"], "c", True, False, ["a.md"], []),
        CompoundCaseRow("q2", ["b.md"], "c", True, False, ["b.md"], []),
    ]
    report = summarize_compound_ab(rows)
    assert report["recommendation"]["action"] == "keep_default"
