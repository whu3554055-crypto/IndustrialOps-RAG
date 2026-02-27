"""SubQuestion 自研 vs 官方 LI 适配器 benchmark CLI（非生产 dispatch）."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.retrieval.llamaindex.subquestion.li_benchmark import (  # noqa: E402
    llamaindex_available,
    run_benchmark_cli,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SubQuestion recall benchmark — self-built vs official LI adapter",
    )
    parser.add_argument(
        "--golden",
        default="data/eval/m2_compound.jsonl",
        help="compound golden jsonl (falls back to .example)",
    )
    parser.add_argument(
        "--output",
        default="reports/subquestion_compare.json",
        help="JSON report path",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0, help="first N cases (0=all)")
    args = parser.parse_args()

    limit = args.limit if args.limit > 0 else None
    summary = asyncio.run(
        run_benchmark_cli(
            golden=args.golden,
            output=args.output,
            top_k=args.top_k,
            limit=limit,
        )
    )

    print(f"official LI available: {summary.official_available} ({llamaindex_available()})")
    print(
        f"self-built Recall@{summary.top_k}: {summary.self_recall_at_k:.0%} "
        f"({summary.self_passed}/{summary.total})"
    )
    if summary.official_recall_at_k is not None:
        print(
            f"official adapter Recall@{summary.top_k}: {summary.official_recall_at_k:.0%} "
            f"({summary.official_passed}/{summary.total})"
        )
    print(f"report: {args.output}")


if __name__ == "__main__":
    main()
