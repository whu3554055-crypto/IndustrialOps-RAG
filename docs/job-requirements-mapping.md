# 岗位要求 ↔ 项目模块映射

> 招聘图「大模型 RAG 工程师」逐条覆盖，面试/demo 按表索骥。

| 招聘要求 | 仓库路径 | 状态 |
|----------|----------|------|
| LangChain | `apps/agent/`, `apps/retrieval/langchain/` | scaffold |
| LlamaIndex | `apps/retrieval/llamaindex/` | scaffold |
| Milvus | `deploy/helm/.../milvus`, `deploy/compose` | scaffold |
| Qdrant/Chroma | `docs/decisions.md` 选型说明；可选 POC | 文档 |
| 混合检索 BM25+向量 | `apps/retrieval/hybrid/`, OpenSearch | scaffold |
| BGE-reranker | `apps/retrieval/rerank/` | scaffold |
| Llama2/Qwen/GPT-4 | `serving/vllm`, `serving/tensorrt-llm`, API 配置 | scaffold |
| LoRA/QLoRA | `pipelines/finetune/` | scaffold |
| Transformers | `pipelines/finetune/train_qlora.py` | scaffold |
| Python FastAPI | `apps/gateway/` | scaffold |
| MySQL/PostgreSQL | `deploy/.../postgresql`, Gateway models | scaffold |
| Docker | `deploy/compose/docker-compose.yml` | scaffold |
| Kubernetes | `deploy/helm/industrial-ops-rag/` | scaffold |
| 公有云 | `docs/cloud-agnostic.md` | 文档 |
| 端到端 RAG 管道 | `apps/agent/pipeline.py` | scaffold |
| 准确率/降幻觉 | Agent self-check + RAGAS | scaffold |
| CoT / few-shot | `apps/generation/prompts/` | scaffold |
| RAGAS / TruLens | `pipelines/evaluation/` | scaffold |
| 多轮对话 | Gateway sessions + rewrite | scaffold |
| 高可用 99.9% | PDB、探针、`docs/architecture.md` SLO | 文档+配置 |
| Agentic RAG | `apps/agent/tools/` | scaffold |
| 多模态 RAG | `pipelines/ingest/multimodal/` | scaffold |
| 领域数据 100k+ | `docs/scaling-data.md` + pipeline 参数 | 文档 |
| 高并发低延迟 | KEDA、`docs/serving_benchmark.md` | scaffold |
| 检索失败/幻觉排查 | `retrieval_logs` 表 + Grafana | scaffold |
| 技术文档 | `docs/*` | 进行中 |

**状态说明**：`scaffold` = 目录与占位已实现；`文档` = 仅文档；实现完成后改为 `done`。
