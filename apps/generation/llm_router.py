"""LLM Router — vLLM | TensorRT-LLM | API."""

from openai import AsyncOpenAI

from apps.config import get_settings, resolve_vllm_model


def _client_for_backend(backend: str | None = None) -> tuple[AsyncOpenAI, str]:
    s = get_settings()
    backend = backend or s.llm_active_backend
    model = resolve_vllm_model()
    if backend == "vllm":
        return AsyncOpenAI(base_url=s.vllm_base_url, api_key="EMPTY"), model
    if backend == "tensorrt_llm":
        return AsyncOpenAI(base_url=s.tensorrt_llm_base_url, api_key="EMPTY"), model
    if backend == "api":
        return AsyncOpenAI(), model  # 使用 OPENAI_* 环境变量
    raise ValueError(f"Unknown backend: {backend}")


async def generate(messages: list[dict], backend: str | None = None) -> str:
    client, model = _client_for_backend(backend)
    resp = await client.chat.completions.create(model=model, messages=messages)
    return resp.choices[0].message.content or ""
