"""Agent prompt templates."""

from __future__ import annotations

from apps.config import ROOT

SYSTEM_PROMPT_PATH = ROOT / "apps" / "generation" / "prompts" / "system_zh.txt"

REFUSE_MESSAGE = (
    "抱歉，知识库中未找到足够依据回答该问题。"
    "请咨询现场工程师或查阅完整设备手册，勿凭猜测操作。"
)

REWRITE_SYSTEM = (
    "你是工业运维场景的 query 改写器。"
    "根据对话历史，将用户最新问题改写成独立、可检索的完整中文问句。"
    "只输出一句改写结果，不要解释、不要引号。"
)

SELF_CHECK_SYSTEM = (
    "你是答案质检员。仅根据参考资料判断：候选答案是否完全被资料支持且无编造。"
    "第一行必须只写 YES 或 NO；第二行可选一句理由。"
)


def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def format_context(hits: list[dict]) -> str:
    if not hits:
        return "（无）"
    blocks: list[str] = []
    for i, hit in enumerate(hits, start=1):
        cite = f"{hit['doc_id']}:{hit['chunk_id']}"
        blocks.append(f"[{i}] [{cite}] {hit.get('title', '')}\n{hit['text']}")
    return "\n\n".join(blocks)


def hits_to_citations(hits: list[dict]) -> list[dict]:
    return [
        {
            "doc_id": h["doc_id"],
            "chunk_id": h["chunk_id"],
            "source_file": h.get("source_file", ""),
            "title": h.get("title", ""),
            "score": h.get("score", 0.0),
        }
        for h in hits
    ]
