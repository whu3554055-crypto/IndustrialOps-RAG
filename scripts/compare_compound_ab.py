"""复合问句离线 A/B — hybrid_rerank vs sub_question on m2_compound golden."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.ab_test.compound_compare import (  # noqa: E402
    COMPOUND_AB_EXPERIMENT_ID,
    render_compound_ab_markdown,
    run_compound_ab_compare,
)
from apps.config import ROOT  # noqa: E402
from apps.eval_paths import resolve_eval_jsonl  # noqa: E402
from apps.retrieval.langchain.hybrid_chain import retrieve_context  # noqa: E402
from apps.retrieval.llamaindex.subquestion_engine import query_subquestion  # noqa: E402
from scripts.verify_m2 import TOP_K, load_golden  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compound golden offline A/B: hybrid_rerank vs sub_question (C5)",
        epilog=(
            "示例:\n"
            "  python scripts/compare_compound_ab.py\n"
            "  python scripts/compare_compound_ab.py --golden data/eval/m2_compound_tiny.jsonl\n"
            "在线 A/B 配置见 deploy/profiles/examples/ab-test-subquestion-compound.yaml"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--golden",
        default="data/eval/m2_compound.jsonl",
        help="compound golden (falls back to .example)",
    )
    parser.add_argument(
        "--output",
        default="reports/compound_ab_compare.json",
        help="JSON report path",
    )
    parser.add_argument(
        "--markdown",
        default="reports/compound_ab_compare.md",
        help="Markdown report path",
    )
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument("--limit", type=int, default=0, help="first N cases (0=all)")
    parser.add_argument(
        "--subquestion-generator",
        default="rule_based",
        help="sub_question generator: rule_based | llm | profile",
    )
    args = parser.parse_args()

    try:
        golden_path = resolve_eval_jsonl(args.golden)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    limit = args.limit if args.limit > 0 else None
    cases = load_golden(golden_path, limit=limit)
    if not cases:
        print("empty golden set", file=sys.stderr)
        sys.exit(2)

    gen_raw = args.subquestion_generator.strip().lower()
    generator: str | None
    if gen_raw in ("profile", ""):
        generator = None
    elif gen_raw in ("rule_based", "llm"):
        generator = gen_raw
    else:
        print(f"unknown --subquestion-generator {args.subquestion_generator!r}", file=sys.stderr)
        sys.exit(2)

    top_k = args.top_k

    async def hybrid_fn(q: str) -> list[dict]:
        return await retrieve_context(q, mode="hybrid_rerank")

    async def sub_fn(q: str) -> list[dict]:
        return await query_subquestion(q, top_k=top_k, generator=generator)

    report = asyncio.run(
        run_compound_ab_compare(
            cases,
            hybrid_fn=hybrid_fn,
            sub_question_fn=sub_fn,
            top_k=top_k,
            experiment_id=COMPOUND_AB_EXPERIMENT_ID,
            subquestion_generator=generator or "profile",
        )
    )

    json_path = ROOT / args.output
    md_path = ROOT / args.markdown
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_compound_ab_markdown(report), encoding="utf-8")

    h = report["hybrid_rerank"]
    s = report["sub_question"]
    print(f"compound A/B ({report['total']} cases, top_k={top_k})")
    print(f"  {report['mode_a']}: {h['recall_at_k']:.0%} ({h['passed']}/{report['total']})")
    print(f"  {report['mode_b']}: {s['recall_at_k']:.0%} ({s['passed']}/{report['total']})")
    print(f"  recommendation: {report['recommendation']['action']}")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")


if __name__ == "__main__":
    main()
