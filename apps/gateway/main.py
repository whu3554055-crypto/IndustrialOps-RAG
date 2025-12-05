"""FastAPI Gateway — 会话、问答、反馈、健康检查."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from apps.agent.pipeline import run_agentic_rag
from apps.config import get_settings, load_profile
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
    retrieval_log_id: str | None = None
    refused: bool = False


class FeedbackRequest(BaseModel):
    session_id: str
    message_id: str
    rating: int = Field(..., ge=-1, le=1, description="-1 踩 / 1 赞")
    comment: str | None = None


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
    }


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
    try:
        result = await run_agentic_rag(req.session_id, req.query)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Agent pipeline failed: {exc}",
        ) from exc
    return ChatResponse(
        answer=result.answer,
        citations=result.citations,
        retrieval_log_id=result.retrieval_log_id,
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


@app.post("/v1/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    hits = await _dispatch_search(req.query, req.mode, req.top_k)
    return SearchResponse(query=req.query, mode=req.mode, hits=hits)


@app.post("/v1/feedback")
async def feedback(req: FeedbackRequest) -> dict:
    # TODO: 写入 PostgreSQL
    return {"ok": True, "session_id": req.session_id}


@app.post("/v1/ingest")
async def ingest_trigger() -> dict:
    # TODO: 触发 ingest Job 或本地 pipelines.ingest
    return {"ok": True, "message": "ingest not implemented"}


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
