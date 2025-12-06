# Docker Compose — 本地中间件

> **M1 前提**：Milvus + OpenSearch；ingest 见 [docs/m1_ingest.md](../../docs/m1_ingest.md) §6。

```bash
cp ../../.env.example ../../.env
docker compose -f docker-compose.yml up -d
```

服务：PostgreSQL、Redis、MinIO、etcd、Milvus、OpenSearch。

LLM（vLLM）建议单独进程或 K8s，见 `serving/vllm/README.md`。
