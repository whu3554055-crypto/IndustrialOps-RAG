"""Serving benchmark CLI — TTFT / TPOT / QPS for vLLM | TensorRT-LLM."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.config import get_settings  # noqa: E402
from apps.generation.llm_router import probe_backend, run_benchmark  # noqa: E402


def _gpu_mem_peak_mb() -> int | None:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        )
        values = [int(x.strip()) for x in out.strip().splitlines() if x.strip().isdigit()]
        return max(values) if values else None
    except (FileNotFoundError, subprocess.SubprocessError, ValueError):
        return None


def _update_serving_doc(report: dict, doc_path: Path) -> None:
    if not doc_path.exists():
        return
    text = doc_path.read_text(encoding="utf-8")
    backend = report["backend"]
    row_label = "vLLM" if backend == "vllm" else "TensorRT-LLM"
    tpot = report.get("tpot_p50_s")
    tpot_cell = f"{tpot:.3f}s" if tpot is not None else "—"
    gpu = report.get("gpu_mem_peak_mb")
    gpu_cell = f"{gpu} MiB" if gpu is not None else "—"
    new_row = (
        f"| {row_label} | {report['ttft_p50_s']:.3f}s | {report['ttft_p95_s']:.3f}s | "
        f"{tpot_cell} | {report['qps']:.2f} | {gpu_cell} |"
    )
    pattern = rf"\| {re.escape(row_label)} \|[^\n]*\n"
    if re.search(pattern, text):
        text = re.sub(pattern, new_row + "\n", text, count=1)
    else:
        text = text.replace(
            "| vLLM | | | | | |\n",
            new_row + "\n" if row_label == "vLLM" else "| vLLM | | | | | |\n",
        )
        if row_label == "TensorRT-LLM":
            text = text.replace("| TensorRT-LLM | | | | | |\n", new_row + "\n")
    measured = datetime.now(UTC).strftime("%Y-%m-%d")
    if "## 最近测量" not in text:
        text = text.rstrip() + f"\n\n## 最近测量\n\n- {measured}：`{backend}` concurrency={report['concurrency']}\n"
    doc_path.write_text(text, encoding="utf-8")


async def _main_async(args: argparse.Namespace) -> int:
    backend = args.backend
    status = await probe_backend(backend or get_settings().llm_active_backend)
    if not status.reachable:
        print(f"Backend unreachable: {status.name} @ {status.base_url}")
        print(f"  {status.error or 'unknown error'}")
        print("Hint: start vLLM Docker (COLLABORATION §3.5) or use --backend matching a live service.")
        return 1

    backend = status.name
    print(
        f"Benchmark {backend} model={status.model} "
        f"warmup={args.warmup} concurrency={args.concurrency} requests={args.requests}"
    )

    gpu_before = _gpu_mem_peak_mb()
    result = await run_benchmark(
        backend,
        concurrency=args.concurrency,
        requests=args.requests,
        warmup_requests=args.warmup,
        max_tokens=args.max_tokens,
    )
    gpu_after = _gpu_mem_peak_mb()
    gpu_peak = max(x for x in (gpu_before, gpu_after) if x is not None) if gpu_before or gpu_after else None

    report = {
        "backend": result.backend,
        "model": status.model,
        "methodology": {
            "metric": "streaming",
            "warmup_requests": result.warmup_requests,
            "ttft": "first content chunk latency",
            "tpot": "(total - ttft) / (output_tokens - 1); token count from usage or zh char estimate",
            "qps": "completed_requests / wall_clock_seconds",
        },
        "concurrency": result.concurrency,
        "requests": result.requests,
        "ttft_p50_s": round(result.ttft_p50_s, 4),
        "ttft_p95_s": round(result.ttft_p95_s, 4),
        "tpot_p50_s": round(result.tpot_p50_s, 4) if result.tpot_p50_s is not None else None,
        "qps": round(result.qps, 4),
        "gpu_mem_peak_mb": gpu_peak,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    print(
        f"{result.backend}: TTFT p50={report['ttft_p50_s']}s p95={report['ttft_p95_s']}s "
        f"TPOT p50={report['tpot_p50_s']} QPS={report['qps']}"
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report: {out}")

    if args.update_doc:
        _update_serving_doc(report, ROOT / "docs" / "serving_benchmark.md")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="M4 serving benchmark")
    parser.add_argument("--backend", default=None, help="vllm | tensorrt_llm | api")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--requests", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--warmup", type=int, default=1, help="预热请求数（不计入统计）")
    parser.add_argument(
        "--lite",
        action="store_true",
        help="本机轻量档：concurrency=1 requests=2 max-tokens=64（6GB GPU 推荐）",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "reports" / "serving_benchmark.json"),
    )
    parser.add_argument("--update-doc", action="store_true", help="回填 docs/serving_benchmark.md 表格")
    args = parser.parse_args()
    if args.lite:
        args.concurrency = 1
        args.requests = 2
        args.max_tokens = 64
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
