#!/usr/bin/env bash
# M6 一键 Helm 安装（WSL2 / Linux）— 见 docs/m6_eval.md §6
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CLUSTER="${IOR_K3D_CLUSTER:-industrial-rag}"
NAMESPACE="${IOR_NAMESPACE:-industrial-ops}"

if ! command -v k3d >/dev/null 2>&1; then
  echo "k3d not found — install k3d first (docs/m6_eval.md §6)"
  exit 1
fi

if ! k3d cluster list 2>/dev/null | grep -q "$CLUSTER"; then
  k3d cluster create "$CLUSTER" --agents 1 --gpus all
  kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.5/nvidia-device-plugin.yml
fi

helm upgrade --install ior "$ROOT/deploy/helm/industrial-ops-rag" \
  -f "$ROOT/deploy/helm/industrial-ops-rag/values-dev-single-node.yaml" \
  -n "$NAMESPACE" --create-namespace

echo "Helm release applied. Verify: python scripts/verify_m6.py --write-report"
kubectl -n "$NAMESPACE" get pods
