#!/usr/bin/env bash
# 构建 Gateway 镜像供 Helm 使用
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${1:-industrial-ops-rag/gateway:0.1.0}"
docker build -f "$ROOT/deploy/docker/Dockerfile.gateway" -t "$IMAGE" "$ROOT"
echo "Built $IMAGE"
