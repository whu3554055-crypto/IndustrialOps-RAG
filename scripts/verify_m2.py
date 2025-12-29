"""M2 检索验收 — golden Top5 Recall + 多模式对比.

学习文档：docs/m2_retrieval.md §7
通过线：hybrid_rerank Recall@5 ≥ 8/10（data/eval/m2_golden.jsonl）
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.config import ROOT  # noqa: E402
from apps.eval_paths import resolve_eval_jsonl  # noqa: E402
from apps.retrieval.langchain.hybrid_chain import retrieve_context  # noqa: E402
from apps.retrieval.llamaindex.router_engine import query_router  # noqa: E402

TOP_K = 5
PASS_THRESHOLD = 8
MODES = [
    ("vector", lambda q: retrieve_context(q, mode="vector", rerank=False)),
    ("bm25", lambda q: retrieve_context(q, mode="bm25", rerank=False)),
    ("hybrid", lambda q: retrieve_context(q, mode="hybrid", rerank=False)),
    ("hybrid_rerank", lambda q: retrieve_context(q, mode="hybrid_rerank")),
    ("router", query_router),
]


@dataclass
class GoldenCase:
    question: str
    doc_ids: list[str]
    category: str


def load_golden(path: Path) -> list[GoldenCase]:
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
    return cases


def _hit(source_files: list[str], doc_ids: list[str]) -> bool:
    return any(
        doc_id in source for source in source_files for doc_id in doc_ids
    )


async def eval_mode(cases: list[GoldenCase], mode_name: str, fn) -> dict:
    passed = 0
    latencies: list[float] = []
    for case in cases:
        t0 = time.perf_counter()
        hits = await fn(case.question)
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
    }


async def run_all(golden_path: Path) -> list[dict]:
    cases = load_golden(golden_path)
    results: list[dict] = []
    for mode_name, fn in MODES:
        print(f"evaluating {mode_name}...")
        results.append(await eval_mode(cases, mode_name, fn))
    return results


def print_report(results: list[dict]) -> None:
    print(f"\n{'mode':<16} {'Recall@5':<10} {'pass':<8} {'P95 ms'}")
    print("-" * 48)
    for row in results:
        recall = f"{row['recall_at_5']:.0%}"
        print(f"{row['mode']:<16} {recall:<10} {row['passed']}/{row['total']:<5} {row['p95_ms']}")

    hybrid_rerank = next(r for r in results if r["mode"] == "hybrid_rerank")
    ok = hybrid_rerank["passed"] >= PASS_THRESHOLD
    print("-" * 48)
    print(f"M2 验收 (hybrid_rerank): {'PASS' if ok else 'FAIL'} (需 ≥{PASS_THRESHOLD}/{hybrid_rerank['total']})")


def write_outputs(results: list[dict], json_path: Path, write_evolution: bool) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"date": date.today().isoformat(), "top_k": TOP_K, "results": results}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告: {json_path}")

    if not write_evolution:
        return
    hybrid = next(r for r in results if r["mode"] == "hybrid_rerank")
    recall_pct = f"{hybrid['recall_at_5']:.0%}"
    row = (
        f"| {date.today().isoformat()} | M2 hybrid+rerank | {recall_pct} | - | "
        f"P95 {hybrid['p95_ms']}ms |"
    )
    path = ROOT / "docs" / "retrieval_modes.md"
    text = path.read_text(encoding="utf-8")
    marker = "| hybrid + rerank | | | | |"
    if marker in text:
        text = text.replace(
            marker,
            f"| hybrid + rerank | {recall_pct} | - | {hybrid['p95_ms']} | m2_golden |",
        )
        path.write_text(text, encoding="utf-8")
        print("已更新 docs/retrieval_modes.md")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="M2 retrieval benchmark — 5 modes × golden Recall@5",
        epilog="示例: python scripts/verify_m2.py --write-evolution\n"
        "文档: docs/m2_retrieval.md §7",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--golden", type=str, default="data/eval/m2_golden.jsonl")
    parser.add_argument("--output", type=str, default="reports/m2_verify.json")
    parser.add_argument("--write-evolution", action="store_true")
    args = parser.parse_args()

    try:
        golden_path = resolve_eval_jsonl(args.golden)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    if golden_path.name.endswith(".example"):
        print(f"使用模板: {golden_path}")
    results = asyncio.run(run_all(golden_path))
    print_report(results)
    write_outputs(results, ROOT / args.output, args.write_evolution)

    hybrid = next(r for r in results if r["mode"] == "hybrid_rerank")
    if hybrid["passed"] < PASS_THRESHOLD:
        sys.exit(1)


if __name__ == "__main__":
    main()
