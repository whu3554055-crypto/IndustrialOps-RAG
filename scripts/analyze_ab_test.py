"""分析 A/B 实验结果 — 输出 Markdown + JSON.

用法:
  python scripts/analyze_ab_test.py --experiment exp_demo --dry-run
  python scripts/analyze_ab_test.py --experiment exp_demo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.ab_test.analyze import build_experiment_report, render_markdown  # noqa: E402
from apps.ab_test.assignment_log import load_assignments  # noqa: E402
from apps.ab_test.config import load_ab_test_config  # noqa: E402
from apps.feedback import load_feedback_events  # noqa: E402
from apps.retrieval_log import load_all_logs  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "ab_test"


def _load_dry_run(experiment_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    assign_path = FIXTURE_DIR / "assignments.jsonl"
    fb_path = FIXTURE_DIR / "feedback.jsonl"
    log_path = FIXTURE_DIR / "retrieval_logs.jsonl"
    assignments = [
        json.loads(line)
        for line in assign_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    feedback = [
        json.loads(line) for line in fb_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    logs = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assignments = [a for a in assignments if a.get("experiment_id") == experiment_id]
    return assignments, feedback, logs


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze A/B test experiment")
    parser.add_argument("--experiment", required=True, help="experiment_id")
    parser.add_argument("--dry-run", action="store_true", help="use tests/fixtures/ab_test/*.jsonl")
    parser.add_argument(
        "--min-sample-size",
        type=int,
        default=None,
        help="override profile ab_test.min_sample_size",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "reports",
        help="report output directory",
    )
    args = parser.parse_args()

    if args.dry_run:
        assignments, feedback, logs = _load_dry_run(args.experiment)
    else:
        assignments = load_assignments(experiment_id=args.experiment)
        feedback = load_feedback_events()
        logs = load_all_logs(experiment_id=args.experiment)

    cfg = load_ab_test_config()
    min_n = args.min_sample_size
    if min_n is None:
        min_n = cfg.min_sample_size if cfg else 200

    report = build_experiment_report(
        experiment_id=args.experiment,
        assignments=assignments,
        feedback=feedback,
        retrieval_logs=logs,
        min_sample_size=min_n,
    )

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"ab_test_{args.experiment}.json"
    md_path = out_dir / f"ab_test_{args.experiment}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {md_path}")
    print(f"Wrote {json_path}")
    print(f"recommendation={report['recommendation']}")
    if not report["sample_sufficient"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
