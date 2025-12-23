# M6 一键 Helm 安装（Windows PowerShell）— 见 docs/m6_eval.md §6
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Cluster = if ($env:IOR_K3D_CLUSTER) { $env:IOR_K3D_CLUSTER } else { "industrial-rag" }
$Namespace = if ($env:IOR_NAMESPACE) { $env:IOR_NAMESPACE } else { "industrial-ops" }

if (-not (Get-Command k3d -ErrorAction SilentlyContinue)) {
    Write-Error "k3d not found — install k3d first (docs/m6_eval.md §6)"
}

$exists = k3d cluster list 2>$null | Select-String $Cluster
if (-not $exists) {
    k3d cluster create $Cluster --agents 1 --gpus all
    kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.5/nvidia-device-plugin.yml
}

helm upgrade --install ior "$Root\deploy\helm\industrial-ops-rag" `
    -f "$Root\deploy\helm\industrial-ops-rag\values-dev-single-node.yaml" `
    -n $Namespace --create-namespace

Write-Host "Helm release applied. Verify: python scripts\verify_m6.py --write-report"
kubectl -n $Namespace get pods
