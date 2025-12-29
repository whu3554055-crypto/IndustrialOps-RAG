"""简易 Prometheus 文本指标（无额外依赖）."""

from __future__ import annotations

_retrieval_logs_total = 0
_chat_requests_total = 0


def inc_retrieval_log() -> None:
    global _retrieval_logs_total
    _retrieval_logs_total += 1


def inc_chat_request() -> None:
    global _chat_requests_total
    _chat_requests_total += 1


def render_prometheus() -> str:
    return (
        f"ior_retrieval_logs_total {_retrieval_logs_total}\n"
        f"ior_chat_requests_total {_chat_requests_total}\n"
    )
