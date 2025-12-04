# vLLM 服务

> **M4 学习**：总览与流程图见 [docs/m4_serving.md](../docs/m4_serving.md)。  
> **本机命令**： [COLLABORATION.md](../docs/COLLABORATION.md) §3.5。

vLLM 是 M4 的 **默认推理引擎**：动态 batching、OpenAI 兼容 API、适合日常开发与压测基线。

---

## 本地启动（dev-single-node）

### Windows / 驱动 546.x（推荐 Docker，6GB 实测）

勿 `pip install vllm`。`latest` 镜像需 CUDA 13（驱动 ≥580）；本机用固定 **CUDA 12** tag：

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

验证：`curl http://localhost:8000/v1/models` → 记下 `id`，写入 `.env` 的 `VLLM_MODEL`。

### Docker 参数说明（6GB 场景）

| 参数 | 示例值 | 作用 | 调参场景 |
|------|--------|------|----------|
| `--gpus all` | — | 透传 NVIDIA GPU | WSL2/Docker Desktop 需 nvidia-container-toolkit |
| `--ipc=host` | — | 共享 IPC，多进程 tensor 通信 | 去掉可能 OOM 或 hang |
| `-p 8000:8000` | — | OpenAI API 端口 | 与 `VLLM_BASE_URL` 一致 |
| `-v .../models:/models` | — | 挂载 HF 下载目录 | 路径与 `--model` 对齐 |
| `--model` | `/models/Qwen2.5-7B-Instruct-AWQ` | 权重路径 | 非 HF 仓库名 |
| `--quantization awq_marlin` | — | AWQ 4bit 快速 kernel | 6GB 必开；OOM 可试 `awq` |
| `--gpu-memory-utilization` | `0.95` | 预占显存比例 | OOM → `0.88` |
| `--max-model-len` | `2048` | KV cache 最大 context | 越大越占显存；与 profile 对齐 |
| `--max-num-seqs` | `2` | 最大并发序列 | 压测 concurrency=2 时对应 |
| `--max-num-batched-tokens` | `2048` | 单 batch token 上限 | 与 max-model-len 联动 |
| `--cpu-offload-gb` | `2` | 权重 offload 到 RAM | 6GB 救星；需足够系统内存 |

K8s / 大显存节点仍用 `deploy/profiles/dev-single-node.yaml` 中更大 context 数值。

### WSL2 Ubuntu / Linux（原生 pip）

```bash
pip install vllm
vllm serve /mnt/d/repo/RAG/models/Qwen2.5-7B-Instruct-AWQ \
  --quantization awq \
  --gpu-memory-utilization 0.88 \
  --max-model-len 4096 \
  --max-num-seqs 2 \
  --max-num-batched-tokens 2048 \
  --port 8000
```

---

## 与 TensorRT-LLM 分时切换

6GB 单卡 **不能** 与 TRT 同时占 GPU。切换步骤见 [m4_serving.md §3.2](../docs/m4_serving.md#32-vllm--tensorrt-llm-分时切换6gb-单卡)。

停 vLLM：

```powershell
docker ps --filter ancestor=vllm/vllm-openai:v0.6.6
docker stop <CONTAINER_ID>
```

---

## K8s

- Deployment：`deploy/helm/industrial-ops-rag/templates/vllm-deployment.yaml`
- KEDA 扩缩：`deploy/helm/industrial-ops-rag/templates/keda-scaledobject-vllm.yaml`
-  standalone 参考：`deploy/keda/scaledobject-vllm.yaml`

---

## 压测

```powershell
python scripts/benchmark_serving.py --backend vllm --lite --update-doc
```

详见 [m4_serving.md §6](../docs/m4_serving.md#6-压测脚本-benchmark_servingpy)。
