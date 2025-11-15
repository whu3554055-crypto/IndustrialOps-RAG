"""BGE reranker — 默认 CPU（见 profile）."""

from apps.config import get_settings, load_profile


def get_rerank_config() -> dict:
    profile = load_profile(get_settings().ior_profile)
    return profile.get("rerank", {})


async def rerank(query: str, documents: list[dict], top_n: int | None = None) -> list[dict]:
    raise NotImplementedError("M2: load BAAI/bge-reranker-v2-m3")
