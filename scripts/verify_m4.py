"""M4 验收 — LLM router、KEDA 配置、可选 serving 压测.

学习文档：docs/m4_serving.md §7
用例：profile 双后端+KEDA → active 后端 probe →（可选）Gateway /v1/llm/backends →（可选）quick benchmark
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.config import load_profile  # noqa: E402
from apps.generation.llm_router import list_backend_status, probe_backend  # noqa: E402

GATEWAY = "http://localhost:8080"


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def _case_profile_keda(report: dict) -> bool:
    profile = load_profile()
    keda = profile.get("keda", {})
    llm = profile.get("llm", {})
    backends = llm.get("backends", {})
    ok = (
        keda.get("enabled") is True
        and backends.get("vllm", {}).get("enabled") is True
        and backends.get("tensorrt_llm", {}).get("enabled") is True
        and llm.get("active_backend") in ("vllm", "tensorrt_llm", "api")
    )
    detail = f"active={llm.get('active_backend')} keda.max={keda.get('vllm', {}).get('max_replicas')}"
    _check("profile KEDA + 双后端", ok, detail)
    report["cases"].append({"name": "profile_keda", "ok": ok, "detail": detail})
    return ok


async def _case_router_probe(report: dict) -> bool:
    active = load_profile().get("llm", {}).get("active_backend", "vllm")
    status = await probe_backend(active)
    ok = status.reachable
    detail = status.model or status.error or "unknown"
    _check(f"router probe ({active})", ok, detail[:80])
    report["cases"].append(
        {
            "name": "router_probe",
            "backend": active,
            "reachable": status.reachable,
            "model": status.model,
            "error": status.error,
            "ok": ok,
        }
    )
    return ok


def _case_gateway_backends(gateway: str, report: dict) -> bool:
    url = f"{gateway.rstrip('/')}/v1/llm/backends"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        backends = data.get("backends", [])
        active = [b for b in backends if b.get("active")]
        ok = len(backends) >= 2 and any(b.get("reachable") for b in backends if b.get("active"))
        detail = f"{len(backends)} backends, active reachable={ok}"
        _check("GET /v1/llm/backends", ok, detail)
        report["cases"].append({"name": "gateway_backends", "response": data, "ok": ok})
        return ok
    except urllib.error.URLError as exc:
        err = str(exc.reason) if hasattr(exc, "reason") else str(exc)
        _check("GET /v1/llm/backends", False, err[:120])
        report["cases"].append({"name": "gateway_backends", "error": err, "ok": False})
        return False


async def _case_quick_benchmark(report: dict) -> bool:
    from apps.generation.llm_router import run_benchmark

    try:
        result = await run_benchmark(concurrency=2, requests=2, max_tokens=64)
        ok = result.requests >= 2 and result.ttft_p50_s > 0
        detail = f"TTFT p50={result.ttft_p50_s:.3f}s QPS={result.qps:.2f}"
        _check("quick benchmark (2 req)", ok, detail)
        report["cases"].append(
            {
                "name": "quick_benchmark",
                "ttft_p50_s": result.ttft_p50_s,
                "qps": result.qps,
                "ok": ok,
            }
        )
        return ok
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        _check("quick benchmark (2 req)", False, err[:120])
        report["cases"].append({"name": "quick_benchmark", "error": err, "ok": False})
        return False


async def _async_main(args: argparse.Namespace) -> int:
    report: dict = {"cases": []}
    passed = 0
    total = 0

    for fn in (_case_profile_keda,):
        total += 1
        if fn(report):
            passed += 1

    total += 1
    if await _case_router_probe(report):
        passed += 1

    if not args.skip_gateway:
        total += 1
        if _case_gateway_backends(args.gateway, report):
            passed += 1

    if args.benchmark:
        total += 1
        if await _case_quick_benchmark(report):
            passed += 1

    statuses = await list_backend_status()
    report["backends"] = [
        {
            "name": s.name,
            "enabled": s.enabled,
            "active": s.active,
            "reachable": s.reachable,
            "model": s.model,
            "error": s.error,
        }
        for s in statuses
    ]

    print(f"\nM4: {passed}/{total} passed")
    if args.write_report:
        out = ROOT / "reports" / "m4_verify.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {out}")

    return 0 if passed == total else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="M4 serving / router verification",
        epilog="示例: python scripts/verify_m4.py --skip-gateway --write-report\n"
        "文档: docs/m4_serving.md §7",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--gateway", default=GATEWAY)
    parser.add_argument("--skip-gateway", action="store_true", help="Gateway 未起时跳过 HTTP 用例")
    parser.add_argument("--benchmark", action="store_true", help="跑 2 请求快速压测（需 vLLM）")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    sys.exit(main())
