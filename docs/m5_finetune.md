# M5 — QLoRA 微调与 RAG/SFT 对比

> **学习入口**：微调流程、参数、验收集中在此。  
> **操作命令**：[COLLABORATION.md](./COLLABORATION.md) §3.9、§3.9.1。  
> **线上完整 Epoch**：[m5_online_train.md](./m5_online_train.md)（**推荐 AutoDL 4090 24GB**）。  
> **Serving**（M4）：训练前须停 vLLM，见 [m4_serving.md](./m4_serving.md) §3.2。  
> **踩坑日记**：[finetune_pitfalls.md](./finetune_pitfalls.md)。

---

## 1. M5 解决什么问题？

| 里程碑 | 关注点 |
|--------|--------|
| **M4** | 纯 LLM 推理吞吐、Router、KEDA |
| **M5** | 领域 **SFT/QLoRA**；对比「只改模型」vs「只改 RAG」 |
| **M6** | RAGAS CI、完整评测流水线 |

M5 **不替代** M3 问答验收；验收重点是 **训练可跑通 + 文档化风险 + RAGAS 前后**。

### 1.1 M5「完整」分两档

| 档位 | 在哪里做 | 内容 |
|------|----------|------|
| **本地完整** | 6GB Windows | 数据划分、无 GPU 验收、**迷你 epoch**（`dev-finetune-mini`）、RAGAS 对比、adapter 产出 |
| **训练完整** | **线上 24GB** | `train-gpu-24g` 跑满 epoch → `qlora-adapter.tgz` 回传 → 再 RAGAS after |

本机用 **§11 迷你 epoch**（约 20 分钟、防 OOM）；**完整多 epoch** 见 [m5_online_train.md](./m5_online_train.md)。

---

## 2. 模块与文件地图

```
pipelines/finetune/train_qlora.py      ← QLoRA 训练（profile 驱动）
scripts/generate_sft_from_corpus.py    ← 从 data/raw 批量生成 SFT
data/processed/sft.jsonl               ← 全量语料（你维护）
data/processed/sft_train.jsonl         ← 真正拿去训练
data/processed/sft_holdout.jsonl       ← 留出、禁止进训练
data/processed/sft.jsonl.example       ← 格式样例
deploy/profiles/dev-single-node.yaml     ← 默认 finetune 超参
deploy/profiles/dev-finetune-mini.yaml   ← 6GB 迷你 epoch（防 OOM）
deploy/profiles/train-gpu-24g.yaml       ← 线上 24GB
scripts/verify_m5.py                     ← M5 验收（无 GPU）
scripts/split_sft_by_doc_id.py           ← 按 doc_id 划分
scripts/init_ragas_reports.py            ← RAGAS 前后 JSON 模板
scripts/compare_ragas.py                 ← 对比 before/after
docs/m5_online_train.md                  ← 线上 4090 完整 epoch
pipelines/finetune/merge_lora.py         ← merge adapter（大显存）
docs/finetune_pitfalls.md                ← 踩坑日记
pipelines/evaluation/run_ragas.py        ← 评测（M6 实装）
```

### 2.1 三个 JSONL 各干什么？（一句话）

| 文件 | 通俗理解 |
|------|----------|
| **`sft.jsonl`** | **题库全集** — 样例 + 生成的所有问答，你编辑、追加都在这里 |
| **`sft_train.jsonl`** | **真正用来上课的题** — 从全集按 `doc_id` 切出来，**喂给 QLoRA** |
| **`sft_holdout.jsonl`** | **期末模拟题（不能偷看）** — 指定 `doc_id` 整篇留出，**不进训练**，用来对照 RAGAS / 人工看是否「背题」 |

类比：全集 = 教材所有习题；train = 学生能见的练习册；holdout = 封存试卷（默认留出 `pump_p101_manual.md` 相关题，避免和 golden 评测重叠）。

---

## 3. 流程图

### 3.0 SFT / 微调端到端（M5）

```mermaid
flowchart TD
    subgraph data [1 数据 — 不占 GPU]
        Raw[data/raw 运维文档]
        Gen[generate_sft_from_corpus.py]
        All[sft.jsonl 全集]
        Split[split_sft_by_doc_id.py]
        TrainDS[sft_train.jsonl]
        Hold[sft_holdout.jsonl]
        Raw --> Gen --> All --> Split
        Split --> TrainDS
        Split --> Hold
    end

    subgraph nvidia [2 训练 — 独占 GPU]
        Stop[停 vLLM Docker]
        QL[train_qlora.py + dev-finetune-mini]
        Adp[models/qlora-adapter]
        Stop --> QL
        TrainDS --> QL --> Adp
    end

    subgraph eval [3 验收 —  mostly 无 GPU]
        V5[verify_m5.py]
        RBefore[ragas_before.json]
        RAfter[ragas_after.json]
        Cmp[compare_ragas.py]
        V5 --> RBefore
        Adp --> RAfter
        RBefore --> Cmp
        RAfter --> Cmp
    end

    subgraph infer [4 推理 — 与 M4 分时]
        VLLM[重启 vLLM AWQ]
        RAG[M3 Agent + M2 检索]
        Adp -.->|merge 或 enable-lora| VLLM
        VLLM --> RAG
    end
```

### 3.1 训练与推理分工

```mermaid
flowchart LR
    subgraph train [训练阶段 — 独占 GPU]
        StopVLLM[停 vLLM / scale 0]
        SFT[sft.jsonl]
        QLoRA[train_qlora.py]
        Adapter[models/qlora-adapter]
        StopVLLM --> QLoRA
        SFT --> QLoRA --> Adapter
    end
    subgraph infer [推理阶段 — 与 M4 衔接]
        Load[加载 AWQ 基座 + LoRA 或 merge]
        VLLM[vLLM OpenAI API]
        RAG[M3 Agent + M2 检索]
        Load --> VLLM --> RAG
    end
    Adapter -.-> Load
```

### 3.2 训练基座 vs 推理基座（为什么不能同一个？）

| | **训练基座** | **推理基座** |
|--|--------------|--------------|
| **仓库里是谁** | `Qwen/Qwen2.5-7B-Instruct`（HF 全精度名） | `Qwen2.5-7B-Instruct-AWQ`（vLLM 挂载的 AWQ 权重） |
| **干什么** | 在 4bit 上挂 LoRA，**只更新 adapter 小矩阵** | **高吞吐在线答题**（M3/M4 Gateway） |
| **显存策略** | `bitsandbytes` 4bit + checkpoint，6GB 能训 | AWQ/Marlin 压缩权重，6GB 能推 |

**不能混用的原因**（见 [finetune_pitfalls.md](./finetune_pitfalls.md) #7）：

1. **QLoRA 训练**要在「可反传的全精度计算图 + 4bit 加载」上做；AWQ 已是推理专用量化格式，**不能再当训练底座**。  
2. **vLLM + AWQ** 为推理优化，**不承载** HuggingFace `Trainer` 那套训练循环。  
3. 产物是 **LoRA adapter**；要接到 AWQ 推理上，需 **merge 后再量化**，或换 **非 AWQ 基座 + `--enable-lora`**。

口诀：**训练用 HF 全精度名，推理用 AWQ 服务；中间靠 adapter 文件衔接。**

### 3.3 RAG vs SFT 对比（M5 验收意图）

```mermaid
flowchart TD
    Base[同一 golden 集]
    Base --> R0[RAGAS baseline — 仅 RAG]
    R0 --> PathA[路径 A: 只跑 QLoRA]
    PathA --> R1[RAGAS after SFT]
    Base --> PathB[路径 B: 只调检索/提示 — 可选]
    R1 --> Compare{指标是否提升?}
    Compare -->|faithfulness 升、检索不变| SFT有效
    Compare -->|无提升| 优先改 RAG 或数据量
```

---

## 4. SFT 数据格式

`data/processed/sft.jsonl`：每行一条 JSON。

| 字段 | 必填 | 说明 |
|------|------|------|
| `messages` | 二选一 | `[{role, content}, ...]` 对话，须含 assistant |
| `instruction` + `output` | 二选一 | 简写指令对；可选 `input` |
| `doc_id` | 推荐 | 划分 train/eval，**防评测泄漏**（见 pitfalls #5） |

复制样例：

```powershell
copy data\processed\sft.jsonl.example data\processed\sft.jsonl
```

---

## 5. Profile 参数（`finetune.*`）

| Profile | 用途 | `max_seq_length` | `gradient_accumulation_steps` |
|---------|------|------------------|-------------------------------|
| `dev-single-node` | 默认开发 | 2048 | 16 |
| **`dev-finetune-mini`** | **6GB 本机迷你 epoch** | **512** | **2** |
| `train-gpu-24g` | 线上 4090 完整训练 | 4096 | 8 |

| 字段 | 含义 |
|------|------|
| `base_model` | 训练基座：本机推荐 `models/Qwen2.5-7B-Instruct`（`hf download --local-dir`）；线上可用 Hub 名 |
| `qlora_r` / `qlora_alpha` | LoRA 秩 / 缩放 |
| `per_device_train_batch_size` | 单卡 micro-batch |
| `gradient_checkpointing` + `bnb_4bit` | 6GB 必开 |
| `num_train_epochs` | 小样本保持 1 |

---

## 6. 训练 CLI

| 参数 | 默认 | 说明 |
|------|------|------|
| `--dry-run` | off | 只校验 profile + JSONL |
| `--dataset` | `data/processed/sft.jsonl` | 训练集路径 |
| `--output-dir` | `models/qlora-adapter` | adapter 输出 |
| `--max-samples` | profile 上限 | 调试截断 |
| `--max-steps` | - | 覆盖 epoch，冒烟训练 |
| `--profile` | `IOR_PROFILE` | 本机迷你 epoch 用 **`dev-finetune-mini`** |

---

## 7. 验收 `verify_m5.py`

### 7.1 「无 GPU 验收」是什么意思？

**不启动 QLoRA 训练、不占 CUDA**，只检查「训练前该齐的东西是否齐了」：

- profile 里 `finetune.*` 字段齐全  
- SFT JSONL 能解析、格式合法  
- `train_qlora.py --dry-run` 能退出 0（只读数据 + 配置）  
- 踩坑文档、Helm Job 模板存在  

适合在 **停 vLLM 之前 / 下载模型之前** 先跑一遍，避免白占 GPU 才发现数据写错。

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\verify_m5.py --write-report
python scripts\verify_m5.py --dataset data\processed\sft.jsonl --write-report
```

| 用例 | 验证什么 |
|------|----------|
| profile_finetune | `finetune.*` 关键字段存在 |
| sft_example | `sft.jsonl.example` 可解析 |
| sft_train.jsonl | 已划分训练集 |
| train_dry_run | `train_qlora.py --dry-run` 退出 0 |
| pitfalls_doc | `finetune_pitfalls.md` ≥8 条 |
| helm_train_job | Helm Job 模板存在 |
| ragas_compare | **可选**；见 §7.2 |

### 7.2 RAGAS 前后 JSON 对比是干什么的？

M6 之前没有强制跑真 RAGAS 流水线时，用两个 JSON 文件记录 **同一 golden 集** 上、**微调前后** 五个指标的数值：

| 文件 | 含义 |
|------|------|
| `reports/ragas_before.json` | 只有 RAG + 原模型（未挂 adapter） |
| `reports/ragas_after.json` | 同一套题，训练后 / 挂 adapter 再测 |

`compare_ragas.py` 打印 before / after / **delta**，回答：**「只改模型（SFT）有没有让 faithfulness 等变好？」**  
若检索没变、生成指标却涨 → SFT 有效；若没涨 → 优先加数据或改 RAG（见 §3.3）。

占位生成（指标可先为 `null`，训练后手填或跑真 RAGAS）：

```powershell
python scripts\init_ragas_reports.py --phase before
# 训练完成后
python scripts\init_ragas_reports.py --phase after
python scripts\compare_ragas.py
python scripts\verify_m5.py --check-ragas --write-report
```

**完整 M5 闭环（含 GPU 训练）**：§11 → 再 `ragas_after` → `compare_ragas` → `evolution.md` 记一行。

---

## 8. K8s Train Job

`finetune.trainJob.enabled: true` 时 apply Job（**须** 集群 GPU + 含依赖的镜像）。默认 `values-dev-single-node.yaml` 为 `false`；与 vLLM **分时**调度。

---

## 9. M5 验收清单

**本地（必做）**

- [ ] `split_sft_by_doc_id.py` → `sft_train.jsonl` / `sft_holdout.jsonl`  
- [ ] `python scripts/verify_m5.py --write-report` → 全 PASS  
- [ ] `pytest tests/test_finetune_m5.py`  

**线上（训练完整）**

- [ ] [m5_online_train.md](./m5_online_train.md)：`train-gpu-24g` 完整 epoch  
- [ ] `qlora-adapter.tgz` 回传到 `models/qlora-adapter`  

**闭环（回传后）**

- [ ] `init_ragas_reports.py` before/after（或真 RAGAS）→ `compare_ragas.py`  
- [ ] `verify_m5.py --check-ragas` → `evolution.md` 追加一行  
- [ ] 新踩坑写入 `finetune_pitfalls.md`

---

## 10. 与 M4/M6 的分工

| | M4 | M5 | M6 |
|--|----|----|-----|
| GPU | vLLM 推理 | QLoRA 训练 | RAGAS CronJob |
| 文档 | `m4_serving.md` | 本文 | RAGAS CI + 一键 Helm |

---

## 11. 本机 20 分钟迷你 epoch（分步命令）

> **目标**：6GB 单卡、**不 OOM**、产出 `models/qlora-adapter/`（验证链路，非生产效果）。  
> **Profile**：`dev-finetune-mini`（`max_seq_length=512`，`gradient_accumulation_steps=2`）。  
> **数据**：`sft_train.jsonl`（不要用 holdout 训练）。  
> **操作副本**：[COLLABORATION.md](./COLLABORATION.md) §3.9.0。

### 前提

- 已安装 `.venv`（Python 3.12）  
- 训练前 **必须停** 占用 GPU 的 vLLM 容器  
- 首次训练会下载 `Qwen/Qwen2.5-7B-Instruct`（~15GB **磁盘**），**可能超过 20 分钟**；建议步骤 1～3 通过后再做步骤 4 预下载

### 下载前确认（6GB 必看）

| 项目 | 说明 |
|------|------|
| **下载体积** | ~15GB **硬盘**（HF 权重文件），不是占满 15GB 显存 |
| **训练显存** | `bnb_4bit` + LoRA + `max_seq_length=512` 峰值约 **5～6GB**；与 vLLM AWQ 推理同级，**须独占 GPU** |
| **本机能做什么** | **`dev-finetune-mini` 迷你 epoch**（链路验收、产出 adapter）；**完整多 epoch / 4096 seq** 见 [m5_online_train.md](./m5_online_train.md) |
| **风险** | RTX 3060 6GB 为 **边界配置**；vLLM AWQ 已实测，QLoRA 迷你 epoch 按 profile 设计但峰值仍可能 OOM → 见文末降级项 |
| **建议顺序** | 步骤 1 → 2 停 vLLM → 3 dry-run → **4 预下载** → **5 冒烟 10 step** → 6 迷你 epoch |

### 步骤 1 — 数据与无 GPU 验收

```powershell
cd d:\repo\RAG
.\.venv\Scripts\Activate.ps1

python scripts\split_sft_by_doc_id.py `
  --input data\processed\sft.jsonl `
  --train-out data\processed\sft_train.jsonl `
  --holdout-out data\processed\sft_holdout.jsonl `
  --holdout-doc-ids pump_p101_manual.md

python scripts\verify_m5.py --write-report
pytest tests\test_finetune_m5.py tests\test_split_sft_m5.py -q

python scripts\init_ragas_reports.py --phase before
```

### 步骤 2 — 释放 GPU（停 vLLM）

在跑 vLLM 的终端 **Ctrl+C**，或：

```powershell
docker ps --format "{{.ID}} {{.Image}}" | findstr vllm
docker stop <上一步看到的容器ID>
```

确认 GPU 空闲（可选）：

```powershell
nvidia-smi
```

### 步骤 3 — 训练前 dry-run（仍不占训练显存）

```powershell
cd d:\repo\RAG
.\.venv\Scripts\Activate.ps1

python pipelines\finetune\train_qlora.py `
  --profile dev-finetune-mini `
  --dataset data\processed\sft_train.jsonl `
  --dry-run
```

### 步骤 4 — 预下载训练基座（可选）

> **前置**：步骤 1～3 已通过；vLLM 已停。  
> **勿设** `HF_ENDPOINT=https://hf-mirror.com`：`huggingface_hub` ≥1.17 经镜像 HEAD 拿不到 `commit_hash`，会报 `FileMetadataError`。本机若可直连 `huggingface.co`，直接下载即可。

```powershell
cd d:\repo\RAG
.\.venv\Scripts\Activate.ps1
Remove-Item Env:HF_ENDPOINT -ErrorAction SilentlyContinue
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"   # Windows 无 symlink 时可消警告

.\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen2.5-7B-Instruct')"
```

或指定本地目录：

```powershell
Remove-Item Env:HF_ENDPOINT -ErrorAction SilentlyContinue
hf download Qwen/Qwen2.5-7B-Instruct --local-dir d:\repo\RAG\models\Qwen2.5-7B-Instruct
```

直连失败时可用 ModelScope（国内备选）：

```powershell
pip install modelscope
python -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen2.5-7B-Instruct', cache_dir=r'd:\repo\RAG\models')"
```

### 步骤 5 — 冒烟 10 step（下载后，确认 6GB 不 OOM）

```powershell
python pipelines\finetune\train_qlora.py `
  --profile dev-finetune-mini `
  --max-steps 10 `
  --dataset data\processed\sft_train.jsonl `
  --output-dir models\qlora-adapter-smoke
```

通过后再做步骤 6；若 `CUDA out of memory`，见文末 OOM 降级项，**不要**直接跑满 epoch。

### 步骤 6 — 迷你 epoch 训练

```powershell
cd d:\repo\RAG
.\.venv\Scripts\Activate.ps1

python pipelines\finetune\train_qlora.py `
  --profile dev-finetune-mini `
  --dataset data\processed\sft_train.jsonl `
  --output-dir models\qlora-adapter `
  --num-train-epochs 1
```

若仍担心显存或时间，步骤 5 的 `--max-steps 10` 已足够验收链路；步骤 6 为完整 1 epoch。

成功标志：终端出现 `[done] adapter saved to ...`，目录下有 `adapter_config.json` 等。

### 步骤 7 — 恢复推理（重启 vLLM）

按 [m4_serving.md](./m4_serving.md) / [COLLABORATION.md](./COLLABORATION.md) §3.6 原命令启动 vLLM。  
**注意**：AWQ vLLM **不能** 直接加载 QLoRA；对比效果前需 merge 或 `enable-lora`（pitfalls #7）。

### 步骤 8 — RAGAS 占位与对比

```powershell
python scripts\init_ragas_reports.py --phase after
python scripts\compare_ragas.py
python scripts\verify_m5.py --check-ragas --write-report
```

### 6GB 本机训练失败时（放弃本机、改线上）

若冒烟/训练出现下列任一情况，**不必再调本机**，按 [m5_online_train.md](./m5_online_train.md) 在 **4090 24GB** 跑 `train-gpu-24g`：

- `Some modules are dispatched on the CPU or the disk`（`device_map=auto` 显存不够；profile 已改为 `single_gpu`，仍失败即硬件不够）
- `CUDA out of memory`
- `train_qlora.py` 退出码 `2` 且提示改走线上

本机 M5 **仍可完成**：数据划分、`verify_m5`、RAGAS 占位、adapter 从云上下载回传。

### OOM 时（仅当仍想赌本机）

1. 确认 vLLM 已停、`nvidia-smi` 显存空闲  
2. `dev-finetune-mini` 已含 `device_map: single_gpu`、`max_seq_length: 384`、`qlora_r: 4`  
3. 仍 OOM → **放弃本机训练**（见上）
