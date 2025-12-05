"""Multi-turn query rewrite.

无 history 时原样返回；有 history 时调 LLM 改写成独立问句。
expand=True 用于自检失败后的二次检索（补全设备/故障指代）。
文档：docs/m3_agent.md §3.2
"""

from __future__ import annotations

from apps.agent.prompts import REWRITE_SYSTEM
from apps.generation.llm_router import generate


def _format_history(history: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for msg in history:
        role = "用户" if msg["role"] == "user" else "助手"
        lines.append(f"{role}：{msg['content']}")
    return "\n".join(lines)


async def rewrite_query(
    query: str,
    history: list[dict[str, str]] | None,
    *,
    expand: bool = False,
) -> str:
    """Rewrite follow-up queries; passthrough when no history."""
    if not history:
        return query

    history_text = _format_history(history)
    extra = "若指代不清，结合历史补全设备编号与故障上下文。" if expand else ""
    user = (
        f"对话历史：\n{history_text}\n\n"
        f"最新问题：{query}\n\n"
        f"{extra}\n"
        "改写后的独立问句："
    ).strip()

    rewritten = await generate(
        [
            {"role": "system", "content": REWRITE_SYSTEM},
            {"role": "user", "content": user},
        ]
    )
    text = rewritten.strip().strip('"').strip("'")
    return text or query
