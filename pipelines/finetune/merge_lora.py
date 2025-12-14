"""将 QLoRA adapter merge 进基座（供非 LoRA 推理或再量化）.

学习：docs/m5_finetune.md §4.1、finetune_pitfalls.md #7
需要较大 GPU 显存；本机 6GB 请在线上 merge 或直接用 vLLM --enable-lora。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.config import load_profile  # noqa: E402
from pipelines.finetune.train_qlora import finetune_cfg  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter-dir", type=Path, default=ROOT / "models" / "qlora-adapter")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "models" / "merged-7b")
    parser.add_argument("--profile", default="train-gpu-24g")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = finetune_cfg(load_profile(args.profile))
    base = str(cfg["base_model"])
    if args.dry_run:
        print(f"[dry-run] merge {args.adapter_dir} -> {args.output_dir}")
        print(f"  base_model={base}")
        if not args.adapter_dir.is_dir():
            print("  WARN: adapter-dir missing")
        return

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise SystemExit("CUDA required for merge; use --dry-run locally.")

    if not args.adapter_dir.is_dir():
        raise SystemExit(f"Adapter not found: {args.adapter_dir}")

    tokenizer = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        base,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(model, str(args.adapter_dir))
    merged = model.merge_and_unload()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"[done] merged weights at {args.output_dir}")


if __name__ == "__main__":
    main()
