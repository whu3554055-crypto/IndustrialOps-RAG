# 架构决策记录 (ADR)

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-05-31 | 项目名 IndustrialOps-RAG | 工业运维场景，国内岗位高频 |
| 2026-05-31 | 向量库选 Milvus | 技术栈常见；生产扩展路径清晰 |
| 2026-05-31 | BM25 用 OpenSearch | 与 Milvus 并列工业常见组合；单节点 `discovery.type=single-node` |
| 2026-05-31 | 主 LLM Qwen2.5-7B-AWQ | 覆盖 Qwen；4bit 在 6GB 上勉强推理 |
| 2026-05-31 | vLLM 与 TRT-LLM GPU 互斥 | 6GB 无法双引擎同占；架构仍保留双引擎 |
| 2026-05-31 | Embedding/Rerank 默认 CPU | 把 GPU 留给 LLM |
| 2026-05-31 | 架构不随硬件删减 | 仅 `deploy/profiles` 调参 |
| 2026-05-31 | 不从零 fork RAGFlow | 吸收 deepdoc 思路，代码自研可控 |
| 2026-05-31 | Windows 本地 vLLM 用 Docker `v0.6.6` | 原生 pip 不支持；`latest` 需 CUDA 13 驱动，546.x 用 cu12 tag |
| 2026-05-31 | 6GB 本机 vLLM 用 awq_marlin + cpu-offload | RTX 3060 实测：`max-model-len 512`、`cpu-offload-gb 2`；profile 4096 留 K8s |
| 2026-05-31 | Embedding/Rerank 分时释放内存 | 16GB RAM 上 bge-m3 与 reranker 不可同驻；rerank 前 `release_embedder()` |
| 2026-05-31 | Agent 生成不含对话历史 | 多轮仅 rewrite 用 history；生成 prompt = system + 检索上下文 + 当前问句（工业 RAG 常规） |
| 2026-05-31 | vLLM `served_model_id` 与 OpenAI API 对齐 | `GET /v1/models` 的 id 写入 profile / `VLLM_MODEL`，非 HF 仓库名 |
| 2026-05-31 | M4 压测走 streaming TTFT | `scripts/benchmark_serving.py` 直连 OpenAI 兼容 API，不经 RAG 管道 |
| 2026-05-31 | 里程碑文档分层 L1–L5 | 学习 hub `docs/m{N}_*.md` + 代码 docstring 指向；见 `docs/milestones/README.md` |
| 2026-05-31 | M5 训练用全精度 Qwen2.5-7B-Instruct | AWQ 仅推理；QLoRA adapter 与 vLLM 加载路径见 `finetune_pitfalls.md` #7 |
| 2026-05-31 | 微调与 vLLM GPU 互斥 | 训练前停 vLLM 或 K8s scale 0；与 M4 分时一致 |
| 2026-05-31 | M5 完整 epoch 在 24GB 线上跑 | 本机 6GB 仅 dry-run；`train-gpu-24g` + [m5_online_train.md](./m5_online_train.md)（默认 AutoDL 4090） |
| 2026-06-02 | M5 本机迷你 epoch 验收完成、不做线上 epoch | RTX 3060 6GB + `dev-finetune-mini`（single_gpu/384/qlora_r4）已跑通 adapter；RAGAS 用 `--fill-example` 占位至 M6 |
| 2026-06-02 | M6 RAGAS CI 用 dry-run stub | 真评测须 Gateway+vLLM 用户代劳；CI/`verify_m6` 只验流水线与 Helm 模板 |
| 2026-06-02 | M6 15min live 问答本机跳过 | RTX 3060 6GB：vLLM 首条 502/超时 + CPU 检索冷启动；验收以 `verify_m6` 为准 |
| 2026-06-02 | M7 demo 语料放 `data/corpus/demo` | `data/raw` 仍 gitignore；seed 复制到 `raw/samples` 再 ingest |
| 2026-06-02 | M7 反馈默认 file 后端 | 无 PostgreSQL 也能闭环；生产可切 `demo.feedback_backend: postgresql` |
| 2026-06-02 | M7 本机可跳过的是执行非验收 | ingest/vLLM/live demo/真 RAGAS 因硬件可不跑；`verify_m7`+pytest 必 PASS |
| 2026-06-02 | CI 含 verify_m7 + golden_m7 dry-run --limit 3 | 不跑 ingest/真 RAGAS；真实语料放 `data/corpus/business`（gitignore） |
| 2026-06-03 | 自动调参只写 reports、不自动改 profile | 防误提交；结果须人工 Review 后再 merge yaml |
| 2026-06-03 | 调参/贝叶斯默认 tiny golden + `--limit` | 本机 6GB/CPU 不跑 80 题×多轮；全量留大显存或 CI dry-run |
| 2026-06-03 | Phase 3 A/B 不自动 promote | 与调参一致；`analyze_ab_test` 仅建议，改 profile 须人工 |
| 2026-06-03 | A/B 复用 M7 反馈表、新增 ab_assignments | 不建 `ab_test_feedback`；JOIN `retrieval_log_id` 分析 |
| 2026-06-03 | A/B 先 search 后 chat | 降 LLM 成本；chat 需 pipeline 可配置 retrieval mode |
| 2026-06-03 | 生产开 A/B 前双后端切 PostgreSQL | `feedback_backend` + `retrieval_log_backend` 为 postgresql 且 `init_db` |
| 2026-06-03 | 首个 A/B 实验 search-only | `ab_test.scope: search`；hybrid_rerank vs graph |
| 2026-06-03 | SubQuestion 生产走自研、官方 LI 仅 benchmark | 检索 core 与 M1 ingest 一致；`llama-index` 包仅 `li_benchmark` 对照，不接入 `mode_dispatch` 默认路径；见 `docs/plans/subquestion-complete-roadmap.md` |
| 2026-06-03 | SubQuestion 开发独立分支 | `3d09b32` 起置于 `feature/subquestion-complete`；`feature/auto-evaluation-optimization` 不含该提交 |
| 2026-06-03 | SubQuestion API：Retrieve 与 Generate 分离 | `/v1/search` 永远 hits-only（含 `mode=sub_question`）；LLM 合成仅 Query 层：`/v1/chat` + `retrieval_mode=sub_question`；可选 `/v1/query` 轻量 RAG；禁止 search+synthesize 与 `/v1/subquestion/*` 对外路径 |
| 2026-06-03 | 复合问句 A/B 离线优先、不自动 promote | C5：`compare_compound_ab.py` 在 `m2_compound` golden 上对照 hybrid_rerank vs sub_question；在线实验用 profile 示例 `ab-test-subquestion-compound.yaml`，与 Phase 3 一致须人工改 profile |
| 2026-06-03 | SubQuestion 分支收尾 G6 | `golden_compound.jsonl.example` + `run_ragas --retrieval-mode/--endpoint`；`/v1/chat` 支持 `retrieval_mode`；`verify_subquestion.py` 脚手架验收 |

<!-- 新决策追加在表末 -->
