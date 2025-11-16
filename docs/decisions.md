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
| 2026-05-31 | Windows 本地 vLLM 用 Docker `v0.6.6` | 原生 pip 不支持；`latest` 需 CUDA 13 驱动，546.x 用 cu12 tag |
| 2026-05-31 | 6GB 本机 vLLM 用 awq_marlin + cpu-offload | RTX 3060 实测：`max-model-len 512`、`cpu-offload-gb 2`；profile 4096 留 K8s |

<!-- 新决策追加在表末 -->
