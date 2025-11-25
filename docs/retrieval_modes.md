# 检索模式与评测记录

## LlamaIndex 模式（`apps/retrieval/llamaindex/`）

| 模式 | 类/模块占位 | 适用查询 |
|------|-------------|----------|
| VectorStoreIndex | `vector_engine.py` | 现象描述、语义问法 |
| BM25 / Keyword | `keyword_engine.py` | 故障码、型号 |
| Summary Index | `summary_engine.py` | 章节级粗召回 |
| Tree Index | `tree_engine.py` | 手册目录层级 |
| Knowledge Graph | `graph_engine.py` | 部件关系 |
| RouterQueryEngine | `router_engine.py` | 自动选路 |
| SubQuestionQueryEngine | `subquestion_engine.py` | 复杂多步问题 |

## LangChain 路径（`apps/retrieval/langchain/`）

- Hybrid + RRF：`apps/retrieval/hybrid/`
- Rerank：`apps/retrieval/rerank/`

## Golden Set 指标表

| 配置 | Recall@5 | RAGAS faithfulness | P95 ms | 备注 |
|------|----------|-------------------|--------|------|
| vector only | 100% | - | 309.5 | m2_golden |
| bm25 only | 100% | - | 84.2 | m2_golden |
| hybrid | 100% | - | 431.3 | m2_golden |
| hybrid + rerank | 100% | - | 13939.8 | m2_golden |
| llamaindex router | 100% | - | 11523.6 | m2_golden |

**数据来源（两文件，用途不同）：**

| 文件 | 用途 | 状态 |
|------|------|------|
| `data/eval/m2_golden.jsonl` | 检索 Recall@5 / P95（10 题，仅需 `question` + `doc_ids`） | 已有 |
| `data/eval/golden.jsonl` | RAGAS faithfulness（需 `ground_truth`，见 `.example`） | 待构建 |

- Recall@5 / P95：本地跑 `python scripts/verify_m2.py --write-evolution`，报告见 `reports/m2_verify.json`。
- RAGAS faithfulness：待 M3+ Agent 管道与 `pipelines/evaluation/run_ragas.py` 实现后，构建 `golden.jsonl` 再跑 §3.7 命令填列。