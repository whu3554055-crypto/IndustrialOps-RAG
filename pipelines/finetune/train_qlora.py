"""QLoRA 微调 — 训练前须 scale vLLM to 0（见 profile）."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/processed/sft.jsonl")
    parser.add_argument("--output-dir", default="models/qlora-adapter")
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()
    # TODO M5: transformers + peft + bitsandbytes
    print(f"[scaffold] QLoRA train dataset={args.dataset}")
    print("长时训练须见 docs/COLLABORATION.md 拍板")


if __name__ == "__main__":
    main()
