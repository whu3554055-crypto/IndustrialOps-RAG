# M7 之后落地状态（非 GPU 执行项）

> 硬件/大显存机才做的：**真 RAGAS live、vLLM 15min、TRT 压测、K8s 全绿** — 见 `evolution.md`。  
> 下列为已在仓库落地的代码/配置（无需 Cursor 大批量 token）。

## 已落地

| 项 | 路径 |
|----|------|
| 会话持久化 | `apps/session_store.py` + `deploy/sql/session_schema.sql` |
| 检索日志 | `apps/retrieval_log.py` + `deploy/sql/retrieval_logs_schema.sql` |
| DB 一键初始化 | `scripts/init_db.py` |
| Gateway ingest | `POST /v1/ingest` → `run_ingest_job` |
| 增量 ingest | `--no-recreate` 按 `doc_id` 覆盖 |
| PDF 入库 | `pipelines/ingest/deepdoc/pdf_loader.py`（pypdf） |
| M2 golden 模板 ~40 条 | `data/eval/m2_golden.jsonl.example`（`generate_m2_golden_from_corpus.py`） |
| RAGAS golden | `data/eval/golden.jsonl.example`（`build_eval_golden.py`） |
| 岗位映射更新 | `docs/job-requirements-mapping.md` |

## 仍须本机/线上执行（非代码缺失）

- `docker compose up` + `run_ingest` + `verify_m1`
- `init_db.py`（若用 PostgreSQL 持久化）
- vLLM / live demo / 真 RAGAS

## 维护命令

```powershell
python scripts\generate_m2_golden_from_corpus.py
python scripts\build_eval_golden.py
python scripts\init_db.py
```
