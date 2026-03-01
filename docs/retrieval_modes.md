# 检索模式与评测记录

> **学习文档**（流程图、模式说明、verify 参数）：[m2_retrieval.md](./m2_retrieval.md)

本文档保留 **Golden Set 指标演进表**；概念与架构详见 m2_retrieval。

---

## Golden Set 指标表

| 配置 | Recall@5 | RAGAS faithfulness | P95 ms | 备注 |
|------|----------|-------------------|--------|------|
| vector only | 100% | - | 309.5 | m2_golden |
| bm25 only | 100% | - | 84.2 | m2_golden |
| hybrid | 100% | - | 431.3 | m2_golden |
| hybrid + rerank | 100% | - | 13939.8 | m2_golden |
| llamaindex router | 100% | - | 11523.6 | m2_golden |
| graph engine | | | | |
| summary engine | | | | |
| tree engine | | | | |
| sub-question engine | | | | |

**复合问句评测集**（Phase C）：

| 文件 | 用途 |
|------|------|
| `data/eval/m2_compound.jsonl` | 检索 Recall@5（模板 `m2_compound.jsonl.example`，24 题） |
| `data/eval/golden_compound.jsonl` | RAGAS 复合问句（模板 `golden_compound.jsonl.example`，8 题，含 `ground_truth`） |
| `data/eval/m2_compound_tiny.jsonl` / `golden_compound_tiny.jsonl` | smoke（3 题） |

- `verify_m2 --golden data/eval/m2_compound.jsonl --extended --subquestion-generator both`
- `scripts/benchmark_subquestion.py` → `reports/subquestion_compare.json`（自研 vs LI 适配器，**非生产 dispatch**）
- `scripts/compare_compound_ab.py` → `reports/compound_ab_compare.md`（**hybrid_rerank vs sub_question** 离线 A/B，C5）

**数据来源（两文件，用途不同）：**

| 文件 | 用途 | 状态 |
|------|------|------|
| `data/eval/m2_golden.jsonl` | 检索 Recall@5 / P95（80 题，5 类 category） | 模板见 `m2_golden.jsonl.example` |
| `data/eval/golden.jsonl` | RAGAS faithfulness（需 `ground_truth`） | 模板见 `golden.jsonl.example` |

- Recall@5 / P95：本地跑 `python scripts/verify_m2.py --write-evolution`（5 模式）或 `--extended`（7 模式），报告见 `reports/m2_verify.json`。
- RAGAS faithfulness：模板 `golden.jsonl.example`（`build_eval_golden.py`）；live 见 COLLABORATION §3.10。

---

## LlamaIndex 模式索引

完整说明见 [m2_retrieval.md §4.2](./m2_retrieval.md#42-llamaindex-路径研究--gateway-扩展-mode)。

| 模式 | 模块 |
|------|------|
| Vector | `vector_engine.py` |
| BM25 / Keyword | `keyword_engine.py` |
| Summary | `summary_engine.py` |
| Tree | `tree_engine.py` |
| Graph | `graph_engine.py` |
| Router | `router_engine.py` |
| SubQuestion | `subquestion_engine.py` |

## LangChain 路径

Hybrid + RRF + Rerank：`apps/retrieval/langchain/hybrid_chain.py` — 见 [m2_retrieval.md §3](./m2_retrieval.md#3-生产主链路hybrid_rerank)。
