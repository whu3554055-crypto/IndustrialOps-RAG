"""RAGAS 评测 — 大规模运行须拍板."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="data/eval/golden.jsonl")
    parser.add_argument("--output", default="reports/ragas_report.json")
    args = parser.parse_args()
    # TODO M6: ragas.evaluate
    print(f"[scaffold] RAGAS on {args.golden} → {args.output}")


if __name__ == "__main__":
    main()
