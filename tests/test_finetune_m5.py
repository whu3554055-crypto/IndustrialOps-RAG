"""M5 微调 — 无 GPU 单元测试."""

from pathlib import Path

import pytest

from pipelines.finetune.model_path import resolve_base_model
from pipelines.finetune.train_qlora import (
    finetune_cfg,
    load_sft_records,
    normalize_messages,
    resolve_device_map,
    validate_sft_records,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "data" / "processed" / "sft.jsonl.example"


def test_normalize_messages_variants() -> None:
    msgs = normalize_messages(
        {
            "instruction": "问",
            "input": "补充",
            "output": "答",
        }
    )
    assert msgs[0]["content"] == "问\n补充"
    assert msgs[1]["role"] == "assistant"

    roundtrip = normalize_messages({"messages": msgs})
    assert roundtrip == msgs


def test_load_example_dataset() -> None:
    records = load_sft_records(EXAMPLE, max_samples=3)
    validate_sft_records(records)
    assert len(records) == 3


def test_finetune_profile_keys() -> None:
    cfg = finetune_cfg()
    assert cfg["qlora_r"] >= 1
    assert cfg["max_seq_length"] >= 512


def test_resolve_base_model_prefers_local_dir(tmp_path: Path) -> None:
    local = tmp_path / "models" / "Qwen2.5-7B-Instruct"
    local.mkdir(parents=True)
    (local / "config.json").write_text("{}", encoding="utf-8")
    (local / "model-00001-of-00004.safetensors").write_bytes(b"x")

    resolved = resolve_base_model(
        "models/Qwen2.5-7B-Instruct",
        root=tmp_path,
    )
    assert resolved == str(local.resolve())

    hub = resolve_base_model("Qwen/Qwen2.5-7B-Instruct", root=tmp_path)
    assert hub == str(local.resolve())


def test_resolve_device_map_single_gpu() -> None:
    assert resolve_device_map({"device_map": "single_gpu"}) == {"": 0}
    assert resolve_device_map({"device_map": "auto"}) == "auto"


def test_empty_dataset_raises() -> None:
    empty = ROOT / "reports" / "_empty_sft.jsonl"
    empty.parent.mkdir(parents=True, exist_ok=True)
    empty.write_text("", encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="empty"):
            validate_sft_records([])
    finally:
        empty.unlink(missing_ok=True)
