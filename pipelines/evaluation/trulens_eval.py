"""TruLens 评测占位 — 与 RAGAS 并列；CI 用 dry-run 避免额外 judge.

学习：docs/post-m7-landing.md
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def dry_run_report(sample_count: int) -> dict:
    return {
        "mode": "trulens-dry-run",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sample_count": sample_count,
        "note": "TruLens SDK 未接入；指标为占位，真评测请拍板后接 trulens-eval",
        "groundedness": 0.75,
        "answer_relevance": 0.78,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="TruLens stub evaluator")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "trulens_report.json")
    parser.add_argument("--samples", type=int, default=12)
    args = parser.parse_args()
    if not args.dry_run:
        raise SystemExit("仅支持 --dry-run；真 TruLens 须 Gateway+vLLM 且单独拍板")
    body = dry_run_report(args.samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"TruLens dry-run -> {args.output}")


if __name__ == "__main__":
    main()
