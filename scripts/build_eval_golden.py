"""合并 M7 对齐题 + 通用 RAGAS 模板 → golden.jsonl.example."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M7 = ROOT / "data" / "eval" / "golden_m7.jsonl.example"
OUT = ROOT / "data" / "eval" / "golden.jsonl.example"


def main() -> None:
    rows: list[dict] = []
    for line in M7.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not row.get("ground_truth"):
            continue
        rows.append(
            {
                "question": row["question"],
                "ground_truth": row["ground_truth"],
                "doc_ids": row.get("doc_ids", []),
                "category": row.get("category", "m7"),
            }
        )
    if len(rows) < 10:
        raise SystemExit("golden_m7 missing ground_truth rows")

    with OUT.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    main()
