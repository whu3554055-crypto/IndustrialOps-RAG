"""LlamaIndex SubQuestionQueryEngine — 子问题分解 + 多工具检索 + RRF 融合."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from functools import lru_cache

from apps.retrieval.core import ChunkHit, get_retrieval_config
from apps.retrieval.hybrid.rrf import reciprocal_rank_fusion
from apps.retrieval.llamaindex.subquestion.question_gen import (
    QuestionGenerator,
    RuleBasedQuestionGenerator,
    build_question_generator,
)
from apps.retrieval.llamaindex.subquestion.tools import (
    DEFAULT_TOOL_DEFS,
    DEFAULT_TOOLS,
    RetrievalToolFn,
)
from apps.retrieval.llamaindex.subquestion.types import (
    QueryEngineTool,
    SubQuestion,
)


@dataclass
class SubQuestionResult:
    """SubQuestionQueryEngine 检索结果（含子问题轨迹，便于调试/日志）."""

    hits: list[ChunkHit]
    sub_questions: list[SubQuestion] = field(default_factory=list)
    generator: str = "rule_based"

    def to_dict(self) -> dict:
        return {
            "hits": [h.to_dict() for h in self.hits],
            "sub_questions": [
                {"sub_question": sq.sub_question, "tool_name": sq.tool_name}
                for sq in self.sub_questions
            ],
            "generator": self.generator,
        }


class SubQuestionQueryEngine:
    """对应 LlamaIndex SubQuestionQueryEngine（检索-only，无 ResponseSynthesizer）."""

    def __init__(
        self,
        *,
        tools: dict[str, RetrievalToolFn] | None = None,
        tool_defs: list[QueryEngineTool] | None = None,
        question_generator: QuestionGenerator | None = None,
        rrf_k: int | None = None,
    ) -> None:
        cfg = get_retrieval_config()
        self._tools = tools or DEFAULT_TOOLS
        self._tool_defs = tool_defs or DEFAULT_TOOL_DEFS
        self._generator = question_generator or build_question_generator(cfg)
        self._rrf_k = rrf_k if rrf_k is not None else cfg.get("rrf_k", 60)

    async def retrieve(self, query: str, top_k: int = 10) -> SubQuestionResult:
        subqs = await self._generator.generate(query, self._tool_defs)
        if not subqs:
            subqs = [SubQuestion(sub_question=query.strip(), tool_name="hybrid")]

        if len(subqs) == 1:
            hits = await self._run_tool(subqs[0], top_k)
            return SubQuestionResult(
                hits=[self._tag_hit(h) for h in hits[:top_k]],
                sub_questions=subqs,
                generator=self._generator.name,
            )

        ranked_lists: list[list[str]] = []
        id_to_hit: dict[str, ChunkHit] = {}
        for sq in subqs:
            hits = await self._run_tool(sq, top_k)
            ranked_lists.append([h.chunk_id for h in hits])
            id_to_hit.update({h.chunk_id: h for h in hits})

        fused = reciprocal_rank_fusion(ranked_lists, k=self._rrf_k, top_n=top_k)
        results = [
            self._tag_hit(
                ChunkHit(
                    chunk_id=chunk_id,
                    doc_id=id_to_hit[chunk_id].doc_id,
                    source_file=id_to_hit[chunk_id].source_file,
                    title=id_to_hit[chunk_id].title,
                    text=id_to_hit[chunk_id].text,
                    score=score,
                    retriever="sub_question",
                )
            )
            for chunk_id, score in fused
            if chunk_id in id_to_hit
        ]
        return SubQuestionResult(
            hits=results,
            sub_questions=subqs,
            generator=self._generator.name,
        )

    async def _run_tool(self, sq: SubQuestion, top_k: int) -> list[ChunkHit]:
        fn = self._tools.get(sq.tool_name)
        if fn is None:
            raise ValueError(f"Unknown sub-question tool: {sq.tool_name!r}")
        return await asyncio.to_thread(fn, sq.sub_question, top_k)

    @staticmethod
    def _tag_hit(hit: ChunkHit) -> ChunkHit:
        if hit.retriever == "sub_question":
            return hit
        return ChunkHit(
            chunk_id=hit.chunk_id,
            doc_id=hit.doc_id,
            source_file=hit.source_file,
            title=hit.title,
            text=hit.text,
            score=hit.score,
            retriever="sub_question",
        )


@lru_cache
def _engine_for_config_key(config_key: str) -> SubQuestionQueryEngine:
    cfg = get_retrieval_config()
    return SubQuestionQueryEngine()


def get_default_engine() -> SubQuestionQueryEngine:
    cfg = get_retrieval_config()
    key = json.dumps(cfg.get("sub_question", {}), sort_keys=True, ensure_ascii=False)
    return _engine_for_config_key(key)


def clear_default_engine_cache() -> None:
    """Profile 热更新或单测后清缓存."""
    _engine_for_config_key.cache_clear()


async def query_subquestion(query: str, top_k: int = 10) -> list[dict]:
    """Gateway / mode_dispatch 入口 — 返回 chunk hits."""
    result = await get_default_engine().retrieve(query, top_k=top_k)
    return [h.to_dict() for h in result.hits]


async def query_subquestion_detail(query: str, top_k: int = 10) -> dict:
    """带 sub_questions 轨迹的完整结果（调试/日志）."""
    result = await get_default_engine().retrieve(query, top_k=top_k)
    return result.to_dict()
