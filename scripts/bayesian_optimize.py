"""多参数联合调优 — 贝叶斯优化（可选）或随机搜索 fallback.

本地性能有限：默认小 ``--n-calls`` + ``--limit`` / ``m2_golden_tiny.jsonl``；``--dry-run`` 不连 Milvus。

用法：
  python scripts/bayesian_optimize.py --dry-run --n-calls 3 --limit 8
  python scripts/bayesian_optimize.py --golden data/eval/m2_golden_tiny.jsonl --n-calls 5
  pip install -e \".[tune]\"   # 可选 scikit-optimize
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.config import ROOT, get_settings  # noqa: E402
from apps.eval.tune_common import (  # noqa: E402
    BAYESIAN_PARAMS,
    DEFAULT_PROFILE,
    TINY_GOLDEN,
    limited_golden_file,
    objective_score,
    params_from_vector,
    pick_best,
    profile_override,
    save_tune_report,
    score_result,
    split_holdout,
)
from apps.eval_paths import resolve_eval_jsonl  # noqa: E402
from scripts.verify_m2 import run_benchmark  # noqa: E402

RESULTS_PATH = ROOT / "reports" / "bayesian_tune_results.json"
PARAM_NAMES = [name for name, _, _ in BAYESIAN_PARAMS]


async def evaluate_params(
    golden_path: Path,
    param_values: dict[str, int],
    *,
    profile_name: str,
    eval_mode: str,
) -> dict:
    with profile_override(profile_name, param_values):
        results = await run_benchmark(golden_path, mode=eval_mode)
    row = results[0]
    recall = float(row["recall_at_5"])
    p95 = float(row["p95_ms"])
    return {
        "params": param_values,
        "mode": eval_mode,
        "recall": recall,
        "p95_ms": p95,
        "score": round(score_result(recall, p95), 4),
        "objective": round(objective_score(recall, p95), 4),
        "passed": row["passed"],
        "total": row["total"],
    }


def _sample_params(rng: random.Random) -> dict[str, int]:
    return {
        name: rng.randint(low, high)
        for name, low, high in BAYESIAN_PARAMS
    }


def _plan_trials(n_calls: int, random_state: int) -> list[dict[str, int]]:
    rng = random.Random(random_state)
    return [_sample_params(rng) for _ in range(n_calls)]


def run_gp_minimize(
    objective_fn,
    n_calls: int,
    random_state: int,
) -> tuple[list[dict], dict | None]:
    from skopt import gp_minimize  # type: ignore[import-untyped]
    from skopt.space import Integer  # type: ignore[import-untyped]

    space = [Integer(low, high, name=name) for name, low, high in BAYESIAN_PARAMS]
    trials: list[dict] = []

    def wrapped(values: list[int]) -> float:
        params = params_from_vector(PARAM_NAMES, [int(v) for v in values])
        result = objective_fn(params)
        trials.append(result)
        return float(result["objective"])

    gp_minimize(
        wrapped,
        space,
        n_calls=n_calls,
        random_state=random_state,
        verbose=False,
    )
    return trials, pick_best(trials)


def run_random_search(
    objective_fn,
    n_calls: int,
    random_state: int,
) -> tuple[list[dict], dict | None]:
    trials: list[dict] = []
    for params in _plan_trials(n_calls, random_state):
        trials.append(objective_fn(params))
    return trials, pick_best(trials)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bayesian / random joint param tuning")
    parser.add_argument("--profile", type=str, default=DEFAULT_PROFILE)
    parser.add_argument(
        "--golden",
        type=str,
        default=str(TINY_GOLDEN.relative_to(ROOT)),
        help="default tiny 10-question set for local smoke",
    )
    parser.add_argument("--mode", type=str, default="hybrid_rerank")
    parser.add_argument("--n-calls", type=int, default=5, help="optimizer iterations (keep low locally)")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--limit", type=int, default=0, help="cap questions per eval (0=all in golden file)")
    parser.add_argument(
        "--holdout-ratio",
        type=float,
        default=0.0,
        help="0=disabled; e.g. 0.2 tune on 80%%, validate best on holdout",
    )
    parser.add_argument("--output", type=str, default=str(RESULTS_PATH.relative_to(ROOT)))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--optimizer",
        choices=("auto", "bayesian", "random"),
        default="auto",
        help="auto=bayesian if scikit-optimize installed else random",
    )
    args = parser.parse_args()

    profile_name = args.profile or get_settings().ior_profile
    golden_path = resolve_eval_jsonl(args.golden)
    output_path = ROOT / args.output
    limit = args.limit if args.limit > 0 else None

    holdout_rows: list[dict] = []
    if args.holdout_ratio > 0 and not args.dry_run:
        from apps.eval.tune_common import load_golden_rows, write_golden_rows

        tune_rows, holdout_rows = split_holdout(
            load_golden_rows(golden_path),
            holdout_ratio=args.holdout_ratio,
            seed=args.random_state,
        )
        tune_tmp = ROOT / "reports" / "_tune_golden_tmp.jsonl"
        write_golden_rows(tune_tmp, tune_rows)
        golden_path = tune_tmp
        print(f"tune={len(tune_rows)} holdout={len(holdout_rows)} (ratio={args.holdout_ratio})")

    planned = _plan_trials(args.n_calls, args.random_state)
    if args.dry_run:
        payload = {
            "dry_run": True,
            "optimizer": args.optimizer,
            "n_calls": args.n_calls,
            "golden": str(golden_path),
            "limit": limit,
            "planned_params": planned,
        }
        save_tune_report(payload, output_path)
        print(f"dry-run: {args.n_calls} trials planned -> {output_path}")
        return

    def objective_fn(params: dict[str, int]) -> dict:
        with limited_golden_file(golden_path, limit) as eval_path:
            return asyncio.run(
                evaluate_params(
                    eval_path,
                    params,
                    profile_name=profile_name,
                    eval_mode=args.mode,
                )
            )

    use_bayesian = args.optimizer == "bayesian" or (
        args.optimizer == "auto" and _has_skopt()
    )
    if use_bayesian and _has_skopt():
        print(f"optimizer=bayesian n_calls={args.n_calls}")
        trials, best = run_gp_minimize(objective_fn, args.n_calls, args.random_state)
        optimizer_used = "bayesian"
    else:
        if args.optimizer == "bayesian":
            print("scikit-optimize not installed; falling back to random search", file=sys.stderr)
        print(f"optimizer=random n_calls={args.n_calls}")
        trials, best = run_random_search(objective_fn, args.n_calls, args.random_state)
        optimizer_used = "random"

    holdout_eval = None
    if best and holdout_rows:
        holdout_tmp = ROOT / "reports" / "_holdout_golden_tmp.jsonl"
        from apps.eval.tune_common import write_golden_rows

        write_golden_rows(holdout_tmp, holdout_rows)
        holdout_eval = asyncio.run(
            evaluate_params(
                holdout_tmp,
                best["params"],
                profile_name=profile_name,
                eval_mode=args.mode,
            )
        )
        holdout_tmp.unlink(missing_ok=True)

    payload = {
        "optimizer": optimizer_used,
        "n_calls": args.n_calls,
        "golden": str(golden_path),
        "limit": limit,
        "holdout_ratio": args.holdout_ratio,
        "trials": trials,
        "best": best,
        "holdout_eval": holdout_eval,
    }
    save_tune_report(payload, output_path)
    if best:
        print(f"best score={best['score']} recall={best['recall']:.0%} params={best['params']}")
    print(f"results -> {output_path}")


def _has_skopt() -> bool:
    try:
        import skopt  # noqa: F401

        return True
    except ImportError:
        return False


if __name__ == "__main__":
    main()
