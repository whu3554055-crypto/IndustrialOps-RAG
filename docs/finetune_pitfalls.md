# 微调踩坑日记

> 训练前后在此记录现象、原因、修复。M5 验收要求 ≥8 条（见 PROJECT_PLAN）。

| # | 现象 | 原因 | 修复 | 日期 |
|---|------|------|------|------|
| 1 | 生成口吻与训练不一致 | Chat template 与 Qwen 推理模板不一致 | 训练用 `tokenizer.apply_chat_template`；推理侧同一 tokenizer 族 | 2026-05-31 |
| 2 | 第一步 CUDA OOM | seq_len/batch 过大或未开 checkpoint | 降 `max_seq_length`→1024、`per_device_train_batch_size=1`、确认 `gradient_checkpointing: true` | 2026-05-31 |
| 3 | 小样本 loss 很快趋近 0 | 数据过少重复多 epoch | 减 `num_train_epochs` 或增样本；混入通用指令防过拟合 | 2026-05-31 |
| 4 | 通用问答变差 | 灾难性遗忘，仅领域 SFT | 混合 10–20% 通用多轮指令数据 | 2026-05-31 |
| 5 | RAGAS 虚高 | 评测题 doc_id 出现在训练集 | 按 `doc_id` 划分 train/eval，golden 与 sft 零重叠 | 2026-05-31 |
| 6 | 微调后检索仍错 | 仅 SFT 未改 embedding/分块 | 先查 M2 Recall；SFT 只修生成，不修检索 miss | 2026-05-31 |
| 7 | vLLM 加载 adapter 失败 | 训练在全精度基座，推理用 AWQ | merge LoRA 后量化，或 vLLM 非 AWQ 基座 + `--enable-lora`；见 m5_finetune.md §3.1 | 2026-05-31 |
| 8 | 中文标点不一致 | 全角/半角混用 | 语料与 prompt 统一标点；ingest 阶段规范化 | 2026-05-31 |

## 必踩主题清单

- [x] Chat template 与 Qwen 推理不一致
- [x] 6GB OOM（seq_len / batch / 未 checkpoint）
- [x] 小数据过拟合
- [x] 灾难性遗忘（未混通用指令）
- [x] 评测集泄漏（未按 doc_id 划分）
- [x] 仅 SFT 未改检索的局限
- [x] QLoRA 权重与 AWQ vLLM 加载路径
- [x] 中文全半角/标点一致性

<!-- 真实训练后在本表末追加行，勿删历史 -->
