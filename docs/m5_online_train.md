# M5 线上完整 Epoch 训练（推荐方案）

> **目标**：6GB 本机只做数据/验收/回传；**完整 QLoRA epoch** 在 **24GB 单卡** 上跑。  
> **本地入口**：[m5_finetune.md](./m5_finetune.md)、[COLLABORATION.md](./COLLABORATION.md) §3.9。

---

## 1. 推荐方案（具体可行）

| 项 | 选择 | 原因 |
|----|------|------|
| **平台** | [AutoDL](https://www.autodl.com) 或同类（恒源云、矩池云） | 按小时租 GPU，支持 Jupyter/SSH，国内 HF 镜像方便 |
| **实例** | **1× RTX 4090 24GB**，CUDA 12.x | 7B QLoRA 2 epoch + `max_seq_length=4096` 宽裕；比 A10 便宜 |
| **镜像** | 官方 **PyTorch 2.x + CUDA 12**（勿选 6GB 入门机） | 与 `bitsandbytes` / `transformers` 兼容 |
| **训练配置** | Profile **`train-gpu-24g`** | 仓库已调好 batch/epoch，勿用本机 `dev-single-node` |
| **交付物** | `models/qlora-adapter/` 打包 `qlora-adapter.tgz` | SCP 回 Windows 后接 vLLM LoRA 或 merge |

**预估成本**：SFT 约 500～2000 条、2 epoch，磁盘拉模型约 15GB，训练 **1～3 小时**；4090 约 **¥2～4/小时** → 单次 **¥5～15**。

---

## 2. 本机先做（不占 GPU 训练）

```powershell
cd d:\repo\RAG
.\.venv\Scripts\Activate.ps1

# 1) 准备 SFT（从样例扩展或自有语料）
copy data\processed\sft.jsonl.example data\processed\sft.jsonl
# 按 doc_id 划分，避免评测泄漏
python scripts/split_sft_by_doc_id.py `
  --input data\processed\sft.jsonl `
  --train-out data\processed\sft_train.jsonl `
  --holdout-out data\processed\sft_holdout.jsonl `
  --holdout-doc-ids pump_p101_manual.md

# 2) 本地 M5 验收（无 epoch）
python scripts\verify_m5.py --write-report
pytest tests/test_finetune_m5.py -q

# 3) RAGAS 基线占位（微调前，有 Gateway 再跑真 RAGAS）
python scripts\init_ragas_reports.py --phase before

# 4) 打包上传清单（可选）
python scripts\prepare_m5_online_bundle.py
```

---

## 3. 线上：AutoDL 逐步（复制执行）

### 3.1 租机与登录

1. 创建实例：**RTX 4090 ×1**，磁盘 **≥50GB**，镜像 **PyTorch 2.3 / CUDA 12.1**。  
2. 开机后 **SSH** 或 **Jupyter 终端** 进入。

### 3.2 拉代码与数据

```bash
# 勿设 HF_ENDPOINT=hf-mirror.com（huggingface_hub ≥1.17 不兼容）；国内慢见 m5_finetune.md §11 步骤 4 ModelScope
export HF_HOME=/root/autodl-tmp/hf-cache

git clone <你的 RAG 仓库 URL> /root/RAG
cd /root/RAG

# 若本机已划分 train 集：用 scp / AutoDL 网盘上传到 data/processed/sft_train.jsonl
# 或直接在云上 copy example 再编辑
cp data/processed/sft.jsonl.example data/processed/sft_train.jsonl
```

本机上传示例（PowerShell，按 AutoDL 面板改 IP/端口）：

```powershell
scp -P <port> data\processed\sft_train.jsonl root@<host>:/root/RAG/data/processed/sft_train.jsonl
```

### 3.3 安装依赖

```bash
cd /root/RAG
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

### 3.4 完整 Epoch 训练（核心）

**方式 A — 直接 Python（推荐，日志最直观）**

```bash
cd /root/RAG
source .venv/bin/activate
export HF_HOME=/root/autodl-tmp/hf-cache

python pipelines/finetune/train_qlora.py \
  --profile train-gpu-24g \
  --dataset data/processed/sft_train.jsonl \
  --output-dir models/qlora-adapter
```

**方式 B — Docker Compose（环境一致）**

```bash
cd /root/RAG
docker compose -f deploy/compose/docker-compose.finetune.yml build
# 确保 data/processed/sft_train.jsonl 存在
docker compose -f deploy/compose/docker-compose.finetune.yml run --rm qlora-train
```

训练结束应看到 `[done] adapter saved to models/qlora-adapter`。

### 3.5 打包回传

```bash
cd /root/RAG
tar czvf /root/autodl-tmp/qlora-adapter.tgz -C models qlora-adapter
ls -lh /root/autodl-tmp/qlora-adapter.tgz
```

```powershell
# 本机
scp -P <port> root@<host>:/root/autodl-tmp/qlora-adapter.tgz d:\repo\RAG\models\
cd d:\repo\RAG\models
tar -xzf qlora-adapter.tgz
```

**关机释放 GPU**，避免持续计费。

---

## 4. 回本机后：推理与 M5 闭环

### 4.1 加载 LoRA（二选一）

| 方式 | 适用 | 命令/配置 |
|------|------|-----------|
| **vLLM + LoRA** | 24GB 或本机 AWQ 基座 + adapter | vLLM `--enable-lora --lora-modules qlora=/path/to/adapter`（基座需与训练同系列，见 pitfalls #7） |
| **Merge 全量** | 需额外 ~14GB 显存 merge | `python pipelines/finetune/merge_lora.py --dry-run` 后真 merge |

本机 6GB 建议：**云训练 + 云上用非 AWQ 7B + LoRA 做 RAGAS**，再把 `ragas_after.json` 拉回；或 merge 后在云上 AWQ 量化（进阶，M5 不强制）。

### 4.2 RAGAS 与验收

```powershell
# 微调后（Gateway + vLLM 已起且已挂 adapter）
python scripts\init_ragas_reports.py --phase after
# 或 M6 前：python pipelines/evaluation/run_ragas.py ...

python scripts\compare_ragas.py
python scripts\verify_m5.py --check-ragas --write-report
```

在 [evolution.md](./evolution.md) 追加一行（RAGAS F、备注「M5 online 4090」）。

---

## 5. 备选：自有 K8s GPU 节点（Helm Job）

若已有 **带 `nvidia.com/gpu` 的集群**（非 k3d 本机）：

1. 构建并推送 `industrial-ops-rag/finetune` 镜像（`Dockerfile.finetune`）。  
2. 将 `sft_train.jsonl` 放入 PVC / 对象存储。  
3. `values` 中 `finetune.trainJob.enabled: true`，`datasetPath` 指向挂载路径。  
4. Job 完成后从 PVC 取 `qlora-adapter`。

与本机 6GB **无关**；与 M4 k3d 学习集群 **分开**，避免 OOM。

---

## 6. 方案对比（为何不用 6GB 本机 epoch）

| | 本机 6GB | 线上 4090 24GB |
|--|----------|----------------|
| `max_seq_length` | 1024～2048 易 OOM | 4096 稳定 |
| `num_train_epochs` | 仅 `--max-steps` 冒烟 | 2 epoch 完整收敛 |
| 与 vLLM 并行 | 禁止 | 训练完再推理 |
| M5 定位 | dry-run + 文档 + 回传 | **正式 adapter** |

---

## 7. 检查清单

- [ ] 本机 `sft_train.jsonl` / `sft_holdout.jsonl` 已划分  
- [ ] 本机 `verify_m5.py` PASS  
- [ ] 线上 `train-gpu-24g` 完整 epoch 成功  
- [ ] `qlora-adapter.tgz` 已回传  
- [ ] `ragas_before` / `ragas_after` + `compare_ragas.py`  
- [ ] `evolution.md` 已追加  
