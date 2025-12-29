"""大批量 ingest — 按目录分批调用 run_ingest_job（scaling-data 对齐）.

示例: python scripts/batch_ingest.py --input data/raw --shard-index 0 --shard-count 4
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines.ingest.documents import load_documents  # noqa: E402
from pipelines.ingest.run_ingest import run_ingest_job  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Sharded batch ingest")
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--docs-per-shard", type=int, default=1000)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--no-recreate", action="store_true")
    args = parser.parse_args()

    input_dir = args.input if args.input.is_absolute() else ROOT / args.input
    docs = load_documents(input_dir)
    if not docs:
        raise SystemExit(f"No docs under {input_dir}")

    shard_size = max(1, (len(docs) + args.shard_count - 1) // args.shard_count)
    start = args.shard_index * shard_size
    end = min(start + shard_size, len(docs))
    shard_docs = docs[start:end]
    if not shard_docs:
        print(f"Shard {args.shard_index} empty (total docs={len(docs)})")
        return

    # 写入临时子目录仅含本分片（避免改 run_ingest 接口）
    staging = ROOT / "data" / "processed" / f"ingest_shard_{args.shard_index}"
    if staging.exists():
        for f in staging.rglob("*"):
            if f.is_file():
                f.unlink()
    for d in shard_docs:
        src = input_dir / d.source_file
        dst = staging / d.source_file
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() == ".pdf":
            shutil.copy2(src, dst)
        else:
            dst.write_text(src.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

    result = run_ingest_job(
        input_dir=staging,
        batch_size=args.batch_size,
        recreate=not args.no_recreate and args.shard_index == 0,
        max_docs=args.docs_per_shard,
    )
    print(f"Shard {args.shard_index}/{args.shard_count}: {result}")


if __name__ == "__main__":
    main()
