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
| 2026-05-31 | Embedding/Rerank 分时释放内存 | 16GB RAM 上 bge-m3 与 reranker 不可同驻；rerank 前 `release_embedder()` |
| 2026-05-31 | Agent 生成不含对话历史 | 多轮仅 rewrite 用 history；生成 prompt = system + 检索上下文 + 当前问句（工业 RAG 常规） |
| 2026-05-31 | vLLM `served_model_id` 与 OpenAI API 对齐 | `GET /v1/models` 的 id 写入 profile / `VLLM_MODEL`，非 HF 仓库名 |
| 2026-05-31 | M4 压测走 streaming TTFT | `scripts/benchmark_serving.py` 直连 OpenAI 兼容 API，不经 RAG 管道 |
| 2026-05-31 | 里程碑文档分层 L1–L5 | 学习 hub `docs/m{N}_*.md` + 代码 docstring 指向；见 `docs/milestones/README.md` |

<!-- 新决策追加在表末 -->
