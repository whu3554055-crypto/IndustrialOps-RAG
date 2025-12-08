"""M0 验收 — profile、Compose 中间件、可选 vLLM.

学习文档：docs/m0_infra.md §9
K8s 全栈验收仍用：kubectl -n industrial-ops get pods
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.config import get_settings, load_profile  # noqa: E402


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def _probe_url(url: str, timeout: int = 5) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status < 400, f"HTTP {resp.status}"
    except urllib.error.URLError as exc:
        reason = exc.reason if hasattr(exc, "reason") else exc
        return False, str(reason)[:120]


def _case_profile(report: dict) -> bool:
    profile = load_profile()
    order = profile.get("startup_order", [])
    services = profile.get("services", {})
    required = ("milvus", "opensearch", "postgresql")
    ok = (
        profile.get("profile") == "dev-single-node"
        and len(order) >= 5
        and all(services.get(name, {}).get("enabled") for name in required)
    )
    detail = f"startup_order={len(order)} steps"
    _check("profile dev-single-node", ok, detail)
    report["cases"].append({"name": "profile", "ok": ok, "startup_order_len": len(order)})
    return ok


def _case_opensearch(report: dict) -> bool:
    s = get_settings()
    url = f"http://{s.opensearch_host}:{s.opensearch_port}/"
    ok, detail = _probe_url(url)
    _check("OpenSearch reachable", ok, detail)
    report["cases"].append({"name": "opensearch", "ok": ok, "url": url, "detail": detail})
    return ok


def _case_milvus(report: dict) -> bool:
    s = get_settings()
    # Milvus 2.x standalone exposes REST on 9091; 19530 is gRPC — try HTTP health first
    for port in (9091, s.milvus_port):
        url = f"http://{s.milvus_host}:{port}/healthz"
        ok, detail = _probe_url(url, timeout=3)
        if ok:
            _check("Milvus reachable", True, f"{url} {detail}")
            report["cases"].append({"name": "milvus", "ok": True, "url": url})
            return True
    url = f"http://{s.milvus_host}:{s.milvus_port}"
    _check("Milvus reachable", False, f"healthz failed; gRPC port {s.milvus_port} not HTTP-probed")
    report["cases"].append({"name": "milvus", "ok": False, "url": url})
    return False


def _case_vllm(report: dict) -> bool:
    s = get_settings()
    base = s.vllm_base_url.rstrip("/")
    url = f"{base}/models"
    ok, detail = _probe_url(url, timeout=10)
    _check("vLLM /v1/models", ok, detail)
    report["cases"].append({"name": "vllm", "ok": ok, "url": url, "detail": detail})
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(
        description="M0 infra verification — profile + Compose (+ optional vLLM)",
        epilog="示例: python scripts/verify_m0.py --write-report\n"
        "文档: docs/m0_infra.md §9\n"
        "K8s: kubectl -n industrial-ops get pods",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--skip-compose", action="store_true", help="跳过 OpenSearch/Milvus 探活")
    parser.add_argument("--check-vllm", action="store_true", help="额外检查 vLLM OpenAI /models")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    report: dict = {"cases": [], "k8s_note": "kubectl -n industrial-ops get pods（分时全绿）"}
    passed = 0
    total = 0

    total += 1
    if _case_profile(report):
        passed += 1

    if not args.skip_compose:
        total += 1
        if _case_opensearch(report):
            passed += 1
        total += 1
        if _case_milvus(report):
            passed += 1

    if args.check_vllm:
        total += 1
        if _case_vllm(report):
            passed += 1

    print(f"\nM0: {passed}/{total} passed")
    print(f"K8s 扩展验收: {report['k8s_note']}")

    if args.write_report:
        out = ROOT / "reports" / "m0_verify.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {out}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
