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

```powershell
cd d:\repo\RAG
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

**省 token**：依赖问题把 `pip install` 最后 20 行错误贴过来即可，不要贴全文 log。

### 3.2 中间件（Compose）

```powershell
cd d:\repo\RAG
docker compose -f deploy/compose/docker-compose.yml up -d
docker compose -f deploy/compose/docker-compose.yml ps
```

验证：浏览器或 `curl http://localhost:9200`（OpenSearch）、Milvus `19530`。

**省 token**：只回复 `ps` 里 unhealthy 的行，不要贴 `docker compose logs` 全文（可先本地 `logs --tail 50`）。

### 3.3 下载模型（HF）

```powershell
.\.venv\Scripts\activate
pip install -U "huggingface_hub[cli]"
# 需先在 hf.co 设置 token: huggingface-cli login

huggingface-cli download Qwen/Qwen2.5-7B-Instruct-AWQ --local-dir d:\repo\RAG\models\Qwen2.5-7B-Instruct-AWQ
huggingface-cli download BAAI/bge-m3 --local-dir d:\repo\RAG\models\bge-m3
huggingface-cli download BAAI/bge-reranker-v2-m3 --local-dir d:\repo\RAG\models\bge-reranker-v2-m3
```

**省 token**：下载进度在本地看；找 Agent 时只说「下完了」或「报错最后一行」。

### 3.4 启动 vLLM（7B-AWQ，对齐 profile）

```powershell
.\.venv\Scripts\activate
pip install vllm
# GPU 占用期间不要同时跑 QLoRA / TRT build

vllm serve d:\repo\RAG\models\Qwen2.5-7B-Instruct-AWQ `
  --quantization awq `
  --gpu-memory-utilization 0.88 `
  --max-model-len 4096 `
  --max-num-seqs 2 `
  --max-num-batched-tokens 2048 `
  --port 8000
```

另开终端测一条：

```powershell
curl http://localhost:8000/v1/models
```

**省 token**：vLLM 启动日志 **不要**贴满；OOM 只贴含 `CUDA out of memory` 的 ~15 行。

### 3.5 Gateway（自测）

```powershell
cd d:\repo\RAG
.\.venv\Scripts\activate
uvicorn apps.gateway.main:app --host 0.0.0.0 --port 8080
```

```powershell
curl http://localhost:8080/v1/health
```

### 3.6 小样本 Ingest（≤20 文档，你代劳）

```powershell
cd d:\repo\RAG
# 把 PDF/MD 放进 data\raw\
.\.venv\Scripts\activate
python pipelines/ingest/run_ingest.py --input data/raw --batch-size 10
```

实现完成后才有完整逻辑；此前仅 scaffold。输出重定向省 token：

```powershell
python pipelines/ingest/run_ingest.py --input data/raw 2>&1 | Tee-Object -FilePath reports\ingest_last.log
```

找 Agent：「`ingest_last.log` 最后 30 行 + 现象一句话」。

### 3.7 RAGAS 评测（实现后，你代劳跑）

```powershell
copy data\eval\golden.jsonl.example data\eval\golden.jsonl
python pipelines/evaluation/run_ragas.py --golden data/eval/golden.jsonl --output reports/ragas_report.json
```

**省 token**：把 `reports/ragas_report.json` 留在磁盘；聊天只贴 **汇总 5 个指标数字**。

### 3.8 QLoRA 训练（实现后，训练前关掉 vLLM）

```powershell
# 先停 vLLM 进程释放 GPU
python pipelines/finetune/train_qlora.py --dataset data/processed/sft.jsonl --output-dir models/qlora-adapter
```

**省 token**：训练曲线用本地 tensorboard/wandb；别让 Agent 解读 200 行 epoch log。

### 3.9 K8s / Helm（可选，日志本地化）

```powershell
k3d cluster create industrial-rag --agents 1
kubectl get pods -A
helm upgrade --install ior ./deploy/helm/industrial-ops-rag `
  -f ./deploy/helm/industrial-ops-rag/values-dev-single-node.yaml `
  -n industrial-ops --create-namespace
```

**省 token**：`kubectl describe pod <name>` 的 Events 段 + `logs --tail=40` 即可。

### 3.10 查看 profile（无需 Agent）

```powershell
python scripts/load_profile.py dev-single-node
```

---

## 4. 省 Token 节点提醒（Agent 必须主动提示）

在以下**节点**，Agent 应 **先提醒**再动作（即使用户未开口）：

| 节点 | 提醒话术（示例） |
|------|------------------|
| 开始新里程碑 | 「建议开新对话 + 小结模式；本步只做 Mx.y，是否继续？」 |
| 即将读多个文件 | 「将读 N 个文件，约 X KB 上下文；可改为你本地跑命令，我只改 1 个文件」 |
| 即将跑长命令 | 「输出将写入 `reports/`，聊天只回摘要，是否同意？」 |
| 测试/ingest 失败 | 「请贴最后 30 行或 `reports/*.log` 路径，勿贴全文」 |
| 评测/对比多配置 | 「矩阵评测建议你本地跑 §3.7；我根据 JSON 摘要改代码」 |
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
| 下载 7B 模型 | 低（你代劳 §3.3） | 磁盘/带宽 |
| vLLM 常开 | 低 | GPU/电 |
| Agent 实现 M1 全模块 | **高** | 低 |
| 你跑 ingest + Agent 改 1 文件 | **低** | 中 |

**原则**：能 **你跑命令 + Agent 改少量文件** 的，优先该组合。
