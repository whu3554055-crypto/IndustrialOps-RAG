"""基于网格搜索的自动参数调优.

用法：
  python scripts/auto_tune_params.py --param rrf_k --values 50,60,70 --limit 8
  python scripts/auto_tune_params.py --all --dry-run
  python scripts/auto_tune_params.py --golden data/eval/m2_golden_tiny.jsonl

依赖：Milvus + OpenSearch + M1 ingest（``--dry-run`` 除外）
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.config import ROOT, get_settings  # noqa: E402
from apps.eval.tune_common import (  # noqa: E402
    DEFAULT_PROFILE,
    SEARCH_SPACE,
    TINY_GOLDEN,
    limited_golden_file,
    pick_best,
    profile_override,
    resolve_param,
    save_tune_report,
    score_result,
    split_holdout,
    load_golden_rows,
    write_golden_rows,
)
from apps.eval_paths import resolve_eval_jsonl  # noqa: E402
from scripts.verify_m2 import run_benchmark  # noqa: E402

RESULTS_PATH = ROOT / "reports" / "auto_tune_results.json"

# 兼容旧测试 import
__all__ = ["PROFILES_DIR", "profile_override", "score_result", "SEARCH_SPACE"]
from apps.config import PROFILES_DIR  # noqa: E402


async def evaluate_once(
    golden_path: Path,
    updates: dict[str, int],
    *,
    profile_name: str,
    eval_mode: str = "hybrid_rerank",
    limit: int | None = None,
) -> dict:
    with limited_golden_file(golden_path, limit) as eval_path:
        with profile_override(profile_name, updates):
            results = await run_benchmark(eval_path, mode=eval_mode)
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
    limit: int | None = None,
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
                limit=limit,
            )
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid-search retrieval/agent profile params")
    parser.add_argument("--param", type=str, default="", help="e.g. rrf_k or retrieval.rrf_k")
    parser.add_argument("--values", type=str, default="", help="comma-separated ints")
    parser.add_argument("--all", action="store_true", help="search each param independently")
    parser.add_argument("--profile", type=str, default=DEFAULT_PROFILE)
    parser.add_argument(
        "--golden",
        type=str,
        default=str(TINY_GOLDEN.relative_to(ROOT)),
        help="default m2_golden_tiny.jsonl (10 core questions)",
    )
    parser.add_argument("--mode", type=str, default="hybrid_rerank")
    parser.add_argument("--limit", type=int, default=0, help="cap questions per trial (0=all)")
    parser.add_argument("--holdout-ratio", type=float, default=0.0)
    parser.add_argument("--output", type=str, default=str(RESULTS_PATH.relative_to(ROOT)))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    profile_name = args.profile or get_settings().ior_profile
    golden_path = resolve_eval_jsonl(args.golden)
    output_path = ROOT / args.output
    limit = args.limit if args.limit > 0 else None

    if args.holdout_ratio > 0 and not args.dry_run:
        tune_rows, holdout_rows = split_holdout(
            load_golden_rows(golden_path),
            holdout_ratio=args.holdout_ratio,
        )
        tune_tmp = ROOT / "reports" / "_grid_tune_tmp.jsonl"
        write_golden_rows(tune_tmp, tune_rows)
        golden_path = tune_tmp
        print(f"tune={len(tune_rows)} holdout={len(holdout_rows)}")

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
                    limit=limit,
                )
            )
            best = pick_best(rows)
            all_results.append({"param": param_path, "trials": rows, "best": best})
            if best:
                print(
                    f"best {param_path}: value={list(best['params'].values())[0]} "
                    f"score={best['score']} recall={best['recall']:.0%}"
                )
        save_tune_report({"results": all_results}, output_path)
        print(f"results -> {output_path}")
        return

    param_path = resolve_param(args.param.strip()) if args.param else ""
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
            limit=limit,
        )
    )
    best = pick_best(results)
    save_tune_report({"results": results, "best": best}, output_path)
    if best:
        val = list(best["params"].values())[0]
        print(f"\nBest {param_path}={val} score={best['score']} recall={best['recall']:.0%}")
    print(f"results -> {output_path}")


if __name__ == "__main__":
    main()
