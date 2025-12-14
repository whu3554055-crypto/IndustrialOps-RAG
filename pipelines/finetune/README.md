# QLoRA 微调

> **学习 hub**：[docs/m5_finetune.md](../../docs/m5_finetune.md)

## 脚本

| 文件 | 作用 |
|------|------|
| `train_qlora.py` | 从 profile 读超参，4bit QLoRA 训练，保存 adapter |
| `merge_lora.py` | merge adapter 到全量权重（大显存） |

## 本机最短路径

```powershell
copy data\processed\sft.jsonl.example data\processed\sft.jsonl
# 停 vLLM 释放 GPU
python pipelines/finetune/train_qlora.py --dry-run
python pipelines/finetune/train_qlora.py --max-samples 32 --max-steps 10
```

训练前 **勿与 vLLM / TRT 编译同占 GPU**（见 `deploy/profiles/dev-single-node.yaml` `gpu.mutual_exclusive_gpu`）。

**完整 epoch**：见 [docs/m5_online_train.md](../../docs/m5_online_train.md)，使用 `--profile train-gpu-24g`。
