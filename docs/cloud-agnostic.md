# 多云与迁移

- **镜像**：避免云厂商硬编码 SDK；对象存储兼容 S3 API（MinIO → OSS/COS/S3）
- **Ingress**：Helm 抽象 `ingress.className`（nginx / alb / slb）
- **GPU 节点**：`nodeSelector: { accelerator: nvidia }` 各云标签在 overlay 替换
- **密钥**：Secret + 外部 Secret Store（生产可选 Vault/云 KMS）

未绑定单一云；文档示例以通用 K8s 为准。
