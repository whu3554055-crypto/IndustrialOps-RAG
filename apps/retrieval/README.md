# 检索层（M2）

> **学习 hub**：[docs/m2_retrieval.md](../../docs/m2_retrieval.md)  
> **指标表**：[docs/retrieval_modes.md](../../docs/retrieval_modes.md)  
> **验收**：`python scripts/verify_m2.py --write-evolution`

## 目录结构

| 路径 | 职责 |
|------|------|
| `core.py` | Milvus vector + OpenSearch BM25 + 模型加载/释放 |
| `hybrid/` | RRF 融合 |
| `langchain/hybrid_chain.py` | **生产主入口** `retrieve_context` |
| `rerank/` | BGE CrossEncoder |
| `llamaindex/` | 七种 QueryEngine（研究/对比） |

## 生产默认

```python
await retrieve_context(query, mode="hybrid_rerank")
```

M3 `hybrid_search` 封装此调用。

## 测试

```powershell
pytest tests/test_rrf.py tests/test_agent_m3.py -q  # RRF 无需中间件
python scripts/verify_m2.py --write-evolution       # 需 Milvus+OpenSearch+ingest
```
