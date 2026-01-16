# 下一版需求 — 仅大显存 / GPU 运行时

> **v0.2 代码**（图谱、OCR、TruLens 接线、MinIO API、Helm 镜像、80 题 golden 模板等）已交付，见 [code-delivery-v0.2.md](./code-delivery-v0.2.md)。

下列项 **必须 GPU 或大显存环境执行**，仓库内保留脚本与配置，**不以本机 6GB 验收为阻塞**。

---

## NV-R1 真 RAGAS live

- 命令：`python pipelines/evaluation/run_ragas.py --golden data/eval/golden.jsonl --gateway http://localhost:8080`
- 依赖：Gateway + vLLM judge
- 产出：更新 `docs/evolution.md` 五指标

## NV-R2 M6 / M7 live 问答

- README 15min：`curl /v1/chat` 或 `apps/web/demo_ui.py`
- 依赖：vLLM 稳定（6GB 易 502/超时）

## NV-R3 TensorRT-LLM 压测

- `python scripts/benchmark_serving.py --backend tensorrt_llm --update-doc`
- 依赖：分时关闭 vLLM，24GB 级更稳

## NV-R4 K8s 全栈真部署

- `scripts/build_gateway_image.ps1` 构建并推送镜像
- `helm upgrade` + `ingest.cronJob.enabled=true`
- `kubectl get pods` 全绿（非占位 ImagePullBackOff）

## NV-R5 M5 完整 epoch（可选）

- 见 [m5_online_train.md](./m5_online_train.md)，24GB 线上

## NV-R6 TruLens live（可选）

- `pip install -e ".[eval-extra]"` + `trulens_eval.py` 无 `--dry-run`
- 依赖：同 NV-R1 judge

---

## 验收建议（运行时）

| 项 | 通过标准 |
|----|----------|
| NV-R1 | `reports/ragas_report.json` 为 `mode=ragas` |
| NV-R2 | 单条 chat 返回非拒答且 <120s |
| NV-R4 | 目标 namespace Pod Running ≥90% |
