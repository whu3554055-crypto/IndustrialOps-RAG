# 分支说明：feature/subquestion-complete

## 概述

自 commit `3d09b32`（SubQuestion 自研骨架）起，在本分支完成 **LlamaIndex SubQuestion 模式的功能补全**。

**架构拍板**：生产默认 **自研** `apps/retrieval/llamaindex/subquestion/`；官方 `llama-index` 包 **仅用于 benchmark 对照**，不替换 `mode_dispatch` 默认路径。

**API 拍板（工业规范）**：

- `/v1/search` — Retrieve，hits-only；SubQuestion 只做检索，不调合成 LLM
- `/v1/chat` — Query 主入口；`retrieval_mode=sub_question` 时走拆问 + 检索 + ResponseSynthesizer
- `/v1/query` — 可选，无会话轻量 RAG（Phase B5）

## 与 `feature/auto-evaluation-optimization` 的关系

| 分支 | HEAD 说明 |
|------|-----------|
| `feature/auto-evaluation-optimization` | 停在 `2a92952`（Phase 3 A/B + 自动调参，**不含** sub_question 提交） |
| `feature/subquestion-complete` | 含 `3d09b32` 及后续 SubQuestion 开发 |

合并顺序建议：auto-evaluation 先合 master → 再 rebase/merge subquestion-complete。

## 开发计划

详见 [subquestion-complete-roadmap.md](./subquestion-complete-roadmap.md)。

## 本地开发

```powershell
git checkout feature/subquestion-complete
pytest tests/test_subquestion_engine.py -q
python scripts/verify_m2.py --extended --mode sub_question
```

LLM 路径（Phase A1 已完成，需 vLLM）：

```powershell
# profile: retrieval.sub_question.generator: llm
python scripts/verify_m2.py --extended --mode sub_question
```
