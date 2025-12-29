# Ingest 管道（M1）

> **学习 hub**：[docs/m1_ingest.md](../../docs/m1_ingest.md)  
> **验收**：`python scripts/verify_m1.py --write-evolution`（需 Compose + ingest）

## 快速开始

```powershell
docker compose -f deploy/compose/docker-compose.yml up -d
python pipelines/ingest/run_ingest.py --input data/raw --batch-size 8
python scripts/verify_m1.py --write-evolution
```

## 模块

| 文件 | 职责 |
|------|------|
| `run_ingest.py` | CLI |
| `documents.py` | 扫描 md/txt |
| `chunker.py` | 中文 RecursiveCharacterTextSplitter |
| `indexer.py` | bge-m3 → Milvus + OpenSearch |

## 扩展

- `deepdoc/` — PDF + 表格行增强
- `multimodal/` — Markdown 图片 alt
- `scripts/batch_ingest.py` — 分片大批量
