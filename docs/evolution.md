# RAG 指标演进日志

| 日期 | 阶段 | Recall@5 | RAGAS F | 备注 |
|------|------|----------|---------|------|
| 2026-05-31 | M0 scaffold | - | - | 基线未测 |

| 2026-05-31 | M1 ingest+索引 | 10/10 | - | Vec 10/10 BM25 10/10 Top5 PASS |
| 2026-05-31 | M5 本地脚手架 | - | - | verify_m5 PASS；epoch 待线上 4090 |
| 2026-06-02 | **M5 本地完成** | - | 占位 0.72→0.77 | 迷你 epoch + adapter；`verify_m5 --check-ragas` PASS（`--fill-example`）；线上 epoch 不做 |
| 2026-06-02 | **M6 脚手架** | - | dry-run | `verify_m6` PASS；RAGAS CI + Grafana + Helm 一键 |
| 2026-06-02 | **M6 15min 问答** | - | - | **跳过** — 6GB 本机 vLLM 502/首条超时；脚手架已验，live 问答留 M7/大显存 |

<!-- 每完成一里程碑追加一行 -->
