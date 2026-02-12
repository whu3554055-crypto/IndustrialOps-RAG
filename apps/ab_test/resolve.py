"""解析当前会话应使用的检索 mode（A/B 或 agent 默认）."""

from __future__ import annotations

from dataclasses import dataclass

from apps.ab_test.config import load_ab_test_config
from apps.ab_test.router import select_variant
from apps.config import load_profile

DEFAULT_MODE = "hybrid_rerank"


@dataclass(frozen=True)
class ResolvedRetrieval:
    mode: str
    experiment_id: str | None
    variant: str | None


def resolve_retrieval_mode(session_id: str) -> ResolvedRetrieval:
    ab = load_ab_test_config()
    if ab and ab.active_for_chat():
        sel = select_variant(session_id, ab)
        return ResolvedRetrieval(sel.mode, sel.experiment_id, sel.variant)
    agent = load_profile().get("agent", {})
    mode = str(agent.get("default_retrieval_mode", DEFAULT_MODE))
    return ResolvedRetrieval(mode, None, None)
