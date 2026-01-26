"""基于网格搜索的自动参数调优.

用法：
  python scripts/auto_tune_params.py --param rrf_k --values 30,40,50,60,70
  python scripts/auto_tune_params.py --all --dry-run

依赖：Milvus + OpenSearch + M1 ingest（与 verify_m2 相同）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.config import PROFILES_DIR, ROOT, get_settings  # noqa: E402
from apps.eval_paths import resolve_eval_jsonl  # noqa: E402
from scripts.verify_m2 import run_benchmark  # noqa: E402

DEFAULT_PROFILE = "dev-single-node"
RESULTS_PATH = ROOT / "reports" / "auto_tune_results.json"

SEARCH_SPACE: dict[str, list[int]] = {
    "retrieval.vector_top_k": [10, 20, 30, 40, 50],
    "retrieval.bm25_top_k": [10, 20, 30, 40, 50],
    "retrieval.rrf_k": [30, 40, 50, 60, 70, 80, 90, 100],
    "retrieval.rerank_top_n": [3, 5, 7, 10],
    "agent.max_history_turns": [1, 2, 3, 4, 5],
}

PARAM_ALIASES: dict[str, str] = {
    "vector_top_k": "retrieval.vector_top_k",
    "bm25_top_k": "retrieval.bm25_top_k",
    "rrf_k": "retrieval.rrf_k",
    "rerank_top_n": "retrieval.rerank_top_n",
    "context_top_k": "retrieval.rerank_top_n",
    "max_history_turns": "agent.max_history_turns",
}


def _resolve_param(name: str) -> str:
    return PARAM_ALIASES.get(name, name)


def _set_nested(data: dict, dotted: str, value: int) -> None:
    parts = dotted.split(".")
    node = data
    for key in parts[:-1]:
        node = node.setdefault(key, {})
    node[parts[-1]] = value


def _get_nested(data: dict, dotted: str) -> int | None:
    node: object = data
    for key in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node if isinstance(node, int) else None


def score_result(recall: float, p95_ms: float) -> float:
    latency_term = 10000 / p95_ms if p95_ms > 0 else 0
    return recall * 0.7 + latency_term * 0.3


@contextmanager
def profile_override(profile_name: str, updates: dict[str, int]) -> Iterator[Path]:
    path = PROFILES_DIR / f"{profile_name}.yaml"
    backup = path.read_text(encoding="utf-8")
    data = yaml.safe_load(backup) or {}
    for param_path, value in updates.items():
        _set_nested(data, param_path, value)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    try:
        yield path
    finally:
        path.write_text(backup, encoding="utf-8")


async def evaluate_once(
    golden_path: Path,
    updates: dict[str, int],
    *,
    profile_name: str,
    eval_mode: str = "hybrid_rerank",
) -> dict:
    with profile_override(profile_name, updates):
        results = await run_benchmark(golden_path, mode=eval_mode)
    row = results[0]
    recall = float(row["recall_at_5"])
    p95 = float(row["p95_ms"])
    return {
        "params": updates,
        "mode": eval_mode,
        "recall": recall,
        "p95_ms": p95,
        "score": round(score_result(recall, p95), 4),
        "passed": row["passed"],
        "total": row["total"],
    }


async def grid_search_param(
    param_path: str,
    values: list[int],
    golden_path: Path,
    *,
    profile_name: str,
    eval_mode: str = "hybrid_rerank",
    dry_run: bool = False,
) -> list[dict]:
    results: list[dict] = []
    for value in values:
        updates = {param_path: value}
        print(f"testing {param_path}={value}...")
        if dry_run:
            results.append({"params": updates, "dry_run": True})
            continue
        results.append(
            await evaluate_once(
                golden_path,
                updates,
                profile_name=profile_name,
                eval_mode=eval_mode,
            )
        )
    return results


def save_results(results: list[dict], path: Path = RESULTS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"date": date.today().isoformat(), "results": results}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"results -> {path}")


def pick_best(results: list[dict]) -> dict | None:
    scored = [row for row in results if "score" in row]
    if not scored:
        return None
    return max(scored, key=lambda row: row["score"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid-search retrieval/agent profile params")
    parser.add_argument("--param", type=str, default="", help="e.g. rrf_k or retrieval.rrf_k")
    parser.add_argument("--values", type=str, default="", help="comma-separated ints")
    parser.add_argument("--all", action="store_true", help="search each param independently")
    parser.add_argument("--profile", type=str, default=DEFAULT_PROFILE)
    parser.add_argument("--golden", type=str, default="data/eval/m2_golden.jsonl")
    parser.add_argument("--mode", type=str, default="hybrid_rerank")
    parser.add_argument("--output", type=str, default=str(RESULTS_PATH.relative_to(ROOT)))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    profile_name = args.profile or get_settings().ior_profile
    golden_path = resolve_eval_jsonl(args.golden)
    output_path = ROOT / args.output

    if args.all:
        all_results: list[dict] = []
        for param_path, values in SEARCH_SPACE.items():
            rows = asyncio.run(
                grid_search_param(
                    param_path,
                    values,
                    golden_path,
                    profile_name=profile_name,
                    eval_mode=args.mode,
                    dry_run=args.dry_run,
                )
            )
            best = pick_best(rows)
            all_results.append({"param": param_path, "trials": rows, "best": best})
            if best:
                print(
                    f"best {param_path}: value={list(best['params'].values())[0]} "
                    f"score={best['score']} recall={best['recall']:.0%}"
                )
        save_results(all_results, output_path)
        return

    param_path = _resolve_param(args.param.strip()) if args.param else ""
    if not param_path:
        parser.error("specify --param or --all")

    if args.values:
        values = [int(v.strip()) for v in args.values.split(",") if v.strip()]
    else:
        values = SEARCH_SPACE.get(param_path, [])
    if not values:
        parser.error(f"no default search space for {param_path}; pass --values")

    results = asyncio.run(
        grid_search_param(
            param_path,
            values,
            golden_path,
            profile_name=profile_name,
            eval_mode=args.mode,
            dry_run=args.dry_run,
        )
    )
    best = pick_best(results)
    save_results(results, output_path)
    if best:
        val = list(best["params"].values())[0]
        print(f"\nBest {param_path}={val} score={best['score']} recall={best['recall']:.0%}")


if __name__ == "__main__":
    main()
