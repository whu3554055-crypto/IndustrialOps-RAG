# 技术栈 ↔ 项目模块映射

> 大模型 RAG 工程师技术栈逐条覆盖，学习/demo 按表索骥。

| 技术要求 | 仓库路径 | 状态 |
|----------|----------|------|
| LangChain | `apps/agent/`, `apps/retrieval/langchain/` | **done** |
| LlamaIndex | `apps/retrieval/llamaindex/` | **done** |
| Milvus | `deploy/helm/.../milvus`, `deploy/compose` | **done** |
| Qdrant/Chroma | `docs/decisions.md` 选型说明；可选 POC | 文档 |
| 混合检索 BM25+向量 | `apps/retrieval/hybrid/`, OpenSearch | **done** |
| BGE-reranker | `apps/retrieval/rerank/` | **done** |
| Llama2/Qwen/GPT-4 | `serving/vllm`, `serving/tensorrt-llm`, API 配置 | **done**（推理须本机 GPU） |
| LoRA/QLoRA | `pipelines/finetune/` | **done**（完整 epoch 见 m5_online_train） |
| Transformers | `pipelines/finetune/train_qlora.py` | **done** |
| Python FastAPI | `apps/gateway/` | **done** |
| MySQL/PostgreSQL | `deploy/sql/`, `session_store`, `feedback` | **done** |
| Docker | `deploy/compose/docker-compose.yml` | **done** |
| Kubernetes | `deploy/helm/industrial-ops-rag/` | **done**（全绿须线上验证） |
| 公有云 | `docs/cloud-agnostic.md` | 文档 |
| 端到端 RAG 管道 | `apps/agent/pipeline.py` | **done** |
| 准确率/降幻觉 | Agent self-check + RAGAS | **done**（真 RAGAS 须 Gateway+vLLM） |
| CoT / few-shot | `apps/generation/prompts/` | **done** |
| RAGAS / TruLens | `run_ragas.py` / `trulens_eval.py` | **done**（CI dry-run；TruLens 真 SDK 未接） |
| 多轮对话 | `session_store` + rewrite | **done** |
| 高可用 99.9% | PDB、探针、`docs/architecture.md` SLO | 文档+配置 |
| Agentic RAG | `apps/agent/tools/` | **done** |
| 多模态 RAG | `pipelines/ingest/multimodal/` | **部分**（alt 提取；视觉模型未接） |
| 领域数据 100k+ | `docs/scaling-data.md` + ingest 分批 | 文档+脚本 |
| 高并发低延迟 | KEDA、`docs/serving_benchmark.md` | **done**（TRT 行待压测） |
| 检索失败/幻觉排查 | `retrieval_logs` + `reports/retrieval_logs.jsonl` | **done** |
| 技术文档 | `docs/*` | **done** |

**状态说明**：`done` = 代码与验收脚本齐备；运行时指标见 `evolution.md`。  
**GPU 除外**：vLLM 常开、真 RAGAS live、TRT 填表、K8s 镜像全绿 — 用户本机/大显存执行。
