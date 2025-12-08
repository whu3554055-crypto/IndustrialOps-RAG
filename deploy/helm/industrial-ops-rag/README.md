# Helm Chart — industrial-ops-rag

> **M0 学习**：[docs/m0_infra.md](../../docs/m0_infra.md) §6（k3d、GPU、Helm、启服顺序）。  
> **可执行步骤**：[COLLABORATION.md](../../docs/COLLABORATION.md) §3.3。

## 安装（单机 dev）

```bash
# 创建集群（示例 k3d，GPU 节点）
k3d cluster create industrial-rag --agents 1 --gpus 1

# GPU device plugin（Pod Pending 无 nvidia.com/gpu 时，WSL2 内执行）
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.5/nvidia-device-plugin.yml

# 安装（模板占位，镜像需本地 build 或后续替换）
helm upgrade --install ior ./deploy/helm/industrial-ops-rag \
  -f ./deploy/helm/industrial-ops-rag/values-dev-single-node.yaml \
  --namespace industrial-ops --create-namespace

# M0 验收
kubectl -n industrial-ops get pods
python scripts/verify_m0.py --skip-compose --write-report  # profile 层
```

## 启服顺序

见 `deploy/profiles/dev-single-node.yaml` → `startup_order`（[m0_infra.md §4.1](../../docs/m0_infra.md#41-startup_orderk8s-分时启服)）

## GPU 互斥切换 TensorRT-LLM

见 [m4_serving.md §3.2](../../docs/m4_serving.md#32-vllm--tensorrt-llm-分时切换6gb-单卡)

## 与 profile 对齐

修改资源时同步更新：

- `deploy/profiles/dev-single-node.yaml`
- `values-dev-single-node.yaml`
