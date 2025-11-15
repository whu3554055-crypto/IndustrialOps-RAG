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

## Golden Set 指标表（待填）

| 配置 | Recall@5 | RAGAS faithfulness | P95 ms | 备注 |
|------|----------|-------------------|--------|------|
| vector only | | | | |
| bm25 only | | | | |
| hybrid | | | | |
| hybrid + rerank | | | | |
| llamaindex router | | | | |

数据：`data/eval/golden.jsonl`（待构建）
