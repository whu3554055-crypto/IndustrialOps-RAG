# TRT-LLM 最短启服 — trtllm-serve pytorch 直连 AWQ（与 vLLM 同 CUDA 12.3 栈）
# 用法（PowerShell，仓库根目录）:
#   .\serving\tensorrt-llm\run-serve.ps1
# 前提: 已 docker login nvcr.io；已停 vLLM；模型在 d:\repo\RAG\models\Qwen2.5-7B-Instruct-AWQ

$ErrorActionPreference = "Stop"

$Image = "nvcr.io/nvidia/tensorrt-llm/release:latest"
$ModelsHost = "d:/repo/RAG/models"
$ModelId = "/models/Qwen2.5-7B-Instruct-AWQ"
$ContainerName = "trt-llm-serve"
$HostPort = 8001

Write-Host "==> 停止旧 TRT 容器（若有）"
docker rm -f $ContainerName 2>$null | Out-Null

Write-Host "==> 拉取镜像（仅首次，约 10GB+）: $Image"
docker pull $Image

Write-Host "==> 启动 trtllm-serve :$HostPort"
docker run --gpus all --ipc=host -d `
  --name $ContainerName `
  -p "${HostPort}:8000" `
  -v "${ModelsHost}:/models" `
  $Image `
  trtllm-serve $ModelId `
  --host 0.0.0.0 `
  --port 8000 `
  --backend pytorch `
  --max_batch_size 1 `
  --max_seq_len 2048

Write-Host "==> 等待 90s 加载模型…"
Start-Sleep -Seconds 90

Write-Host "==> 探活 GET /v1/models"
curl.exe -s "http://localhost:${HostPort}/v1/models"
Write-Host ""
Write-Host "若上面有 JSON 则成功。下一步见 docs/m4_user_runbook.md Phase 2 Step 6"
