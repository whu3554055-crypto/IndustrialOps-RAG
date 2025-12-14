"""初始化 M5 RAGAS 前后对比 JSON（M6 实装 RAGAS 前可手写/后填）.

学习：docs/m5_finetune.md §7
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "answer_correctness",
)


def _template(phase: str) -> dict:
    return {
        "phase": phase,
        "milestone": "M5",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "Replace null with values from run_ragas.py or manual eval; see COLLABORATION §3.8",
        **{k: None for k in METRICS},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--fill-example", action="store_true", help="Write demo numbers for verify_m5 --check-ragas dry-run")
    args = parser.parse_args()

    out = args.output or (ROOT / "reports" / f"ragas_{args.phase}.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    body = _template(args.phase)
    if args.fill_example:
        demo = {
            "faithfulness": 0.72,
            "answer_relevancy": 0.68,
            "context_precision": 0.75,
            "context_recall": 0.70,
            "answer_correctness": 0.71,
        }
        if args.phase == "after":
            demo = {k: round(v + 0.05, 2) for k, v in demo.items()}
        body.update(demo)
        body["note"] = "EXAMPLE ONLY — replace after real RAGAS"

    out.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
