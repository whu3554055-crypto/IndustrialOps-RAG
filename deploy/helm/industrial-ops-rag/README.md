# Helm Chart — industrial-ops-rag

可执行步骤见 [docs/COLLABORATION.md](../../docs/COLLABORATION.md) §3.3（M0 步骤 3）。

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
```

## 启服顺序

见 `deploy/profiles/dev-single-node.yaml` → `startup_order`

## GPU 互斥切换 TensorRT-LLM

```bash
# 缩容 vLLM，启用 TRT（示例，具体以 values 为准）
kubectl -n industrial-ops scale deployment ior-vllm --replicas=0
kubectl -n industrial-ops scale deployment ior-tensorrt-llm --replicas=1
```

## 与 profile 对齐

修改资源时同步更新：

- `deploy/profiles/dev-single-node.yaml`
- `values-dev-single-node.yaml`
