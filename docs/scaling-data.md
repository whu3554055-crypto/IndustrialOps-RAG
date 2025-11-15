# 数据规模扩展（2k → 100k+）

## Pipeline 阶段

1. **raw** → `data/raw/` 原始文档  
2. **parsed** → `data/processed/` 深度解析输出  
3. **chunks** → JSONL + metadata（`device_model`, `fault_code`, ...）  
4. **instructions** → Alpaca/Qwen 格式 SFT  
5. **eval** → `data/eval/golden.jsonl`（与训练 doc_id 隔离）

## 本地验证

- `finetune.dataset_max_samples: 5000`（profile 可调）
- 架构与脚本按 100k 分批设计：`batch_size=1000` ingest / 训练

## 质量门槛

- 人工校正 ≥200 条黄金问答  
- 自动生成需抽样 10% 人工审核
