"""对比 reports/ragas_before.json 与 ragas_after.json（M5）."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "answer_correctness",
)


def _load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: float(data[k]) for k in KEYS if data.get(k) is not None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, default=ROOT / "reports" / "ragas_before.json")
    parser.add_argument("--after", type=Path, default=ROOT / "reports" / "ragas_after.json")
    args = parser.parse_args()

    if not args.before.is_file() or not args.after.is_file():
        raise SystemExit("Missing ragas_before.json or ragas_after.json — run init_ragas_reports.py")

    b = _load(args.before)
    a = _load(args.after)
    if not b or not a:
        raise SystemExit("Metrics are null; fill JSON or run RAGAS (COLLABORATION §3.8)")

    print(f"{'metric':<22} {'before':>8} {'after':>8} {'delta':>8}")
    improved = 0
    for k in KEYS:
        if k not in b or k not in a:
            continue
        delta = a[k] - b[k]
        if delta > 0:
            improved += 1
        print(f"{k:<22} {b[k]:8.3f} {a[k]:8.3f} {delta:+8.3f}")
    print(f"\nImproved metrics: {improved}/{len(KEYS)}")
    raise SystemExit(0 if improved >= 1 else 1)


if __name__ == "__main__":
    main()
