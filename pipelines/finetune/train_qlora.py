"""QLoRA 微调 — 训练前须释放 GPU（停 vLLM / scale 0）.

学习文档：docs/m5_finetune.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.config import load_profile  # noqa: E402
from pipelines.finetune.model_path import HF_HUB_INSTRUCT, resolve_base_model  # noqa: E402

DEFAULT_DATASET = ROOT / "data" / "processed" / "sft.jsonl"
DEFAULT_OUTPUT = ROOT / "models" / "qlora-adapter"

LORA_TARGET_MODULES = (
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
)


def finetune_cfg(profile: dict | None = None) -> dict:
    p = profile or load_profile()
    cfg = dict(p.get("finetune") or {})
    cfg.setdefault("base_model", "models/Qwen2.5-7B-Instruct")
    cfg.setdefault("dataset_max_samples", 5000)
    cfg.setdefault("qlora_r", 8)
    cfg.setdefault("qlora_alpha", 16)
    cfg.setdefault("lora_dropout", 0.05)
    cfg.setdefault("max_seq_length", 2048)
    cfg.setdefault("per_device_train_batch_size", 1)
    cfg.setdefault("gradient_accumulation_steps", 16)
    cfg.setdefault("gradient_checkpointing", True)
    cfg.setdefault("bnb_4bit", True)
    cfg.setdefault("learning_rate", 2e-4)
    cfg.setdefault("num_train_epochs", 1)
    return cfg


def load_sft_records(path: Path, max_samples: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"SFT dataset not found: {path}")
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}") from exc
    if max_samples is not None:
        records = records[:max_samples]
    return records


def normalize_messages(record: dict[str, Any]) -> list[dict[str, str]]:
    if "messages" in record:
        msgs = record["messages"]
        if not isinstance(msgs, list) or len(msgs) < 2:
            raise ValueError("messages must be a list with at least user + assistant")
        return [{"role": m["role"], "content": str(m["content"])} for m in msgs]

    if "instruction" in record and "output" in record:
        user = str(record["instruction"])
        if record.get("input"):
            user = f"{user}\n{record['input']}"
        return [
            {"role": "user", "content": user},
            {"role": "assistant", "content": str(record["output"])},
        ]

    raise ValueError(
        "Each record needs 'messages' or 'instruction'+'output'; optional doc_id for split"
    )


def validate_sft_records(records: list[dict[str, Any]]) -> None:
    if not records:
        raise ValueError("SFT dataset is empty")
    for i, rec in enumerate(records):
        normalize_messages(rec)
        if "doc_id" not in rec and "doc_ids" not in rec:
            # warn only at dry-run — still allow generic instruction rows
            continue


def run_dry_run(
    *,
    dataset: Path,
    output_dir: Path,
    profile_name: str | None,
    max_samples: int | None,
    base_model_override: str | None = None,
) -> int:
    profile = load_profile(profile_name)
    cfg = finetune_cfg(profile)
    cap = max_samples if max_samples is not None else cfg.get("dataset_max_samples")
    records = load_sft_records(dataset, cap)
    validate_sft_records(records)
    doc_ids = {r.get("doc_id") or (r.get("doc_ids") or [None])[0] for r in records}
    resolved = resolve_base_model(str(cfg["base_model"]), cli_override=base_model_override)
    print("[dry-run] finetune profile OK")
    print(f"  base_model(profile)={cfg['base_model']}")
    print(f"  base_model(resolved)={resolved}")
    print(f"  records={len(records)} unique_doc_ids≈{len(doc_ids)}")
    print(f"  qlora r={cfg['qlora_r']} alpha={cfg['qlora_alpha']} max_seq={cfg['max_seq_length']}")
    print(f"  output_dir={output_dir}")
    print("  GPU: training requires CUDA; stop vLLM before real run (docs/m5_finetune.md)")
    return 0


def run_train(
    *,
    dataset: Path,
    output_dir: Path,
    profile_name: str | None,
    max_samples: int | None,
    num_train_epochs: float | None,
    max_steps: int | None,
    base_model_override: str | None = None,
    local_files_only: bool = False,
) -> int:
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
        Trainer,
        DataCollatorForLanguageModeling,
    )

    if not torch.cuda.is_available():
        print("ERROR: CUDA not available. Use --dry-run or run on a GPU machine.", file=sys.stderr)
        return 1

    profile = load_profile(profile_name)
    cfg = finetune_cfg(profile)
    cap = max_samples if max_samples is not None else cfg.get("dataset_max_samples")
    records = load_sft_records(dataset, cap)
    validate_sft_records(records)

    base_model = resolve_base_model(str(cfg["base_model"]), cli_override=base_model_override)
    load_kw: dict[str, Any] = {"trust_remote_code": True}
    if local_files_only:
        load_kw["local_files_only"] = True
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[train] loading base_model from {base_model}")
    tokenizer = AutoTokenizer.from_pretrained(base_model, **load_kw)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    texts: list[str] = []
    for rec in records:
        messages = normalize_messages(rec)
        texts.append(
            tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
            )
        )

    def tokenize(batch: dict[str, list[str]]) -> dict:
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=int(cfg["max_seq_length"]),
            padding=False,
        )

    hf_ds = Dataset.from_dict({"text": texts}).map(tokenize, batched=True, remove_columns=["text"])

    quant_config = None
    if cfg.get("bnb_4bit"):
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=quant_config,
        device_map="auto",
        **load_kw,
    )
    model = prepare_model_for_kbit_training(model)
    lora = LoraConfig(
        r=int(cfg["qlora_r"]),
        lora_alpha=int(cfg["qlora_alpha"]),
        lora_dropout=float(cfg.get("lora_dropout", 0.05)),
        target_modules=list(LORA_TARGET_MODULES),
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)

    epochs = float(num_train_epochs if num_train_epochs is not None else cfg["num_train_epochs"])
    train_args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=int(cfg["per_device_train_batch_size"]),
        gradient_accumulation_steps=int(cfg["gradient_accumulation_steps"]),
        learning_rate=float(cfg["learning_rate"]),
        num_train_epochs=epochs,
        max_steps=max_steps if max_steps is not None else -1,
        logging_steps=10,
        save_strategy="epoch",
        bf16=torch.cuda.is_bf16_supported(),
        gradient_checkpointing=bool(cfg.get("gradient_checkpointing", True)),
        report_to="none",
        remove_unused_columns=False,
    )

    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(
        model=model,
        args=train_args,
        train_dataset=hf_ds,
        data_collator=collator,
    )
    trainer.train()
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    (output_dir / "train_config.json").write_text(
        json.dumps({"profile_finetune": cfg, "dataset": str(dataset)}, indent=2),
        encoding="utf-8",
    )
    print(f"[done] adapter saved to {output_dir}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="QLoRA fine-tune (Qwen2.5-7B)")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", default=None, help="Profile name (default: IOR_PROFILE)")
    parser.add_argument("--dry-run", action="store_true", help="Validate dataset + profile only")
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--num-train-epochs", type=float, default=None)
    parser.add_argument("--max-steps", type=int, default=None, help="Override epochs for smoke test")
    parser.add_argument(
        "--base-model",
        default=None,
        help=f"Override finetune.base_model (default: profile or local {HF_HUB_INSTRUCT})",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Do not download; fail if resolved base_model path is incomplete",
    )
    args = parser.parse_args()

    if args.dry_run:
        raise SystemExit(
            run_dry_run(
                dataset=args.dataset,
                output_dir=args.output_dir,
                profile_name=args.profile,
                max_samples=args.max_samples,
                base_model_override=args.base_model,
            )
        )
    raise SystemExit(
        run_train(
            dataset=args.dataset,
            output_dir=args.output_dir,
            profile_name=args.profile,
            max_samples=args.max_samples,
            num_train_epochs=args.num_train_epochs,
            max_steps=args.max_steps,
            base_model_override=args.base_model,
            local_files_only=args.local_files_only,
        )
    )


if __name__ == "__main__":
    main()
