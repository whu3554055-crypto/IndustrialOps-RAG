"""Profile ab_test 段加载与校验."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.config import load_profile

SEARCH_SCOPES = frozenset({"search", "both"})
CHAT_SCOPES = frozenset({"chat", "both"})
VALID_MODES = frozenset(
    {
        "vector",
        "bm25",
        "keyword",
        "hybrid",
        "hybrid_rerank",
        "summary",
        "tree",
        "graph",
        "router",
        "sub_question",
    }
)


@dataclass(frozen=True)
class VersionArm:
    label: str
    mode: str


@dataclass(frozen=True)
class ABTestConfig:
    experiment_id: str
    traffic_split: float
    min_sample_size: int
    scope: str
    version_a: VersionArm
    version_b: VersionArm

    def active_for_search(self) -> bool:
        return self.scope in SEARCH_SCOPES

    def active_for_chat(self) -> bool:
        return self.scope in CHAT_SCOPES


def _parse_arm(raw: dict[str, Any], default_label: str) -> VersionArm:
    label = str(raw.get("label", default_label)).upper()[:1]
    if label not in ("A", "B"):
        label = default_label
    mode = str(raw.get("mode", "hybrid_rerank"))
    if mode not in VALID_MODES:
        raise ValueError(f"ab_test invalid mode: {mode}")
    return VersionArm(label=label, mode=mode)


def load_ab_test_config() -> ABTestConfig | None:
    """实验未启用时返回 None."""
    raw = load_profile().get("ab_test") or {}
    if not raw.get("enabled"):
        return None
    experiment_id = str(raw.get("experiment_id", "")).strip()
    if not experiment_id:
        return None
    traffic_split = float(raw.get("traffic_split", 0.5))
    if not 0.0 <= traffic_split <= 1.0:
        raise ValueError("ab_test.traffic_split must be in [0, 1]")
    scope = str(raw.get("scope", "search")).lower()
    if scope not in SEARCH_SCOPES | CHAT_SCOPES:
        raise ValueError(f"ab_test.scope invalid: {scope}")
    return ABTestConfig(
        experiment_id=experiment_id,
        traffic_split=traffic_split,
        min_sample_size=int(raw.get("min_sample_size", 200)),
        scope=scope,
        version_a=_parse_arm(raw.get("version_a") or {}, "A"),
        version_b=_parse_arm(raw.get("version_b") or {}, "B"),
    )
