# TensorRT-LLM 服务

与 vLLM **GPU 互斥**（`mutual_exclusive_gpu: true`）。

## 流程

1. 将 AWQ 权重编译为 TRT engine（WSL2 Ubuntu 推荐）
2. 构建推理镜像，暴露 OpenAI 兼容 `:8001`
3. Helm：`tensorrtLlm.replicaCount: 1`，同时 `vllm.replicaCount: 0`

## Benchmark

结果填入 `docs/serving_benchmark.md`

## 注意

TensorRT-LLM 构建耗时、耗磁盘 — **须用户拍板**后再执行。
