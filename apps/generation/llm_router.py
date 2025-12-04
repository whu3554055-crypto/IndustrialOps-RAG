"""LLM Router — vLLM | TensorRT-LLM | API.

M4 推理层统一入口：按 profile / .env 选择后端，OpenAI 兼容调用。
学习文档（流程图、切换、压测、KEDA）：docs/m4_serving.md

主要 API:
  - probe_backend / list_backend_status  探活 GET /v1/models
  - generate                             Agent / Gateway 非流式
  - generate_stream_metrics + run_benchmark  压测 TTFT/TPOT（见 scripts/benchmark_serving.py）
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from openai import AsyncOpenAI

from apps.config import get_settings, load_profile, resolve_vllm_model

BACKENDS = ("vllm", "tensorrt_llm", "api")


@dataclass
class BackendStatus:
    name: str
    enabled: bool
    active: bool
    base_url: str
    reachable: bool
    model: str | None = None
    error: str | None = None


@dataclass
class StreamMetrics:
    ttft_s: float
    total_s: float
    output_tokens: int
    text: str = ""

    @property
    def tpot_s(self) -> float | None:
        if self.output_tokens <= 1:
            return None
        return (self.total_s - self.ttft_s) / (self.output_tokens - 1)


@dataclass
class BenchmarkResult:
    backend: str
    concurrency: int
    requests: int
    warmup_requests: int
    ttft_p50_s: float
    ttft_p95_s: float
    tpot_p50_s: float | None
    qps: float
    gpu_mem_peak_mb: int | None = None
    samples: list[StreamMetrics] = field(default_factory=list)


def _backend_base_url(backend: str) -> str:
    s = get_settings()
    if backend == "vllm":
        return s.vllm_base_url.rstrip("/")
    if backend == "tensorrt_llm":
        return s.tensorrt_llm_base_url.rstrip("/")
    if backend == "api":
        return (s.model_dump().get("openai_base_url") or "").rstrip("/") or "https://api.openai.com/v1"
    raise ValueError(f"Unknown backend: {backend}")


def _client_for_backend(backend: str | None = None) -> tuple[AsyncOpenAI, str]:
    s = get_settings()
    backend = backend or s.llm_active_backend
    model = resolve_vllm_model()
    if backend == "vllm":
        return AsyncOpenAI(base_url=s.vllm_base_url, api_key="EMPTY"), model
    if backend == "tensorrt_llm":
        return AsyncOpenAI(base_url=s.tensorrt_llm_base_url, api_key="EMPTY"), model
    if backend == "api":
        return AsyncOpenAI(), model
    raise ValueError(f"Unknown backend: {backend}")


def configured_backends() -> list[str]:
    profile = load_profile()
    llm = profile.get("llm", {})
    backends_cfg = llm.get("backends", {})
    out = [name for name in BACKENDS if backends_cfg.get(name, {}).get("enabled")]
    return out or [get_settings().llm_active_backend]


async def probe_backend(backend: str) -> BackendStatus:
    s = get_settings()
    profile = load_profile()
    llm = profile.get("llm", {})
    backends_cfg = llm.get("backends", {})
    key = backend
    cfg = backends_cfg.get(key, {})
    enabled = bool(cfg.get("enabled", backend == llm.get("active_backend")))
    active = backend == (s.llm_active_backend or llm.get("active_backend", "vllm"))
    base = _backend_base_url(backend)
    status = BackendStatus(
        name=backend,
        enabled=enabled,
        active=active,
        base_url=base,
        reachable=False,
    )
    if not enabled:
        status.error = "disabled in profile"
        return status
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base}/models")
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data") or []
            status.model = models[0]["id"] if models else resolve_vllm_model()
            status.reachable = True
    except Exception as exc:  # noqa: BLE001 — probe aggregates errors for status API
        status.error = str(exc)
    return status


async def list_backend_status() -> list[BackendStatus]:
    return [await probe_backend(name) for name in configured_backends()]


async def generate(
    messages: list[dict[str, Any]],
    backend: str | None = None,
    *,
    max_tokens: int = 512,
) -> str:
    client, model = _client_for_backend(backend)
    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


async def generate_stream_metrics(
    messages: list[dict[str, Any]],
    backend: str | None = None,
    *,
    max_tokens: int = 128,
) -> StreamMetrics:
    client, model = _client_for_backend(backend)
    started = time.perf_counter()
    ttft: float | None = None
    chunks: list[str] = []
    output_tokens = 0

    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        stream=True,
    )
    async for event in stream:
        now = time.perf_counter()
        if not event.choices:
            continue
        delta = event.choices[0].delta.content
        if delta:
            if ttft is None:
                ttft = now - started
            chunks.append(delta)
        usage = getattr(event, "usage", None)
        if usage and getattr(usage, "completion_tokens", None):
            output_tokens = usage.completion_tokens

    total = time.perf_counter() - started
    text = "".join(chunks)
    if output_tokens == 0 and text:
        output_tokens = _estimate_output_tokens(text)
    return StreamMetrics(
        ttft_s=ttft if ttft is not None else total,
        total_s=total,
        output_tokens=output_tokens,
        text=text,
    )


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (same spirit as NumPy)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (k - f) * (ordered[c] - ordered[f])


def _estimate_output_tokens(text: str) -> int:
    """Fallback when streaming usage is absent (vLLM 0.6.x). ~1.5 chars/token for zh."""
    if not text:
        return 0
    return max(1, round(len(text) / 1.5))


async def run_benchmark(
    backend: str | None = None,
    *,
    concurrency: int = 2,
    requests: int = 4,
    warmup_requests: int = 1,
    max_tokens: int = 128,
    prompt: str | None = None,
) -> BenchmarkResult:
    import asyncio

    backend = backend or get_settings().llm_active_backend
    prompt = prompt or "请用三句话说明离心泵日常点检要点。"
    messages = [{"role": "user", "content": prompt}]

    for _ in range(max(0, warmup_requests)):
        await generate_stream_metrics(messages, backend, max_tokens=min(32, max_tokens))

    sem = asyncio.Semaphore(max(1, concurrency))
    samples: list[StreamMetrics] = []

    async def one() -> None:
        async with sem:
            samples.append(
                await generate_stream_metrics(messages, backend, max_tokens=max_tokens)
            )

    wall_start = time.perf_counter()
    await asyncio.gather(*(one() for _ in range(max(1, requests))))
    wall_s = time.perf_counter() - wall_start

    ttfts = [s.ttft_s for s in samples]
    tpots = [s.tpot_s for s in samples if s.tpot_s is not None]

    return BenchmarkResult(
        backend=backend,
        concurrency=concurrency,
        requests=len(samples),
        warmup_requests=warmup_requests,
        ttft_p50_s=_percentile(ttfts, 50),
        ttft_p95_s=_percentile(ttfts, 95),
        tpot_p50_s=_percentile(tpots, 50) if tpots else None,
        qps=len(samples) / wall_s if wall_s > 0 else 0.0,
        samples=samples,
    )
