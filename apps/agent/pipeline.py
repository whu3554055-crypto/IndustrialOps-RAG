"""Agentic RAG 主管道 — LangChain 编排."""

from dataclasses import dataclass


@dataclass
class PipelineResult:
    answer: str
    citations: list[dict]
    retrieval_log_id: str | None
    refused: bool


async def run_agentic_rag(
    session_id: str,
    query: str,
    *,
    history: list[dict] | None = None,
) -> PipelineResult:
    """
    流程（M3 实现）:
    1. query rewrite
    2. router → LangChain / LlamaIndex
    3. hybrid retrieve + rerank
    4. generate (vLLM / TRT / API)
    5. self-check → refuse or second retrieval
    """
    _ = session_id, query, history
    raise NotImplementedError("M3: implement agentic pipeline")
