# Kubernetes 学习打卡（绑定 IndustrialOps-RAG）

完成即在 `[ ]` 填 `x`，并注明对应仓库文件/命令。

## 工作负载

- [ ] Deployment — Gateway, vLLM
- [ ] StatefulSet — Milvus, PostgreSQL
- [ ] DaemonSet — nvidia-device-plugin（GPU 节点）
- [ ] Job — ingest 单次
- [ ] CronJob — RAGAS 周评
- [ ] Pod 排障 — `kubectl describe/logs`

## 网络

- [ ] Service ClusterIP / Headless
- [ ] Ingress + TLS（cert-manager 可选）
- [ ] NetworkPolicy — 限制 Milvus 访问

## 存储与配置

- [ ] PVC + StorageClass
- [ ] ConfigMap — 模型路径、prompt 版本
- [ ] Secret — API keys

## 弹性

- [ ] resources requests/limits（`values-dev-single-node.yaml`）
- [ ] HPA — Gateway CPU
- [ ] KEDA ScaledObject — vLLM
- [ ] PDB — 推理服务
- [ ] rollout undo

## 可观测与安全

- [ ] ServiceMonitor — Prometheus
- [ ] Grafana 仪表盘
- [ ] RBAC — 命名空间只读角色
- [ ] Helm install/upgrade/rollback

## GitOps（可选）

- [ ] Argo CD Application 指向本 chart

## 本地集群

完整步骤见 [docs/COLLABORATION.md](../docs/COLLABORATION.md) §3.3。

```bash
# 示例：k3d 单节点（执行前确认 Docker/WSL2 资源）
k3d cluster create industrial-rag --agents 1 --gpus 1
kubectl cluster-info
```
