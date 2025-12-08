# Docker Compose — 本地中间件

> **M0 学习**：[docs/m0_infra.md](../../docs/m0_infra.md) §5。  
> **M1 ingest**：[docs/m1_ingest.md](../../docs/m1_ingest.md) §6。

```bash
cp ../../.env.example ../../.env
docker compose -f docker-compose.yml up -d
```

服务：PostgreSQL、Redis、MinIO、etcd、Milvus、OpenSearch。

LLM（vLLM）建议单独进程或 K8s，见 `serving/vllm/README.md`。
