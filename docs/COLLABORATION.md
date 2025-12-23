# 协作约定 — 以 Cursor 对话 Token 计费为中心

> **拍板**：指可能显著增加 **你与 Cursor Agent 对话计费 token** 的操作。  
> **本机成本**（下载模型、GPU 训练、Docker 占内存）由你自行决定；Agent 不默认代跑，但可在你代劳时提供下方**可复制命令**。

---

## 1. 防止上下文遗忘（低 token）

- 方案唯一来源：[PROJECT_PLAN.md](./PROJECT_PLAN.md)
- 决策 → [decisions.md](./decisions.md)；指标 → [evolution.md](./evolution.md)、[retrieval_modes.md](./retrieval_modes.md)
- **新里程碑开新对话**，附一句：`按 PROJECT_PLAN 做 Mx，小结模式`
- Agent **不要**在聊天里复述长方案；只读必要章节，回复 **≤5 行摘要 + 文件路径**

---

## 2. 须你拍板（Agent 侧 — 高对话 Token）

Agent **不得擅自**做下列事；须先说明「为何费 token + 预估范围」，征得同意后再做：

| 类型 | 为何费 token | 示例 |
|------|----------------|------|
| **跨里程碑大包** | 多轮 tool、大段 diff 累积 | 「M1–M4 一次做完」 |
| **大量读文件** | 文件内容进入上下文 | 通读 RAGFlow、一次读 >10 个中等文件、整份 PDF 文本 |
| **长输出贴聊天** | 输出计入对话 | 全文日志、完整 RAGAS JSON、几百行 stdout |
| **广探索搜索** | 多轮 search + read | 「把整个 repo 扫一遍」、无范围 SemanticSearch |
| **子 Agent / 并行 Task** | 多路上下文叠加 | 多 subagent 同时探库 |
| **大矩阵评测由 Agent 驱动** | 反复推理 + 贴结果 | 500+ 题 RAGAS × 多配置，且每轮回报细节 |
| **重复全文粘贴** | 重复计 token | 每轮再贴 PROJECT_PLAN 全文 |

**Agent 默认不必拍板**（低 token）：

- 改 **1–3 个**相关源文件、补测试、改 docs 一节
- 只读当前任务涉及的 **1–2 个**文件（且用 offset/limit 读大文件）
- 跑 **单文件**单元测试；失败时只贴 **最后 30 行**
- 结论写入 `reports/` 或 `docs/`，聊天只给摘要

---

## 3. 建议你代劳（省对话 Token）— 可执行步骤

下列操作 **你本机执行**；Agent 仅在你说「做完了 / 报错了」时做**短回复**排查。需要时 Agent 应指向本节，而不是在对话里逐步代跑长命令链。

### 3.1 环境（一次性）

> **学习文档**：[m0_infra.md](./m0_infra.md) §7。

```powershell
cd d:\repo\RAG
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

**省 token**：依赖问题把 `pip install` 最后 20 行错误贴过来即可，不要贴全文 log。

### 3.2 中间件（Compose）

> **学习文档**：[m0_infra.md](./m0_infra.md) §5。

```powershell
cd d:\repo\RAG
docker compose -f deploy/compose/docker-compose.yml up -d
docker compose -f deploy/compose/docker-compose.yml ps
```

验证：浏览器或 `curl http://localhost:9200`（OpenSearch）、Milvus `19530`。

**省 token**：只回复 `ps` 里 unhealthy 的行，不要贴 `docker compose logs` 全文（可先本地 `logs --tail 50`）。

### 3.3 K8s 集群 + Helm（M0 步骤 3）

> **学习文档**：[m0_infra.md](./m0_infra.md) §6。

对应 [PROJECT_PLAN.md](./PROJECT_PLAN.md) §9 第 3 步；Chart 细节见 [deploy/helm/industrial-ops-rag/README.md](../deploy/helm/industrial-ops-rag/README.md)。

**前提**：Docker 可用；WSL2 内跑 k3d 时建议 RAM ≥12GB。

**Step 1 — 创建 k3d 集群**

```powershell
k3d cluster create industrial-rag --agents 1 --gpus 1
kubectl cluster-info
```

**Step 2 — GPU 透传（RTX / WSL2）**

若 vLLM Pod 卡在 `Pending`（无 `nvidia.com/gpu`），在 **WSL2 Ubuntu** 内安装 device plugin：

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.5/nvidia-device-plugin.yml
kubectl -n kube-system rollout status daemonset/nvidia-device-plugin-daemonset
```

Windows 原生 Docker Desktop + k3d 时 `--gpus 1` 行为因版本而异；M0 建议在 WSL2 内执行本节。

**Step 3 — 安装 Helm chart**

```powershell
cd d:\repo\RAG
helm upgrade --install ior ./deploy/helm/industrial-ops-rag `
  -f ./deploy/helm/industrial-ops-rag/values-dev-single-node.yaml `
  -n industrial-ops --create-namespace
```

**Step 4 — 验收（M0）**

```powershell
python scripts/verify_m0.py --write-report
kubectl -n industrial-ops get pods
```

目标：Compose/`verify_m0` profile+中间件 PASS；K8s 分时启服后 `kubectl get pods` 全绿。启服顺序见 `deploy/profiles/dev-single-node.yaml` → `startup_order`。镜像未本地 build 时可能 `ImagePullBackOff`，见 Chart README；**可先走 Compose 路径完成 M1–M4**。

**省 token**：排障只贴 `kubectl describe pod <name>` 的 Events + `logs --tail=40`，勿贴全文。

### 3.4 下载模型（HF）

> **勿设** `HF_ENDPOINT=https://hf-mirror.com`：`huggingface_hub` ≥1.17 与镜像不兼容，会报 `FileMetadataError`。直连 `huggingface.co`；失败用 ModelScope（见 [m5_finetune.md](./m5_finetune.md) §11 步骤 4）。

```powershell
.\.venv\Scripts\activate
Remove-Item Env:HF_ENDPOINT -ErrorAction SilentlyContinue
pip install -U "huggingface_hub[cli]"
# 需先在 hf.co 设置 token: hf auth login

hf download Qwen/Qwen2.5-7B-Instruct-AWQ --local-dir d:\repo\RAG\models\Qwen2.5-7B-Instruct-AWQ
hf download BAAI/bge-m3 --local-dir d:\repo\RAG\models\bge-m3
hf download BAAI/bge-reranker-v2-m3 --local-dir d:\repo\RAG\models\bge-reranker-v2-m3
```

**省 token**：下载进度在本地看；找 Agent 时只说「下完了」或「报错最后一行」。

### 3.5 启动 vLLM（7B-AWQ，RTX 3060 6GB 实测）

> **Windows 勿 `pip install vllm`**（官方不支持；且 `latest` 镜像需 CUDA 13 驱动 ≥580）。  
> 本机驱动 546.x → 用 **Docker + 固定 CUDA 12 tag**（`v0.6.6`）。  
> 下列参数在 6GB 显存上**已验证可跑**；与 `dev-single-node.yaml` 的 4096 context 不同，属单机压显存调优。

**Step 1 — 验证 Docker GPU（CUDA 12）**

```powershell
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
```

**Step 2 — 拉取镜像（仅首次，体积大）**

```powershell
docker pull vllm/vllm-openai:v0.6.6
```

**Step 3 — 启动（GPU 占用期间不要同时跑 QLoRA / TRT build）**

```powershell
docker run --gpus all --ipc=host -p 8000:8000 `
  -v d:/repo/RAG/models:/models `
  vllm/vllm-openai:v0.6.6 `
  --model /models/Qwen2.5-7B-Instruct-AWQ `
  --quantization awq_marlin `
  --gpu-memory-utilization 0.95 `
  --max-model-len 2048 `
  --max-num-seqs 2 `
  --max-num-batched-tokens 2048 `
  --cpu-offload-gb 2
```

另开终端测一条：

```powershell
curl http://localhost:8000/v1/models
```

**OOM 时**：先降 `--gpu-memory-utilization`（如 `0.88`），或再降 `--max-model-len` / `--max-num-batched-tokens`。

**驱动升级后**（≥580）：可改用 `vllm/vllm-openai:latest`；生产仍建议固定 tag。

**省 token**：vLLM 启动日志 **不要**贴满；OOM 只贴含 `CUDA out of memory` 的 ~15 行。

### 3.6 Gateway（自测）

```powershell
cd d:\repo\RAG
.\.venv\Scripts\activate
uvicorn apps.gateway.main:app --host 0.0.0.0 --port 8080
```

```powershell
curl http://localhost:8080/v1/health
```

### 3.7 小样本 Ingest（≤20 文档，你代劳）

> **学习文档**：[m1_ingest.md](./m1_ingest.md)（ingest 流程、双索引、切块、verify_m1）。

```powershell
cd d:\repo\RAG
.\.venv\Scripts\activate
# 默认 ingest data/raw（含 samples/ 下 3 篇示例 MD）；自有语料可放入 data\raw\
python pipelines/ingest/run_ingest.py --input data/raw --batch-size 8
```

输出重定向省 token：

```powershell
python pipelines/ingest/run_ingest.py --input data/raw 2>&1 | Tee-Object -FilePath reports\ingest_last.log
```

成功时应看到 `done: N chunks indexed`。找 Agent：「`ingest_last.log` 最后 30 行 + 现象一句话」。

**M1 验收（10 题 Top5，ingest 后执行）：**

```powershell
python scripts/verify_m1.py --write-evolution
```

通过：向量与 BM25 **各自** ≥8/10 命中。详情见 `reports/m1_verify.json`；聊天只贴终端汇总行。

### 3.7.1 M2 检索验收

> **学习文档**：[m2_retrieval.md](./m2_retrieval.md)（hybrid_rerank 流程、RRF、模式表、verify 参数）。

Gateway 自测（需 uvicorn 已起）。**勿用 `Invoke-RestMethod`**：Windows PowerShell 5.x 对中文 JSON 请求/响应易乱码。用 **curl** 或 **Python**：

```powershell
# 方式 A — curl（推荐，终端直接可读）
@'
{"query":"P-101 出口压力正常范围","mode":"hybrid_rerank","top_k":5}
'@ | Set-Content -Path reports\_search_body.json -Encoding utf8NoBOM
curl.exe -X POST "http://localhost:8080/v1/search" `
  -H "Content-Type: application/json; charset=utf-8" `
  --data-binary "@reports\_search_body.json"

# 方式 B — Python 一行（.venv 已激活时）
python -c "import json,urllib.request as u; q='P-101 出口压力正常范围'; b=json.dumps({'query':q,'mode':'hybrid_rerank','top_k':5},ensure_ascii=False).encode(); print(u.urlopen(u.Request('http://localhost:8080/v1/search',data=b,headers={'Content-Type':'application/json'})).read().decode())"

# 10 题 golden 对比 vector / bm25 / hybrid / hybrid_rerank / router
python scripts/verify_m2.py --write-evolution
```

若报 `WinError 10055`（套接字缓冲区满）：多为反复 curl/uvicorn 后 Windows 端口耗尽。先释放再重跑：

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 30
python scripts/verify_m2.py --write-evolution
```

仍失败则重启 Windows 后再跑。`coroutine 'run_all' was never awaited` 是连带警告，可忽略。

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 30
python scripts/verify_m2.py --write-evolution
```

仍失败则重启 Windows 后再跑。`coroutine 'run_all' was never awaited` 是连带警告，可忽略。

通过：`hybrid_rerank` Recall@5 ≥ 8/10。报告见 `reports/m2_verify.json`。

### 3.7.2 M3 Agent 验收

> **学习文档**：[m3_agent.md](./m3_agent.md)（管道流程图、多轮 history、拒答、exclusive 检索、verify 参数）。

前提：**vLLM 已起**（§3.5）+ **Gateway 已起**（§3.6）。本机 **勿改** 检索 `release_embedder` / `release_reranker`（16GB 上防 OOM）；慢是预期，用加长超时与分 case 验收即可。

```powershell
# Gateway 建议单 worker，避免多进程各载一份 CPU 模型
uvicorn apps.gateway.main:app --host 0.0.0.0 --port 8080

# 单条 chat 自测
@'
{"session_id":"test1","query":"P-101 出口压力正常范围是多少？"}
'@ | Set-Content -Path reports\_chat_body.json -Encoding utf8NoBOM
curl.exe -X POST "http://localhost:8080/v1/chat" `
  -H "Content-Type: application/json; charset=utf-8" `
  --data-binary "@reports\_chat_body.json"

# 全量（单次 /v1/chat 默认 1200s 超时）
python scripts/verify_m3.py --write-report

# 仅 3 轮追问（Case2，连续 3 次 chat，最耗时）
python scripts/verify_m3.py --case 2 --write-report
# 等价：--case followup

# 单跑其它：--case 1 | --case 3  或  --case in_domain | out_of_corpus
```

通过：所选 case 均 PASS。报告见 `reports/m3_verify.json`；聊天只贴汇总行。全量 3/3 时约 5 次 chat，总耗时可达十余分钟，属正常。

### 3.7.3 M4 Serving / Router 验收

> **用户操作（最短路径）**：[m4_user_runbook.md](./m4_user_runbook.md) — vLLM/TRT 压测、NGC 登录、k3d+KEDA 逐步命令。

前提：**vLLM 已起**（§3.5）。Gateway 可选（验 `/v1/llm/backends` 时需 **重启** uvicorn，见 runbook Phase 4）。

```powershell
# 配置 + router 探活（Gateway 未起时加 --skip-gateway）
python scripts/verify_m4.py --write-report

# 含 Gateway 后端列表 + 2 请求快速压测（需 vLLM）
python scripts/verify_m4.py --benchmark --write-report

# 正式压测并回填 docs/serving_benchmark.md（vLLM）
python scripts/benchmark_serving.py --backend vllm --concurrency 2 --requests 4 --update-doc
```

**TRT-LLM**：须先停 vLLM、编译 engine（见 `serving/tensorrt-llm/README.md`，**高本机成本须拍板**），再跑 `--backend tensorrt_llm`。

通过：`verify_m4` profile/router 用例 PASS；`serving_benchmark.md` 至少 vLLM 行有数据。报告见 `reports/m4_verify.json`。

### 3.8 RAGAS 评测（实现后，你代劳跑）

```powershell
copy data\eval\golden.jsonl.example data\eval\golden.jsonl
python pipelines/evaluation/run_ragas.py --golden data/eval/golden.jsonl --output reports/ragas_report.json
```

**省 token**：把 `reports/ragas_report.json` 留在磁盘；聊天只贴 **汇总 5 个指标数字**。

### 3.9.0 本机 20 分钟迷你 epoch（6GB，推荐）

> **全文**：[m5_finetune.md](./m5_finetune.md) §11（三个 JSONL 含义、流程图、基座说明见同文档 §2.1、§3）。  
> **Profile**：`dev-finetune-mini`（512 seq、grad_accum=2，防 OOM）。  
> **6GB 说明**：下载 ~15GB **磁盘**；训练时 4bit 加载约 **5～6GB 显存**，**须先停 vLLM**。本档目标为 **迷你 epoch 链路验收**（非完整多 epoch）；完整训练见 §3.9.2 / [m5_online_train.md](./m5_online_train.md)。下载前先做步骤 1～3，再步骤 4 预下载、步骤 5 冒烟。

```powershell
cd d:\repo\RAG
.\.venv\Scripts\Activate.ps1

# --- 步骤 1：划分 + 无 GPU 验收 ---
python scripts\split_sft_by_doc_id.py `
  --input data\processed\sft.jsonl `
  --train-out data\processed\sft_train.jsonl `
  --holdout-out data\processed\sft_holdout.jsonl `
  --holdout-doc-ids pump_p101_manual.md
python scripts\verify_m5.py --write-report
python scripts\init_ragas_reports.py --phase before

# --- 步骤 2：停 vLLM（Ctrl+C 或 docker stop）---
# docker ps --format "{{.ID}} {{.Image}}" | findstr vllm
# docker stop <容器ID>

# --- 步骤 3：dry-run ---
python pipelines\finetune\train_qlora.py `
  --profile dev-finetune-mini `
  --dataset data\processed\sft_train.jsonl `
  --dry-run

# --- 步骤 3b（下载后，步骤 5）— 10 step 冒烟，确认 6GB 不 OOM ---
python pipelines\finetune\train_qlora.py `
  --profile dev-finetune-mini `
  --max-steps 10 `
  --dataset data\processed\sft_train.jsonl `
  --output-dir models\qlora-adapter-smoke

# --- 步骤 4：训练（约 10～20 分钟，模型已缓存时）---
python pipelines\finetune\train_qlora.py `
  --profile dev-finetune-mini `
  --dataset data\processed\sft_train.jsonl `
  --output-dir models\qlora-adapter `
  --num-train-epochs 1

# --- 步骤 5：RAGAS 占位对比（M6 前用 --fill-example）---
python scripts\init_ragas_reports.py --phase before --fill-example
python scripts\init_ragas_reports.py --phase after --fill-example
python scripts\compare_ragas.py
python scripts\verify_m5.py --check-ragas --write-report
```

可选预下载训练基座（~15GB 磁盘，首次可能 >20 分钟）：**先完成步骤 1～3 并停 vLLM**，再按 [m5_finetune.md](./m5_finetune.md) §11 步骤 4（**勿设** `HF_ENDPOINT=hf-mirror.com`）。

### 3.9 QLoRA 训练（M5 通用）

> **学习文档**：[m5_finetune.md](./m5_finetune.md)。

```powershell
copy data\processed\sft.jsonl.example data\processed\sft.jsonl
# 先停 vLLM / Docker 释放 GPU（与 M4 分时）
python pipelines/finetune/train_qlora.py --dry-run
python pipelines/finetune/train_qlora.py --dataset data/processed/sft.jsonl --output-dir models/qlora-adapter
# 冒烟（数分钟级，仍须 GPU）：
python pipelines/finetune/train_qlora.py --profile dev-finetune-mini --max-steps 10 `
  --dataset data/processed/sft_train.jsonl --output-dir models/qlora-adapter
```

**省 token**：训练曲线用本地 tensorboard/wandb；别让 Agent 解读 200 行 epoch log。

### 3.9.1 M5 验收

```powershell
python scripts/verify_m5.py --write-report
pytest tests/test_finetune_m5.py -q
```

RAGAS 前后对比（M6 实装前可手写 `reports/ragas_*.json` 五指标）：

```powershell
python pipelines/evaluation/run_ragas.py --golden data/eval/golden.jsonl --output reports/ragas_before.json
# 训练 + 加载 adapter 后
python pipelines/evaluation/run_ragas.py --golden data/eval/golden.jsonl --output reports/ragas_after.json
python scripts/verify_m5.py --check-ragas --write-report
```

通过：`verify_m5` 无 GPU 用例全 PASS；完整闭环见 [m5_finetune.md](./m5_finetune.md) §9。

### 3.9.2 M5 线上完整 Epoch（不在 6GB 本机跑）

> **步骤全文**：[m5_online_train.md](./m5_online_train.md)（推荐 **AutoDL RTX 4090 24GB** + profile `train-gpu-24g`）。

本机准备：

```powershell
python scripts/split_sft_by_doc_id.py --input data/processed/sft.jsonl `
  --train-out data/processed/sft_train.jsonl --holdout-out data/processed/sft_holdout.jsonl
python scripts/init_ragas_reports.py --phase before
python scripts/prepare_m5_online_bundle.py
```

线上（SSH 到 GPU 机后，节选）：

```bash
# 勿设 HF_ENDPOINT=hf-mirror.com（huggingface_hub ≥1.17 不兼容）；国内慢可试 ModelScope，见 m5_finetune.md §11 步骤 4
export HF_HOME=/root/autodl-tmp/hf-cache

python pipelines/finetune/train_qlora.py --profile train-gpu-24g \
  --dataset data/processed/sft_train.jsonl --output-dir models/qlora-adapter
tar czvf qlora-adapter.tgz -C models qlora-adapter
```

回传后：`init_ragas_reports.py --phase after`（或真 RAGAS）→ `compare_ragas.py` → `verify_m5.py --check-ragas`。

### 3.10 查看 profile（无需 Agent）

```powershell
python scripts/load_profile.py dev-single-node
```

### 3.11 M6 — RAGAS / 验收 / 一键 Helm

> **学习文档**：[m6_eval.md](./m6_eval.md)。

```powershell
# CI 等价 dry-run（无 Gateway）
python pipelines\evaluation\run_ragas.py --dry-run --golden data\eval\golden.jsonl.example

# M6 脚手架验收
python scripts\verify_m6.py --write-report
pytest tests\test_ragas_m6.py -q

# 真 RAGAS（须 Gateway + vLLM 就绪，大规模须拍板）
copy data\eval\golden.jsonl.example data\eval\golden.jsonl
python pipelines\evaluation\run_ragas.py --golden data\eval\golden.jsonl --gateway http://localhost:8080

# Helm 一键（k3d + GPU）
.\scripts\one_click_k8s.ps1
```

**省 token**：指标摘要留在 `reports/ragas_report.json`；聊天只贴五指标数字。

---

## 4. 省 Token 节点提醒（Agent 必须主动提示）

在以下**节点**，Agent 应 **先提醒**再动作（即使用户未开口）：

| 节点 | 提醒话术（示例） |
|------|------------------|
| 开始新里程碑 | 「建议开新对话 + 小结模式；本步只做 Mx.y，是否继续？」 |
| 即将读多个文件 | 「将读 N 个文件，约 X KB 上下文；可改为你本地跑命令，我只改 1 个文件」 |
| 即将跑长命令 | 「输出将写入 `reports/`，聊天只回摘要，是否同意？」 |
| 测试/ingest 失败 | 「请贴最后 30 行或 `reports/*.log` 路径，勿贴全文」 |
| 评测/对比多配置 | 「矩阵评测建议你本地跑 §3.8；我根据 JSON 摘要改代码」 |
| 探索大型外仓 | 「通读 RAGFlow 极费 token；改为指定文件路径或官方文档链接」 |
| 单次回复变长 | 「已超 200 字，详细内容在 `docs/...`，需要展开哪一节？」 |
| 线程已很长 | 「建议新开会话，携带 `AGENTS.md` + 当前 M 编号」 |

**用户固定口令**（可直接复制）：

- `小结模式` — 聊天 ≤5 行，详情写文件  
- `本步范围：仅 <路径或模块>` — 禁止广搜  
- `日志见 reports/，不要贴 stdout`  
- `我本地跑，你改代码` — Agent 给 diff 方案，不代执行长命令  

---

## 5. Agent 回复格式（默认）

1. **结论**（1–3 句）  
2. **变更文件**（路径列表）  
3. **你若需本地执行**（仅当本节 §3 相关命令，可复制）  
4. **下一拍板项**（若有，一句话）  

避免：重复 PROJECT_PLAN、贴长 diff 讲解、逐行解释 obvious 代码。

---

## 6. 用户环境摘要

- GPU：RTX 3060 6GB | RAM：16GB | CPU：Ryzen 7 5800H  
- 领域：工业运维，中文  
- Profile：`dev-single-node`（见 `deploy/profiles/dev-single-node.yaml`）

---

## 7. 与「本机成本」的关系

| 事项 | 对话 token | 本机成本 |
|------|------------|----------|
| 下载 7B 模型 | 低（你代劳 §3.4） | 磁盘/带宽 |
| vLLM 常开 | 低 | GPU/电 |
| Agent 实现 M1 全模块 | **高** | 低 |
| 你跑 ingest + Agent 改 1 文件 | **低** | 中 |

**原则**：能 **你跑命令 + Agent 改少量文件** 的，优先该组合。
