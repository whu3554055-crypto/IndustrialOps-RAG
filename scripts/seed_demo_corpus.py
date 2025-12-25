"""将 M7 脱敏 demo 语料复制到 data/raw/samples/，供 run_ingest 使用.

学习文档：docs/m7_demo.md §3
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "data" / "corpus" / "demo"
DEFAULT_DST = ROOT / "data" / "raw" / "samples"


def seed(src: Path, dst: Path, *, force: bool) -> int:
    if not src.is_dir():
        raise FileNotFoundError(f"Demo corpus not found: {src}")
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    present = 0
    for path in sorted(src.glob("*.md")):
        target = dst / path.name
        if target.exists() and not force:
            print(f"[skip] {target.name} exists (use --force)")
            present += 1
            continue
        shutil.copy2(path, target)
        print(f"[copy] {path.name} -> {target}")
        copied += 1
    total = copied + present
    print(f"Done: copied {copied}, already present {present} -> {dst}")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed data/raw/samples from data/corpus/demo")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--dst", type=Path, default=DEFAULT_DST)
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()
    n = seed(args.src, args.dst, force=args.force)
    raise SystemExit(0 if n >= 1 else 1)


if __name__ == "__main__":
    main()
