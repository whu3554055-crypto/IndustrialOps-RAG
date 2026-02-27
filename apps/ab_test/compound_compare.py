"""复合问句离线 A/B — hybrid_rerank vs sub_question（C5，不自动 promote）."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Awaitable, Callable

from apps.ab_test.analyze import two_proportion_z_test

COMPOUND_AB_EXPERIMENT_ID = "exp_subquestion_vs_hybrid_compound"
DEFAULT_MODE_A = "hybrid_rerank"
DEFAULT_MODE_B = "sub_question"


@dataclass
class CompoundCaseRow:
    question: str
    doc_ids: list[str]
    category: str
    hybrid_recall: bool
    sub_question_recall: bool
    hybrid_sources: list[str]
    sub_question_sources: list[str]

    @property
    def winner(self) -> str:
        if self.hybrid_recall and self.sub_question_recall:
            return "both"
        if self.hybrid_recall:
            return DEFAULT_MODE_A
        if self.sub_question_recall:
            return DEFAULT_MODE_B
        return "neither"


RetrievalFn = Callable[[str], Awaitable[list[dict]]]


def recall_from_hits(hits: list[dict], doc_ids: list[str], top_k: int = 5) -> tuple[bool, list[str]]:
    sources = [str(h.get("source_file", "")) for h in hits[:top_k]]
    hit = any(doc_id in source for source in sources for doc_id in doc_ids)
    return hit, sources


def merge_case_rows(
    cases: list[Any],
    hybrid_rows: list[tuple[bool, list[str]]],
    sub_rows: list[tuple[bool, list[str]]],
) -> list[CompoundCaseRow]:
    merged: list[CompoundCaseRow] = []
    for case, (h_ok, h_src), (s_ok, s_src) in zip(cases, hybrid_rows, sub_rows, strict=True):
        merged.append(
            CompoundCaseRow(
                question=case.question,
                doc_ids=case.doc_ids,
                category=case.category,
                hybrid_recall=h_ok,
                sub_question_recall=s_ok,
                hybrid_sources=h_src,
                sub_question_sources=s_src,
            )
        )
    return merged


def summarize_compound_ab(
    case_rows: list[CompoundCaseRow],
    *,
    experiment_id: str = COMPOUND_AB_EXPERIMENT_ID,
    mode_a: str = DEFAULT_MODE_A,
    mode_b: str = DEFAULT_MODE_B,
    top_k: int = 5,
) -> dict[str, Any]:
    total = len(case_rows)
    hybrid_passed = sum(1 for row in case_rows if row.hybrid_recall)
    sub_passed = sum(1 for row in case_rows if row.sub_question_recall)
    only_hybrid = sum(1 for row in case_rows if row.winner == mode_a)
    only_sub = sum(1 for row in case_rows if row.winner == mode_b)
    both_hit = sum(1 for row in case_rows if row.winner == "both")
    neither = sum(1 for row in case_rows if row.winner == "neither")

    stats = two_proportion_z_test(hybrid_passed, total, sub_passed, total)
    delta = (sub_passed - hybrid_passed) / total if total else 0.0

    recommendation = _recommendation(
        mode_a=mode_a,
        mode_b=mode_b,
        hybrid_passed=hybrid_passed,
        sub_passed=sub_passed,
        total=total,
        stats=stats,
    )

    return {
        "date": date.today().isoformat(),
        "experiment_id": experiment_id,
        "golden_type": "compound",
        "top_k": top_k,
        "total": total,
        "mode_a": mode_a,
        "mode_b": mode_b,
        "hybrid_rerank": {
            "passed": hybrid_passed,
            "recall_at_k": hybrid_passed / total if total else 0.0,
        },
        "sub_question": {
            "passed": sub_passed,
            "recall_at_k": sub_passed / total if total else 0.0,
        },
        "delta_recall": delta,
        "case_breakdown": {
            "only_hybrid_rerank": only_hybrid,
            "only_sub_question": only_sub,
            "both_hit": both_hit,
            "neither_hit": neither,
        },
        "significance": stats,
        "recommendation": recommendation,
        "cases": [
            {
                "question": row.question,
                "category": row.category,
                "doc_ids": row.doc_ids,
                "hybrid_recall": row.hybrid_recall,
                "sub_question_recall": row.sub_question_recall,
                "winner": row.winner,
            }
            for row in case_rows
        ],
    }


def _recommendation(
    *,
    mode_a: str,
    mode_b: str,
    hybrid_passed: int,
    sub_passed: int,
    total: int,
    stats: dict[str, Any],
) -> dict[str, str]:
    """仅建议，不自动改 profile（与 Phase 3 ADR 一致）."""
    if total == 0:
        return {
            "action": "insufficient_data",
            "summary": "无评测样本，无法给出建议。",
        }

    p_value = float(stats.get("p_value", 1.0))
    if sub_passed > hybrid_passed and stats.get("valid") and p_value < 0.05:
        return {
            "action": "consider_online_ab",
            "summary": (
                f"{mode_b} 在 compound golden 上 Recall 显著高于 {mode_a}；"
                f"可手动启用 profile 示例 `ab-test-subquestion-compound.yaml` 做小流量 search A/B，"
                "优胜后再人工 promote。"
            ),
        }
    if hybrid_passed >= sub_passed:
        return {
            "action": "keep_default",
            "summary": (
                f"默认 {mode_a} 不劣于 {mode_b}；暂不建议为复合问句切换检索默认或开在线实验。"
            ),
        }
    return {
        "action": "inconclusive",
        "summary": (
            f"{mode_b} Recall 略高但未达显著（p={p_value:.3f}）；"
            "可加大样本或开在线 A/B 再观察，仍须人工 promote。"
        ),
    }


def render_compound_ab_markdown(report: dict[str, Any]) -> str:
    h = report["hybrid_rerank"]
    s = report["sub_question"]
    br = report["case_breakdown"]
    sig = report["significance"]
    rec = report["recommendation"]
    lines = [
        f"# 复合问句离线 A/B — {report['experiment_id']} ({report['date']})",
        "",
        f"Golden: compound · Top-{report['top_k']} · n={report['total']}",
        "",
        "| mode | Recall@K | passed |",
        "|------|----------|--------|",
        f"| {report['mode_a']} | {h['recall_at_k']:.0%} | {h['passed']}/{report['total']} |",
        f"| {report['mode_b']} | {s['recall_at_k']:.0%} | {s['passed']}/{report['total']} |",
        "",
        f"Δ recall (B−A): {report['delta_recall']:+.0%}",
        "",
        "**逐题胜负**",
        "",
        f"- 仅 {report['mode_a']}: {br['only_hybrid_rerank']}",
        f"- 仅 {report['mode_b']}: {br['only_sub_question']}",
        f"- 两者均命中: {br['both_hit']}",
        f"- 均未命中: {br['neither_hit']}",
        "",
        "**显著性（两比例 z 检验）**",
        "",
        f"- p-value: {sig.get('p_value', 1.0):.4f}",
        f"- valid: {sig.get('valid', False)}",
        "",
        f"**建议（{rec['action']}）**: {rec['summary']}",
        "",
        "> 本报告仅离线对照；启用在线 A/B 请合并 `deploy/profiles/examples/ab-test-subquestion-compound.yaml` 并人工 Review。",
        "",
    ]
    return "\n".join(lines)


async def eval_per_case(
    cases: list[Any],
    fn: RetrievalFn,
    *,
    top_k: int = 5,
) -> list[tuple[bool, list[str]]]:
    rows: list[tuple[bool, list[str]]] = []
    for case in cases:
        hits = await fn(case.question)
        rows.append(recall_from_hits(hits, case.doc_ids, top_k))
    return rows


async def run_compound_ab_compare(
    cases: list[Any],
    *,
    hybrid_fn: RetrievalFn,
    sub_question_fn: RetrievalFn,
    top_k: int = 5,
    experiment_id: str = COMPOUND_AB_EXPERIMENT_ID,
    subquestion_generator: str | None = None,
) -> dict[str, Any]:
    hybrid_rows = await eval_per_case(cases, hybrid_fn, top_k=top_k)
    sub_rows = await eval_per_case(cases, sub_question_fn, top_k=top_k)
    case_rows = merge_case_rows(cases, hybrid_rows, sub_rows)
    report = summarize_compound_ab(case_rows, experiment_id=experiment_id, top_k=top_k)
    if subquestion_generator:
        report["subquestion_generator"] = subquestion_generator
    return report
