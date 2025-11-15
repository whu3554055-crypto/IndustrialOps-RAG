"""Ingest CLI — 解析 → 切块 → Milvus + OpenSearch + Graph."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="IndustrialOps-RAG ingest")
    parser.add_argument("--input", type=str, default="data/raw", help="原始文档目录")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    # TODO M1: deepdoc + chunk + embed + index
    print(f"[scaffold] ingest from {args.input}, batch={args.batch_size}")
    print("大目录 ingest 须见 docs/COLLABORATION.md 拍板")


if __name__ == "__main__":
    main()
