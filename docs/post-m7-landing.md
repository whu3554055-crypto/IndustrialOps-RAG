# M7 之后落地状态

> **仅运行时（GPU/大显存）**：真 RAGAS live、vLLM 15min、TRT 压测填表、K8s 镜像全绿。

## 已落地（代码 / 脚本 / 文档）

| 类别 | 项 |
|------|-----|
| **验收** | `verify_m1 --write-report`；`verify_m2` 自动回退 `*.jsonl.example` |
| **持久化** | 会话、检索日志、反馈；`init_db.py` |
| **Gateway** | `/v1/ingest`（local/k8s）、限流、`/metrics`、`/v1/admin/*`、MinIO 健康 |
| **Ingest** | 增量 `--no-recreate`、PDF、表格增强、多模态 alt、分批 `batch_ingest.py` |
| **Helm** | `templates/ingest-cronjob.yaml` |
| **评测** | `fill_golden_ground_truth.py`、`trulens_eval.py --dry-run` |
| **Grafana** | Retrieval logs 说明面板 |
| **数据** | `m2_golden.jsonl.example`、`golden.jsonl.example` |

## 本机已执行（用户）

Compose、ingest、verify_m1、`init_db`、golden 维护脚本 — 见 `evolution.md`。

## 维护命令

```powershell
python scripts\generate_m2_golden_from_corpus.py
python scripts\fill_golden_ground_truth.py --in-place
python scripts\build_eval_golden.py
python scripts\init_db.py
python pipelines\evaluation\trulens_eval.py --dry-run
```

## K8s ingest

```powershell
# Helm 启用 ingest.cronJob.enabled=true 后
curl -X POST http://localhost:8080/v1/ingest -H "Content-Type: application/json" -d "{\"mode\":\"k8s\"}"
```
