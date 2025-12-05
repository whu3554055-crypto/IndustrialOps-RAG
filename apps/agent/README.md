# Agent 模块（M3）

> **学习 hub**：[docs/m3_agent.md](../../docs/m3_agent.md)  
> **验收**：`python scripts/verify_m3.py`（见 COLLABORATION §3.7.2）

## 目录职责

| 文件 | 职责 |
|------|------|
| `pipeline.py` | `run_agentic_rag` 主管道 |
| `rewrite.py` | 多轮 query 改写 |
| `session.py` | 内存会话（按 `session_id`） |
| `prompts.py` | 模板、context 格式化、citations |
| `tools/hybrid_search.py` | 封装 M2 hybrid_rerank |
| `tools/self_check.py` | 置信度阈值 + 答案 YES/NO 质检 |

## 依赖

- 检索：`apps/retrieval/langchain/hybrid_chain.py`
- 生成：`apps/generation/llm_router.py`（M4）

## 单元测试

```powershell
pytest tests/test_agent_m3.py -q
```

无需 vLLM；覆盖 session 裁剪、拒答阈值、prompt 组装等。
