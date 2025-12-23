# IndustrialOps-RAG 项目总方案

> **文档用途**：防止多轮对话上下文遗忘；后续开发、面试、部署均以此为准。  
> **最后更新**：2026-05-31  
> **部署档**：`deploy/profiles/dev-single-node.yaml`（单机勉强跑） / `production.yaml`（生产数值）

---

## 1. 项目定位

| 项 | 内容 |
|----|------|
| **名称** | IndustrialOps-RAG — 工业设备运维知识库智能问答系统 |
| **场景** | 设备手册、故障码、SOP、维修案例；中文优先 |
| **目标** | 工业标准、可交付、可演示；覆盖「大模型 RAG 工程师」招聘全文 |
| **原则** | **架构不因本机硬件而删减**；仅通过 `profiles` 调参、分时、互斥占 GPU |
| **硬件参考** | RTX 3060 6GB / 16GB RAM / Ryzen 7 5800H；WSL2 Ubuntu 22.04 推荐 |
| **学习模式** | 突击高投入；质量与技术含量优先；时间不设硬上限 |

---

## 2. 设计原则

1. **全栈保留**：Milvus、OpenSearch(BM25)、图谱、BGE、LangChain + LlamaIndex 全检索模式、Agentic、RAGAS、QLoRA、FastAPI、PostgreSQL、Redis、MinIO、vLLM、TensorRT-LLM、KEDA、Prometheus/Grafana、Helm/K8s。
2. **单机勉强跑**：全组件 `replicas: 1` + 严格 `requests/limits`；vLLM 与 TensorRT-LLM **GPU 互斥**（`mutual_exclusive_gpu`）。
3. **配置驱动**：所有资源配比见 `deploy/profiles/*.yaml`，禁止为省资源删除 Chart 组件。
4. **开源吸收**：RAGFlow(深度解析)、Langchain-Chatchat(中文/API)、LightRAG(图谱)、rag-from-scratch(阶段方法论)、RAGAS(评测) — **抽模块自研，不 fork 整库**。
5. **协作约定**：见 [COLLABORATION.md](./COLLABORATION.md)（**拍板 = Cursor 对话 token**；高消耗操作优先用户代劳，Agent 提供 §3 命令）。

---

## 3. 逻辑架构

```
用户(Web/API)
    → FastAPI Gateway（会话、反馈、路由）
    → Agentic Orchestrator（LangChain：改写、路由、工具、自检）
         ├→ LangChain LCEL（混合检索、RRF、Rerank）
         └→ LlamaIndex QueryEngines（Vector/Summary/Tree/Graph/Router/SubQuestion）
    → 检索层：Milvus + OpenSearch + Graph Store
    → BGE-Reranker（默认 CPU）
    → LLM Router → vLLM | TensorRT-LLM |（可选 API 对照）
    → PostgreSQL / Redis / MinIO
    → 异步：Ingest CronJob、RAGAS CronJob、QLoRA Train Job
    → 可观测：Prometheus + Grafana；KEDA 扩缩容
```

详图见 [architecture.md](./architecture.md)。

---

## 4. 里程碑（质量优先）

| 阶段 | 交付物 | 验收 |
|------|--------|------|
| **M0** | k3d/kind、Helm 骨架、`profiles`、GPU 透传、vLLM 7B-AWQ 单条通 | `kubectl get pods` 全绿（分时启服） |
| **M1** | 语料 ingest、Milvus+OpenSearch、metadata 中文 | 10 问手工 Top5 命中 |
| **M2** | LlamaIndex 全模式 + LangChain hybrid + Rerank | golden 80 题基线表 |
| **M3** | Agentic、多轮、拒答、引用、中文 UI | 3 轮追问 + 库外拒答 |
| **M4** | vLLM + TRT-LLM + KEDA + router + benchmark | `serving_benchmark.md` 有数据 |
| **M5** | QLoRA Job + pitfalls 文档 + RAG/SFT 对比 | RAGAS 前后对比 |
| **M6** | RAGAS CI、Grafana、Helm 一键、全套 docs | 新环境 README 15min 问答 |
| **M7** | 真实脱敏语料、反馈闭环 | 可给业务方 demo |

---

## 5. 模型与推理（招聘对齐）

| 用途 | 默认模型 | 备注 |
|------|----------|------|
| 主 LLM | `Qwen2.5-7B-Instruct-AWQ` | vLLM / TRT-LLM；4bit 压 6GB |
| API 对照 | 配置 `OPENAI_COMPATIBLE_*` | GPT-4/DeepSeek/Qwen-Plus 可选 |
| Embedding | `BAAI/bge-m3` | 默认 CPU |
| Rerank | `BAAI/bge-reranker-v2-m3` | 默认 CPU |
| 微调 | Qwen2.5-7B + QLoRA | 训练时 vLLM scale 0 |

---

## 6. 单机启服顺序（避免 OOM）

1. PostgreSQL、Redis、MinIO  
2. Milvus → OpenSearch → ingest Job（小批量）  
3. vLLM（7B-AWQ）就绪后 Gateway  
4. Prometheus、Grafana  
5. **分时**：TensorRT-LLM（关闭 vLLM 占 GPU）  
6. KEDA ScaledJob、RAGAS CronJob、Train Job  

---

## 7. 目录结构

见仓库根 [README.md](../README.md)。

---

## 8. 相关文档索引

| 文档 | 说明 |
|------|------|
| [architecture.md](./architecture.md) | 架构与时序 |
| [job-requirements-mapping.md](./job-requirements-mapping.md) | 岗位要求逐条映射 |
| [decisions.md](./decisions.md) | ADR 决策记录 |
| [m0_infra.md](./m0_infra.md) | **M0** 基础设施、Profile、Compose、K8s/Helm（学习 hub） |
| [m1_ingest.md](./m1_ingest.md) | **M1** 语料 ingest、Milvus+OpenSearch、验收（学习 hub） |
| [retrieval_modes.md](./retrieval_modes.md) | M2 指标演进表 |
| [m2_retrieval.md](./m2_retrieval.md) | **M2** 混合检索、RRF、Rerank、LlamaIndex 模式（学习 hub） |
| [m3_agent.md](./m3_agent.md) | **M3** Agent 管道、多轮、拒答、引用（学习 hub） |
| [finetune_pitfalls.md](./finetune_pitfalls.md) | 微调踩坑日记 |
| [serving_benchmark.md](./serving_benchmark.md) | vLLM vs TRT 压测结果表 |
| [m4_serving.md](./m4_serving.md) | **M4** 推理 Router、KEDA、压测、引擎切换（学习 hub） |
| [m5_finetune.md](./m5_finetune.md) | **M5** QLoRA、SFT 数据、RAG/SFT 对比（学习 hub） |
| [m6_eval.md](./m6_eval.md) | **M6** RAGAS CI、Grafana、Helm 一键（学习 hub） |
| [m5_online_train.md](./m5_online_train.md) | **M5** 线上 24GB 完整 epoch（AutoDL 4090 等） |
| [milestones/README.md](./milestones/README.md) | 各里程碑文档层级约定 |
| [scaling-data.md](./scaling-data.md) | 2k→100k 数据扩展 |
| [cloud-agnostic.md](./cloud-agnostic.md) | 多云迁移说明 |
| [evolution.md](./evolution.md) | baseline→最终 指标演进 |
| [COLLABORATION.md](./COLLABORATION.md) | 人机协作与 token 约定 |
| [../k8s-learning/checklist.md](../k8s-learning/checklist.md) | K8s 能力打卡 |

---

## 9. 下一步（M0）

1. 复制 `.env.example` → `.env`  
2. `docker compose -f deploy/compose/docker-compose.yml up -d`（本地开发子集）  
3. 创建 k3d 集群，安装 Helm chart（见 [COLLABORATION.md](./COLLABORATION.md) §3.3；Chart 细节见 `deploy/helm/industrial-ops-rag/README.md`）  
4. 拉取模型等见 [COLLABORATION.md](./COLLABORATION.md) §3.4（用户代劳省对话 token）  
