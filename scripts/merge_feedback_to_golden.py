"""反馈候选合并进 golden 审核队列（半自动）."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=ROOT / "data" / "eval" / "golden_candidates.jsonl")
    parser.add_argument("--queue", type=Path, default=ROOT / "data" / "eval" / "golden_review_queue.jsonl")
    parser.add_argument("--auto-approve-rating", type=int, default=1, help="自动入队 rating >= N")
    args = parser.parse_args()

    if not args.candidates.is_file():
        print("No candidates file; run export_feedback first")
        return

    queue: list[dict] = []
    if args.queue.is_file():
        for line in args.queue.read_text(encoding="utf-8").splitlines():
            if line.strip():
                queue.append(json.loads(line))

    seen = {r.get("question") for r in queue}
    added = 0
    for line in args.candidates.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("rating", 0) < args.auto_approve_rating:
            continue
        if row.get("question") in seen:
            continue
        row["status"] = "pending_review"
        queue.append(row)
        seen.add(row["question"])
        added += 1

    args.queue.parent.mkdir(parents=True, exist_ok=True)
    with args.queue.open("w", encoding="utf-8") as f:
        for row in queue:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Queue {len(queue)} rows (+{added}) -> {args.queue}")


if __name__ == "__main__":
    main()
