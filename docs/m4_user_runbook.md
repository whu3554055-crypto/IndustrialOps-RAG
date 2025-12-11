# M4 用户操作手册（最短路径 · 可逐条复制）

> **本机已确认**：驱动 **546.30**，CUDA **12.3**，RTX 3060 Laptop **6GB**（与 vLLM `v0.6.6` 同栈）。  
> **固定 TRT 镜像**：`nvcr.io/nvidia/tensorrt-llm/release:latest`（勿改 tag；拉取前须 NGC 登录）。  
> 背景：[m4_serving.md](./m4_serving.md)

---

## 常量（全文统一）

| 项 | 值 |
|----|-----|
| 仓库根 | `d:\repo\RAG` |
| vLLM 镜像 | `vllm/vllm-openai:v0.6.6` |
| TRT 镜像 | `nvcr.io/nvidia/tensorrt-llm/release:latest` |
| 模型目录 | `d:\repo\RAG\models\Qwen2.5-7B-Instruct-AWQ` |
| vLLM 端口 | `8000` |
| TRT 端口 | `8001` |

**GPU 互斥**：做 TRT 前必须停 vLLM；做 vLLM 前必须停 TRT。

---

## Phase 1 — vLLM 压测行（约 5 分钟）

**1.1** 确认 vLLM 在跑：

```powershell
curl.exe http://localhost:8000/v1/models
```

**1.2** 若无响应，启动 vLLM（与 COLLABORATION §3.5 相同）：

```powershell
docker pull vllm/vllm-openai:v0.6.6
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

**1.3** 写 benchmark 表：

```powershell
cd d:\repo\RAG
.\.venv\Scripts\activate
python scripts/benchmark_serving.py --backend vllm --lite --update-doc
```

---

## Phase 2 — TRT-LLM 压测行（最短：pytorch 直 serve）

### Step 1 — 停 vLLM

```powershell
docker ps --format "{{.ID}} {{.Image}}" | findstr vllm
docker stop <上一步看到的CONTAINER_ID>
```

### Step 2 — NGC 登录（仅首次，否则 pull 会 Access Denied）

1. 浏览器打开 https://org.ngc.nvidia.com/setup/api-key → Generate API Key → 复制 key  
2. PowerShell：

```powershell
docker login nvcr.io -u `$oauthtoken` -p <粘贴你的NGC_API_KEY>
```

成功应显示 `Login Succeeded`。

### Step 3 — 一键启 TRT（推荐）

```powershell
cd d:\repo\RAG
powershell -ExecutionPolicy Bypass -File .\serving\tensorrt-llm\run-serve.ps1
```

脚本会：`docker pull` → 起容器 `trt-llm-serve` → `curl :8001/v1/models`。

### Step 4 — 手动探活（与脚本二选一）

```powershell
curl.exe http://localhost:8001/v1/models
```

**成功标准**：返回 JSON，且含 `data` / `model` 字段。

### Step 5 — 改 `.env`

编辑 `d:\repo\RAG\.env`：

```ini
LLM_ACTIVE_BACKEND=tensorrt_llm
TENSORRT_LLM_BASE_URL=http://localhost:8001/v1
```

### Step 6 — 压测 + 验收

```powershell
cd d:\repo\RAG
.\.venv\Scripts\activate
python scripts/verify_m4.py --skip-gateway --write-report
python scripts/benchmark_serving.py --backend tensorrt_llm --lite --update-doc
```

打开 `docs/serving_benchmark.md`，**TensorRT-LLM** 行应有数字。

### Step 7 — 切回 vLLM（日常 M3）

```powershell
docker rm -f trt-llm-serve
```

`.env` 改回：

```ini
LLM_ACTIVE_BACKEND=vllm
```

再按 Phase 1 的 **1.2** 启动 vLLM。

---

## Phase 2B — 仅当 Step 4 失败或容器 OOM 时

**现象**：`curl :8001` 无响应、`docker logs trt-llm-serve` 含 OOM/CUDA error。

**1.** 删容器：

```powershell
docker rm -f trt-llm-serve
```

**2.** 编译 engine（1–3 小时，交互少，脚本内自动跑两条命令）：

```powershell
cd d:\repo\RAG
powershell -ExecutionPolicy Bypass -File .\serving\tensorrt-llm\build-engine.ps1
```

**3.** 用 engine 启服（脚本结束时会打印此命令，原样复制执行）：

```powershell
docker rm -f trt-llm-serve 2>$null
docker run --gpus all --ipc=host -d --name trt-llm-serve -p 8001:8000 `
  -v d:/repo/RAG:/work `
  nvcr.io/nvidia/tensorrt-llm/release:latest `
  trtllm-serve /work/serving/tensorrt-llm/engines/int4-awq-1gpu `
  --host 0.0.0.0 --port 8000
```

**4.** 从 Phase 2 **Step 4** 继续（curl → .env → benchmark）。

---

## Phase 3 — K8s（k3d）+ KEDA（约 30 分钟，PowerShell）

> **16GB 注意**：装 k3d 当天 **不要** 同时跑 M3 全量压测；Compose 可保留，勿再起第二个 vLLM。  
> **M6 之前**日常开发 **不依赖** K8s；装一次即可闭环 M0/M4 架构。

### Step 1 — 安装 CLI（仅首次，缺哪个装哪个）

```powershell
choco install k3d kubernetes-helm kubernetes-cli -y
# 无 choco 时: winget install k3d.k3d ; winget install Helm.Helm ; winget install Kubernetes.kubectl
```

### Step 2 — 建集群

```powershell
k3d cluster create industrial-rag --agents 1 --gpus all
kubectl cluster-info
kubectl get nodes
```

### Step 3 — GPU Device Plugin

```powershell
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.5/nvidia-device-plugin.yml
kubectl -n kube-system rollout status daemonset/nvidia-device-plugin-daemonset --timeout=120s
kubectl describe node | findstr nvidia.com/gpu
```

**成功标准**：输出含 `nvidia.com/gpu: 1`。

### Step 4 — 装 KEDA

```powershell
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda -n keda --create-namespace
kubectl get pods -n keda
```

**成功标准**：`keda-operator-*` 为 `Running`。

### Step 5 — 装本项目 Chart

```powershell
cd d:\repo\RAG
helm upgrade --install ior ./deploy/helm/industrial-ops-rag `
  -f ./deploy/helm/industrial-ops-rag/values-dev-single-node.yaml `
  -n industrial-ops --create-namespace
```

### Step 6 — 验收

```powershell
kubectl -n industrial-ops get scaledobject
kubectl -n industrial-ops get pods
cd d:\repo\RAG
.\.venv\Scripts\activate
python scripts/verify_m0.py --skip-compose --write-report
python scripts/verify_m4.py --skip-gateway --write-report
```

**成功标准**：

- `get scaledobject` 有 `ior-*-vllm-scaler`
- `verify_m0` / `verify_m4` profile 用例 PASS  
- Pod 若 `ImagePullBackOff` **可忽略**（占位镜像）；ScaledObject 存在即 KEDA 接线完成

---

## Phase 4 — Gateway 404 时（M4 verify）

`GET /v1/llm/backends` 返回 404 = Gateway 旧进程。重启：

```powershell
# 停旧 uvicorn 窗口 Ctrl+C，或：
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 5
cd d:\repo\RAG
.\.venv\Scripts\activate
uvicorn apps.gateway.main:app --host 0.0.0.0 --port 8080
```

再跑：

```powershell
curl.exe http://localhost:8080/v1/llm/backends
python scripts/verify_m4.py --benchmark --write-report
```

---

## M4 收口清单

- [ ] Phase 1：`serving_benchmark.md` **vLLM** 行有数
- [ ] Phase 2：`serving_benchmark.md` **TensorRT-LLM** 行有数
- [ ] Phase 3：`kubectl get scaledobject` 有 vllm-scaler
- [ ] Phase 4（可选）：Gateway `/v1/llm/backends` 200

---

## 以后是否必须 K8s？

| 里程碑 | 必须 K8s？ |
|--------|------------|
| M1–M5 日常 | 否 |
| M4 KEDA 真跑 | 是（Phase 3 一次即可） |
| **M6** 验收 | 是（Helm 一键、Grafana、RAGAS CI） |
