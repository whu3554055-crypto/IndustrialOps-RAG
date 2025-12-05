"""M3 Agent 验收 — 库内问答、3 轮追问、库外拒答.

学习文档：docs/m3_agent.md §7
Case1 库内+引用 | Case2 三轮追问(最慢) | Case3 库外拒答
本机 exclusive 检索：单次 chat 可达数分钟，--timeout 默认 1200s/req。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

GATEWAY = "http://localhost:8080"
SESSION = "m3-verify"
# 本机 exclusive 检索：每次 hybrid+rerank 会加载/释放 CPU 模型；单次 chat 常数分钟级
DEFAULT_TIMEOUT_S = 1200

CASE_CHOICES = ("all", "1", "2", "3", "in_domain", "followup", "out_of_corpus")


def _format_url_error(exc: urllib.error.URLError) -> str:
    if isinstance(exc.reason, TimeoutError):
        return (
            f"请求超时（{exc.reason}）。"
            "本机 Agent 含 CPU 检索加载与多次 vLLM，属预期偏慢；"
            "可加大 --timeout、用 --case 2 单独验追问，或先 curl /v1/health。"
        )
    if isinstance(exc, urllib.error.HTTPError):
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("detail", body)
        except json.JSONDecodeError:
            detail = body
        text = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
        return f"HTTP {exc.code}: {text[:240]}"
    return str(exc)


def _post_chat(query: str, session_id: str = SESSION, *, timeout_s: int = DEFAULT_TIMEOUT_S) -> dict:
    body = json.dumps({"session_id": session_id, "query": query}, ensure_ascii=False).encode(
        "utf-8"
    )
    req = urllib.request.Request(
        f"{GATEWAY}/v1/chat",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def _normalize_cases(raw: str) -> set[str]:
    if raw == "all":
        return {"1", "2", "3"}
    aliases = {
        "in_domain": "1",
        "followup": "2",
        "out_of_corpus": "3",
    }
    key = aliases.get(raw, raw)
    return {key}


def _run_case_in_domain(chat: Callable[..., dict], report: dict) -> bool:
    try:
        r1 = chat("P-101 出口压力正常范围是多少？", session_id=f"{SESSION}-1")
        ok = not r1.get("refused") and len(r1.get("citations", [])) > 0
        _check("库内问答 + 引用", ok, r1.get("answer", "")[:60])
        report["cases"].append({"name": "in_domain", "response": r1, "ok": ok})
        return ok
    except urllib.error.URLError as exc:
        err = _format_url_error(exc)
        _check("库内问答 + 引用", False, err)
        report["cases"].append({"name": "in_domain", "error": err, "ok": False})
        return False


def _run_case_followup(chat: Callable[..., dict], report: dict) -> bool:
    try:
        sid = f"{SESSION}-followup"
        chat("离心泵 P-101 用什么润滑油？", session_id=sid)
        chat("更换周期呢？", session_id=sid)
        r3 = chat("还有什么是日常点检要注意的？", session_id=sid)
        ans = r3.get("answer", "")
        ok = not r3.get("refused") and ("P-101" in ans or "轴承" in ans)
        _check("3 轮追问", ok, r3.get("answer", "")[:60])
        report["cases"].append({"name": "followup_3turn", "response": r3, "ok": ok})
        return ok
    except urllib.error.URLError as exc:
        err = _format_url_error(exc)
        _check("3 轮追问", False, err)
        report["cases"].append({"name": "followup_3turn", "error": err, "ok": False})
        return False


def _run_case_out_of_corpus(chat: Callable[..., dict], report: dict) -> bool:
    try:
        r4 = chat(
            "请分析一下今天 A 股上证指数走势并给出投资建议。",
            session_id=f"{SESSION}-ood",
        )
        ok = bool(r4.get("refused"))
        _check("库外拒答", ok, r4.get("answer", "")[:60])
        report["cases"].append({"name": "out_of_corpus", "response": r4, "ok": ok})
        return ok
    except urllib.error.URLError as exc:
        err = _format_url_error(exc)
        _check("库外拒答", False, err)
        report["cases"].append({"name": "out_of_corpus", "error": err, "ok": False})
        return False


def main() -> int:
    global GATEWAY  # noqa: PLW0603
    parser = argparse.ArgumentParser(
        description="M3 Agent verification — /v1/chat 库内/追问/拒答",
        epilog="示例: python scripts/verify_m3.py --case 2 --write-report\n"
        "文档: docs/m3_agent.md §7",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--gateway", default=GATEWAY)
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_S,
        help=f"单次 /v1/chat 超时秒数（默认 {DEFAULT_TIMEOUT_S}）",
    )
    parser.add_argument(
        "--case",
        default="all",
        choices=CASE_CHOICES,
        help="运行用例：all | 1/2/3 | in_domain | followup | out_of_corpus",
    )
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    GATEWAY = args.gateway.rstrip("/")
    timeout_s = max(30, args.timeout)
    selected = _normalize_cases(args.case)

    case2_note = "（本 case 共 3 次 /v1/chat）" if "2" in selected else ""
    print(f"Gateway={GATEWAY}  timeout={timeout_s}s/req  cases={sorted(selected)}{case2_note}")

    def chat(query: str, session_id: str = SESSION) -> dict:
        print(f"  → {query[:40]}…" if len(query) > 40 else f"  → {query}")
        return _post_chat(query, session_id=session_id, timeout_s=timeout_s)

    report: dict = {"session_id": SESSION, "cases": [], "selected_cases": sorted(selected)}
    passed = 0
    total = 0

    runners = {
        "1": _run_case_in_domain,
        "2": _run_case_followup,
        "3": _run_case_out_of_corpus,
    }
    for key in ("1", "2", "3"):
        if key not in selected:
            continue
        total += 1
        if runners[key](chat, report):
            passed += 1

    print(f"\nM3: {passed}/{total} passed")
    if args.write_report:
        out = Path(__file__).resolve().parents[1] / "reports" / "m3_verify.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {out}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
