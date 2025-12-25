# 里程碑学习文档约定

每个里程碑除 **验收脚本** 外，提供 **分层文档**，方便复习与 onboarding。

## 文档层级

| 层级 | 位置 | 内容 |
|------|------|------|
| **L1 学习 hub** | `docs/m{N}_*.md` | 流程图、模块地图、参数表、场景、验收清单 |
| **L2 操作手册** | `docs/COLLABORATION.md` §3.x | 可复制命令（用户本机执行） |
| **L3 组件 README** | `serving/*/`, `pipelines/*/` | 单组件启动参数、踩坑 |
| **L4 代码入口** | 模块 docstring | 1 段摘要 + 指向 L1 |
| **L5 配置注释** | `deploy/profiles/*.yaml` | 难懂字段行尾说明 |

## 进度

| 里程碑 | 学习 hub | 状态 |
|--------|----------|------|
| M0 | [m0_infra.md](../m0_infra.md) | **已完成** |
| M1 | [m1_ingest.md](../m1_ingest.md) | **已完成** |
| M2 | [m2_retrieval.md](../m2_retrieval.md) | **已完成**（指标表见 retrieval_modes.md） |
| M3 | [m3_agent.md](../m3_agent.md) | **已完成** |
| **M4** | **[m4_serving.md](../m4_serving.md)** | **已完成** |
| **M5** | **[m5_finetune.md](../m5_finetune.md)** + [m5_online_train.md](../m5_online_train.md) | **本地完整**；epoch 在 [线上 4090](../m5_online_train.md) |
| **M6** | **[m6_eval.md](../m6_eval.md)** | **脚手架完成**（RAGAS CI + Grafana + 一键 Helm） |
| **M7** | **[m7_demo.md](../m7_demo.md)** | **脚手架完成**（脱敏语料 + 反馈 + Gradio demo） |

## 新里程碑 Agent  checklist

1. 写 `docs/m{N}_*.md`（含 mermaid + 参数表）
2. COLLABORATION §3 增一节并链接 hub
3. 核心模块 docstring 指向 hub
4. profile / Helm 难字段加注释
5. 更新本表与 PROJECT_PLAN §8 索引
