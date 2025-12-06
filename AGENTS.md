# Agent 工作指引

## 必读

1. [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)
2. [docs/COLLABORATION.md](docs/COLLABORATION.md) — **拍板 = 对话 token；高消耗优先用户代劳（见 §3 命令）**
3. [deploy/profiles/dev-single-node.yaml](deploy/profiles/dev-single-node.yaml)

## 原则

- **不删减架构组件**；资源仅改 profile / Helm values。
- **高对话 token 操作须先拍板**（见 COLLABORATION §2）；说明原因与范围，征得同意。
- **省 token**：小结模式、少读文件、日志写 `reports/`、不贴长 stdout、跨里程碑建议新对话。
- **节点提醒**：在 COLLABORATION §4 所列节点，**主动提醒**用户后再继续。
- **用户代劳**：模型下载 / compose / vLLM / 大批量 ingest / RAGAS / 训练 — 给 **§3 可复制命令**，不要代跑长链。
- 决策 → `docs/decisions.md`；指标 → `docs/evolution.md`。

## 回复格式（默认）

结论（≤3 句）→ 变更文件路径 →（如需）用户本地命令 §3 → 下一拍板项（若有）。

## 当前状态

M0–M4 文档：`docs/milestones/README.md`。M1 ingest → [m1_ingest.md](docs/m1_ingest.md)；M2 → [m2_retrieval.md](docs/m2_retrieval.md)；M3 → [m3_agent.md](docs/m3_agent.md)；M4 → [m4_serving.md](docs/m4_serving.md)。
