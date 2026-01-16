# v0.2 代码交付清单（无大显存）

验收：`python scripts/verify_code_complete.py`

| ID | 交付 |
|----|------|
| NV-03 | `m2_golden.jsonl.example` 80 条 + `fill_golden_ground_truth.py` |
| NV-04 | `Dockerfile.gateway` + `build_gateway_image.ps1` |
| NV-10 | `data/graph/relations.yaml` + `graph/store.py` + `extract_graph_from_corpus.py` |
| NV-11 | `deepdoc/layout.py`（pdfplumber 表 + md 表行） |
| NV-12 | `multimodal/ocr.py`（rapidocr / pytesseract 可选） |
| NV-13 | `trulens_eval.py`（SDK live + dry-run 回退） |
| NV-14 | `storage/minio_store.py` + Gateway `/v1/storage/*` |
| NV-15 | Grafana Prometheus 面板 + `prometheus-scrape-gateway.yaml` |
| NV-20 | `batch_ingest.py`（已有）+ Helm ingest CronJob |
| NV-21 | `verify_production_profile.py` |
| NV-22 | `merge_feedback_to_golden.py` + review queue |
| NV-23 | `retrieval/poc/qdrant_poc.py` |
| NV-30/31 | 文档同步见 m0/m2/architecture |

可选依赖：`pip install -e ".[storage,doc,ocr,poc,eval-extra]"`
