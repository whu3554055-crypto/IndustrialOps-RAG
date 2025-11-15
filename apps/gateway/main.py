"""FastAPI Gateway — 会话、问答、反馈、健康检查."""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from apps.config import get_settings

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
