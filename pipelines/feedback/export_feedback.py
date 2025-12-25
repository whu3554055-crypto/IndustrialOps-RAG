"""导出反馈事件，并生成待审核 golden 候选.

学习文档：docs/m7_demo.md §4.3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from apps.feedback import load_feedback_events  # noqa: E402


def export_events(out: Path, *, limit: int | None) -> int:
    rows = load_feedback_events(limit=limit)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Exported {len(rows)} event(s) -> {out}")
    return len(rows)


def export_golden_candidates(out: Path, *, min_rating: int) -> int:
    rows = load_feedback_events()
    candidates: list[dict] = []
    for row in rows:
        rating = int(row.get("rating", 0))
        if rating > min_rating:
            continue
        q = row.get("query") or ""
        if not q:
            continue
        candidates.append(
            {
                "question": q,
                "ground_truth": "",
                "doc_ids": [],
                "category": "from_feedback",
                "source_event_id": row.get("event_id"),
                "rating": rating,
                "comment": row.get("comment"),
            }
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"Wrote {len(candidates)} golden candidate(s) -> {out}")
    return len(candidates)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export M7 feedback for review")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "feedback_export.jsonl")
    parser.add_argument("--golden-candidates", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--min-rating",
        type=int,
        default=-1,
        help="Export questions with rating <= this (default -1: thumbs-down only)",
    )
    args = parser.parse_args()
    export_events(args.output, limit=args.limit)
    if args.golden_candidates:
        export_golden_candidates(args.golden_candidates, min_rating=args.min_rating)


if __name__ == "__main__":
    main()
