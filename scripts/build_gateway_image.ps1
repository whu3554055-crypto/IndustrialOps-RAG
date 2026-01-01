# 构建 Gateway 镜像供 Helm 使用
param([string]$Image = "industrial-ops-rag/gateway:0.1.0")
$Root = Split-Path -Parent $PSScriptRoot
docker build -f "$Root\deploy\docker\Dockerfile.gateway" -t $Image $Root
Write-Host "Built $Image"
