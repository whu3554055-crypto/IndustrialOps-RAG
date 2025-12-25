# IndustrialOps-RAG

工业设备运维知识库 RAG 平台 — 对齐「大模型 RAG 工程师」岗位全栈要求，**架构全量、单机通过 `dev-single-node` profile 调参运行**。

## 文档入口（防上下文遗忘）

| 文档 | 说明 |
|------|------|
| [docs/m0_infra.md](docs/m0_infra.md) | **M0 基础设施**（Profile、Compose、K8s） |
| [docs/m1_ingest.md](docs/m1_ingest.md) | M1 ingest |
| [docs/m5_finetune.md](docs/m5_finetune.md) | M5 QLoRA |
| [docs/m6_eval.md](docs/m6_eval.md) | **M6** RAGAS CI、Grafana、Helm 一键 |
| [docs/m7_demo.md](docs/m7_demo.md) | **M7** 脱敏 demo 语料、反馈、Gradio |
| [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) | **总方案（必读）** |
| [docs/COLLABORATION.md](docs/COLLABORATION.md) | **对话 token 拍板** + 用户代劳命令 + 省 token 提醒 |
| [docs/architecture.md](docs/architecture.md) | 架构与时序 |
| [docs/job-requirements-mapping.md](docs/job-requirements-mapping.md) | 岗位映射 |
| [deploy/profiles/dev-single-node.yaml](deploy/profiles/dev-single-node.yaml) | 单机资源与启服顺序 |

## 仓库结构

```
apps/           # Gateway、Agent、检索、生成、Web
pipelines/      # Ingest、微调、RAGAS 评测
serving/        # vLLM、TensorRT-LLM 说明与构建
deploy/         # compose、profiles、helm、keda、monitoring
data/           # raw / processed / eval
docs/           # 设计与 ADR
k8s-learning/   # K8s 打卡清单
tests/
```

## 新环境 15 分钟问答（M6 验收）

详见 [docs/m6_eval.md](docs/m6_eval.md) §6。

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -e ".[dev]"
copy .env.example .env
docker compose -f deploy/compose/docker-compose.yml up -d
# vLLM + Gateway 见 COLLABORATION §3.5–3.6
curl -X POST http://localhost:8080/v1/chat -H "Content-Type: application/json" -d "{\"session_id\":\"demo\",\"query\":\"故障码 E1024 如何处理？\"}"
python scripts\verify_m6.py --write-report
```

Helm 一键：`.\scripts\one_click_k8s.ps1`（WSL/Linux：`bash scripts/one_click_k8s.sh`）。

## 快速开始（M0）

详见 [docs/m0_infra.md](docs/m0_infra.md)（Compose 路径 vs K8s 路径）。

```bash
# 1. 环境
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. 配置
cp .env.example .env

# 3. 中间件（Compose）
docker compose -f deploy/compose/docker-compose.yml up -d

# 4. K8s 全架构（M0 步骤 3，详见 COLLABORATION §3.3）
k3d cluster create industrial-rag --agents 1 --gpus 1
helm upgrade --install ior ./deploy/helm/industrial-ops-rag \
  -f ./deploy/helm/industrial-ops-rag/values-dev-single-node.yaml \
  -n industrial-ops --create-namespace

# 5. Gateway（开发）
uvicorn apps.gateway.main:app --reload --host 0.0.0.0 --port 8080
```

**高对话 token 的 Agent 操作** — 见 [docs/COLLABORATION.md](docs/COLLABORATION.md) §2；**模型下载等建议你自己跑** §3.4。

## K8s（全架构）

完整步骤（含 GPU 透传、验收）见 [docs/COLLABORATION.md](docs/COLLABORATION.md) §3.3。快速命令：

```bash
k3d cluster create industrial-rag --agents 1 --gpus 1
helm upgrade --install ior ./deploy/helm/industrial-ops-rag \
  -f ./deploy/helm/industrial-ops-rag/values-dev-single-node.yaml \
  -n industrial-ops --create-namespace
```

## 硬件

RTX 3060 6GB / 16GB RAM — 参数见 `deploy/profiles/dev-single-node.yaml`（7B-AWQ、max_num_seqs=2 等）。

## 里程碑

M0 → M7 见 [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md#4-里程碑质量优先)。

## License

Private / 学习用途（按需补充）。
