"""M6 15min 路径 — 单次 /v1/chat 探针，结果写 reports/."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = "http://localhost:8080"
QUERY = "故障码 E1024 如何处理？"


def main() -> int:
    body = json.dumps({"session_id": "m6-15min-demo", "query": QUERY}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{GATEWAY}/v1/chat",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    out = ROOT / "reports" / "m6_15min_chat.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    refused = data.get("refused", False)
    answer = data.get("answer", "")[:200]
    cites = len(data.get("citations", []))
    print(f"refused={refused} citations={cites}")
    print(f"answer: {answer}")
    print(f"report: {out}")
    return 0 if not refused and answer else 1


if __name__ == "__main__":
    raise SystemExit(main())
