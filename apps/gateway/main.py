"""FastAPI Gateway — 会话、问答、反馈、健康检查."""

import asyncio
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from apps.ab_test import load_ab_test_config, select_variant
from apps.ab_test.assignment_log import load_assignments, write_assignment
from apps.agent.pipeline import run_agentic_rag
from apps.feedback import FeedbackEvent, append_feedback, load_feedback_events
from apps.config import ROOT, get_settings, load_profile
from apps.ingest_k8s import trigger_ingest_cronjob
from apps.metrics import inc_chat_request, render_prometheus
from apps.minio_client import minio_health
from apps.rate_limit import allow_request
from apps.retrieval_log import load_recent_logs, write_retrieval_log
from pipelines.ingest.run_ingest import run_ingest_job
from pipelines.feedback.export_feedback import export_golden_candidates
from apps.generation.llm_router import generate, list_backend_status  # M4: docs/m4_serving.md
from apps.retrieval.mode_dispatch import dispatch_search
from apps.retrieval.llamaindex.subquestion_engine import query_subquestion_detail
from apps.retrieval.llamaindex.subquestion.synthesizer import run_subquestion_query

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
    experiment_id: str | None = None
    variant: str | None = None
    retrieval_mode: str | None = None
    sub_questions: list[SubQuestionTraceItem] | None = None
    sub_answers: list[dict] | None = None
    subquestion_generator: str | None = None


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="复合或单一问句（无会话轻量 RAG）")
    top_k: int = Field(default=5, ge=1, le=50)


class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: list[dict] = Field(default_factory=list)
    sub_questions: list[SubQuestionTraceItem] | None = None
    sub_answers: list[dict] | None = None
    subquestion_generator: str | None = None


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
    session_id: str | None = Field(
        None,
        description="A/B 开启时必填，用于粘性分流",
    )
    mode: str = Field(
        default="hybrid_rerank",
        description="vector | bm25 | hybrid | hybrid_rerank | summary | tree | graph | router | sub_question",
    )
    top_k: int = Field(default=5, ge=1, le=50)
    include_trace: bool = Field(
        default=False,
        description="mode=sub_question 时返回 sub_questions 轨迹（无 LLM 合成）",
    )


class SubQuestionTraceItem(BaseModel):
    sub_question: str
    tool_name: str


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
    experiment_id: str | None = None
    variant: str | None = None
    log_id: str | None = Field(None, description="检索日志 ID，供后续反馈关联")
    sub_questions: list[SubQuestionTraceItem] | None = None
    subquestion_generator: str | None = None


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
    sub_qs = (
        [SubQuestionTraceItem(**item) for item in result.sub_questions]
        if result.sub_questions
        else None
    )
    return ChatResponse(
        answer=result.answer,
        citations=result.citations,
        message_id=log_id,
        retrieval_log_id=log_id,
        refused=result.refused,
        experiment_id=result.experiment_id,
        variant=result.variant,
        retrieval_mode=result.retrieval_mode,
        sub_questions=sub_qs,
        sub_answers=result.sub_answers,
        subquestion_generator=result.subquestion_generator,
    )


@app.post("/v1/query", response_model=QueryResponse)
async def query_rag(req: QueryRequest) -> QueryResponse:
    """无会话轻量 RAG — SubQuestion 检索 + 合成（无 rewrite/self-check）."""
    agent_cfg = load_profile().get("agent", {})
    raw_chars = agent_cfg.get("max_chars_per_chunk")
    max_chars = int(raw_chars) if raw_chars is not None else None
    try:
        result = await run_subquestion_query(
            req.query,
            top_k=req.top_k,
            sub_answer_max_tokens=int(agent_cfg.get("sub_answer_max_tokens", 256)),
            synthesis_max_tokens=int(agent_cfg.get("synthesis_max_tokens", 512)),
            max_chars_per_chunk=max_chars,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"SubQuestion query failed: {exc}") from exc
    from apps.agent.prompts import hits_to_citations

    sub_qs = [SubQuestionTraceItem(**item) for item in result.sub_questions]
    return QueryResponse(
        query=req.query,
        answer=result.answer,
        citations=hits_to_citations(result.hits),
        sub_questions=sub_qs,
        sub_answers=result.sub_answers,
        subquestion_generator=result.generator,
    )


@app.get("/v1/admin/ab-test/status")
async def admin_ab_test_status() -> dict:
    cfg = load_ab_test_config()
    if cfg is None:
        return {"enabled": False}
    rows = load_assignments(experiment_id=cfg.experiment_id)
    counts: dict[str, int] = {"A": 0, "B": 0}
    scopes: dict[str, int] = {}
    for row in rows:
        v = str(row.get("variant", "?"))
        counts[v] = counts.get(v, 0) + 1
        sc = str(row.get("scope", ""))
        scopes[sc] = scopes.get(sc, 0) + 1
    return {
        "enabled": True,
        "experiment_id": cfg.experiment_id,
        "traffic_split": cfg.traffic_split,
        "scope": cfg.scope,
        "version_a": {"label": cfg.version_a.label, "mode": cfg.version_a.mode},
        "version_b": {"label": cfg.version_b.label, "mode": cfg.version_b.mode},
        "assignment_counts": counts,
        "by_scope": scopes,
        "total_assignments": len(rows),
    }


@app.post("/v1/search", response_model=SearchResponse)  # M2: docs/m2_retrieval.md §5
async def search(req: SearchRequest) -> SearchResponse:
    ab_config = load_ab_test_config()
    mode = req.mode
    experiment_id: str | None = None
    variant: str | None = None
    log_id: str | None = None

    if ab_config and ab_config.active_for_search():
        if not req.session_id:
            raise HTTPException(
                status_code=400,
                detail="session_id is required when ab_test is enabled (scope=search|both)",
            )
        selection = select_variant(req.session_id, ab_config)
        mode = selection.mode
        experiment_id = selection.experiment_id
        variant = selection.variant
        log_id = str(uuid.uuid4())

    t0 = time.perf_counter()
    sub_questions: list[SubQuestionTraceItem] | None = None
    subquestion_generator: str | None = None
    try:
        if mode == "sub_question" and req.include_trace:
            detail = await query_subquestion_detail(req.query, top_k=req.top_k)
            hits = detail["hits"]
            sub_questions = [
                SubQuestionTraceItem(**item) for item in detail.get("sub_questions", [])
            ]
            subquestion_generator = detail.get("generator")
        else:
            hits = await dispatch_search(req.query, mode, req.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    latency_ms = (time.perf_counter() - t0) * 1000.0

    trace_payload: dict | None = None
    if sub_questions is not None:
        trace_payload = {
            "generator": subquestion_generator,
            "sub_questions": [item.model_dump() for item in sub_questions],
        }

    if log_id and req.session_id:
        write_retrieval_log(
            log_id=log_id,
            session_id=req.session_id,
            query=req.query,
            search_query=req.query,
            hits=hits,
            refused=False,
            experiment_id=experiment_id,
            variant=variant,
            retrieval_mode=mode,
            sub_question_trace=trace_payload,
        )
        write_assignment(
            log_id=log_id,
            experiment_id=experiment_id or "",
            session_id=req.session_id,
            variant=variant or "",
            retrieval_mode=mode,
            scope="search",
            latency_ms=latency_ms,
        )

    return SearchResponse(
        query=req.query,
        mode=mode,
        hits=hits,
        experiment_id=experiment_id,
        variant=variant,
        log_id=log_id,
        sub_questions=sub_questions,
        subquestion_generator=subquestion_generator,
    )


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


@app.post("/v1/storage/upload")
async def storage_upload(key: str, file: UploadFile = File(...)) -> dict:
    try:
        from apps.storage.minio_store import upload_bytes

        data = await file.read()
        return upload_bytes(key, data, content_type=file.content_type or "application/octet-stream")
    except ImportError as exc:
        raise HTTPException(status_code=501, detail="pip install minio or .[storage]") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/storage/download/{key:path}")
async def storage_download(key: str) -> Response:
    try:
        from apps.storage.minio_store import download_bytes

        data = download_bytes(key)
        return Response(content=data, media_type="application/octet-stream")
    except ImportError as exc:
        raise HTTPException(status_code=501, detail="pip install minio or .[storage]") from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/storage/list")
async def storage_list(prefix: str = "", limit: int = 50) -> dict:
    try:
        from apps.storage.minio_store import list_objects

        return {"objects": list_objects(prefix=prefix, limit=limit)}
    except ImportError as exc:
        raise HTTPException(status_code=501, detail="pip install minio or .[storage]") from exc


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
