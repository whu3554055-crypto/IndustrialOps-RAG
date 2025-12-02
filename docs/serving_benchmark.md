# 推理服务压测（vLLM vs TensorRT-LLM）

> 执行压测前须阅读 [COLLABORATION.md](./COLLABORATION.md) §3.7.3。

## 环境

- Profile: `dev-single-node`
- GPU: RTX 3060 6GB
- 模型: Qwen2.5-7B-Instruct-AWQ

## 指标

| 后端 | TTFT p50 | TTFT p95 | TPOT | QPS @并发=2 | GPU 显存峰值 |
|------|----------|----------|------|-------------|--------------|
| vLLM | | | | | |
| TensorRT-LLM | | | | | |

## 如何测量

```powershell
# 本机 6GB 轻量档（推荐）
python scripts/benchmark_serving.py --backend vllm --lite --update-doc

# 标准档（并发=2，4 次采样）
python scripts/benchmark_serving.py --backend vllm --concurrency 2 --requests 4 --update-doc

# TRT-LLM 分时切换后（须先停 vLLM，见 serving/tensorrt-llm/README.md）
python scripts/benchmark_serving.py --backend tensorrt_llm --lite --update-doc
```

原始 JSON：`reports/serving_benchmark.json`

## vLLM 启动参数快照

见 `deploy/profiles/dev-single-node.yaml` → `llm.backends.vllm`

## TensorRT-LLM 构建笔记

见 `serving/tensorrt-llm/README.md`

## KEDA

Helm 模板：`deploy/helm/industrial-ops-rag/templates/keda-scaledobject-vllm.yaml`  
单机 dev `maxReplicas: 1`；生产 overlay 见 `values.yaml`。

## 最近测量

（跑 `--update-doc` 后自动追加）
