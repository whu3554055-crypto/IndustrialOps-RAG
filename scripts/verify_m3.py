"""M3 Agent 验收 — 库内问答、3 轮追问、库外拒答."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

GATEWAY = "http://localhost:8080"
SESSION = "m3-verify"


def _format_url_error(exc: urllib.error.URLError) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("detail", body)
        except json.JSONDecodeError:
            detail = body
        text = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
        return f"HTTP {exc.code}: {text[:240]}"
    return str(exc)


def _post_chat(query: str, session_id: str = SESSION) -> dict:
    body = json.dumps({"session_id": session_id, "query": query}, ensure_ascii=False).encode(
        "utf-8"
    )
    req = urllib.request.Request(
        f"{GATEWAY}/v1/chat",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    global GATEWAY  # noqa: PLW0603
    parser = argparse.ArgumentParser(description="M3 agent verification")
    parser.add_argument("--gateway", default=GATEWAY)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    GATEWAY = args.gateway.rstrip("/")

    report: dict = {"session_id": SESSION, "cases": []}
    passed = 0
    total = 0

    # Case 1: in-domain
    total += 1
    try:
        r1 = _post_chat("P-101 出口压力正常范围是多少？", session_id=f"{SESSION}-1")
        ok = not r1.get("refused") and len(r1.get("citations", [])) > 0
        passed += int(ok)
        _check("库内问答 + 引用", ok, r1.get("answer", "")[:60])
        report["cases"].append({"name": "in_domain", "response": r1, "ok": ok})
    except urllib.error.URLError as exc:
        err = _format_url_error(exc)
        _check("库内问答 + 引用", False, err)
        report["cases"].append({"name": "in_domain", "error": err, "ok": False})

    # Case 2: 3-turn follow-up (same session)
    total += 1
    try:
        sid = f"{SESSION}-followup"
        _post_chat("离心泵 P-101 用什么润滑油？", session_id=sid)
        _post_chat("更换周期呢？", session_id=sid)
        r3 = _post_chat("还有什么是日常点检要注意的？", session_id=sid)
        ok = not r3.get("refused") and "P-101" in r3.get("answer", "") or "轴承" in r3.get(
            "answer", ""
        )
        passed += int(ok)
        _check("3 轮追问", ok, r3.get("answer", "")[:60])
        report["cases"].append({"name": "followup_3turn", "response": r3, "ok": ok})
    except urllib.error.URLError as exc:
        err = _format_url_error(exc)
        _check("3 轮追问", False, err)
        report["cases"].append({"name": "followup_3turn", "error": err, "ok": False})

    # Case 3: out-of-corpus refuse
    total += 1
    try:
        r4 = _post_chat(
            "请分析一下今天 A 股上证指数走势并给出投资建议。",
            session_id=f"{SESSION}-ood",
        )
        ok = bool(r4.get("refused"))
        passed += int(ok)
        _check("库外拒答", ok, r4.get("answer", "")[:60])
        report["cases"].append({"name": "out_of_corpus", "response": r4, "ok": ok})
    except urllib.error.URLError as exc:
        err = _format_url_error(exc)
        _check("库外拒答", False, err)
        report["cases"].append({"name": "out_of_corpus", "error": err, "ok": False})

    print(f"\nM3: {passed}/{total} passed")
    if args.write_report:
        out = Path(__file__).resolve().parents[1] / "reports" / "m3_verify.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {out}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
