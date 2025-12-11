# TRT-LLM engine 编译（仅当 run-serve.ps1 探活失败或 OOM 时）
# 用法: powershell -ExecutionPolicy Bypass -File .\serving\tensorrt-llm\build-engine.ps1
# 然后进入容器，复制粘贴 runbook Phase 2B 两条命令

$ErrorActionPreference = "Stop"
$Image = "nvcr.io/nvidia/tensorrt-llm/release:latest"
$Repo = "d:/repo/RAG"

New-Item -ItemType Directory -Force -Path "$Repo/serving/tensorrt-llm/checkpoints" | Out-Null
New-Item -ItemType Directory -Force -Path "$Repo/serving/tensorrt-llm/engines" | Out-Null

Write-Host @"

进入容器后执行（整段复制）:

python3 examples/models/core/qwen/convert_checkpoint.py \
  --model_dir /work/models/Qwen2.5-7B-Instruct-AWQ \
  --output_dir /work/serving/tensorrt-llm/checkpoints/int4-awq

trtllm-build \
  --checkpoint_dir /work/serving/tensorrt-llm/checkpoints/int4-awq \
  --output_dir /work/serving/tensorrt-llm/engines/int4-awq-1gpu \
  --gemm_plugin float16 \
  --max_batch_size 1 \
  --max_input_len 2048 \
  --max_seq_len 2560 \
  --max_num_tokens 2048

exit

"@

docker run --gpus all --rm -it -v "${Repo}:/work" -w /work $Image bash
