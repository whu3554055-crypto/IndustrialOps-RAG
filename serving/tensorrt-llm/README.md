# TensorRT-LLM 服务

> **最短操作**：[docs/m4_user_runbook.md](../../docs/m4_user_runbook.md) Phase 2  
> **一键脚本**：`powershell -ExecutionPolicy Bypass -File .\serving\tensorrt-llm\run-serve.ps1`

与 vLLM **GPU 互斥**。本机固定：

- 镜像：`nvcr.io/nvidia/tensorrt-llm/release:latest`
- 驱动 **546.30** / CUDA **12.3**（与 vLLM `v0.6.6` 一致）
- 端口：**8001**

## 顺序

1. `docker stop` vLLM  
2. `docker login nvcr.io`（NGC API Key，仅首次）  
3. `run-serve.ps1`  
4. `benchmark_serving.py --backend tensorrt_llm --lite --update-doc`  

engine 编译（仅 serve 失败时）：`build-engine.ps1` → runbook Phase 2B
