# M4 用户操作手册 — TRT-LLM 压测、K8s、KEDA

> 本机：**RTX 3060 6GB / 16GB RAM / Windows**；GPU 推理与 TRT **分时**，勿与 vLLM 同占。  
> 学习背景：[m4_serving.md](./m4_serving.md) | 命令索引：[COLLABORATION.md](./COLLABORATION.md) §3.7.3

---

## 0. 硬件与路径选择（先读）

| 能力 | 16GB + 6GB GPU | 建议 |
|------|----------------|------|
| **Compose + Docker vLLM + M1–M3** | 可以（已验证） | 日常开发主路径 |
| **TRT-LLM engine 编译 + 推理** | 可以，须 **停 vLLM**；编译约 1–3h，磁盘 **≥40GB** | WSL2 内做 |
| **k3d + KEDA + Helm 占位** | **可以**，但勿与 Compose **全量**同时满载 | WSL2；与 Compose **二选一占满 RAM** 或分时 |
| **K8s 内再跑全套 Milvus/OpenSearch + vLLM + 开发** | **不建议** 16GB 同时全开 | M6 前 Helm 子 chart 未全齐，当前 k3d 较轻 |

### 以后哪些里程碑 **必须** K8s？

| 里程碑 | K8s 是否必需 | 说明 |
|--------|--------------|------|
| M1–M4 日常 | **否** | Compose + 本机脚本可完成 |
| M4 KEDA | **架构必需，本机可不装** | profile + Helm 模板即可；要 **真跑 ScaledObject** 需 k3d + KEDA |
| M5 QLoRA | **否**（本机 `train_qlora.py`） | K8s Train Job 为生产路径 |
| **M6** | **是（验收向）** | 「Helm 一键、Grafana、RAGAS CI」假定集群环境 |
| M7 | 否 | Demo 可仍用 Compose |

**结论**：你现在装 k3d + KEDA **值得做**（为 M6 预热、M4 架构闭环），但 **M1–M5 日常开发不依赖**；16GB 上 **不要** Compose 全栈 + k3d 全栈 + vLLM 同时跑。

---

## 1. 补全 vLLM 行（若尚未填）

**Windows PowerShell**（vLLM Docker 已起 `:8000`）：

```powershell
cd d:\repo\RAG
.\.venv\Scripts\activate
python scripts/benchmark_serving.py --backend vllm --lite --update-doc
```

---

## 2. TRT-LLM 行（用户操作，WSL2 推荐）

TRT 与 vLLM **互斥**。全程在 **WSL2 Ubuntu** 内执行（GPU 透传）。Windows 侧先停 vLLM：

```powershell
docker ps --filter ancestor=vllm/vllm-openai:v0.6.6
docker stop <CONTAINER_ID>
```

### Step 2.1 — WSL2 前提

```bash
# WSL2 内
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
```

若无 GPU，先在 Windows 装 WSL2 + [NVIDIA CUDA on WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)。

> **驱动 546.x**：TRT-LLM 最新镜像可能要求更高驱动；若 `docker pull`/`run` 失败，改用较旧 tag（如 `nvcr.io/nvidia/tensorrt-llm/release:v0.16.0`），以 NVIDIA 文档为准。

### Step 2.2 — 拉 TRT-LLM 开发镜像（仅首次，体积大）

```bash
docker pull nvcr.io/nvidia/tensorrt-llm/release:latest
# 或固定 tag：nvcr.io/nvidia/tensorrt-llm/release:v0.16.0
```

### Step 2.3 — AWQ 权重 → TRT engine（6GB 保守参数）

模型已在 Windows 下载时，WSL 路径为 `/mnt/d/repo/RAG/models/Qwen2.5-7B-Instruct-AWQ`。

```bash
cd /mnt/d/repo/RAG
mkdir -p serving/tensorrt-llm/engines

docker run --gpus all --rm -it \
  -v /mnt/d/repo/RAG:/work \
  -w /work \
  nvcr.io/nvidia/tensorrt-llm/release:latest \
  bash
```

**容器内**（路径按 [TensorRT-LLM Qwen 文档](https://github.com/NVIDIA/TensorRT-LLM/blob/main/examples/models/core/qwen/README.md) INT4-AWQ 一节）：

```bash
# 1) AutoAWQ HF → TRT-LLM checkpoint
python examples/models/core/qwen/convert_checkpoint.py \
  --model_dir /work/models/Qwen2.5-7B-Instruct-AWQ \
  --output_dir /work/serving/tensorrt-llm/checkpoints/int4-awq

# 2) 编译 engine（6GB：batch=1，限制序列长度）
trtllm-build \
  --checkpoint_dir /work/serving/tensorrt-llm/checkpoints/int4-awq \
  --output_dir /work/serving/tensorrt-llm/engines/int4-awq-1gpu \
  --gemm_plugin float16 \
  --max_batch_size 1 \
  --max_input_len 2048 \
  --max_seq_len 2560 \
  --max_num_tokens 2048
```

编译 OOM：先 `--max_input_len 1024`，或关闭 Windows 其它占 GPU 进程。

### Step 2.4 — 启动 OpenAI 兼容服务（:8001）

仍在容器内，或新起容器：

```bash
docker run --gpus all --rm -d \
  --name trt-llm-serve \
  -p 8001:8000 \
  -v /mnt/d/repo/RAG:/work \
  nvcr.io/nvidia/tensorrt-llm/release:latest \
  trtllm-serve \
    --host 0.0.0.0 \
    --port 8000 \
    /work/serving/tensorrt-llm/engines/int4-awq-1gpu
```

> 若你的 TRT-LLM 版本 CLI 不同，改用该版本文档的 `trtllm-serve` / `mpirun` + `engine_dir` 示例；**验收标准**是 `curl http://localhost:8001/v1/models` 有响应。

WSL 内验证：

```bash
curl http://localhost:8001/v1/models
```

Windows 浏览器/curl 访问 `http://localhost:8001/v1/models`（WSL 端口转发通常可用）。

### Step 2.5 — 改 `.env` 并压测

**Windows** `d:\repo\RAG\.env`：

```ini
LLM_ACTIVE_BACKEND=tensorrt_llm
TENSORRT_LLM_BASE_URL=http://localhost:8001/v1
```

```powershell
cd d:\repo\RAG
.\.venv\Scripts\activate
python scripts/verify_m4.py --skip-gateway --write-report
python scripts/benchmark_serving.py --backend tensorrt_llm --lite --update-doc
```

`docs/serving_benchmark.md` 应出现 **TensorRT-LLM** 行。

### Step 2.6 — 切回 vLLM（日常开发）

```powershell
# WSL: docker stop trt-llm-serve
# Windows .env: LLM_ACTIVE_BACKEND=vllm
# 再 docker run vLLM（见 COLLABORATION §3.5）
```

---

## 3. 安装 K8s（k3d）+ KEDA

**在 WSL2 内**（与 Windows Docker Desktop 共用引擎时，注意内存上限：Docker Desktop → Resources → **≥12GB** 给 WSL）。

### Step 3.1 — k3d 集群

```bash
k3d cluster create industrial-rag --agents 1 --gpus all
kubectl cluster-info
kubectl get nodes
```

Windows PowerShell 若已装 k3d 且 `--gpus 1` 可用，也可在 Windows 执行；**M0 文档推荐 WSL2**。

### Step 3.2 — NVIDIA Device Plugin

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.5/nvidia-device-plugin.yml
kubectl -n kube-system rollout status daemonset/nvidia-device-plugin-daemonset
kubectl describe node | grep nvidia.com/gpu
```

### Step 3.3 — 安装 KEDA

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda -n keda --create-namespace
kubectl get pods -n keda
```

### Step 3.4 — 安装本项目 Helm（ScaledObject 随 Chart 下发）

```bash
cd /mnt/d/repo/RAG
helm upgrade --install ior ./deploy/helm/industrial-ops-rag \
  -f ./deploy/helm/industrial-ops-rag/values-dev-single-node.yaml \
  -n industrial-ops --create-namespace

kubectl -n industrial-ops get pods
kubectl -n industrial-ops get scaledobject
```

**预期**：

- `ior-*-vllm` 等可能 `ImagePullBackOff`（占位镜像）— M0/M4 **模板验收**仍算通过
- `ior-*-vllm-scaler` ScaledObject 存在即 KEDA  wiring 就绪
- dev `maxReplicas: 1` → **不会真的扩多 Pod**

### Step 3.5 — M0/M4 集群侧验收

```bash
kubectl -n industrial-ops get pods
kubectl -n industrial-ops get scaledobject
kubectl -n keda get pods
```

Windows 侧 profile 验收：

```powershell
python scripts/verify_m0.py --skip-compose --write-report
python scripts/verify_m4.py --skip-gateway --write-report
```

---

## 4. 资源 coexist 备忘（16GB）

| 同时运行 | 建议 |
|----------|------|
| Compose + vLLM + Gateway | OK（M3 日常） |
| Compose + k3d 集群 idle | 勉强，注意 Docker RAM |
| Compose + k3d + vLLM + TRT 编译 | **禁止** |
| TRT 编译/推理 | 停 vLLM、停 M3 Gateway 压测、可保留 Compose 中间件 |

---

## 5. M4 完整收口清单

- [ ] `serving_benchmark.md` **vLLM** 行有数据
- [ ] `serving_benchmark.md` **TensorRT-LLM** 行有数据
- [ ] `verify_m4.py` profile + router probe PASS
- [ ] （可选）Gateway 重启后 `verify_m4` 含 `/v1/llm/backends` PASS
- [ ] （可选）k3d + KEDA + ScaledObject 已 apply
