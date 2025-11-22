"""FastAPI Gateway — 会话、问答、反馈、健康检查."""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from apps.config import get_settings
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


@app.get("/v1/health")
async def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "profile": s.ior_profile,
        "llm_backend": s.llm_active_backend,
    }


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    # TODO M3: 接入 apps.agent.pipeline
    return ChatResponse(
        answer=f"[scaffold] 收到问题：{req.query}。请实现 Agent 管道。",
        citations=[],
        refused=False,
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
