# 架构决策记录 (ADR)

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-05-31 | 项目名 IndustrialOps-RAG | 工业运维场景，国内岗位高频 |
| 2026-05-31 | 向量库选 Milvus | 招聘点名；生产扩展路径清晰 |
| 2026-05-31 | BM25 用 OpenSearch | 与 Milvus 并列工业常见组合；单节点 `discovery.type=single-node` |
| 2026-05-31 | 主 LLM Qwen2.5-7B-AWQ | 覆盖 Qwen；4bit 在 6GB 上勉强推理 |
| 2026-05-31 | vLLM 与 TRT-LLM GPU 互斥 | 6GB 无法双引擎同占；架构仍保留双引擎 |
| 2026-05-31 | Embedding/Rerank 默认 CPU | 把 GPU 留给 LLM |
| 2026-05-31 | 架构不随硬件删减 | 仅 `deploy/profiles` 调参 |
| 2026-05-31 | 不从零 fork RAGFlow | 吸收 deepdoc 思路，代码自研可控 |

<!-- 新决策追加在表末 -->
