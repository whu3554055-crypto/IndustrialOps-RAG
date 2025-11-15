# 推理服务压测（vLLM vs TensorRT-LLM）

> 执行压测前须阅读 [COLLABORATION.md](./COLLABORATION.md)。

## 环境

- Profile: `dev-single-node`
- GPU: RTX 3060 6GB
- 模型: Qwen2.5-7B-Instruct-AWQ

## 指标（待填）

| 后端 | TTFT p50 | TTFT p95 | TPOT | QPS @并发=2 | GPU 显存峰值 |
|------|----------|----------|------|-------------|--------------|
| vLLM | | | | | |
| TensorRT-LLM | | | | | |

## vLLM 启动参数快照

见 `deploy/profiles/dev-single-node.yaml` → `llm.backends.vllm`

## TensorRT-LLM 构建笔记

见 `serving/tensorrt-llm/README.md`
