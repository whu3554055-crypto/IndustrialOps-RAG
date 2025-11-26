# vLLM 服务

## 本地启动（dev-single-node 参数）

### Windows / 驱动 546.x（推荐 Docker，6GB 实测）

勿 `pip install vllm`。`latest` 镜像需 CUDA 13（驱动 ≥580）；本机用固定 **CUDA 12** tag：

```powershell
# 须先下载模型 — 见 docs/COLLABORATION.md §3.4
docker pull vllm/vllm-openai:v0.6.6

docker run --gpus all --ipc=host -p 8000:8000 `
  -v d:/repo/RAG/models:/models `
  vllm/vllm-openai:v0.6.6 `
  --model /models/Qwen2.5-7B-Instruct-AWQ `
  --quantization awq_marlin `
  --gpu-memory-utilization 0.95 `
  --max-model-len 512 `
  --max-num-seqs 1 `
  --max-num-batched-tokens 512 `
  --cpu-offload-gb 2
```

K8s / 大显存节点仍用 `deploy/profiles/dev-single-node.yaml` 中的 `awq` + 4096 context。

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

## K8s

`deploy/helm/industrial-ops-rag/templates/vllm-deployment.yaml`

## KEDA

`deploy/keda/scaledobject-vllm.yaml`
