"""M1 验收 — 10 题向量 + BM25 Top5 命中检查.

学习文档：docs/m1_ingest.md §7
通过：Vector 与 BM25 各自 ≥8/10；不需 Gateway/vLLM。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opensearchpy import OpenSearch  # noqa: E402
from pymilvus import MilvusClient  # noqa: E402

from apps.config import ROOT, get_settings  # noqa: E402
from pipelines.ingest.indexer import Embedder, resolve_embedding_model_path  # noqa: E402

TOP_K = 5
PASS_THRESHOLD = 8  # 10 题中至少 8 题命中

# 与 data/eval/golden_m7.jsonl.example 中 m1_aligned=true 的 10 题一致；ingest 后 source_file 为 samples/<file>
M1_CASES: list[tuple[str, str]] = [
    ("P-101 出口压力正常范围是多少？", "pump_p101_manual.md"),
    ("P-101 故障码 E01 怎么处理？", "pump_p101_manual.md"),
    ("反应釜 R-201 什么情况下要按 ESD 紧急停车？", "reactor_r201_sop.md"),
    ("F201-02 搅拌电流高可能是什么原因？", "reactor_r201_sop.md"),
    ("空压站 ALM-101 排气温度过高怎么处理？", "compressor_sa01_fault_codes.md"),
    ("SA-01 螺杆空压机排气量是多少？", "compressor_sa01_fault_codes.md"),
    ("E-301 管壳式换热器设计换热面积是多少？", "heat_exchanger_e301_manual.md"),
    ("E-301 检漏发现微漏点如何处理？", "heat_exchanger_e301_manual.md"),
    ("CV-110 皮带机启动前必须确认哪些联锁？", "conveyor_cv110_sop.md"),
    ("CV-110 跑偏报警 B201 怎么处理？", "conveyor_cv110_sop.md"),
]


@dataclass
class CaseResult:
    question: str
    expected: str
    vector_hit: bool
    bm25_hit: bool
    vector_top_source: str
    bm25_top_source: str


def _hit(source_files: list[str], expected: str) -> bool:
    return any(expected in path for path in source_files)


def search_vector(
    client: MilvusClient,
    collection: str,
    embedder: Embedder,
    query: str,
    top_k: int,
) -> list[str]:
    vec = embedder.encode([query], batch_size=1)[0]
    hits = client.search(
        collection_name=collection,
        data=[vec],
        limit=top_k,
        output_fields=["source_file"],
    )[0]
    return [hit["entity"]["source_file"] for hit in hits]


def search_bm25(client: OpenSearch, index: str, query: str, top_k: int) -> list[str]:
    resp = client.search(
        index=index,
        body={
            "query": {"match": {"text": query}},
            "size": top_k,
            "_source": ["source_file"],
        },
    )
    return [hit["_source"]["source_file"] for hit in resp["hits"]["hits"]]


def run_cases() -> list[CaseResult]:
    s = get_settings()
    embedder = Embedder(resolve_embedding_model_path(), s.embedding_device)
    milvus = MilvusClient(uri=f"http://{s.milvus_host}:{s.milvus_port}")
    opensearch = OpenSearch(
        hosts=[{"host": s.opensearch_host, "port": s.opensearch_port}],
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False,
    )

    results: list[CaseResult] = []
    for question, expected in M1_CASES:
        vector_files = search_vector(milvus, s.milvus_collection, embedder, question, TOP_K)
        bm25_files = search_bm25(opensearch, s.opensearch_index, question, TOP_K)
        results.append(
            CaseResult(
                question=question,
                expected=expected,
                vector_hit=_hit(vector_files, expected),
                bm25_hit=_hit(bm25_files, expected),
                vector_top_source=vector_files[0] if vector_files else "",
                bm25_top_source=bm25_files[0] if bm25_files else "",
            )
        )
    return results


def print_report(results: list[CaseResult]) -> None:
    vector_pass = sum(1 for r in results if r.vector_hit)
    bm25_pass = sum(1 for r in results if r.bm25_hit)
    either_pass = sum(1 for r in results if r.vector_hit or r.bm25_hit)

    print(f"\n{'#':<3} {'Vec':<4} {'BM25':<5} 期望文档 / 问题")
    print("-" * 72)
    for i, r in enumerate(results, 1):
        v = "PASS" if r.vector_hit else "FAIL"
        b = "PASS" if r.bm25_hit else "FAIL"
        print(f"{i:<3} {v:<4} {b:<5} {r.expected}")
        print(f"    Q: {r.question}")
        if not r.vector_hit:
            print(f"    vector top1: {r.vector_top_source or '(empty)'}")
        if not r.bm25_hit:
            print(f"    bm25 top1:   {r.bm25_top_source or '(empty)'}")

    print("-" * 72)
    print(f"Vector Top{TOP_K}: {vector_pass}/{len(results)}")
    print(f"BM25 Top{TOP_K}:  {bm25_pass}/{len(results)}")
    print(f"任一路命中:     {either_pass}/{len(results)}")
    m1_ok = vector_pass >= PASS_THRESHOLD and bm25_pass >= PASS_THRESHOLD
    print(f"M1 验收: {'PASS' if m1_ok else 'FAIL'} (各路需 ≥{PASS_THRESHOLD}/{len(results)})")


def write_json(results: list[CaseResult], path: Path) -> None:
    vector_pass = sum(1 for r in results if r.vector_hit)
    bm25_pass = sum(1 for r in results if r.bm25_hit)
    payload = {
        "date": date.today().isoformat(),
        "top_k": TOP_K,
        "vector_pass": vector_pass,
        "bm25_pass": bm25_pass,
        "total": len(results),
        "m1_pass": vector_pass >= PASS_THRESHOLD and bm25_pass >= PASS_THRESHOLD,
        "cases": [asdict(r) for r in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告已写入 {path}")


def append_evolution(results: list[CaseResult]) -> None:
    vector_pass = sum(1 for r in results if r.vector_hit)
    bm25_pass = sum(1 for r in results if r.bm25_hit)
    m1_ok = vector_pass >= PASS_THRESHOLD and bm25_pass >= PASS_THRESHOLD
    note = f"Vec {vector_pass}/10 BM25 {bm25_pass}/10 Top{TOP_K}"
    row = f"| {date.today().isoformat()} | M1 ingest+索引 | {vector_pass}/10 | - | {note} {'PASS' if m1_ok else 'FAIL'} |"

    path = ROOT / "docs" / "evolution.md"
    text = path.read_text(encoding="utf-8")
    marker = "<!-- 每完成一里程碑追加一行 -->"
    if marker in text:
        text = text.replace(marker, f"{row}\n\n{marker}")
    else:
        text = text.rstrip() + "\n" + row + "\n"
    path.write_text(text, encoding="utf-8")
    print(f"已追加 evolution.md: {note}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="M1 retrieval acceptance — vector + BM25 Top5 × 10 questions",
        epilog="示例: python scripts/verify_m1.py --write-report --write-evolution\n"
        "文档: docs/m1_ingest.md §7",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/m1_verify.json",
        help="JSON 报告路径",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="写入 JSON 报告（默认路径见 --output）",
    )
    parser.add_argument(
        "--write-evolution",
        action="store_true",
        help="追加一行到 docs/evolution.md",
    )
    args = parser.parse_args()

    results = run_cases()
    print_report(results)
    out = ROOT / args.output
    if args.write_report or args.write_evolution:
        write_json(results, out)
    elif not out.is_file():
        write_json(results, out)
    if args.write_evolution:
        append_evolution(results)
    if args.write_report:
        print(f"Report: {out}")

    vector_pass = sum(1 for r in results if r.vector_hit)
    bm25_pass = sum(1 for r in results if r.bm25_hit)
    if vector_pass < PASS_THRESHOLD or bm25_pass < PASS_THRESHOLD:
        sys.exit(1)


if __name__ == "__main__":
    main()
