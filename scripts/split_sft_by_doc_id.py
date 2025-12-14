"""按 doc_id 划分 SFT 训练/留出集，防止评测泄漏（M5）.

学习：docs/m5_finetune.md §4
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _doc_id(record: dict) -> str | None:
    if "doc_id" in record:
        return str(record["doc_id"])
    ids = record.get("doc_ids")
    if isinstance(ids, list) and ids:
        return str(ids[0])
    return None


def split_file(
    input_path: Path,
    train_out: Path,
    holdout_out: Path,
    holdout_doc_ids: set[str],
) -> tuple[int, int]:
    train_rows: list[str] = []
    holdout_rows: list[str] = []
    with input_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            did = _doc_id(rec)
            if did and did in holdout_doc_ids:
                holdout_rows.append(line)
            else:
                train_rows.append(line)
    train_out.parent.mkdir(parents=True, exist_ok=True)
    train_out.write_text("\n".join(train_rows) + ("\n" if train_rows else ""), encoding="utf-8")
    holdout_out.write_text("\n".join(holdout_rows) + ("\n" if holdout_rows else ""), encoding="utf-8")
    return len(train_rows), len(holdout_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Split SFT JSONL by doc_id")
    parser.add_argument("--input", type=Path, default=Path("data/processed/sft.jsonl"))
    parser.add_argument("--train-out", type=Path, default=Path("data/processed/sft_train.jsonl"))
    parser.add_argument("--holdout-out", type=Path, default=Path("data/processed/sft_holdout.jsonl"))
    parser.add_argument(
        "--holdout-doc-ids",
        nargs="+",
        default=["pump_p101_manual.md"],
        help="doc_id values held out from training",
    )
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Missing input: {args.input}")

    holdout_set = set(args.holdout_doc_ids)
    n_train, n_hold = split_file(args.input, args.train_out, args.holdout_out, holdout_set)
    print(f"train={n_train} -> {args.train_out}")
    print(f"holdout={n_hold} -> {args.holdout_out} (doc_ids={sorted(holdout_set)})")
    if n_train == 0:
        raise SystemExit("No training rows; check --holdout-doc-ids")


if __name__ == "__main__":
    main()
