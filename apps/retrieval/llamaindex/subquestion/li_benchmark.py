"""Official LlamaIndex SubQuestion benchmark — NOT imported by mode_dispatch.

对比自研 SubQuestionQueryEngine 与 LI CustomQueryEngine 适配器路径的 Recall@K。
生产 dispatch 禁止 import 本模块。
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Awaitable, Callable

RetrievalRunner = Callable[[str, int], Awaitable[list[dict]]]


def llamaindex_available() -> bool:
    try:
        import llama_index.core  # noqa: F401

        return True
    except ImportError:
        return False


def recall_hit(hits: list[dict], doc_ids: list[str], top_k: int = 5) -> tuple[bool, list[str]]:
    sources = [str(h.get("source_file", "")) for h in hits[:top_k]]
    hit = any(doc_id in source for source in sources for doc_id in doc_ids)
    return hit, sources


@dataclass
class BenchmarkCaseResult:
    question: str
    doc_ids: list[str]
    category: str = ""
    self_recall: bool = False
    official_recall: bool | None = None
    self_sources: list[str] = field(default_factory=list)
    official_sources: list[str] = field(default_factory=list)


@dataclass
class BenchmarkSummary:
    total: int
    self_passed: int
    official_passed: int | None
    official_available: bool
    top_k: int
    cases: list[BenchmarkCaseResult] = field(default_factory=list)

    @property
    def self_recall_at_k(self) -> float:
        return self.self_passed / self.total if self.total else 0.0

    @property
    def official_recall_at_k(self) -> float | None:
        if self.official_passed is None or not self.total:
            return None
        return self.official_passed / self.total

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": date.today().isoformat(),
            "top_k": self.top_k,
            "official_available": self.official_available,
            "self_recall_at_k": self.self_recall_at_k,
            "official_recall_at_k": self.official_recall_at_k,
            "self_passed": self.self_passed,
            "official_passed": self.official_passed,
            "total": self.total,
            "cases": [
                {
                    "question": c.question,
                    "doc_ids": c.doc_ids,
                    "category": c.category,
                    "self_recall": c.self_recall,
                    "official_recall": c.official_recall,
                    "self_sources": c.self_sources,
                    "official_sources": c.official_sources,
                }
                for c in self.cases
            ],
        }


def _chunk_hits_to_dicts(hits: list[Any]) -> list[dict]:
    return [h.to_dict() for h in hits]


def _nodes_to_hits(nodes: list[Any]) -> list[dict]:
    hits: list[dict] = []
    for nws in nodes:
        node = nws.node if hasattr(nws, "node") else nws
        meta = getattr(node, "metadata", {}) or {}
        hits.append(
            {
                "chunk_id": meta.get("chunk_id", ""),
                "doc_id": meta.get("doc_id", ""),
                "source_file": meta.get("source_file", ""),
                "text": getattr(node, "text", ""),
                "score": getattr(nws, "score", 0.0),
                "retriever": "official_li_adapter",
            }
        )
    return hits


def _build_li_tool_engines(top_k: int) -> dict[str, Any]:
    from llama_index.core.base.response.schema import Response
    from llama_index.core.query_engine import CustomQueryEngine
    from llama_index.core.schema import NodeWithScore, TextNode

    from apps.retrieval.llamaindex.subquestion.tools import DEFAULT_TOOLS

    engines: dict[str, Any] = {}

    for name, fn in DEFAULT_TOOLS.items():
        tool_fn = fn

        class _CoreToolEngine(CustomQueryEngine):
            def custom_query(self, query_str: str) -> Response:
                raw_hits = tool_fn(query_str, top_k)
                nodes = [
                    NodeWithScore(
                        node=TextNode(
                            text=h.text,
                            metadata={
                                "chunk_id": h.chunk_id,
                                "doc_id": h.doc_id,
                                "source_file": h.source_file,
                            },
                        ),
                        score=h.score,
                    )
                    for h in raw_hits
                ]
                return Response(source_nodes=nodes)

        engines[name] = _CoreToolEngine()

    return engines


async def _run_tool_li(engine: Any, sq: Any, top_k: int) -> list[Any]:
    from apps.retrieval.core import ChunkHit

    response = await asyncio.to_thread(engine.custom_query, sq.sub_question)
    hits = _nodes_to_hits(response.source_nodes or [])
    return [
        ChunkHit(
            chunk_id=str(h.get("chunk_id", "")),
            doc_id=str(h.get("doc_id", "")),
            source_file=str(h.get("source_file", "")),
            title="",
            text=str(h.get("text", "")),
            score=float(h.get("score", 0.0)),
            retriever="official_li_adapter",
        )
        for h in hits[:top_k]
    ]


async def run_official_li_retrieval(query: str, top_k: int = 5) -> list[dict]:
    """LI CustomQueryEngine 适配器 — 规则拆问 + 同一 core 工具 + RRF."""
    if not llamaindex_available():
        return []

    from apps.retrieval.core import ChunkHit, get_retrieval_config
    from apps.retrieval.hybrid.rrf import reciprocal_rank_fusion
    from apps.retrieval.llamaindex.subquestion.question_gen import RuleBasedQuestionGenerator
    from apps.retrieval.llamaindex.subquestion.tools import DEFAULT_TOOL_DEFS
    from apps.retrieval.llamaindex.subquestion.types import SubQuestion

    cfg = get_retrieval_config()
    rrf_k = cfg.get("rrf_k", 60)
    gen = RuleBasedQuestionGenerator(
        min_subquestion_len=cfg.get("sub_question", {}).get("min_subquestion_len", 4),
        include_original=cfg.get("sub_question", {}).get("include_original", True),
    )
    subqs = await gen.generate(query, DEFAULT_TOOL_DEFS)
    if not subqs:
        subqs = [SubQuestion(sub_question=query.strip(), tool_name="hybrid")]

    li_engines = _build_li_tool_engines(top_k)

    if len(subqs) == 1:
        hits = await _run_tool_li(li_engines[subqs[0].tool_name], subqs[0], top_k)
        return _chunk_hits_to_dicts(hits[:top_k])

    ranked_lists: list[list[str]] = []
    id_to_hit: dict[str, ChunkHit] = {}
    for sq in subqs:
        engine = li_engines.get(sq.tool_name)
        if engine is None:
            continue
        hits = await _run_tool_li(engine, sq, top_k)
        ranked_lists.append([h.chunk_id for h in hits])
        id_to_hit.update({h.chunk_id: h for h in hits})

    fused = reciprocal_rank_fusion(ranked_lists, k=rrf_k, top_n=top_k)
    results = [
        ChunkHit(
            chunk_id=chunk_id,
            doc_id=id_to_hit[chunk_id].doc_id,
            source_file=id_to_hit[chunk_id].source_file,
            title=id_to_hit[chunk_id].title,
            text=id_to_hit[chunk_id].text,
            score=score,
            retriever="official_li_adapter",
        )
        for chunk_id, score in fused
        if chunk_id in id_to_hit
    ]
    return _chunk_hits_to_dicts(results)


async def compare_case(
    question: str,
    doc_ids: list[str],
    *,
    top_k: int = 5,
    category: str = "",
    self_runner: RetrievalRunner | None = None,
    official_runner: RetrievalRunner | None = None,
) -> BenchmarkCaseResult:
    if self_runner is None:
        from apps.retrieval.llamaindex.subquestion_engine import query_subquestion

        async def _self_default(q: str, k: int) -> list[dict]:
            return await query_subquestion(q, top_k=k)

        self_fn: RetrievalRunner = _self_default
    else:
        self_fn = self_runner
    official_fn = official_runner or run_official_li_retrieval

    self_hits = await self_fn(question, top_k)
    self_ok, self_sources = recall_hit(self_hits, doc_ids, top_k)

    official_ok: bool | None = None
    official_sources: list[str] = []
    if official_runner is not None or llamaindex_available():
        official_hits = await official_fn(question, top_k)
        official_ok, official_sources = recall_hit(official_hits, doc_ids, top_k)

    return BenchmarkCaseResult(
        question=question,
        doc_ids=doc_ids,
        category=category,
        self_recall=self_ok,
        official_recall=official_ok,
        self_sources=self_sources,
        official_sources=official_sources,
    )


def load_benchmark_cases(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        cases.append(row)
        if limit is not None and limit > 0 and len(cases) >= limit:
            break
    return cases


async def compare_golden(
    golden_path: Path,
    *,
    top_k: int = 5,
    limit: int | None = None,
    self_runner: RetrievalRunner | None = None,
    official_runner: RetrievalRunner | None = None,
) -> BenchmarkSummary:
    rows = load_benchmark_cases(golden_path, limit=limit)
    official_available = official_runner is not None or llamaindex_available()
    case_results: list[BenchmarkCaseResult] = []

    for row in rows:
        case_results.append(
            await compare_case(
                row["question"],
                row["doc_ids"],
                top_k=top_k,
                category=row.get("category", ""),
                self_runner=self_runner,
                official_runner=official_runner,
            )
        )

    self_passed = sum(1 for c in case_results if c.self_recall)
    official_passed: int | None = None
    if official_available:
        official_passed = sum(
            1 for c in case_results if c.official_recall is True
        )

    return BenchmarkSummary(
        total=len(case_results),
        self_passed=self_passed,
        official_passed=official_passed,
        official_available=official_available,
        top_k=top_k,
        cases=case_results,
    )


def write_compare_report(summary: BenchmarkSummary, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


async def run_benchmark_cli(
    golden: str | Path = "data/eval/m2_compound.jsonl",
    output: str | Path = "reports/subquestion_compare.json",
    *,
    top_k: int = 5,
    limit: int | None = None,
) -> BenchmarkSummary:
    from apps.config import ROOT
    from apps.eval_paths import resolve_eval_jsonl

    golden_path = resolve_eval_jsonl(golden)
    summary = await compare_golden(golden_path, top_k=top_k, limit=limit)
    write_compare_report(summary, ROOT / output)
    return summary
