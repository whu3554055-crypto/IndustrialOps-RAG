"""M4 LLM router unit tests (no live vLLM required)."""

from __future__ import annotations

import pytest

from apps.generation.llm_router import (
    BenchmarkResult,
    StreamMetrics,
    _percentile,
    configured_backends,
)


def test_configured_backends_includes_vllm_and_trt():
    names = configured_backends()
    assert "vllm" in names
    assert "tensorrt_llm" in names


def test_stream_metrics_tpot():
    m = StreamMetrics(ttft_s=0.5, total_s=2.5, output_tokens=5)
    assert m.tpot_s == pytest.approx(0.5)
    assert StreamMetrics(ttft_s=0.1, total_s=0.2, output_tokens=1).tpot_s is None


def test_percentile():
    assert _percentile([1.0, 2.0, 3.0], 50) == 2.0
    assert _percentile([], 50) == 0.0


def test_benchmark_result_shape():
    r = BenchmarkResult(
        backend="vllm",
        concurrency=2,
        requests=4,
        warmup_requests=1,
        ttft_p50_s=0.1,
        ttft_p95_s=0.2,
        tpot_p50_s=0.05,
        qps=1.5,
    )
    assert r.backend == "vllm"
    assert r.qps == 1.5
