"""M2 检索验收 — golden Top5 Recall + 多模式对比.

学习文档：docs/m2_retrieval.md §7
通过线：hybrid_rerank Recall@5 ≥ 80%（data/eval/m2_golden.jsonl）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Awaitable, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.config import ROOT  # noqa: E402
from apps.eval_paths import resolve_eval_jsonl  # noqa: E402
from apps.retrieval.langchain.hybrid_chain import retrieve_context  # noqa: E402
from apps.retrieval.llamaindex.graph_engine import query_graph  # noqa: E402
from apps.retrieval.llamaindex.router_engine import query_router  # noqa: E402
from apps.retrieval.llamaindex.subquestion_engine import query_subquestion  # noqa: E402
from apps.retrieval.llamaindex.summary_engine import query_summary  # noqa: E402
from apps.retrieval.llamaindex.tree_engine import query_tree  # noqa: E402

TOP_K = 5
PASS_RATIO = 0.8
PASS_MIN = 8

RetrievalFn = Callable[[str], Awaitable[list[dict]]]

MODES_BASE: list[tuple[str, RetrievalFn]] = [
    ("vector", lambda q: retrieve_context(q, mode="vector", rerank=False)),
    ("bm25", lambda q: retrieve_context(q, mode="bm25", rerank=False)),
    ("hybrid", lambda q: retrieve_context(q, mode="hybrid", rerank=False)),
    ("hybrid_rerank", lambda q: retrieve_context(q, mode="hybrid_rerank")),
    ("router", query_router),
]

MODES_EXTENDED: list[tuple[str, RetrievalFn]] = MODES_BASE + [
    ("graph", lambda q: query_graph(q, top_k=TOP_K)),
    ("summary", lambda q: query_summary(q, top_k=TOP_K)),
    ("tree", lambda q: query_tree(q, top_k=TOP_K)),
    ("sub_question", lambda q: query_subquestion(q, top_k=TOP_K)),
]

MODE_DOC_LABELS: dict[str, str] = {
    "vector": "vector only",
    "bm25": "bm25 only",
    "hybrid": "hybrid",
    "hybrid_rerank": "hybrid + rerank",
    "router": "llamaindex router",
    "graph": "graph engine",
    "summary": "summary engine",
    "tree": "tree engine",
    "sub_question": "sub-question engine",
}


@dataclass
class GoldenCase:
    question: str
    doc_ids: list[str]
    category: str


def pass_threshold(total: int) -> int:
    if total <= 0:
        return PASS_MIN
    return max(PASS_MIN, int(total * PASS_RATIO))


def get_modes(*, extended: bool = False, mode: str | None = None) -> list[tuple[str, RetrievalFn]]:
    catalog = MODES_EXTENDED if extended else MODES_BASE
    if mode:
        selected = [entry for entry in catalog if entry[0] == mode]
        if not selected:
            names = ", ".join(name for name, _ in catalog)
            raise ValueError(f"Unknown mode {mode!r}; choose from: {names}")
        return selected
    return catalog


def load_golden(path: Path, limit: int | None = None) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        cases.append(
            GoldenCase(
                question=row["question"],
                doc_ids=row["doc_ids"],
                category=row.get("category", ""),
            )
        )
        if limit is not None and limit > 0 and len(cases) >= limit:
            break
    return cases


def _hit(source_files: list[str], doc_ids: list[str]) -> bool:
    return any(
        doc_id in source for source in source_files for doc_id in doc_ids
    )


async def _call_with_timeout(fn: RetrievalFn, question: str, timeout_s: float | None) -> list[dict]:
    if timeout_s is None:
        return await fn(question)
    return await asyncio.wait_for(fn(question), timeout=timeout_s)


async def eval_mode(
    cases: list[GoldenCase],
    mode_name: str,
    fn: RetrievalFn,
    *,
    timeout_s: float | None = None,
) -> dict:
    passed = 0
    latencies: list[float] = []
    timeouts = 0
    for case in cases:
        t0 = time.perf_counter()
        try:
            hits = await _call_with_timeout(fn, case.question, timeout_s)
        except TimeoutError:
            timeouts += 1
            latencies.append((time.perf_counter() - t0) * 1000)
            continue
        latencies.append((time.perf_counter() - t0) * 1000)
        sources = [h["source_file"] for h in hits[:TOP_K]]
        if _hit(sources, case.doc_ids):
            passed += 1
    p95 = sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0
    return {
        "mode": mode_name,
        "recall_at_5": passed / len(cases) if cases else 0,
        "passed": passed,
        "total": len(cases),
        "p95_ms": round(p95, 1),
        "timeouts": timeouts,
    }


async def run_all(
    golden_path: Path,
    *,
    extended: bool = False,
    mode: str | None = None,
    timeout_s: float | None = None,
    parallel: bool = False,
    limit: int | None = None,
) -> list[dict]:
    cases = load_golden(golden_path, limit=limit)
    modes = get_modes(extended=extended, mode=mode)
    if parallel and len(modes) > 1:
        tasks = [
            eval_mode(cases, mode_name, fn, timeout_s=timeout_s)
            for mode_name, fn in modes
        ]
        return list(await asyncio.gather(*tasks))

    results: list[dict] = []
    for mode_name, fn in modes:
        print(f"evaluating {mode_name}...")
        results.append(await eval_mode(cases, mode_name, fn, timeout_s=timeout_s))
    return results


def print_report(results: list[dict], *, threshold: int) -> None:
    print(f"\n{'mode':<16} {'Recall@5':<10} {'pass':<8} {'P95 ms':<10} timeouts")
    print("-" * 58)
    for row in results:
        recall = f"{row['recall_at_5']:.0%}"
        to = row.get("timeouts", 0)
        print(
            f"{row['mode']:<16} {recall:<10} {row['passed']}/{row['total']:<5} "
            f"{row['p95_ms']:<10} {to}"
        )

    hybrid_rerank = next((r for r in results if r["mode"] == "hybrid_rerank"), None)
    if hybrid_rerank:
        ok = hybrid_rerank["passed"] >= threshold
        print("-" * 58)
        print(
            f"M2 验收 (hybrid_rerank): {'PASS' if ok else 'FAIL'} "
            f"(需 ≥{threshold}/{hybrid_rerank['total']})"
        )


def write_comparison_markdown(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# M2 模式对比报告 ({date.today().isoformat()})",
        "",
        "| mode | Recall@5 | passed | P95 ms | timeouts |",
        "|------|----------|--------|--------|----------|",
    ]
    for row in results:
        lines.append(
            f"| {row['mode']} | {row['recall_at_5']:.0%} | "
            f"{row['passed']}/{row['total']} | {row['p95_ms']} | {row.get('timeouts', 0)} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"对比报告: {path}")


def write_outputs(
    results: list[dict],
    json_path: Path,
    *,
    write_evolution: bool,
    comparison_md: Path | None,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"date": date.today().isoformat(), "top_k": TOP_K, "results": results}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告: {json_path}")

    if comparison_md:
        write_comparison_markdown(results, comparison_md)

    if not write_evolution:
        return

    path = ROOT / "docs" / "retrieval_modes.md"
    text = path.read_text(encoding="utf-8")
    for row in results:
        label = MODE_DOC_LABELS.get(row["mode"])
        if not label:
            continue
        recall_pct = f"{row['recall_at_5']:.0%}"
        marker = f"| {label} | | | | |"
        replacement = (
            f"| {label} | {recall_pct} | - | {row['p95_ms']} | m2_golden |"
        )
        if marker in text:
            text = text.replace(marker, replacement)
        elif f"| {label} |" not in text:
            insert_after = "| llamaindex router |"
            new_row = f"| {label} | | | | |"
            if insert_after in text and new_row not in text:
                text = text.replace(insert_after, f"{insert_after}\n{new_row}", 1)
                text = text.replace(new_row, replacement)
    path.write_text(text, encoding="utf-8")
    print("已更新 docs/retrieval_modes.md")


async def run_benchmark(
    golden_path: Path,
    *,
    extended: bool = False,
    mode: str | None = None,
    timeout_s: float | None = None,
    parallel: bool = False,
    limit: int | None = None,
) -> list[dict]:
    """Programmatic entry for auto-tuning scripts (no stdout)."""
    return await run_all(
        golden_path,
        extended=extended,
        mode=mode,
        timeout_s=timeout_s,
        parallel=parallel,
        limit=limit,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="M2 retrieval benchmark — golden Recall@5 across retrieval modes",
        epilog="示例:\n"
        "  python scripts/verify_m2.py --write-evolution\n"
        "  python scripts/verify_m2.py --extended --comparison-md reports/m2_compare.md\n"
        "文档: docs/m2_retrieval.md §7",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--golden", type=str, default="data/eval/m2_golden.jsonl")
    parser.add_argument("--output", type=str, default="reports/m2_verify.json")
    parser.add_argument("--comparison-md", type=str, default="")
    parser.add_argument("--write-evolution", action="store_true")
    parser.add_argument(
        "--extended",
        action="store_true",
        help="include graph/summary/tree/sub_question (8 modes total)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="",
        help="evaluate a single mode (must be in base or extended set)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0,
        help="per-query timeout in seconds (0 = no limit)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="evaluate modes concurrently (not per-case parallel)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="evaluate first N questions only (0=all; use tiny golden for smoke)",
    )
    args = parser.parse_args()

    try:
        golden_path = resolve_eval_jsonl(args.golden)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    if golden_path.name.endswith(".example"):
        print(f"使用模板: {golden_path}")

    mode = args.mode.strip() or None
    timeout_s = args.timeout if args.timeout > 0 else None
    limit = args.limit if args.limit > 0 else None
    extended_modes = {name for name, _ in MODES_EXTENDED} - {name for name, _ in MODES_BASE}
    use_extended = args.extended or (mode in extended_modes)
    try:
        results = asyncio.run(
            run_benchmark(
                golden_path,
                extended=use_extended,
                mode=mode,
                timeout_s=timeout_s,
                parallel=args.parallel,
                limit=limit,
            )
        )
    except ValueError as exc:
        print(exc, file=sys.stderr)
        sys.exit(2)

    cases = load_golden(golden_path, limit=limit)
    threshold = pass_threshold(len(cases))
    print_report(results, threshold=threshold)
    comparison = Path(args.comparison_md) if args.comparison_md else None
    if args.extended and comparison is None:
        comparison = ROOT / "reports" / "m2_mode_comparison.md"
    write_outputs(
        results,
        ROOT / args.output,
        write_evolution=args.write_evolution,
        comparison_md=comparison,
    )

    hybrid = next((r for r in results if r["mode"] == "hybrid_rerank"), None)
    if hybrid and hybrid["passed"] < threshold:
        sys.exit(1)


if __name__ == "__main__":
    main()
