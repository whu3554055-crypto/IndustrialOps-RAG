"""FastAPI Gateway — 会话、问答、反馈、健康检查."""

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from apps.agent.pipeline import run_agentic_rag
from apps.feedback import FeedbackEvent, append_feedback, load_feedback_events
from apps.config import ROOT, get_settings, load_profile
from apps.ingest_k8s import trigger_ingest_cronjob
from apps.metrics import inc_chat_request, render_prometheus
from apps.minio_client import minio_health
from apps.rate_limit import allow_request
from apps.retrieval_log import load_recent_logs
from pipelines.ingest.run_ingest import run_ingest_job
from pipelines.feedback.export_feedback import export_golden_candidates
from apps.generation.llm_router import generate, list_backend_status  # M4: docs/m4_serving.md
from apps.retrieval.langchain.hybrid_chain import retrieve_context
from apps.retrieval.llamaindex.graph_engine import query_graph
from apps.retrieval.llamaindex.keyword_engine import query_keyword
from apps.retrieval.llamaindex.router_engine import query_router
from apps.retrieval.llamaindex.subquestion_engine import query_subquestion
from apps.retrieval.llamaindex.summary_engine import query_summary
from apps.retrieval.llamaindex.tree_engine import query_tree
from apps.retrieval.llamaindex.vector_engine import query_vector

app = FastAPI(
    title="IndustrialOps-RAG Gateway",
    description="工业运维知识库 RAG API",
    version="0.1.0",
)


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    query: str = Field(..., min_length=1, description="用户问题（中文）")


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict] = Field(default_factory=list)
    message_id: str | None = Field(None, description="与 retrieval_log_id 相同，供 /v1/feedback 关联")
    retrieval_log_id: str | None = None
    refused: bool = False


class IngestRequest(BaseModel):
    input: str = Field(default="data/raw", description="原始文档根目录")
    batch_size: int = Field(default=8, ge=1, le=64)
    recreate: bool = True
    max_docs: int | None = Field(default=None, ge=1, le=5000)
    mode: str = Field(default="local", description="local | k8s（触发集群 CronJob 一次性 Job）")


class FeedbackRequest(BaseModel):
    session_id: str
    message_id: str
    rating: int = Field(..., ge=-1, le=1, description="-1 踩 / 1 赞")
    comment: str | None = None
    query: str | None = None
    answer_preview: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="检索问句")
    mode: str = Field(
        default="hybrid_rerank",
        description="vector | bm25 | hybrid | hybrid_rerank | summary | tree | graph | router | sub_question",
    )
    top_k: int = Field(default=5, ge=1, le=50)


class SearchHit(BaseModel):
    chunk_id: str
    doc_id: str
    source_file: str
    title: str
    text: str
    score: float
    retriever: str


class SearchResponse(BaseModel):
    query: str
    mode: str
    hits: list[SearchHit]


class GenerateRequest(BaseModel):
    messages: list[dict] = Field(..., min_length=1)
    backend: str | None = Field(default=None, description="vllm | tensorrt_llm | api")
    max_tokens: int = Field(default=256, ge=1, le=2048)


class GenerateResponse(BaseModel):
    content: str
    backend: str


class BackendInfo(BaseModel):
    name: str
    enabled: bool
    active: bool
    base_url: str
    reachable: bool
    model: str | None = None
    error: str | None = None


class BackendsResponse(BaseModel):
    active_backend: str
    mutual_exclusive_gpu: bool
    backends: list[BackendInfo]


@app.get("/v1/health")
async def health() -> dict:
    s = get_settings()
    profile = load_profile()
    return {
        "status": "ok",
        "profile": s.ior_profile,
        "llm_backend": s.llm_active_backend,
        "mutual_exclusive_gpu": profile.get("gpu", {}).get("mutual_exclusive_gpu", True),
        "minio": minio_health(),
    }


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(render_prometheus(), media_type="text/plain; version=0.0.4")


@app.get("/v1/admin/retrieval-logs")
async def admin_retrieval_logs(limit: int = 20) -> dict:
    return {"logs": load_recent_logs(limit=min(limit, 100))}


@app.get("/v1/admin/feedback")
async def admin_feedback(limit: int = 50) -> dict:
    return {"events": load_feedback_events(limit=min(limit, 200))}


@app.get("/v1/llm/backends", response_model=BackendsResponse)
async def llm_backends() -> BackendsResponse:
    s = get_settings()
    profile = load_profile()
    statuses = await list_backend_status()
    return BackendsResponse(
        active_backend=s.llm_active_backend,
        mutual_exclusive_gpu=bool(profile.get("gpu", {}).get("mutual_exclusive_gpu")),
        backends=[BackendInfo(**status.__dict__) for status in statuses],
    )


@app.post("/v1/generate", response_model=GenerateResponse)
async def generate_text(req: GenerateRequest) -> GenerateResponse:
    s = get_settings()
    backend = req.backend or s.llm_active_backend
    try:
        content = await generate(req.messages, backend=backend, max_tokens=req.max_tokens)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"LLM generate failed: {exc}") from exc
    return GenerateResponse(content=content, backend=backend)


@app.post("/v1/chat", response_model=ChatResponse)  # M3: docs/m3_agent.md §6
async def chat(req: ChatRequest) -> ChatResponse:
    if not allow_request(req.session_id):
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    inc_chat_request()
    try:
        result = await run_agentic_rag(req.session_id, req.query)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Agent pipeline failed: {exc}",
        ) from exc
    log_id = result.retrieval_log_id
    return ChatResponse(
        answer=result.answer,
        citations=result.citations,
        message_id=log_id,
        retrieval_log_id=log_id,
        refused=result.refused,
    )


async def _dispatch_search(query: str, mode: str, top_k: int) -> list[dict]:
    if mode == "vector":
        hits = await query_vector(query, top_k=top_k)
    elif mode in ("bm25", "keyword"):
        hits = await query_keyword(query, top_k=top_k)
    elif mode == "hybrid":
        hits = await retrieve_context(query, mode="hybrid", rerank=False)
    elif mode == "hybrid_rerank":
        hits = await retrieve_context(query, mode="hybrid_rerank")
    elif mode == "summary":
        hits = await query_summary(query, top_k=top_k)
    elif mode == "tree":
        hits = await query_tree(query, top_k=top_k)
    elif mode == "graph":
        hits = await query_graph(query, top_k=top_k)
    elif mode == "router":
        hits = await query_router(query)
    elif mode == "sub_question":
        hits = await query_subquestion(query, top_k=top_k)
    else:
        raise ValueError(f"Unknown search mode: {mode}")
    return hits[:top_k]


@app.post("/v1/search", response_model=SearchResponse)  # M2: docs/m2_retrieval.md §5
async def search(req: SearchRequest) -> SearchResponse:
    hits = await _dispatch_search(req.query, req.mode, req.top_k)
    return SearchResponse(query=req.query, mode=req.mode, hits=hits)


@app.post("/v1/feedback")
async def feedback(req: FeedbackRequest) -> dict:
    row = append_feedback(
        FeedbackEvent(
            session_id=req.session_id,
            message_id=req.message_id,
            rating=req.rating,
            comment=req.comment,
            query=req.query,
            answer_preview=req.answer_preview,
            retrieval_log_id=req.message_id,
        )
    )
    return {"ok": True, "session_id": req.session_id, "event_id": row.get("event_id"), "stored": row.get("stored")}


@app.post("/v1/ingest")
async def ingest_trigger(req: IngestRequest) -> dict:
    if req.mode == "k8s":
        ing = load_profile().get("ingest", {}).get("cronJob", {})
        ns = ing.get("namespace", "industrial-ops")
        cj = ing.get("cronJobName", "ior-ingest")
        try:
            result = await asyncio.to_thread(
                trigger_ingest_cronjob,
                namespace=ns,
                cronjob_name=cj,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return result

    input_dir = Path(req.input)
    if not input_dir.is_absolute():
        input_dir = ROOT / input_dir
    try:
        result = await asyncio.to_thread(
            run_ingest_job,
            input_dir=input_dir,
            batch_size=req.batch_size,
            recreate=req.recreate,
            max_docs=req.max_docs,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ingest failed: {exc}") from exc
    return {"ok": True, **result}


@app.post("/v1/feedback/export-golden")
async def feedback_export_golden(min_rating: int = -1) -> dict:
    out = ROOT / "data" / "eval" / "golden_candidates.jsonl"
    n = export_golden_candidates(out, min_rating=min_rating)
    return {"ok": True, "count": n, "path": str(out)}


def run() -> None:
    import uvicorn

    s = get_settings()
    uvicorn.run(
        "apps.gateway.main:app",
        host=s.gateway_host,
        port=s.gateway_port,
        reload=True,
    )


if __name__ == "__main__":
    run()
