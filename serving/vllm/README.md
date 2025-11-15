# vLLM 服务

## 本地启动（dev-single-node 参数）

```bash
# 须先拍板下载模型 — 见 docs/COLLABORATION.md
vllm serve Qwen/Qwen2.5-7B-Instruct-AWQ \
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
