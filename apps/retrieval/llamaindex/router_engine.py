"""LlamaIndex RouterQueryEngine — 自动选检索模式."""

from apps.config import load_profile, get_settings


async def query_router(query: str) -> list[dict]:
    profile = load_profile(get_settings().ior_profile)
    modes = profile.get("retrieval", {}).get("llamaindex_modes", [])
    _ = modes
    raise NotImplementedError("M2: RouterQueryEngine")
